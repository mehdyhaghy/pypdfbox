from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)

from .pd_annotation_markup import PDAnnotationMarkup

_QUAD_POINTS: COSName = COSName.get_pdf_name("QuadPoints")
_IC: COSName = COSName.get_pdf_name("IC")
_RO: COSName = COSName.get_pdf_name("RO")
_OVERLAY_TEXT: COSName = COSName.get_pdf_name("OverlayText")
_REPEAT: COSName = COSName.get_pdf_name("Repeat")
_DA: COSName = COSName.get_pdf_name("DA")
_Q: COSName = COSName.get_pdf_name("Q")


class PDAnnotationRedact(PDAnnotationMarkup):
    """
    Redaction annotation — ``/Subtype /Redact``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationRedact``.

    A redaction annotation identifies content that is intended to be
    removed from the document (PDF 32000-1:2008 §12.5.6.23, Table 192).
    The redaction process consists of two phases — content identification
    (marking with these annotations) and content removal (applying the
    redactions). Extends :class:`PDAnnotationMarkup`.

    Subtype-specific entries:

    * ``/QuadPoints`` — array of 8×n numbers describing the bounding
      quadrilaterals of the regions to be redacted.
    * ``/IC`` — interior color used to fill the redacted region after the
      content has been removed (3 numbers, RGB).
    * ``/RO`` — form XObject (stream) to use in place of redacted content.
    * ``/OverlayText`` — text string to overlay the redacted region.
    * ``/Repeat`` — boolean. If true, ``/OverlayText`` repeats to fill
      the region; otherwise it appears once.
    * ``/DA`` — default appearance string controlling overlay-text
      formatting (font, size, color).
    * ``/Q`` — text-quadding (alignment): 0 = left, 1 = centered, 2 = right.
    """

    SUB_TYPE: str = "Redact"

    # /Q values per spec.
    QUADDING_LEFT: int = 0
    QUADDING_CENTERED: int = 1
    QUADDING_RIGHT: int = 2

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /QuadPoints ----------

    def get_quad_points(self) -> list[float] | None:
        value = self._dict.get_dictionary_object(_QUAD_POINTS)
        if isinstance(value, COSArray):
            return value.to_float_array()
        return None

    def set_quad_points(
        self, points: list[float] | tuple[float, ...] | None
    ) -> None:
        if points is None:
            self._dict.remove_item(_QUAD_POINTS)
            return
        if len(points) % 8 != 0:
            raise ValueError(
                f"/QuadPoints length must be a multiple of 8; got {len(points)}"
            )
        self._dict.set_item(
            _QUAD_POINTS, COSArray([COSFloat(float(v)) for v in points])
        )

    # ---------- /IC (interior color) ----------

    def get_interior_color(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(_IC)
        if isinstance(value, COSArray):
            return value
        return None

    def set_interior_color(
        self, color: COSArray | list[float] | tuple[float, ...] | None
    ) -> None:
        if color is None:
            self._dict.remove_item(_IC)
            return
        if isinstance(color, COSArray):
            self._dict.set_item(_IC, color)
            return
        self._dict.set_item(
            _IC, COSArray([COSFloat(float(c)) for c in color])
        )

    # ---------- /RO (replacement form XObject) ----------

    def get_redaction_appearance(self) -> COSStream | None:
        """Return the raw ``/RO`` form-XObject stream — overlay content
        used in place of redacted material."""
        value = self._dict.get_dictionary_object(_RO)
        if isinstance(value, COSStream):
            return value
        return None

    def set_redaction_appearance(self, stream: COSStream | None) -> None:
        if stream is None:
            self._dict.remove_item(_RO)
            return
        if isinstance(stream, COSStream):
            self._dict.set_item(_RO, stream)
            return
        if hasattr(stream, "get_cos_object"):
            cos = stream.get_cos_object()
            if not isinstance(cos, COSStream):
                raise TypeError(
                    "set_redaction_appearance expects a COSStream-backed wrapper"
                )
            self._dict.set_item(_RO, cos)
            return
        raise TypeError(
            "set_redaction_appearance expects None, COSStream, or wrapper "
            f"exposing get_cos_object(); got {type(stream).__name__}"
        )

    # ---------- /OverlayText ----------

    def get_overlay_text(self) -> str | None:
        return self._dict.get_string(_OVERLAY_TEXT)

    def set_overlay_text(self, value: str | None) -> None:
        self._dict.set_string(_OVERLAY_TEXT, value)

    # ---------- /Repeat ----------

    def is_repeat(self) -> bool:
        """``/Repeat`` — default ``False`` per spec."""
        return self._dict.get_boolean(_REPEAT, False)

    def set_repeat(self, value: bool) -> None:
        self._dict.set_boolean(_REPEAT, bool(value))

    # ---------- /DA (default appearance) ----------

    def get_default_appearance(self) -> str | None:
        return self._dict.get_string(_DA)

    def set_default_appearance(self, value: str | None) -> None:
        self._dict.set_string(_DA, value)

    # ---------- /Q (quadding / alignment) ----------

    def get_q(self) -> int:
        """``/Q`` — default ``0`` (left-justified) per spec."""
        return self._dict.get_int(_Q, 0)

    def set_q(self, value: int) -> None:
        self._dict.set_int(_Q, int(value))


__all__ = ["PDAnnotationRedact"]
