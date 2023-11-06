from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from subprocess import call
from typing import Any, Callable, ClassVar, Iterator

from jinja2 import Environment, StrictUndefined, FileSystemLoader

jinja_env = Environment(autoescape=True,
                        undefined=StrictUndefined,
                        loader=FileSystemLoader("."),
                        auto_reload=False)


def jinja_render(template, **args):
    if "{{" in template or "{%}" in template:
        return jinja_env.from_string(template).render(**args)
    else:
        return template


OPENSCAD_BIN = "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
# SLIC3R compatible
SLICER_BIN = "/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"

OUTPUT_MODELS = "output/gridfinity/models"
OUTPUT_GCODE = "output/gridfinity/gcode"


def path_append_dash_suffix(path: PurePosixPath, value) -> PurePosixPath:
    return path.with_name(path.name + f"{value}-")


def openscad_arg(var_name):
    def to_command(value):
        return ["-D", f"{var_name}={value}"]
    return to_command


def expand_xy(min, max, block=()):
    return tuple(v for v in itertools.combinations_with_replacement(
        range(min, max+1), 2)
        if v not in block)


@dataclass(unsafe_hash=True)
class Factor:
    name: str = field()
    values: tuple | CmdGenerator = field()
    to_command: Callable[[Any], list[str]] = lambda _: []
    to_meta: Callable[[Any], str] = lambda v: str(v)

    def __iter__(self):
        if isinstance(self.values, CmdGenerator):
            return self.values.build_commands()
        else:
            return iter(self.values)


@dataclass
class CmdGeneratorResult:
    path: Path
    cmd_args: list[str]
    meta: dict


@dataclass
class CmdGenerator:
    cmd: list[str] = field()            # default_factory=list)
    factors: list[Factor] = field()     # default_factory=list)
    vars: dict[str, str]
    path: str

    global_meta: ClassVar[dict] = {}

    def product(self):
        return itertools.product(*(factor for factor in self.factors))

    def build_commands(self) -> Iterator[CmdGeneratorResult]:
        for combos in self.product():
            cmd_args = self.cmd.copy()
            meta = dict(self.global_meta)
            for i, value in enumerate(combos):
                factor = self.factors[i]
                if isinstance(value, CmdGeneratorResult):
                    meta.update(value.meta)
                else:
                    meta[factor.name] = factor.to_meta(value)
                    cmd_args.extend(factor.to_command(value))

            meta.update({key: jinja_render(value, **meta)
                         for key, value in self.vars.items()})

            cmd_args = [jinja_render(arg, **meta) for arg in cmd_args]
            path = Path(jinja_render(self.path, **meta))

            # path, cmd_args, meta = self.finalize_command(path, cmd_args, meta)
            yield CmdGeneratorResult(path, cmd_args, meta)


def cmd_gen_for_slicer(scad_cmd: CmdGenerator, path_template):
    return CmdGenerator(
        [
            SLICER_BIN,
            "--export-gcode",
            "--load", "profile_{{ filament_type }}_n{{ nozzle_diameter }}.ini",
            "--output", "{{ gcode_path }}",
            "{{ stl_path }}"
        ],
        [
            Factor("model", scad_cmd),
            Factor("filament_type", ("pla", "petg")),
            Factor("nozzle_diameter", ("06",)),
        ],
        vars={
            "gcode_path": path_template,
        },
        path="{{ gcode_path }}"
    )


