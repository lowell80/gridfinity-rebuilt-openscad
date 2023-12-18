""" gridfinity_drawer_packer.py


Linear programming / Linear optimization (also some integer-only optimizations) - interesting.  (Certainly circle back on the Sodku example); not relevant as all conditions cannot be described as linear inequalities.
Genetic algorithms - (knap sack problem) possibly useful, but completely ignores geometry (so fit would essentially be brute force)
Bin packing -

# NP-complete

2 dimensional bin packing problem (2D-BPP) - https://github.com/ktnr/BinPacking2D


PyMesh:   Geometry Processing Library for Python  https://pymesh.readthedocs.io/en/latest/

"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations_with_replacement, product
from typing import Iterable


'''
from typing import Iterable
def iter_once_default(first_iter: Iterable, remaining: Iterable) -> Iterable[Iterable]:
    """
    Return first_iterable exactly one time.  from then on keep returning 'remaining'.
    """
    yield first_iter
    while True:
        remaining = list(remaining)
        yield iter(remaining)
'''


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def __str__(self):
        return f"Point({self.x}, {self.y})"


@dataclass(frozen=True)
class Size:
    x: int
    y: int

    def swap(self) -> Size:
        return Size(self.y, self.x)

    def side_gt(self, length: int) -> bool:
        return self.x > length or self.y > length

    def side_lt(self, length: int) -> bool:
        return self.x < length or self.y < length

    def __gt__(self, other: Size) -> bool:
        """ object is larger (in either dimension) """
        return self.x > other.x or self.y > other.y

    def __lt__(self, other: Size) -> bool:
        """ object smaller (in either direction) """
        return self.x < other.x or self.y < other.y

    @property
    def area(self):
        return self.x * self.y


@dataclass(frozen=True)
class Bin(Size):
    def __str__(self):
        return f"bin-({self.x}x{self.y})"


@dataclass
class Container:
    size: Size
    array: list[list[int | None]] = field(default_factory=list, init=False)
    _contents: list[tuple[Point, Bin]] = field(
        default_factory=list, init=False)
    _fill: int = field(default=0, init=False)

    def __post_init__(self):
        self.clear()

    def clear(self):
        self.array = [
            [None for y in range(self.size.y)]
            for x in range(self.size.x)]
        self.contents = []

    def filled(self) -> float:
        return self._fill / float(self.size.area)

    def debug_filled1(self):
        found = 0
        array = self.array
        for x in range(self.size.x):
            for y in range(self.size.y):
                if array[x][y] is not None:
                    found += 1
        return found / float(self.size.area)

    def debug_filled2(self) -> float:
        found = sum(bin.area for _, bin in self._contents)
        ''' # Why is sum() slower than the for loop? it should be 2-3x faster. 
        # Just keep this out of any inner loop and we don't care...
        found = 0
        for bin, _ in self._contents:
            found += bin.area
        '''
        return found / float(self.size.area)

    def populated(self, x: int, y: int) -> bool:
        return self.array[x][y] is not None

    def overlaps(self, bin: Bin, pos_x: int, pos_y: int) -> bool:
        return any(self.populated(x, y)
                   for x in range(pos_x, pos_x+bin.x)
                   for y in range(pos_y, pos_y+bin.y))

    def place_bin(self, bin: Bin, x, y) -> bool:
        try:
            if self.overlaps(bin, x, y):
                return False
        except IndexError:
            return False

        bin_id = len(self._contents)
        self._contents.append((Point(x, y), bin))
        for x_ in range(x, x+bin.x):
            for y_ in range(y, y+bin.y):
                self.array[x_][y_] = bin_id

        self._fill += bin.area
        return True

    def find_next_open(self, start=Point(0, 0)) -> Point | None:
        for x in range(start.x, self.size.x):
            for y in range(start.y if x == start.x else 0, self.size.y):
                if not self.populated(x, y):
                    return Point(x, y)
        return None

    def asci_art(self, output=None):
        print("   | ", end="")
        print("----" * self.size.y)
        for x, row in enumerate(self.array):
            print(f"{x:02} | ", end="", file=output)
            for cell in row:
                value = "..." if cell is None else f"{cell:03x}"
                print(f"{value} ", end="", file=output)
            print("", file=output)


def combinations_of_sizes(max_size: Size,
                          min_side: int = 1
                          ) -> Iterable[Size]:
    """ Return all possible combinations of bin sizes """
    for x, y in combinations_with_replacement(
            range(max(max_size.x, max_size.y), 0, -1), 2):
        n = Size(x, y)
        if n.side_gt(min_side) and n < max_size and n < max_size.swap():
            yield n
        # somehow returning sizes that are too big....


def combination_with_sizes_for_area(max_size: Size,
                                    total_area: int,
                                    /,
                                    min_size: Size = Size(2, 2),
                                    ) -> Iterable[tuple[Size, int]]:
    for bin_size in combinations_of_sizes(max_size, 1):
        # min_size ...
        max_count = total_area // bin_size.area // 2
        yield bin_size, max_count


def combinations_that_fit_in_area(combinations: list[tuple[Size, int]],
                                  area: int
                                  ) -> Iterable[tuple[Size, int]]:
    inputs = []
    for (bin, count) in combinations:
        x = [(bin, i) for i in range(count+1)]
        inputs.append(x)
    for pair in product(*inputs):
        total = sum(s.area * c for s, c in pair)
        if total == area:
            yield [(s, c) for s, c in pair if c > 0]   # type: ignore





def test_container_bin_placement():
    """ Run:
    pytest gridfinity_drawer_packer.py
    """
    c = Container(Size(40, 31))
    b = Bin(2, 2)
    b_ = Bin(1, 1)
    assert c.find_next_open() == Point(0, 0)
    assert not c.overlaps(b, 0, 0)
    assert c.place_bin(b, 0, 0)
    assert c.populated(0, 0), "Expect point 0,0 to be populated"
    assert c.overlaps(b, 0, 0)
    assert c.overlaps(b, 1, 1)
    assert not c.overlaps(b, 2, 2)
    assert c.overlaps(b, 0, 1)
    assert c.overlaps(b, 1, 0)

    assert c.find_next_open() == Point(0, 2)
    assert c.find_next_open(Point(0, 2)) == Point(0, 2), \
        "Confirm that the same point can be returned if nothing is at 'start'"

    n = c.find_next_open()
    assert isinstance(n, Point)
    assert c.place_bin(b, n.x, n.y)

    count = 0
    while (n := c.find_next_open(n)) and count < 10000:
        count += 1
        if not c.place_bin(b, n.x, n.y):
            c.place_bin(b_, n.x, n.y)
        '''
        # No need to check this here.  Look for None returned from find_next_open(), but that only works because b equally goes into c.
        if c.filled() == 1:
            break
        '''

    # No longer '==' as not using fixed bin size...
    assert len(c._contents) >= (c.size.area / b.area)
    # print(c._contents)

    assert c.filled() == c.debug_filled1()
    assert c.filled() == c.debug_filled2()

    c.asci_art()



def test_combinations_of_sizes():
    max_size = Size(5, 4)
    combos = list(combinations_of_sizes(max_size))
    assert max_size in combos
    assert Size(5, 5) not in combos



def test_placement_kitchen_drawer528x381():
    base_size_u = 42
    size_mm = Size(528, 381)
    size_u = Size(size_mm.x // base_size_u, size_mm.y // base_size_u)
    max_printable_u = Size(5, 4)

    possible_sizes = []
    for bin_size, count in combination_with_sizes_for_area(max_printable_u,
                                                           size_u.area):
        possible_sizes.extend((bin_size,) * count)


    all_combos = combination_with_sizes_for_area(max_printable_u, size_u.area)
    volumetrically_matching_combos = combinations_that_fit_in_area(all_combos, size_u.area)

    for i in volumetrically_matching_combos:
        print(i)

    # container = Container(size_u)
    # container.filled




if __name__ == '__main__':
    test_container_bin_placement()
    test_combinations_of_sizes()

    test_placement_kitchen_drawer528x381()
