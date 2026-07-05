from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
    COSString,
)

from .pd_annotation import PDAnnotation

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (
        PDMeasureDictionary,
    )

    from .pd_annotation_popup import PDAnnotationPopup
    from .pd_border_style_dictionary import PDBorderStyleDictionary
    from .pd_external_data_dictionary import PDExternalDataDictionary

_CREATION_DATE: COSName = COSName.get_pdf_name("CreationDate")
_IRT: COSName = COSName.get_pdf_name("IRT")
_SUBJ: COSName = COSName.get_pdf_name("Subj")
_RT: COSName = COSName.get_pdf_name("RT")
_IT: COSName = COSName.get_pdf_name("IT")
_CA: COSName = COSName.get_pdf_name("CA")
_POPUP: COSName = COSName.get_pdf_name("Popup")
_RC: COSName = COSName.get_pdf_name("RC")
_EX_DATA: COSName = COSName.get_pdf_name("ExData")
_BS: COSName = COSName.get_pdf_name("BS")
_IC: COSName = COSName.get_pdf_name("IC")
_MEASURE: COSName = COSName.get_pdf_name("Measure")


class PDAnnotationMarkup(PDAnnotation):
    """
    Intermediate base for markup annotations. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationMarkup``.

    Markup annotations carry common review-workflow fields (creation date,
    in-reply-to, subject, reply type, intent, constant opacity) on top of
    the generic :class:`PDAnnotation` surface (PDF 32000-1:2008 §12.5.6.2,
    Table 170).

    Abstract — concrete markup subclasses set their own ``SUB_TYPE`` and
    ``/Subtype`` in their constructors. ``/T`` (title popup) is inherited
    from :class:`PDAnnotation` and is not redefined here.

    Lite scope: rich contents are exposed as raw strings; rich text parsing is
    left to callers.
    """

    # Reply-type values from PDF 1.7 reference Table 170.
    RT_REPLY: str = "R"
    RT_GROUP: str = "Group"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        # Subtype is set by concrete subclasses, not here.

    # ---------- /CreationDate ----------

    def get_creation_date(self) -> str | None:
        """Raw ``/CreationDate`` string. Upstream returns a parsed
        ``Calendar``; we follow the PDAnnotation pattern of returning the
        raw PDF date string and leaving date parsing to the caller."""
        return self._dict.get_string(_CREATION_DATE)

    def set_creation_date(self, date: str | None) -> None:
        self._dict.set_string(_CREATION_DATE, date)

    # ---------- /IRT (in reply to) ----------

    def get_in_reply_to(self) -> COSBase | None:
        """Raw ``/IRT`` value (typically a referenced annotation dictionary).
        Upstream returns a ``PDAnnotation``; lite scope returns the raw COS
        to avoid recursive factory calls during dispatch wiring."""
        value = self._dict.get_dictionary_object(_IRT)
        return value

    def set_in_reply_to(self, annot: PDAnnotation | COSBase | None) -> None:
        if annot is None:
            self._dict.remove_item(_IRT)
            return
        self._dict.set_item(
            _IRT,
            annot.get_cos_object() if hasattr(annot, "get_cos_object") else annot,
        )

    # ---------- /Popup ----------

    def get_popup(self) -> PDAnnotationPopup | None:
        """Return the popup annotation associated with this markup annotation.

        Mirrors upstream ``PDAnnotationMarkup.getPopup``.
        """
        from .pd_annotation_popup import PDAnnotationPopup

        value = self._dict.get_dictionary_object(_POPUP)
        if isinstance(value, COSDictionary):
            return PDAnnotationPopup(value)
        return None

    def set_popup(
        self, popup: PDAnnotationPopup | COSDictionary | None
    ) -> None:
        """Set the popup annotation associated with this markup annotation.

        Mirrors upstream ``PDAnnotationMarkup.setPopup`` while also accepting
        a raw ``COSDictionary`` for callers already operating at the COS layer.
        """
        if popup is None:
            self._dict.remove_item(_POPUP)
            return
        self._dict.set_item(
            _POPUP,
            popup.get_cos_object() if hasattr(popup, "get_cos_object") else popup,
        )

    # ---------- /Subj ----------

    def get_subject(self) -> str | None:
        return self._dict.get_string(_SUBJ)

    def set_subject(self, s: str | None) -> None:
        self._dict.set_string(_SUBJ, s)

    # ---------- /RT (reply type) ----------

    def get_reply_type(self) -> str:
        """Default per spec is :data:`RT_REPLY` (``R``).

        Mirrors upstream ``getReplyType()`` which uses
        ``getNameAsString(COSName.RT, RT_REPLY)`` — a missing ``/RT`` is
        equivalent to a reply (the more common case), not a group.
        """
        return self._dict.get_name_as_string(_RT, self.RT_REPLY)

    def set_reply_type(self, rt: str | None) -> None:
        if rt is None:
            self._dict.remove_item(_RT)
            return
        self._dict.set_name(_RT, rt)

    # ---------- /IT (intent) ----------

    def get_intent(self) -> str | None:
        return self._dict.get_name_as_string(_IT)

    def set_intent(self, it: str | None) -> None:
        if it is None:
            self._dict.remove_item(_IT)
            return
        self._dict.set_name(_IT, it)

    # ---------- /CA (constant opacity) ----------

    def get_constant_opacity(self) -> float:
        """Default per spec is 1.0."""
        return self._dict.get_float(_CA, 1.0)

    def set_constant_opacity(self, ca: float) -> None:
        self._dict.set_float(_CA, float(ca))

    # ---------- /RC (rich contents) ----------

    def get_rich_contents(self) -> str | None:
        """Return the raw rich text contents displayed in the popup window.

        Mirrors upstream ``getRichContents()``: ``/RC`` may be either a
        ``COSString`` (inline rich-text XML) or a ``COSStream`` whose body
        decodes to the same XML. ``None`` is returned for any other / absent
        value.
        """
        value = self._dict.get_dictionary_object(_RC)
        if isinstance(value, COSString):
            return value.get_string()
        if isinstance(value, COSStream):
            return value.to_text_string()
        return None

    def set_rich_contents(self, rc: str | None) -> None:
        if rc is None:
            self._dict.remove_item(_RC)
            return
        self._dict.set_item(_RC, COSString(rc))

    # ---------- /BS (border style) ----------

    def get_border_style(self) -> PDBorderStyleDictionary | None:
        """Return the border style dictionary (line width and dash pattern).

        Mirrors upstream ``PDAnnotationMarkup.getBorderStyle()`` which
        exposes ``/BS`` on every markup-rooted annotation (PDF 32000-1:2008
        §12.5.4).
        """
        from .pd_border_style_dictionary import PDBorderStyleDictionary

        value = self._dict.get_dictionary_object(_BS)
        if isinstance(value, COSDictionary):
            return PDBorderStyleDictionary(value)
        return None

    def set_border_style(
        self, bs: PDBorderStyleDictionary | COSDictionary | None
    ) -> None:
        """Set the border style dictionary, or clear ``/BS`` when ``bs`` is ``None``.

        Mirrors upstream ``PDAnnotationMarkup.setBorderStyle(PDBorderStyleDictionary)``.
        """
        if bs is None:
            self._dict.remove_item(_BS)
            return
        self._dict.set_item(
            _BS,
            bs.get_cos_object() if hasattr(bs, "get_cos_object") else bs,
        )

    # ---------- predicate helper ----------

    def has_popup(self) -> bool:
        """Return ``True`` when ``/Popup`` is present and resolves to a dictionary.

        Convenience predicate that avoids constructing a
        :class:`PDAnnotationPopup` wrapper just to test presence — useful
        for migration paths that strip popups before re-export.
        """
        return isinstance(self._dict.get_dictionary_object(_POPUP), COSDictionary)

    # ---------- /ExData (external data) ----------

    def get_external_data(self) -> PDExternalDataDictionary | None:
        """Return the typed ``/ExData`` external-data dictionary.

        Mirrors upstream ``PDAnnotationMarkup.getExternalData`` which wraps
        the resolved dictionary in a ``PDExternalDataDictionary``; any
        non-dictionary shape yields ``None``.
        """
        from .pd_external_data_dictionary import (  # noqa: PLC0415
            PDExternalDataDictionary,
        )

        value = self._dict.get_dictionary_object(_EX_DATA)
        if isinstance(value, COSDictionary):
            return PDExternalDataDictionary(value)
        return None

    def set_external_data(
        self, ex_data: PDExternalDataDictionary | COSDictionary | None
    ) -> None:
        """Set or clear the ``/ExData`` entry.

        Mirrors upstream ``PDAnnotationMarkup.setExternalData
        (PDExternalDataDictionary)`` while also accepting a raw
        ``COSDictionary`` for callers already operating at the COS layer.
        """
        if ex_data is None:
            self._dict.remove_item(_EX_DATA)
            return
        self._dict.set_item(
            _EX_DATA,
            ex_data.get_cos_object() if hasattr(ex_data, "get_cos_object") else ex_data,
        )

    # ---------- /IC (interior color) ----------

    def get_interior_color(self) -> list[float] | None:
        """Return the ``/IC`` interior-color components, or ``None`` when
        ``/IC`` is absent.

        Mirrors the read shape of the per-subtype ``getInteriorColor``
        accessors on :class:`PDAnnotationLine`, :class:`PDAnnotationPolyline`,
        :class:`PDAnnotationPolygon`, and :class:`PDAnnotationSquareCircle`.
        Component count implies the colour space (1 = DeviceGray,
        3 = DeviceRGB, 4 = DeviceCMYK).

        Exposed on the markup base so read-only callers traversing a
        mixed annotation tree don't have to downcast to a concrete subtype
        before reaching for ``/IC``. The wire-level representation is
        identical across the subtypes that actually populate the entry,
        so a single base accessor is safe.
        """
        value = self._dict.get_dictionary_object(_IC)
        if isinstance(value, COSArray):
            return value.to_float_array()
        return None

    def set_interior_color(
        self, ic: list[float] | tuple[float, ...] | None
    ) -> None:
        """Write the ``/IC`` interior-color array, or remove the entry when
        ``ic`` is ``None``.

        Accepts 1, 3 or 4 floats matching DeviceGray / DeviceRGB /
        DeviceCMYK component counts — the PDF colour space is inferred at
        render time from the array length.
        """
        if ic is None:
            self._dict.remove_item(_IC)
            return
        arr = COSArray([COSFloat(float(c)) for c in ic])
        self._dict.set_item(_IC, arr)

    def remove_interior_color(self) -> None:
        """Remove the ``/IC`` entry. Equivalent to ``set_interior_color(None)``
        but communicates intent more clearly at call sites that strip
        colour metadata before export."""
        self._dict.remove_item(_IC)

    def has_interior_color(self) -> bool:
        """``True`` when ``/IC`` resolves to a numeric array.

        pypdfbox extension — counterpart of :meth:`has_popup`. Avoids
        materialising the float list when the caller only needs a
        presence check.
        """
        return isinstance(self._dict.get_dictionary_object(_IC), COSArray)

    # ---------- /Measure ----------

    def get_measure(self) -> PDMeasureDictionary | None:
        """Return the typed ``/Measure`` dictionary (PDF 32000-1:2008
        §12.7.10) or ``None`` when the entry is absent.

        Exposed on the markup base because ``/Measure`` is shared between
        :class:`PDAnnotationLine`, :class:`PDAnnotationPolyline`, and
        :class:`PDAnnotationPolygon`; the subclasses keep their own typed
        accessors for IDE-discoverable signatures, but read-only callers
        traversing a mixed annotation tree benefit from a single entry
        point.
        """
        from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (  # noqa: PLC0415
            PDMeasureDictionary,
        )

        value = self._dict.get_dictionary_object(_MEASURE)
        if isinstance(value, COSDictionary):
            return PDMeasureDictionary(value)
        return None

    def set_measure(
        self, measure: PDMeasureDictionary | COSDictionary | None
    ) -> None:
        """Set or clear the ``/Measure`` entry. Accepts a typed
        :class:`PDMeasureDictionary` or a raw ``COSDictionary``; ``None``
        removes the entry."""
        if measure is None:
            self._dict.remove_item(_MEASURE)
            return
        self._dict.set_item(
            _MEASURE,
            measure.get_cos_object() if hasattr(measure, "get_cos_object") else measure,
        )

    def remove_measure(self) -> None:
        """Remove the ``/Measure`` entry. Equivalent to ``set_measure(None)``."""
        self._dict.remove_item(_MEASURE)

    def has_measure(self) -> bool:
        """``True`` when ``/Measure`` resolves to a dictionary.

        pypdfbox extension — counterpart of :meth:`has_popup`. Useful for
        callers triaging an annotation tree without materialising the
        typed wrapper.
        """
        return isinstance(self._dict.get_dictionary_object(_MEASURE), COSDictionary)

    # ---------- remove helpers for previously get/set-only entries ----------
    # pypdfbox extension — a deferred follow-up called out ``get/set +
    # remove`` for /Popup. The explicit ``remove_*`` predicates make the
    # intent obvious at call sites that strip review-workflow fields
    # before export (sanitization pipelines, anonymisation, etc.).

    def remove_popup(self) -> None:
        """Remove the ``/Popup`` entry. Equivalent to ``set_popup(None)``."""
        self._dict.remove_item(_POPUP)

    def remove_rich_contents(self) -> None:
        """Remove the ``/RC`` entry. Equivalent to ``set_rich_contents(None)``."""
        self._dict.remove_item(_RC)

    def remove_border_style(self) -> None:
        """Remove the ``/BS`` entry. Equivalent to ``set_border_style(None)``."""
        self._dict.remove_item(_BS)

    def has_border_style(self) -> bool:
        """``True`` when ``/BS`` resolves to a dictionary.

        pypdfbox extension — counterpart of :meth:`has_popup`. Avoids
        materialising :class:`PDBorderStyleDictionary` when the caller
        only needs a presence check.
        """
        return isinstance(self._dict.get_dictionary_object(_BS), COSDictionary)


__all__ = ["PDAnnotationMarkup"]
