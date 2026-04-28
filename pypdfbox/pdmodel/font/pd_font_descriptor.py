from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FONT_NAME: COSName = COSName.get_pdf_name("FontName")
_FONT_FAMILY: COSName = COSName.get_pdf_name("FontFamily")
_FONT_STRETCH: COSName = COSName.get_pdf_name("FontStretch")
_FONT_WEIGHT: COSName = COSName.get_pdf_name("FontWeight")
_FLAGS: COSName = COSName.get_pdf_name("Flags")
_FONT_BBOX: COSName = COSName.get_pdf_name("FontBBox")
_ASCENT: COSName = COSName.get_pdf_name("Ascent")
_DESCENT: COSName = COSName.get_pdf_name("Descent")
_CAP_HEIGHT: COSName = COSName.get_pdf_name("CapHeight")
_X_HEIGHT: COSName = COSName.get_pdf_name("XHeight")
_ITALIC_ANGLE: COSName = COSName.get_pdf_name("ItalicAngle")
_STEM_V: COSName = COSName.get_pdf_name("StemV")
_STEM_H: COSName = COSName.get_pdf_name("StemH")
_AVG_WIDTH: COSName = COSName.get_pdf_name("AvgWidth")
_MAX_WIDTH: COSName = COSName.get_pdf_name("MaxWidth")
_MISSING_WIDTH: COSName = COSName.get_pdf_name("MissingWidth")
_LEADING: COSName = COSName.get_pdf_name("Leading")
_FONT_FILE: COSName = COSName.get_pdf_name("FontFile")
_FONT_FILE2: COSName = COSName.get_pdf_name("FontFile2")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")
_CHAR_SET: COSName = COSName.get_pdf_name("CharSet")
_CID_SET: COSName = COSName.get_pdf_name("CIDSet")
_WIDTHS: COSName = COSName.get_pdf_name("Widths")
_STYLE: COSName = COSName.get_pdf_name("Style")
_PANOSE: COSName = COSName.get_pdf_name("Panose")
_LANG: COSName = COSName.get_pdf_name("Lang")


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

    Exposes metric/flag accessors plus typed access to the embedded font
    program streams (``/FontFile``, ``/FontFile2``, ``/FontFile3``) and
    descriptive entries (``/FontFamily``, ``/FontStretch``, ``/FontWeight``,
    ``/CharSet``).
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

    def get_flag(self, bit: int) -> bool:
        """Return the value of an individual flag bit (1-based, per Table 123)."""
        return self._flag(1 << (int(bit) - 1))

    def set_flag(self, bit: int, value: bool) -> None:
        """Set the value of an individual flag bit (1-based, per Table 123)."""
        self._set_flag(1 << (int(bit) - 1), value)

    def is_fixed_pitch(self) -> bool:
        return self._flag(FLAG_FIXED_PITCH)

    def set_fixed_pitch(self, value: bool) -> None:
        self._set_flag(FLAG_FIXED_PITCH, value)

    def is_serif(self) -> bool:
        return self._flag(FLAG_SERIF)

    def set_serif(self, value: bool) -> None:
        self._set_flag(FLAG_SERIF, value)

    def is_symbolic(self) -> bool:
        return self._flag(FLAG_SYMBOLIC)

    def set_symbolic(self, value: bool) -> None:
        self._set_flag(FLAG_SYMBOLIC, value)

    def is_script(self) -> bool:
        return self._flag(FLAG_SCRIPT)

    def set_script(self, value: bool) -> None:
        self._set_flag(FLAG_SCRIPT, value)

    def is_non_symbolic(self) -> bool:
        return self._flag(FLAG_NON_SYMBOLIC)

    def set_non_symbolic(self, value: bool) -> None:
        self._set_flag(FLAG_NON_SYMBOLIC, value)

    def is_italic(self) -> bool:
        return self._flag(FLAG_ITALIC)

    def set_italic(self, value: bool) -> None:
        self._set_flag(FLAG_ITALIC, value)

    def is_all_cap(self) -> bool:
        return self._flag(FLAG_ALL_CAP)

    def set_all_cap(self, value: bool) -> None:
        self._set_flag(FLAG_ALL_CAP, value)

    def is_small_cap(self) -> bool:
        return self._flag(FLAG_SMALL_CAP)

    def set_small_cap(self, value: bool) -> None:
        self._set_flag(FLAG_SMALL_CAP, value)

    def is_force_bold(self) -> bool:
        return self._flag(FLAG_FORCE_BOLD)

    def set_force_bold(self, value: bool) -> None:
        self._set_flag(FLAG_FORCE_BOLD, value)

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

    def get_font_bounding_box(self) -> PDRectangle | None:
        """Typed accessor mirroring upstream ``getFontBoundingBox()``."""
        v = self._dict.get_dictionary_object(_FONT_BBOX)
        if isinstance(v, COSArray) and len(v) >= 4:
            return PDRectangle.from_cos_array(v)
        return None

    def set_font_bounding_box(self, rect: PDRectangle | None) -> None:
        """Typed setter mirroring upstream ``setFontBoundingBox(PDRectangle)``."""
        if rect is None:
            self._dict.remove_item(_FONT_BBOX)
            return
        self._dict.set_item(_FONT_BBOX, rect.get_cos_array())

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
        # PDFBOX-429: Scheherazade font ships a negative CapHeight; upstream
        # returns the absolute value as a workaround. Match that behavior.
        return abs(self._dict.get_float(_CAP_HEIGHT, 0.0))

    def set_cap_height(self, value: float) -> None:
        self._dict.set_float(_CAP_HEIGHT, float(value))

    def get_x_height(self) -> float:
        # PDFBOX-429: see ``get_cap_height``.
        return abs(self._dict.get_float(_X_HEIGHT, 0.0))

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

    def get_stem_h(self) -> float:
        return self._dict.get_float(_STEM_H, 0.0)

    def set_stem_h(self, value: float) -> None:
        self._dict.set_float(_STEM_H, float(value))

    def get_avg_width(self) -> float:
        return self._dict.get_float(_AVG_WIDTH, 0.0)

    def set_avg_width(self, value: float) -> None:
        self._dict.set_float(_AVG_WIDTH, float(value))

    def get_average_width(self) -> float:
        """Upstream-named alias for ``get_avg_width``."""
        return self.get_avg_width()

    def set_average_width(self, value: float) -> None:
        """Upstream-named alias for ``set_avg_width``."""
        self.set_avg_width(value)

    def get_max_width(self) -> float:
        return self._dict.get_float(_MAX_WIDTH, 0.0)

    def set_max_width(self, value: float) -> None:
        self._dict.set_float(_MAX_WIDTH, float(value))

    def has_widths(self) -> bool:
        """Mirrors upstream ``hasWidths()``: true if /Widths or /MissingWidth is set."""
        return self._dict.contains_key(_WIDTHS) or self._dict.contains_key(_MISSING_WIDTH)

    def has_missing_width(self) -> bool:
        """Mirrors upstream ``hasMissingWidth()``: true if /MissingWidth is set."""
        return self._dict.contains_key(_MISSING_WIDTH)

    def get_missing_width(self) -> float:
        return self._dict.get_float(_MISSING_WIDTH, 0.0)

    def set_missing_width(self, value: float) -> None:
        self._dict.set_float(_MISSING_WIDTH, float(value))

    def get_leading(self) -> float:
        return self._dict.get_float(_LEADING, 0.0)

    def set_leading(self, value: float) -> None:
        self._dict.set_float(_LEADING, float(value))

    # ---------- /FontFamily, /FontStretch, /FontWeight ----------

    def get_font_family(self) -> str | None:
        return self._dict.get_string(_FONT_FAMILY)

    def set_font_family(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_FONT_FAMILY)
            return
        self._dict.set_string(_FONT_FAMILY, value)

    def get_font_stretch(self) -> str | None:
        return self._dict.get_name(_FONT_STRETCH)

    def set_font_stretch(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_FONT_STRETCH)
            return
        self._dict.set_name(_FONT_STRETCH, value)

    def get_font_weight(self) -> float:
        return self._dict.get_float(_FONT_WEIGHT, 0.0)

    def set_font_weight(self, value: float) -> None:
        self._dict.set_float(_FONT_WEIGHT, float(value))

    # ---------- /CharSet ----------

    def get_char_set(self) -> str | None:
        return self._dict.get_string(_CHAR_SET)

    def set_char_set(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_CHAR_SET)
            return
        self._dict.set_string(_CHAR_SET, value)

    def set_character_set(self, value: str | None) -> None:
        """Upstream-named alias for ``set_char_set`` (matches ``setCharacterSet``)."""
        self.set_char_set(value)

    # ---------- font program streams ----------

    def _get_font_file(self, key: COSName) -> PDStream | None:
        v = self._dict.get_dictionary_object(key)
        if isinstance(v, COSStream):
            return PDStream(v)
        return None

    def _set_font_file(self, key: COSName, stream: PDStream | COSStream | None) -> None:
        if stream is None:
            self._dict.remove_item(key)
            return
        if isinstance(stream, PDStream):
            self._dict.set_item(key, stream.get_cos_object())
        else:
            self._dict.set_item(key, stream)

    def get_font_file(self) -> PDStream | None:
        return self._get_font_file(_FONT_FILE)

    def set_font_file(self, stream: PDStream | COSStream | None) -> None:
        self._set_font_file(_FONT_FILE, stream)

    def get_font_file2(self) -> PDStream | None:
        return self._get_font_file(_FONT_FILE2)

    def set_font_file2(self, stream: PDStream | COSStream | None) -> None:
        self._set_font_file(_FONT_FILE2, stream)

    def get_font_file3(self) -> PDStream | None:
        return self._get_font_file(_FONT_FILE3)

    def set_font_file3(self, stream: PDStream | COSStream | None) -> None:
        self._set_font_file(_FONT_FILE3, stream)

    # ---------- /CIDSet ----------

    def get_cid_set(self) -> PDStream | None:
        """A stream containing the CIDSet (CID-keyed fonts only).

        Mirrors upstream ``PDFontDescriptor.getCIDSet()``.
        """
        return self._get_font_file(_CID_SET)

    def set_cid_set(self, stream: PDStream | COSStream | None) -> None:
        """Mirrors upstream ``PDFontDescriptor.setCIDSet(PDStream)``."""
        self._set_font_file(_CID_SET, stream)

    # ---------- /Style /Panose ----------

    def get_panose(self) -> PDPanose | None:
        """Returns the Panose entry of the Style dictionary, if any.

        Mirrors upstream ``PDFontDescriptor.getPanose()``. The Panose entry is
        a 12-byte string: bytes 0-1 are the TrueType ``sFamilyClass`` and
        bytes 2-11 are the 10-byte PANOSE classification.
        """
        v = self._dict.get_dictionary_object(_STYLE)
        if not isinstance(v, COSDictionary):
            return None
        panose = v.get_dictionary_object(_PANOSE)
        # Upstream casts directly to COSString; accept that exact shape.
        try:
            from pypdfbox.cos import COSString
        except ImportError:  # pragma: no cover - circular safety
            return None
        if not isinstance(panose, COSString):
            return None
        data = panose.get_bytes()
        if len(data) >= PDPanose.LENGTH:
            return PDPanose(data)
        return None

    # ---------- /Lang (PDF 32000-1 Table 122) ----------
    # Note: upstream PDFBox 3.0 PDFontDescriptor does NOT expose these — they
    # are PDF-spec-mandated entries we surface for completeness. Recorded in
    # CHANGES.md as a deliberate pypdfbox extension.

    def get_lang(self) -> str | None:
        """Language identifier (BCP 47 string) for the glyphs in this font."""
        return self._dict.get_name(_LANG)

    def set_lang(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_LANG)
            return
        self._dict.set_name(_LANG, value)


