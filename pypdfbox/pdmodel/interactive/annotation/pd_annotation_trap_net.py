from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_annotation import PDAnnotation

_LAST_MODIFIED: COSName = COSName.get_pdf_name("LastModified")
_VERSION: COSName = COSName.get_pdf_name("Version")
_ANNOT_STATES: COSName = COSName.get_pdf_name("AnnotStates")
_FONT_FAUXING: COSName = COSName.get_pdf_name("FontFauxing")


class PDAnnotationTrapNet(PDAnnotation):
    """
    Trap network annotation — ``/Subtype /TrapNet``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationTrapNet``.

    Defines the trapping characteristics for a page (PDF 32000-1:2008
    §12.5.6.21, Table 189). At most one trap network annotation per page;
    when present it must be the last item in the page's ``/Annots`` array.

    Not a markup annotation — extends :class:`PDAnnotation` directly.
    """

    SUB_TYPE: str = "TrapNet"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /LastModified ----------

    def get_last_modified(self) -> str | None:
        """Raw ``/LastModified`` PDF date string."""
        return self._dict.get_string(_LAST_MODIFIED)

    def set_last_modified(self, value: str | None) -> None:
        self._dict.set_string(_LAST_MODIFIED, value)

    # ---------- /Version (array of font names) ----------

    def get_version(self) -> COSArray | None:
        """Return the raw ``/Version`` array describing the version of the
        latest trapping software used (font names + revision integer)."""
        value = self._dict.get_dictionary_object(_VERSION)
        if isinstance(value, COSArray):
            return value
        return None

    def set_version(self, value: COSArray | None) -> None:
        if value is None:
            self._dict.remove_item(_VERSION)
            return
        self._dict.set_item(_VERSION, value)

    # ---------- /AnnotStates ----------

    def get_annot_states(self) -> COSArray | None:
        """Return the ``/AnnotStates`` array — name objects naming the
        appearance states for annotations associated with the trap network."""
        value = self._dict.get_dictionary_object(_ANNOT_STATES)
        if isinstance(value, COSArray):
            return value
        return None

    def set_annot_states(self, value: COSArray | None) -> None:
        if value is None:
            self._dict.remove_item(_ANNOT_STATES)
            return
        self._dict.set_item(_ANNOT_STATES, value)

    # ---------- /FontFauxing ----------

    def get_font_fauxing(self) -> COSArray | None:
        """Return the ``/FontFauxing`` array — list of font dictionaries
        substituted for fonts whose original glyphs cannot be displayed on
        the device."""
        value = self._dict.get_dictionary_object(_FONT_FAUXING)
        if isinstance(value, COSArray):
            return value
        return None

    def set_font_fauxing(self, value: COSArray | None) -> None:
        if value is None:
            self._dict.remove_item(_FONT_FAUXING)
            return
        self._dict.set_item(_FONT_FAUXING, value)


__all__ = ["PDAnnotationTrapNet"]
