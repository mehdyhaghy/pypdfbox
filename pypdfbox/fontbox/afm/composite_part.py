from __future__ import annotations


class CompositePart:
    """A single ``PCC`` part of an AFM ``CC`` composite glyph.

    Mirrors ``org.apache.fontbox.afm.CompositePart``.
    """

    __slots__ = ("_name", "_x_displacement", "_y_displacement")

    def __init__(self, name: str, x_displacement: int, y_displacement: int) -> None:
        self._name = name
        self._x_displacement = int(x_displacement)
        self._y_displacement = int(y_displacement)

    def get_name(self) -> str:
        return self._name

    def get_x_displacement(self) -> int:
        return self._x_displacement

    def get_y_displacement(self) -> int:
        return self._y_displacement

    def __repr__(self) -> str:
        return (
            f"CompositePart({self._name!r}, "
            f"{self._x_displacement}, {self._y_displacement})"
        )