class PDPanoseClassification:
    """10-byte PANOSE classification block.

    Mirrors ``org.apache.pdfbox.pdmodel.font.PDPanoseClassification``. The
    PANOSE classification number is documented at
    https://monotype.de/services/pan2 and at
    https://www.microsoft.com/typography/otspec/os2.htm#pan.
    """

    LENGTH: int = 10

    __slots__ = ("_bytes",)

    def __init__(self, data: bytes | bytearray) -> None:
        # Upstream stores the byte array verbatim — no length validation in
        # the constructor. Match that for behavioral parity (callers may
        # reasonably pass 10 bytes; PDFontDescriptor.get_panose() guards the
        # length before constructing this object).
        self._bytes = bytes(data)

    def get_bytes(self) -> bytes:
        return self._bytes

    def get_family_kind(self) -> int:
        return self._bytes[0]

    def get_serif_style(self) -> int:
        return self._bytes[1]

    def get_weight(self) -> int:
        return self._bytes[2]

    def get_proportion(self) -> int:
        return self._bytes[3]

    def get_contrast(self) -> int:
        return self._bytes[4]

    def get_stroke_variation(self) -> int:
        return self._bytes[5]

    def get_arm_style(self) -> int:
        return self._bytes[6]

    def get_letterform(self) -> int:
        return self._bytes[7]

    def get_midline(self) -> int:
        return self._bytes[8]

    def get_x_height(self) -> int:
        return self._bytes[9]

    def __str__(self) -> str:
        return (
            "{ FamilyKind = "
            + str(self.get_family_kind())
            + ", SerifStyle = "
            + str(self.get_serif_style())
            + ", Weight = "
            + str(self.get_weight())
            + ", Proportion = "
            + str(self.get_proportion())
            + ", Contrast = "
            + str(self.get_contrast())
            + ", StrokeVariation = "
            + str(self.get_stroke_variation())
            + ", ArmStyle = "
            + str(self.get_arm_style())
            + ", Letterform = "
            + str(self.get_letterform())
            + ", Midline = "
            + str(self.get_midline())
            + ", XHeight = "
            + str(self.get_x_height())
            + "}"
        )


