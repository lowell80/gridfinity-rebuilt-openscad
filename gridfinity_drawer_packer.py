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
    array: list[list[Bin | None]] = field(default_factory=list, init=False)
    _contents: list[tuple[Point, Bin]] = field(
        default_factory=list, init=False)
    _fill: int = 0

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
        ''' # Why is this sum() slower than the for loop?  t should be 2-3x faster.... Just keep this out of any inner loop and we don't care...
        found = 0
        for bin, _ in self._contents:
            found += bin.area
        '''
        return found / float(self.size.area)

    def populated(self, x: int, y: int) -> bool:
        return self.array[x][y] is not None

    def overlaps(self, bin: Bin, pos_x: int, pos_y: int) -> bool:
        try:
            return any(self.populated(x, y)
                       for x in range(pos_x, pos_x+bin.x)
                       for y in range(pos_y, pos_y+bin.y))
        except IndexError:
            return False

    def place_bin(self, bin: Bin, x, y) -> bool:
        if self.overlaps(bin, x, y):
            return False

        for x_ in range(x, x+bin.x):
            for y_ in range(y, y+bin.y):
                self.array[x_][y_] = bin
        self._contents.append((Point(x, y), bin))
        self._fill += bin.area
        return True

    def find_next_open(self, start=Point(0, 0)) -> Point | None:
        for x in range(start.x, self.size.x):
            for y in range(start.y if x == start.x else 0, self.size.y):
                if not self.populated(x, y):
                    return Point(x, y)
        return None


def test_container_bin_placement():
    """ Run:
    pytest gridfinity_drawer_packer.py
    """

    c = Container(Size(100, 100))
    b = Bin(2, 2)

    assert c.find_next_open() == Point(0, 0)
    assert not c.overlaps(b, 0, 0)
    assert c.place_bin(b, 0, 0)
    assert c.overlaps(b, 0, 0)
    assert c.overlaps(b, 1, 1)
    assert not c.overlaps(b, 2, 2)
    assert c.overlaps(b, 0, 1)
    assert c.overlaps(b, 1, 0)

    assert c.find_next_open() == Point(0, 2)
    assert c.find_next_open(Point(0, 2)) == Point(0, 2), \
        "Confirm that the same point can be returned if nothing is at 'start'"

    n = c.find_next_open()
    assert c.place_bin(b, n.x, n.y)

    count = 0
    while (n := c.find_next_open(n)) and count < 10000:
        count += 1
        c.place_bin(b, n.x, n.y)
        '''
        # No need to check this here.  Look for None returned from find_next_open(), but that only works because b equally goes into c.
        if c.filled() == 1:
            break
        '''

    assert len(c._contents) == (c.size.area / b.area)
    # print(c._contents)

    assert c.filled() == c.debug_filled1()
    assert c.filled() == c.debug_filled2()


if __name__ == '__main__':
    test_container_bin_placement()
