from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_annotation import PDAnnotation

_CREATION_DATE: COSName = COSName.get_pdf_name("CreationDate")
_IRT: COSName = COSName.get_pdf_name("IRT")
_SUBJ: COSName = COSName.get_pdf_name("Subj")
_RT: COSName = COSName.get_pdf_name("RT")
_IT: COSName = COSName.get_pdf_name("IT")
_CA: COSName = COSName.get_pdf_name("CA")


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

    Lite scope: ``/Popup`` and ``/RC`` accessors are deferred (popup
    annotations and rich-text streams require additional wrappers); see
    ``CHANGES.md``.
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


__all__ = ["PDAnnotationMarkup"]
