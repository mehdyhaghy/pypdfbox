from __future__ import annotations


class TrackKern:
    """An AFM track-kern entry (``TrackKern degree minPt minKern maxPt maxKern``).

    Mirrors ``org.apache.fontbox.afm.TrackKern``. Track kerning lets a
    consumer interpolate a per-pair kerning amount based on point size.
    """

    __slots__ = (
        "_degree",
        "_min_point_size",
        "_min_kern",
        "_max_point_size",
        "_max_kern",
    )

    def __init__(
        self,
        degree: int,
        min_point_size: float,
        min_kern: float,
        max_point_size: float,
        max_kern: float,
    ) -> None:
        self._degree = int(degree)
        self._min_point_size = float(min_point_size)
        self._min_kern = float(min_kern)
        self._max_point_size = float(max_point_size)
        self._max_kern = float(max_kern)

    def get_degree(self) -> int:
        return self._degree

    def get_min_point_size(self) -> float:
        return self._min_point_size

    def get_min_kern(self) -> float:
        return self._min_kern

    def get_max_point_size(self) -> float:
        return self._max_point_size

    def get_max_kern(self) -> float:
        return self._max_kern

    def __repr__(self) -> str:
        return (
            f"TrackKern(degree={self._degree}, "
            f"min_pt={self._min_point_size}, min_kern={self._min_kern}, "
            f"max_pt={self._max_point_size}, max_kern={self._max_kern})"
        )