scad_bin_gen = CmdGenerator(
    [
        OPENSCAD_BIN,
        "--export-format=binstl",
        "--enable", "fast-csg",
        "-o", "{{ stl_path }}",
        "gridfinity-rebuilt-{{ 'lite' if base == 'lite' else 'bins' }}.scad",
    ],
    [
        Factor("base_size",
               expand_xy(1, 5, ((5, 5),)),
               to_command=lambda value: ["-D", f"gridx={value[0]}",
                                         "-D", f"gridy={value[1]}"],
               to_meta=lambda value: f"{value[0]}x{value[1]}",
               ),
        Factor("height",
               (2, 4, 6, 8, 10, 12),
               to_command=openscad_arg("gridz"),
               ),
        Factor("base",
               (0, 1, "lite"),
               to_command=lambda value: [
                   # Not sure why these defaults incorrectly....
                   "-D", f"style_hole={value}"] if value != "lite" else ["-D", "divx=1",
                                                                         "-D", "divy=1"],
               to_meta=lambda v: {0: "flat",
                                  1: "magnet",
                                  "lite": "lite"}[v]
               ),
        Factor("lip",
               (0, 2),
               to_command=openscad_arg("style_lip"),
               to_meta=lambda v: {
                   0: "stackable", 2: "open"}[v],
               ),
        Factor("tab",
               (5,),
               to_command=openscad_arg("style_tab"),
               to_meta=lambda _: "no-tab"
               ),
        Factor("scoop",
               (0,),
               to_command=openscad_arg("scoop"),
               ),
    ],
    vars={
        "stl_path": "{{ output_models }}/bins/"
                    "{{ base }}-{{ lip }}/"
                    "bin-{{ base_size }}-{{ height }}h-{{ base }}-{{ lip }}.stl",
    },
    path="{{ stl_path }}"
)

"""

"style_lip":

• (0) Regular lip
• (2) Disable lip while retaining height


style_tab=5  (no tabs)

style_hole=
• (0) No holes
• (1) Magnet holes only
"""


scad_base_gen = CmdGenerator(
    [
        OPENSCAD_BIN,
        "--export-format=binstl",
        "--enable", "fast-csg",
        "-o", "{{ stl_path }}",
        "gridfinity-rebuilt-baseplate.scad",
    ],
    [
        Factor("size",
               expand_xy(1, 5, ((5, 5),)),
               to_command=lambda value: ["-D", f"gridx={value[0]}",
                                         "-D", f"gridy={value[1]}"],
               to_meta=lambda value: f"{value[0]}x{value[1]}",
               ),
        # [0: thin, 1:weighted, 2:skeletonized, 3: screw together, 4: screw together minimal]

        Factor("plate",
               (0, 1, 2, 3),
               to_command=openscad_arg("style_plate"),
               to_meta=lambda v: {0: "thin",
                                  1: "weighted",
                                  2: "skeletonized",
                                  3: "screw-together",
                                  4: "screw-together-minimal"}[v]
               ),
        Factor("magnet",
               ("true", ),  # The only style where false may make sense is (1) weighted
               to_command=openscad_arg("enable_magnet"),
               to_meta=lambda v: {
                   "true": "magnet",
                   "false": "nomag"}[v],
               ),
        # style_hole = 2; // [0:none, 1:contersink, 2:counterbore]
        Factor("hole",
               (0,),
               to_command=openscad_arg("style_hole"),
               to_meta=lambda _: "none"
               ),
    ],
    vars={
        "stl_path": "{{ output_models }}/baseplate/"
                    "{{ plate }}/"
                    "plate-{{ size}}-{{ plate }}.stl",
    },
    path="{{ stl_path }}"
)


def run_for_series(cmd_generator: CmdGenerator, check_exists=False, output_is_dir=False):
    for i, result in enumerate(cmd_generator.build_commands(), 1):
        if output_is_dir:
            if not result.path.is_dir():
                result.path.mkdir(parents=True)
        else:
            parent: Path = result.path.parent
            if not parent.is_dir():
                parent.mkdir(parents=True)

        if check_exists and result.path.is_file():
            print(f"[{i}]  {result.path} already exists!")
        else:
            print(f"[{i}] {' '.join(result.cmd_args)}")
            call(result.cmd_args)


slicer_bin_gen = cmd_gen_for_slicer(scad_bin_gen,
                                    "{{ output_gcode }}/bins/"
                                    "{{ filament_type }}-n{{ nozzle_diameter}}/{{ base }}-{{ lip }}")

slicer_base_gen = cmd_gen_for_slicer(scad_base_gen,
                                     "{{ output_gcode }}/baseplate/"
                                     "{{ filament_type }}-n{{ nozzle_diameter}}/{{ plate }}")


if __name__ == '__main__':
    shared_meta = {
        "output_models": OUTPUT_MODELS,
        "output_gcode": OUTPUT_GCODE,
    }
    CmdGenerator.global_meta.update(shared_meta)

    run_for_series(scad_bin_gen, check_exists=True)
    run_for_series(slicer_bin_gen, output_is_dir=True)

    run_for_series(scad_base_gen, check_exists=True)
    run_for_series(slicer_base_gen, output_is_dir=True)
