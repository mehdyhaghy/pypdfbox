from __future__ import annotations

from pypdfbox.fontbox.ttf.glyph_data import BoundingBox

from .ligature import Ligature


class CharMetric:
    """Per-glyph metric record from an AFM ``CharMetrics`` block.

    Mirrors ``org.apache.fontbox.afm.CharMetric``. Carries the writing-
    direction-0 advance (``wx``/``wy``), explicit metric-set 0 / 1 widths
    (``w0x``/``w0y``/``w1x``/``w1y`` and the paired ``w``/``w0``/``w1``
    forms), the optional vertical-vector ``vv``, the glyph name, code,
    bounding box, and any ``L`` ligature successors declared on the line.
    """

    __slots__ = (
        "_character_code",
        "_wx",
        "_w0x",
        "_w1x",
        "_wy",
        "_w0y",
        "_w1y",
        "_w",
        "_w0",
        "_w1",
        "_vv",
        "_name",
        "_bounding_box",
        "_ligatures",
    )

    def __init__(self) -> None:
        self._character_code: int = -1
        self._wx: float = 0.0
        self._w0x: float = 0.0
        self._w1x: float = 0.0
        self._wy: float = 0.0
        self._w0y: float = 0.0
        self._w1y: float = 0.0
        self._w: tuple[float, float] | None = None
        self._w0: tuple[float, float] | None = None
        self._w1: tuple[float, float] | None = None
        self._vv: tuple[float, float] | None = None
        self._name: str = ""
        self._bounding_box: BoundingBox | None = None
        self._ligatures: list[Ligature] = []

    # ---------- character code ----------

    def get_character_code(self) -> int:
        return self._character_code

    def set_character_code(self, value: int) -> None:
        self._character_code = int(value)

    # ---------- name ----------

    def get_name(self) -> str:
        return self._name

    def set_name(self, value: str) -> None:
        self._name = value

    # ---------- bounding box ----------

    def get_bounding_box(self) -> BoundingBox | None:
        return self._bounding_box

    def set_bounding_box(self, value: BoundingBox | None) -> None:
        self._bounding_box = value

    # ---------- WX / W0X / W1X ----------

    def get_wx(self) -> float:
        return self._wx

    def set_wx(self, value: float) -> None:
        self._wx = float(value)

    def get_w0x(self) -> float:
        return self._w0x

    def set_w0x(self, value: float) -> None:
        self._w0x = float(value)

    def get_w1x(self) -> float:
        return self._w1x

    def set_w1x(self, value: float) -> None:
        self._w1x = float(value)

    # ---------- WY / W0Y / W1Y ----------

    def get_wy(self) -> float:
        return self._wy

    def set_wy(self, value: float) -> None:
        self._wy = float(value)

    def get_w0y(self) -> float:
        return self._w0y

    def set_w0y(self, value: float) -> None:
        self._w0y = float(value)

    def get_w1y(self) -> float:
        return self._w1y

    def set_w1y(self, value: float) -> None:
        self._w1y = float(value)

    # ---------- W / W0 / W1 (paired) ----------

    def get_w(self) -> tuple[float, float] | None:
        return self._w

    def set_w(self, value: tuple[float, float] | list[float] | None) -> None:
        self._w = None if value is None else (float(value[0]), float(value[1]))

    def get_w0(self) -> tuple[float, float] | None:
        return self._w0

    def set_w0(self, value: tuple[float, float] | list[float] | None) -> None:
        self._w0 = None if value is None else (float(value[0]), float(value[1]))

    def get_w1(self) -> tuple[float, float] | None:
        return self._w1

    def set_w1(self, value: tuple[float, float] | list[float] | None) -> None:
        self._w1 = None if value is None else (float(value[0]), float(value[1]))

    # ---------- VV ----------

    def get_vv(self) -> tuple[float, float] | None:
        return self._vv

    def set_vv(self, value: tuple[float, float] | list[float] | None) -> None:
        self._vv = None if value is None else (float(value[0]), float(value[1]))

    # ---------- ligatures ----------

    def add_ligature(self, ligature: Ligature) -> None:
        self._ligatures.append(ligature)

    def get_ligatures(self) -> list[Ligature]:
        return list(self._ligatures)

    def __repr__(self) -> str:
        return (
            f"CharMetric(code={self._character_code}, name={self._name!r}, "
            f"wx={self._wx})"
        )