class PDPanose:
    """The 12-byte Panose entry of a FontDescriptor's /Style dictionary.

    Mirrors ``org.apache.pdfbox.pdmodel.font.PDPanose``. The first two bytes
    hold the TrueType ``sFamilyClass`` value (signed 16-bit big-endian); the
    remaining 10 bytes are the PANOSE classification number, exposed via
    :class:`PDPanoseClassification`.
    """

    LENGTH: int = 12

    __slots__ = ("_bytes",)

    def __init__(self, data: bytes | bytearray) -> None:
        # Upstream stores the array directly without length checks. Mirror
        # that — accept any length the caller hands in and let the per-byte
        # accessors raise IndexError if the buffer is short.
        self._bytes = bytes(data)

    def get_bytes(self) -> bytes:
        """The raw 12-byte block (sFamilyClass + 10-byte PANOSE)."""
        return self._bytes

    def get_family_class(self) -> int:
        """The TrueType ``sFamilyClass`` value (signed 16-bit big-endian).

        Bytes 0-1 of the Panose block. Mirrors upstream
        ``PDPanose.getFamilyClass()`` which returns ``bytes[0] << 8 | bytes[1]``
        — a *signed* value because Java's ``byte`` is signed. We replicate
        that signedness so round-trips with PDFBox match exactly.
        """
        # Java does (bytes[0] << 8) | (bytes[1] & 0xff) where bytes[0] is a
        # signed byte. Replicate by interpreting bytes[0] as int8.
        high = self._bytes[0]
        if high >= 0x80:
            high -= 0x100
        return (high << 8) | (self._bytes[1] & 0xFF)

    def get_panose(self) -> PDPanoseClassification:
        """The 10-byte PANOSE classification (bytes 2-11)."""
        return PDPanoseClassification(self._bytes[2:12])


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
    "PDPanose",
    "PDPanoseClassification",
]
