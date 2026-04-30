from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_annotation import PDAnnotation

if TYPE_CHECKING:
    from .pd_annotation_popup import PDAnnotationPopup

_CREATION_DATE: COSName = COSName.get_pdf_name("CreationDate")
_IRT: COSName = COSName.get_pdf_name("IRT")
_SUBJ: COSName = COSName.get_pdf_name("Subj")
_RT: COSName = COSName.get_pdf_name("RT")
_IT: COSName = COSName.get_pdf_name("IT")
_CA: COSName = COSName.get_pdf_name("CA")
_POPUP: COSName = COSName.get_pdf_name("Popup")
_RC: COSName = COSName.get_pdf_name("RC")
_EX_DATA: COSName = COSName.get_pdf_name("ExData")


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

    def get_reply_type(self) -> str | None:
        return self._dict.get_name(_RT)

    def set_reply_type(self, rt: str | None) -> None:
        if rt is None:
            self._dict.remove_item(_RT)
            return
        self._dict.set_name(_RT, rt)

    # ---------- /IT (intent) ----------

    def get_intent(self) -> str | None:
        return self._dict.get_name(_IT)

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
        """Return the raw rich text stream displayed in the popup window."""
        return self._dict.get_string(_RC)

    def set_rich_contents(self, rc: str | None) -> None:
        self._dict.set_string(_RC, rc)

    # ---------- /ExData (external data) ----------

    def get_external_data(self) -> COSDictionary | None:
        """Return the raw external data dictionary associated with this markup.

        Upstream exposes ``PDExternalDataDictionary``. The typed wrapper is
        deferred here, so callers get the resolved raw ``COSDictionary``.
        """
        value = self._dict.get_dictionary_object(_EX_DATA)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_external_data(self, ex_data: COSDictionary | None) -> None:
        if ex_data is None:
            self._dict.remove_item(_EX_DATA)
            return
        self._dict.set_item(_EX_DATA, ex_data)


__all__ = ["PDAnnotationMarkup"]
