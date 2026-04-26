from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream

from .pd_cid_system_info import PDCIDSystemInfo
from .pd_font import PDFont

if TYPE_CHECKING:
    from .pd_type0_font import PDType0Font

_CID_SYSTEM_INFO: COSName = COSName.get_pdf_name("CIDSystemInfo")
_DW: COSName = COSName.get_pdf_name("DW")
_DW2: COSName = COSName.get_pdf_name("DW2")
_W: COSName = COSName.get_pdf_name("W")
_W2: COSName = COSName.get_pdf_name("W2")
_CID_TO_GID_MAP: COSName = COSName.get_pdf_name("CIDToGIDMap")
_IDENTITY: COSName = COSName.get_pdf_name("Identity")


class PDCIDFont(PDFont):
    """Abstract CIDFont wrapper. Mirrors PDFBox ``PDCIDFont``.

    A CIDFont is the descendant of a composite ``PDType0Font``; although its
    ``/Type`` is ``/Font`` it is not directly usable as a font. Concrete
    subclasses (``PDCIDFontType0``, ``PDCIDFontType2``) set ``/Subtype``.

    Lite — width-table parsing, vertical-displacement parsing, and the
    ``PDFontLike`` / ``PDVectorFont`` mixins are deferred. This wrapper
    only exposes the COS-level accessors over the dictionary entries
    enumerated in PDF 32000-1 §9.7.4.
    """

    def __init__(
        self,
        font_dict: COSDictionary | None = None,
        parent_type0_font: PDType0Font | None = None,
    ) -> None:
        super().__init__(font_dict)
        self._parent = parent_type0_font

    # ---------- subtype (abstract) ----------

    def get_subtype(self) -> str | None:  # pragma: no cover - overridden
        raise NotImplementedError("PDCIDFont subclasses must implement get_subtype()")

    # ---------- parent Type0 font ----------

    def get_parent(self) -> PDType0Font | None:
        return self._parent

    # ---------- /CIDSystemInfo ----------

    def get_cid_system_info(self) -> PDCIDSystemInfo | None:
        v = self._dict.get_dictionary_object(_CID_SYSTEM_INFO)
        if isinstance(v, COSDictionary):
            return PDCIDSystemInfo(v)
        return None

    def set_cid_system_info(self, info: PDCIDSystemInfo | None) -> None:
        if info is None:
            self._dict.remove_item(_CID_SYSTEM_INFO)
            return
        self._dict.set_item(_CID_SYSTEM_INFO, info.get_cos_object())

    # ---------- /DW (default width) ----------

    def get_dw(self) -> int:
        return self._dict.get_int(_DW, 1000)

    def set_dw(self, width: int) -> None:
        self._dict.set_int(_DW, int(width))

    # ---------- /DW2 (default vertical metrics) ----------

    def get_dw2(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_DW2)
        if isinstance(v, COSArray):
            return v
        return None

    def set_dw2(self, arr: COSArray | None) -> None:
        if arr is None:
            self._dict.remove_item(_DW2)
            return
        self._dict.set_item(_DW2, arr)

    # ---------- /W (per-CID horizontal widths) ----------

    def get_w(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_W)
        if isinstance(v, COSArray):
            return v
        return None

    def set_w(self, arr: COSArray | None) -> None:
        if arr is None:
            self._dict.remove_item(_W)
            return
        self._dict.set_item(_W, arr)

    # ---------- /W2 (per-CID vertical widths) ----------

    def get_w2(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_W2)
        if isinstance(v, COSArray):
            return v
        return None

    def set_w2(self, arr: COSArray | None) -> None:
        if arr is None:
            self._dict.remove_item(_W2)
            return
        self._dict.set_item(_W2, arr)

    # ---------- /CIDToGIDMap ----------

    def get_cid_to_gid_map(self) -> COSStream | str | None:
        """Return the ``/CIDToGIDMap`` entry.

        Per PDF 32000-1 §9.7.4.2 the value is either a stream of glyph
        indices or the name ``/Identity``. Returns the raw ``COSStream``,
        the name string, or ``None`` when absent.
        """
        v = self._dict.get_dictionary_object(_CID_TO_GID_MAP)
        if isinstance(v, COSStream):
            return v
        if isinstance(v, COSName):
            return v.name
        return None

    def set_cid_to_gid_map(self, value: COSStream | str | None) -> None:
        if value is None:
            self._dict.remove_item(_CID_TO_GID_MAP)
            return
        if isinstance(value, COSStream):
            self._dict.set_item(_CID_TO_GID_MAP, value)
            return
        if isinstance(value, str):
            self._dict.set_name(_CID_TO_GID_MAP, value)
            return
        raise TypeError(
            "set_cid_to_gid_map expects COSStream, str, or None; "
            f"got {type(value).__name__}"
        )


__all__ = ["PDCIDFont"]
