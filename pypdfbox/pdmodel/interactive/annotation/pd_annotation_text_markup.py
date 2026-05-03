from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_annotation_markup import PDAnnotationMarkup

_QUAD_POINTS: COSName = COSName.get_pdf_name("QuadPoints")


class PDAnnotationTextMarkup(PDAnnotationMarkup):
    """
    Intermediate base for the four text-markup annotation subtypes:
    Highlight, Underline, Strikeout, Squiggly. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationTextMarkup``.

    Text markup annotations carry a required ``/QuadPoints`` array of
    ``8 * n`` floats describing the quadrilaterals over which the markup
    is rendered (PDF 32000-1:2008 §12.5.6.10).

    Abstract — concrete subclasses set their own ``SUB_TYPE`` and
    ``/Subtype``.
    """

    # /Subtype values for the four concrete text-markup variants — handy
    # constants for callers that want to dispatch on subtype string without
    # importing each subclass.
    SUB_TYPE_HIGHLIGHT: str = "Highlight"
    SUB_TYPE_UNDERLINE: str = "Underline"
    SUB_TYPE_STRIKEOUT: str = "StrikeOut"  # PDF spec capitalisation
    SUB_TYPE_SQUIGGLY: str = "Squiggly"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        # Subtype is set by concrete subclasses, not here. When a subclass
        # default-constructs (no annotation_dict supplied), upstream's
        # ``PDAnnotationTextMarkup(String subType)`` constructor seeds the
        # required ``/QuadPoints`` entry with an empty array; mirror that
        # so the dictionary is spec-conformant from the start. We never
        # overwrite an existing ``/QuadPoints`` entry coming in from a
        # parsed dict.
        if annotation_dict is None and self._dict.get_dictionary_object(
            _QUAD_POINTS
        ) is None:
            self._dict.set_item(_QUAD_POINTS, COSArray())

    # ---------- /QuadPoints ----------

    def get_quad_points(self) -> list[float] | None:
        value = self._dict.get_dictionary_object(_QUAD_POINTS)
        if isinstance(value, COSArray):
            return value.to_float_array()
        return None

    def set_quad_points(self, qp: list[float] | tuple[float, ...] | None) -> None:
        if qp is None:
            self._dict.remove_item(_QUAD_POINTS)
            return
        arr = COSArray([COSFloat(float(v)) for v in qp])
        self._dict.set_item(_QUAD_POINTS, arr)

    def has_quad_points(self) -> bool:
        """Return ``True`` if a ``/QuadPoints`` array is present (even if
        empty).

        Useful predicate for callers that want to know whether the
        annotation has been wired up with markup geometry without
        materialising the full float list.
        """
        return isinstance(
            self._dict.get_dictionary_object(_QUAD_POINTS), COSArray
        )

    def quad_point_count(self) -> int:
        """Return the number of quadrilaterals encoded in ``/QuadPoints``.

        Each quadrilateral is described by 8 floats (4 corner points), so
        this is ``len(/QuadPoints) // 8``. Returns 0 when ``/QuadPoints``
        is absent or not a ``COSArray``. A trailing partial quadrilateral
        (length not a multiple of 8) is rounded down — same convention
        upstream readers use when rendering.
        """
        value = self._dict.get_dictionary_object(_QUAD_POINTS)
        if isinstance(value, COSArray):
            return value.size() // 8
        return 0


__all__ = ["PDAnnotationTextMarkup"]
