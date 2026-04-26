from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName

from .pd_annotation import PDAnnotation

_A: COSName = COSName.get_pdf_name("A")
_DEST: COSName = COSName.get_pdf_name("Dest")
_H: COSName = COSName.get_pdf_name("H")
_BS: COSName = COSName.get_pdf_name("BS")


class PDAnnotationLink(PDAnnotation):
    """
    Link annotation — ``/Subtype /Link``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink``.

    Either ``/A`` (action) or ``/Dest`` (destination) carries the target —
    not both, per PDF 32000-1:2008 §12.5.6.5. Upstream returns typed
    ``PDAction`` / ``PDDestination`` wrappers; cluster #5 lite returns the
    raw ``COSDictionary`` / ``COSArray`` / ``COSName`` because those typed
    wrappers belong to pdmodel cluster #7 (actions) and the destinations
    cluster. See ``CHANGES.md``.
    """

    SUB_TYPE: str = "Link"

    HIGHLIGHT_MODE_NONE: str = "N"
    HIGHLIGHT_MODE_INVERT: str = "I"  # PDF spec default
    HIGHLIGHT_MODE_OUTLINE: str = "O"
    HIGHLIGHT_MODE_PUSH: str = "P"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /A (action) ----------

    def get_action(self) -> COSDictionary | None:
        """Return the raw action dictionary. Replace with a typed
        ``PDAction`` once pdmodel cluster #7 lands."""
        value = self._dict.get_dictionary_object(_A)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_action(self, action: COSDictionary | None) -> None:
        if action is None:
            self._dict.remove_item(_A)
            return
        self._dict.set_item(_A, action)

    # ---------- /Dest (destination) ----------

    def get_destination(self) -> COSBase | None:
        """Return the raw destination — may be a ``COSArray`` (explicit
        destination), ``COSName`` (named destination), or ``COSString``
        (byte-string named destination). PDDestination wrapper lands with
        the destinations port."""
        value = self._dict.get_dictionary_object(_DEST)
        return value

    def set_destination(self, dest: COSBase | None) -> None:
        if dest is None:
            self._dict.remove_item(_DEST)
            return
        self._dict.set_item(_DEST, dest)

    # ---------- /H (highlight mode) ----------

    def get_highlight_mode(self) -> str:
        """Default per spec is INVERT (``I``)."""
        value = self._dict.get_name(_H)
        return value if value is not None else self.HIGHLIGHT_MODE_INVERT

    def set_highlight_mode(self, mode: str | None) -> None:
        if mode is None:
            self._dict.remove_item(_H)
            return
        self._dict.set_name(_H, mode)

    # ---------- /BS (border style) ----------

    def get_border_style(self) -> COSDictionary | None:
        """Cluster #5 lite stub — returns the raw border style dict.
        ``PDBorderStyleDictionary`` is deferred to a later annotation
        cluster."""
        value = self._dict.get_dictionary_object(_BS)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_border_style(self, bs: COSDictionary | None) -> None:
        if bs is None:
            self._dict.remove_item(_BS)
            return
        self._dict.set_item(_BS, bs)

    # ---------- /QuadPoints — exposed as raw array (deferred typed wrapper) ----------

    def get_quad_points(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(COSName.get_pdf_name("QuadPoints"))
        if isinstance(value, COSArray):
            return value
        return None

    def set_quad_points(self, quad_points: COSArray | None) -> None:
        key = COSName.get_pdf_name("QuadPoints")
        if quad_points is None:
            self._dict.remove_item(key)
            return
        self._dict.set_item(key, quad_points)


__all__ = ["PDAnnotationLink"]
