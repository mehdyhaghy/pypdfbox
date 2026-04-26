from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_annotation import PDAnnotation

_DA: COSName = COSName.get_pdf_name("DA")
_Q: COSName = COSName.get_pdf_name("Q")
_DS: COSName = COSName.get_pdf_name("DS")
_RC: COSName = COSName.get_pdf_name("RC")
_IT: COSName = COSName.get_pdf_name("IT")


class PDAnnotationFreeText(PDAnnotation):
    """
    FreeText annotation — ``/Subtype /FreeText``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFreeText``.

    A free-text annotation displays text directly on the page rather than
    in a popup (PDF 32000-1:2008 §12.5.6.6). Cluster #5 lite exposes
    ``/DA``, ``/Q``, ``/DS``, ``/RC`` and ``/IT`` — appearance generation
    and the callout-line geometry (``/CL``, ``/LE``) are deferred.
    """

    SUB_TYPE: str = "FreeText"

    # ---------- /Q justification constants (Table 174) ----------

    JUSTIFICATION_LEFT: int = 0
    JUSTIFICATION_CENTER: int = 1
    JUSTIFICATION_RIGHT: int = 2

    # ---------- /IT intent constants (Table 174) ----------

    IT_FREE_TEXT_CALLOUT: str = "FreeTextCallout"
    IT_FREE_TEXT_TYPE_WRITER: str = "FreeTextTypeWriter"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /DA (default appearance string) ----------

    def get_default_appearance(self) -> str | None:
        return self._dict.get_string(_DA)

    def set_default_appearance(self, default_appearance: str | None) -> None:
        self._dict.set_string(_DA, default_appearance)

    # ---------- /Q (quadding / justification) ----------

    def get_q(self) -> int:
        """Default per spec is ``0`` (left-justified)."""
        return self._dict.get_int(_Q, self.JUSTIFICATION_LEFT)

    def set_q(self, q: int) -> None:
        self._dict.set_int(_Q, int(q))

    # ---------- /DS (default style string) ----------

    def get_default_style_string(self) -> str | None:
        return self._dict.get_string(_DS)

    def set_default_style_string(self, default_style_string: str | None) -> None:
        self._dict.set_string(_DS, default_style_string)

    # ---------- /RC (rich-text contents) ----------

    def get_rich_contents(self) -> str | None:
        return self._dict.get_string(_RC)

    def set_rich_contents(self, rich_contents: str | None) -> None:
        self._dict.set_string(_RC, rich_contents)

    # ---------- /IT (intent) ----------

    def get_intent(self) -> str | None:
        return self._dict.get_name(_IT)

    def set_intent(self, intent: str | None) -> None:
        if intent is None:
            self._dict.remove_item(_IT)
            return
        self._dict.set_name(_IT, intent)


__all__ = ["PDAnnotationFreeText"]
