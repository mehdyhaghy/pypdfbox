from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

if TYPE_CHECKING:
    from .pd_measure_dictionary import PDMeasureDictionary

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_BBOX: COSName = COSName.get_pdf_name("BBox")
_NAME: COSName = COSName.get_pdf_name("Name")
_MEASURE: COSName = COSName.get_pdf_name("Measure")


class PDViewportDictionary:
    """This class represents a viewport dictionary.

    Mirrors PDFBox ``org.apache.pdfbox.pdmodel.interactive.measurement.PDViewportDictionary``.
    """

    #: The ``/Type`` value for a viewport dictionary, per PDF 32000-1 §12.7.5.
    TYPE: str = "Viewport"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        """Return the underlying ``COSDictionary``."""
        return self._dict

    def get_type(self) -> str:
        """Return the type of the viewport dictionary, always ``"Viewport"``."""
        return self.TYPE

    def get_b_box(self) -> PDRectangle | None:
        """Retrieve the rectangle specifying the location of the viewport."""
        bbox = self._dict.get_dictionary_object(_BBOX)
        if isinstance(bbox, COSArray):
            return PDRectangle.from_cos_array(bbox)
        return None

    def set_b_box(self, rectangle: PDRectangle | COSArray | None) -> None:
        """Set the rectangle specifying the location of the viewport.

        Accepts a :class:`PDRectangle`, a raw ``COSArray`` (already-parsed
        rectangle), or ``None`` to clear the entry. Mirrors PDFBox's
        ``setItem(BBox, rectangle)`` which round-trips whatever ``COSBase``
        the supplied ``COSObjectable`` produces.
        """
        if rectangle is None:
            self._dict.remove_item(_BBOX)
            return
        if isinstance(rectangle, COSArray):
            self._dict.set_item(_BBOX, rectangle)
            return
        self._dict.set_item(_BBOX, rectangle.get_cos_object())

    # Upstream PDFBox spelling is ``getBBox`` / ``setBBox`` — the
    # camelCase→snake_case rule splits at every uppercase boundary giving
    # ``get_b_box``, but PDFBox developers reach for ``get_bbox`` first
    # since "BBox" reads as a single acronym. Expose both with identical
    # semantics; ``get_b_box`` / ``set_b_box`` remain for back-compat with
    # earlier callers.
    def get_bbox(self) -> PDRectangle | None:
        """Alias for :meth:`get_b_box`. Mirrors PDFBox ``getBBox()``."""
        return self.get_b_box()

    def set_bbox(self, rectangle: PDRectangle | COSArray | None) -> None:
        """Alias for :meth:`set_b_box`. Mirrors PDFBox ``setBBox()``."""
        self.set_b_box(rectangle)

    def get_name(self) -> str | None:
        """Retrieve the name of the viewport.

        Mirrors upstream ``getNameAsString(COSName.NAME)`` which accepts
        either a ``COSName`` or a ``COSString`` value at the ``/Name`` slot
        — some producers emit the entry as a string. ``None`` is returned
        when the entry is absent or has any other type.
        """
        # ``COSDictionary.get_name_as_string`` mirrors upstream
        # ``getNameAsString``: it returns the underlying value of either a
        # ``COSName`` or a ``COSString``, falling back to the (here unused)
        # default.
        return self._dict.get_name_as_string(_NAME)

    def set_name(self, name: str | None) -> None:
        """Set the name of the viewport."""
        if name is None:
            self._dict.remove_item(_NAME)
            return
        self._dict.set_name(_NAME, name)

    def get_measure(self) -> PDMeasureDictionary | None:
        """Retrieve the measure dictionary."""
        from .pd_measure_dictionary import PDMeasureDictionary

        base = self._dict.get_dictionary_object(_MEASURE)
        if isinstance(base, COSDictionary):
            return PDMeasureDictionary(base)
        return None

    def set_measure(self, measure: PDMeasureDictionary | None) -> None:
        """Set the measure dictionary."""
        if measure is None:
            self._dict.remove_item(_MEASURE)
            return
        self._dict.set_item(_MEASURE, measure.get_cos_object())

    # ------------------------------------------------------------------ predicates
    # Upstream PDFBox lacks these — they are convenience helpers for
    # callers who only want to know whether a slot is populated, without
    # paying the cost of materializing a ``PDRectangle`` /
    # ``PDMeasureDictionary`` wrapper. ``contains_key`` is the
    # ``COSDictionary``-level operation that mirrors upstream's
    # ``COSDictionary.containsKey``.
    def has_b_box(self) -> bool:
        """Return ``True`` when the ``/BBox`` entry is present."""
        return self._dict.contains_key(_BBOX)

    def has_bbox(self) -> bool:
        """Alias for :meth:`has_b_box` matching the upstream "BBox" acronym."""
        return self.has_b_box()

    def has_name(self) -> bool:
        """Return ``True`` when the ``/Name`` entry is present."""
        return self._dict.contains_key(_NAME)

    def has_measure(self) -> bool:
        """Return ``True`` when the ``/Measure`` entry is present."""
        return self._dict.contains_key(_MEASURE)

    def is_named(self, name: str) -> bool:
        """Return ``True`` when ``/Name`` resolves to ``name``.

        The comparison is exact and case-sensitive, matching upstream
        ``getNameAsString(COSName.NAME).equals(name)`` semantics. Returns
        ``False`` when the ``/Name`` entry is absent.
        """
        return self.get_name() == name

    def __repr__(self) -> str:
        # Keep the representation cheap — touch only the COS layer so
        # ``__repr__`` never triggers wrapper construction. Mirrors the
        # debug-friendly format used by ``PDRendition`` / similar wrappers.
        return (
            f"{type(self).__name__}("
            f"name={self.get_name()!r}, "
            f"bbox={'set' if self.has_b_box() else 'unset'}, "
            f"measure={'set' if self.has_measure() else 'unset'})"
        )


__all__ = ["PDViewportDictionary"]
