from __future__ import annotations

import itertools
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from subprocess import call
from typing import Any, Callable, Dict, List


OPENSCAD_BIN = "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
# SLIC3R compatible
SLICER_BIN = "/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"


def path_append_dash_suffix(path: PurePosixPath, value) -> PurePosixPath:
    return path.with_name(path.name + f"{value}-")


def mapping_sub_path(mapping: Dict[Any, str]):
    def to_path(path: PurePosixPath, value) -> PurePosixPath:
        name = mapping.get(value, str(value))
        if name:
            return path.with_name(path.name + f"-{name}")
        return path
    return to_path


def mapping_sub_dirandpath(mapping: Dict[Any, str]):
    def to_path(path: PurePosixPath, value) -> PurePosixPath:
        name = mapping.get(value, str(value))
        if name:
            return path.parent / name / (path.name + f"-{name}")
        return path
    return to_path


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
    to_command: Callable[[Any], List[str]] = field()
    to_meta: Callable[[Any], str] = lambda v: str(v)
    to_path: Callable[[PurePosixPath, Any], PurePosixPath] = lambda p, _: p
    rewrite_args: Callable[[List[str], Any], List[str]] = lambda args, _: args

    def __iter__(self):
        if isinstance(self.values, CmdGenerator):
            return (path for path, _, _ in self.values.build_commands())
        else:
            return iter(self.values)


@dataclass
class CmdGenerator:
    cmd: list[str] = field()            # default_factory=list)
    factors: list[Factor] = field()     # default_factory=list)
    path_suffix: str = field()
    init_path: PurePosixPath = PurePosixPath(".")

    def product(self):
        return itertools.product(*(factor for factor in self.factors))

    def build_commands(self):
        for combos in self.product():
            path = self.init_path
            cmd_args = self.cmd.copy()
            meta = {}
            for i, value in enumerate(combos):
                factor = self.factors[i]
                meta[factor.name] = factor.to_meta(value)
                cmd_args.extend(factor.to_command(value))
                path = factor.to_path(path, value)
                cmd_args = factor.rewrite_args(cmd_args, value)
            path = path.with_suffix(self.path_suffix)
            path, cmd_args, meta = self.finalize_command(path, cmd_args, meta)
            yield path, cmd_args, meta

    @staticmethod
    def finalize_command(path, cmd_args: list[str], meta):
        idx = cmd_args.index("OUTPUT_PATH")
        cmd_args[idx] = os.fspath(path)
        return path, cmd_args, meta


def lite_bin_rewrite(args, value):
    '''
    lambda args, value: args if value != "lite" else
                    [v if a == "gridfinity-rebuilt-bins.scad" else a
                     for a in args]
    '''
    if value == "lite":
        new_args = []
        for arg in args:
            if arg == "gridfinity-rebuilt-bins.scad":
                arg = "gridfinity-rebuilt-lite.scad"
            new_args.append(arg)
        return new_args
    return args


scad_gen = CmdGenerator(
    [
        OPENSCAD_BIN,
        "--export-format=binstl",
        "--enable", "fast-csg",
        "-o", "OUTPUT_PATH",
        "gridfinity-rebuilt-bins.scad",
    ],
    [
        Factor("base_size",
               expand_xy(1, 5, ((5, 5),)),
               to_path=lambda path, value: path.with_name(
                   path.name + f"-{value[0]}x{value[1]}"),
               to_command=lambda value: ["-D", f"gridx={value[0]}",
                                         "-D", f"gridy={value[1]}"],
               to_meta=lambda value: f"{value[0]}x{value[1]}",
               ),
        Factor("height",
               (2, 4, 6, 8, 10, 12),
               to_path=lambda path, value: path.with_name(
                   path.name + f"-{value}h"),
               to_command=openscad_arg("gridz"),
               ),
        Factor("base",
               (0, 1, "lite"),
               to_path=mapping_sub_dirandpath({0: "flat", 1: "magnet"}),
               to_command=lambda value: [
                   # Not sure why this defaults incorrectly....
                   "-D", f"style_hole={value}"] if value != "lite" else ["-D", "divx=1",
                                                                         "-D", "divy=1"],
               to_meta=lambda v: {0: "flat",
                                  1: "magnet-hole", "lite": "lite"}[v],
               rewrite_args=lite_bin_rewrite,
               ),
        Factor("lip",
               (0, 2),
               to_path=mapping_sub_dirandpath({0: "stackable", 2: "nolip"}),
               to_command=openscad_arg("style_lip"),
               to_meta=lambda v: {
                   0: "lip", 2: "disable lib, retain height"}[v],
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
    init_path=Path("output/bin"),
    path_suffix=".stl"
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


slicer_gen = CmdGenerator(
    [
        SLICER_BIN,
        "--export-gcode",
        # "--export-3mf",
        "--output", "OUTPUT_PATH",
    ],
    [
        Factor("model",
               scad_gen,
               to_command=lambda value: [os.fspath(value)],
               ),
        Factor("slicer_config",
               ("pla",
                "petg",
                ),
               to_command=lambda value: ["--load", f"profile_{value}_n06.ini"],
               to_path=lambda path, value: path / str(value).upper(),
               ),

    ],
    init_path=Path("output"),
    path_suffix=""
)


for i, (path, cmd_args, meta) in enumerate(
        scad_gen.build_commands(), 1):
    parent: Path = path.parent
    if not parent.is_dir():
        parent.mkdir(parents=True)

    # if "lite" in str(cmd_args):
    if path.is_file():
        print(f"[{i}]  {path} already exists!")
    else:
        print(f"[{i}] {' '.join(cmd_args)}")
        call(cmd_args)


for i, (path, cmd_args, meta) in enumerate(slicer_gen.build_commands(), 1):
    if not path.is_dir():
        path.mkdir(parents=True)

    print(f"[{i}] {' '.join(cmd_args)}")
    call(cmd_args)
