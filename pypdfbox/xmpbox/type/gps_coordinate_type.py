from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from .text_type import TextType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class GPSCoordinateType(TextType):
    """
    XMP GPS-coordinate simple property.

    pypdfbox addition (no upstream Java class). PDF/A-1 (ISO 19005-1) and the
    EXIF/XMP spec define the ``GPSCoordinate`` type as a string in either
    ``"DDD,MM,SSk"`` or ``"DDD,MM.mmk"`` form, where ``k`` is the hemisphere
    indicator (``N`` / ``S`` for latitude, ``E`` / ``W`` for longitude). On the
    wire this is stored as a plain :class:`TextType`; we add light parse/format
    helpers so callers can interrogate the structured fields without having to
    re-do the string surgery.

    Round-trip with the raw string is intentionally lossless: ``set_value``
    keeps whatever the caller stored (matching upstream ``TextType`` semantics).
    """

    _HEMISPHERES: frozenset[str] = frozenset({"N", "S", "E", "W"})

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace_uri: str | None,
        prefix: str | None,
        property_name: str,
        value: Any,
    ) -> None:
        super().__init__(metadata, namespace_uri, prefix, property_name, value)

    def parse(self) -> tuple[int, float, float, str] | None:
        """
        Decompose the stored coordinate string into
        ``(degrees, minutes, seconds, hemisphere)``.

        ``DDD,MM,SS<hemi>`` returns integer seconds; ``DDD,MM.mm<hemi>`` returns
        ``seconds = 0.0`` and the fractional minutes verbatim. Returns ``None``
        when the string is empty or does not match either upstream form.
        """
        text = self.get_string_value()
        if not text:
            return None
        hemi = text[-1]
        if hemi not in self._HEMISPHERES:
            return None
        body = text[:-1]
        parts = body.split(",")
        if len(parts) == 2:
            try:
                degrees = int(parts[0])
                minutes = float(parts[1])
            except ValueError:
                return None
            if not self._is_valid_coordinate_part(degrees, minutes):
                return None
            return (degrees, minutes, 0.0, hemi)
        if len(parts) == 3:
            try:
                degrees = int(parts[0])
                minutes = float(parts[1])
                seconds = float(parts[2])
            except ValueError:
                return None
            if not self._is_valid_coordinate_part(degrees, minutes, seconds):
                return None
            return (degrees, minutes, seconds, hemi)
        return None

    @staticmethod
    def _is_valid_coordinate_part(
        degrees: int, minutes: float, seconds: float = 0.0
    ) -> bool:
        return (
            degrees >= 0
            and math.isfinite(minutes)
            and math.isfinite(seconds)
            and 0.0 <= minutes < 60.0
            and 0.0 <= seconds < 60.0
        )

    @classmethod
    def format_dms(
        cls, degrees: int, minutes: int, seconds: int, hemisphere: str
    ) -> str:
        """Format ``(D, M, S, hemi)`` as the upstream ``"D,M,Sk"`` string."""
        if hemisphere not in cls._HEMISPHERES:
            raise ValueError(
                f"hemisphere must be one of N/S/E/W, got {hemisphere!r}"
            )
        if not cls._is_valid_coordinate_part(degrees, minutes, seconds):
            raise ValueError(
                "degrees must be non-negative and minutes/seconds must be "
                "finite values in the range [0, 60)"
            )
        return f"{int(degrees)},{int(minutes)},{int(seconds)}{hemisphere}"

    @classmethod
    def format_dm(
        cls, degrees: int, minutes: float, hemisphere: str
    ) -> str:
        """Format ``(D, M.mm, hemi)`` as the upstream ``"D,M.mmk"`` string."""
        if hemisphere not in cls._HEMISPHERES:
            raise ValueError(
                f"hemisphere must be one of N/S/E/W, got {hemisphere!r}"
            )
        if not cls._is_valid_coordinate_part(degrees, minutes):
            raise ValueError(
                "degrees must be non-negative and minutes must be a finite "
                "value in the range [0, 60)"
            )
        return f"{int(degrees)},{minutes}{hemisphere}"
