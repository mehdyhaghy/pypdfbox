from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FONT_NAME: COSName = COSName.get_pdf_name("FontName")
_FLAGS: COSName = COSName.get_pdf_name("Flags")
_FONT_BBOX: COSName = COSName.get_pdf_name("FontBBox")
_ASCENT: COSName = COSName.get_pdf_name("Ascent")
_DESCENT: COSName = COSName.get_pdf_name("Descent")
_CAP_HEIGHT: COSName = COSName.get_pdf_name("CapHeight")
_X_HEIGHT: COSName = COSName.get_pdf_name("XHeight")
_ITALIC_ANGLE: COSName = COSName.get_pdf_name("ItalicAngle")
_STEM_V: COSName = COSName.get_pdf_name("StemV")
_FONT_FILE: COSName = COSName.get_pdf_name("FontFile")
_FONT_FILE2: COSName = COSName.get_pdf_name("FontFile2")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")


# Flag bit constants (PDF 32000-1 §9.8.2, Table 123).
FLAG_FIXED_PITCH = 1 << 0  # 1
FLAG_SERIF = 1 << 1  # 2
FLAG_SYMBOLIC = 1 << 2  # 4
FLAG_SCRIPT = 1 << 3  # 8
FLAG_NON_SYMBOLIC = 1 << 5  # 32
FLAG_ITALIC = 1 << 6  # 64
FLAG_ALL_CAP = 1 << 16  # 65536
FLAG_SMALL_CAP = 1 << 17  # 131072
FLAG_FORCE_BOLD = 1 << 18  # 262144


class PDFontDescriptor:
    """PDF font descriptor wrapper. Mirrors PDFBox ``PDFontDescriptor``.

    Lite surface — exposes the metric/flag accessors needed by the font
    cluster scaffold. Lesser-used metrics (Leading, StemH, AvgWidth,
    MaxWidth, MissingWidth, FontFamily, FontStretch, CharSet) are deferred.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()
        if dictionary is None and self._dict.get_dictionary_object(_TYPE) is None:
            self._dict.set_item(_TYPE, _FONT_DESCRIPTOR)

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /FontName ----------

    def get_font_name(self) -> str | None:
        return self._dict.get_name(_FONT_NAME)

    def set_font_name(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_FONT_NAME)
            return
        self._dict.set_name(_FONT_NAME, name)

    # ---------- /Flags ----------

    def get_flags(self) -> int:
        return self._dict.get_int(_FLAGS, 0)

    def set_flags(self, flags: int) -> None:
        self._dict.set_int(_FLAGS, int(flags))

    def _flag(self, mask: int) -> bool:
        return bool(self.get_flags() & mask)

    def _set_flag(self, mask: int, value: bool) -> None:
        flags = self.get_flags()
        flags = (flags | mask) if value else (flags & ~mask)
        self.set_flags(flags)

    def is_fixed_pitch(self) -> bool:
        return self._flag(FLAG_FIXED_PITCH)

    def set_fixed_pitch(self, value: bool) -> None:
        self._set_flag(FLAG_FIXED_PITCH, value)

    def is_italic(self) -> bool:
        return self._flag(FLAG_ITALIC)

    def set_italic(self, value: bool) -> None:
        self._set_flag(FLAG_ITALIC, value)

    # ---------- /FontBBox ----------

    def get_font_b_box(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_FONT_BBOX)
        if isinstance(v, COSArray):
            return v
        return None

    def set_font_b_box(self, bbox: COSArray | None) -> None:
        if bbox is None:
            self._dict.remove_item(_FONT_BBOX)
            return
        self._dict.set_item(_FONT_BBOX, bbox)

    # ---------- numeric metrics ----------

    def get_ascent(self) -> float:
        return self._dict.get_float(_ASCENT, 0.0)

    def set_ascent(self, value: float) -> None:
        self._dict.set_float(_ASCENT, float(value))

    def get_descent(self) -> float:
        return self._dict.get_float(_DESCENT, 0.0)

    def set_descent(self, value: float) -> None:
        self._dict.set_float(_DESCENT, float(value))

    def get_cap_height(self) -> float:
        return self._dict.get_float(_CAP_HEIGHT, 0.0)

    def set_cap_height(self, value: float) -> None:
        self._dict.set_float(_CAP_HEIGHT, float(value))

    def get_x_height(self) -> float:
        return self._dict.get_float(_X_HEIGHT, 0.0)

    def set_x_height(self, value: float) -> None:
        self._dict.set_float(_X_HEIGHT, float(value))

    def get_italic_angle(self) -> float:
        return self._dict.get_float(_ITALIC_ANGLE, 0.0)

    def set_italic_angle(self, value: float) -> None:
        self._dict.set_float(_ITALIC_ANGLE, float(value))

    def get_stem_v(self) -> float:
        return self._dict.get_float(_STEM_V, 0.0)

    def set_stem_v(self, value: float) -> None:
        self._dict.set_float(_STEM_V, float(value))

    # ---------- font program streams ----------

    def get_font_file(self) -> COSStream | None:
        v = self._dict.get_dictionary_object(_FONT_FILE)
        if isinstance(v, COSStream):
            return v
        return None

    def set_font_file(self, stream: COSStream | None) -> None:
        if stream is None:
            self._dict.remove_item(_FONT_FILE)
            return
        self._dict.set_item(_FONT_FILE, stream)

    def get_font_file2(self) -> COSStream | None:
        v = self._dict.get_dictionary_object(_FONT_FILE2)
        if isinstance(v, COSStream):
            return v
        return None

    def set_font_file2(self, stream: COSStream | None) -> None:
        if stream is None:
            self._dict.remove_item(_FONT_FILE2)
            return
        self._dict.set_item(_FONT_FILE2, stream)

    def get_font_file3(self) -> COSStream | None:
        v = self._dict.get_dictionary_object(_FONT_FILE3)
        if isinstance(v, COSStream):
            return v
        return None

    def set_font_file3(self, stream: COSStream | None) -> None:
        if stream is None:
            self._dict.remove_item(_FONT_FILE3)
            return
        self._dict.set_item(_FONT_FILE3, stream)


__all__ = [
    "FLAG_ALL_CAP",
    "FLAG_FIXED_PITCH",
    "FLAG_FORCE_BOLD",
    "FLAG_ITALIC",
    "FLAG_NON_SYMBOLIC",
    "FLAG_SCRIPT",
    "FLAG_SERIF",
    "FLAG_SMALL_CAP",
    "FLAG_SYMBOLIC",
    "PDFontDescriptor",
]
