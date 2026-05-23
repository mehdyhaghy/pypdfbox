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

    # Class-level mirrors of the module-level FLAG_* masks. Upstream
    # PDFontDescriptor.java declares them as ``private static final int``;
    # exposing them on the class lets callers write
    # ``PDFontDescriptor.FLAG_FORCE_BOLD`` to mirror the Java
    # ``PDFontDescriptor.FLAG_FORCE_BOLD`` reference shape after porting.
    FLAG_FIXED_PITCH: int = FLAG_FIXED_PITCH
    FLAG_SERIF: int = FLAG_SERIF
    FLAG_SYMBOLIC: int = FLAG_SYMBOLIC
    FLAG_SCRIPT: int = FLAG_SCRIPT
    FLAG_NON_SYMBOLIC: int = FLAG_NON_SYMBOLIC
    FLAG_ITALIC: int = FLAG_ITALIC
    FLAG_ALL_CAP: int = FLAG_ALL_CAP
    FLAG_SMALL_CAP: int = FLAG_SMALL_CAP
    FLAG_FORCE_BOLD: int = FLAG_FORCE_BOLD

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()
        if dictionary is None and self._dict.get_dictionary_object(_TYPE) is None:
            self._dict.set_item(_TYPE, _FONT_DESCRIPTOR)

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /FontName ----------

    def get_font_name(self) -> str | None:
        # Upstream uses ``dic.getNameAsString(FONT_NAME)`` which tolerates a
        # /FontName stored as a COSString (some non-conformant writers do
        # this) in addition to the spec-mandated COSName form. ``get_string``
        # implements the same fallback.
        return self._dict.get_string(_FONT_NAME)

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

    def clear_flags(self) -> None:
        """Reset /Flags to zero.

        pypdfbox extension — equivalent to ``set_flags(0)`` but communicates
        intent more clearly when callers want to drop every classification
        bit before re-applying a known set (e.g. swapping a symbolic font
        descriptor for a non-symbolic one).
        """
        self.set_flags(0)

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

    def is_flag_bit_on(self, mask: int) -> bool:
        """Return whether the supplied flag *mask* is set in /Flags.

        Mask-based counterpart of :meth:`get_flag` (which takes a 1-based
        index). Mirrors upstream's private ``isFlagBitOn(int bit)`` — exposed
        publicly here because the ``FLAG_*`` masks are part of the public
        Python surface.
        """
        return self._flag(int(mask))

    def set_flag_bit(self, mask: int, value: bool) -> None:
        """Set or clear the supplied flag *mask* in /Flags.

        Mask-based counterpart of :meth:`set_flag`. Mirrors upstream's
        private ``setFlagBit(int bit, boolean value)``.
        """
        self._set_flag(int(mask), value)

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

    def has_font_bounding_box(self) -> bool:
        """True if /FontBBox is present (regardless of array shape).

        pypdfbox extension — mirrors the ``has_*`` predicate pattern used
        by :meth:`has_font_file`. Returns ``True`` even when /FontBBox is
        a malformed (e.g. short) array, because the entry exists; the
        typed accessor :meth:`get_font_bounding_box` is what enforces the
        4-element shape.
        """
        return self._dict.contains_key(_FONT_BBOX)

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
        # Upstream uses ``dic.getNameAsString(FONT_STRETCH)`` — tolerate a
        # /FontStretch stored as a COSString as well as the spec-mandated
        # COSName form.
        return self._dict.get_string(_FONT_STRETCH)

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

    def has_font_file(self) -> bool:
        """True if /FontFile (Type 1 program) is present.

        pypdfbox extension — upstream callers read ``getFontFile()`` and
        null-check. The predicate avoids materializing a :class:`PDStream`
        wrapper when the caller only needs presence.
        """
        return self._dict.contains_key(_FONT_FILE)

    def has_font_file2(self) -> bool:
        """True if /FontFile2 (TrueType program) is present."""
        return self._dict.contains_key(_FONT_FILE2)

    def has_font_file3(self) -> bool:
        """True if /FontFile3 (CFF / OpenType program) is present."""
        return self._dict.contains_key(_FONT_FILE3)

    def is_embedded(self) -> bool:
        """True if *any* font program stream is present.

        pypdfbox extension — collapses the three ``has_font_file*`` checks
        into a single predicate. Useful for callers that only care whether
        the font is embedded at all (e.g. for PDF/A conformance) and do
        not need to distinguish Type 1 / TrueType / CFF.
        """
        return (
            self._dict.contains_key(_FONT_FILE)
            or self._dict.contains_key(_FONT_FILE2)
            or self._dict.contains_key(_FONT_FILE3)
        )

    # ---------- /CIDSet ----------

    def get_cid_set(self) -> PDStream | None:
        """A stream containing the CIDSet (CID-keyed fonts only).

        Mirrors upstream ``PDFontDescriptor.getCIDSet()``.
        """
        return self._get_font_file(_CID_SET)

    def set_cid_set(self, stream: PDStream | COSStream | None) -> None:
        """Mirrors upstream ``PDFontDescriptor.setCIDSet(PDStream)``."""
        self._set_font_file(_CID_SET, stream)

    def has_cid_set(self) -> bool:
        """True if the /CIDSet stream is present.

        pypdfbox extension — counterpart of :meth:`has_font_file` for the
        /CIDSet entry. Avoids materializing a :class:`PDStream` wrapper
        when the caller only needs presence (e.g. while validating
        CID-keyed font conformance).
        """
        return self._dict.contains_key(_CID_SET)

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

    def has_panose(self) -> bool:
        """True if a /Style/Panose entry is present (any byte length).

        pypdfbox extension — :meth:`get_panose` is strict about the
        12-byte length (returns ``None`` for short buffers) which makes
        it unsuitable as a presence check. ``has_panose`` reports the
        raw key existence so callers can distinguish "absent" from
        "present-but-malformed".
        """
        v = self._dict.get_dictionary_object(_STYLE)
        if not isinstance(v, COSDictionary):
            return False
        return v.contains_key(_PANOSE)

    def set_panose(self, panose: PDPanose | bytes | bytearray | None) -> None:
        """Write the /Style/Panose entry (creating the /Style dict on demand).

        pypdfbox extension — upstream PDFBox 3.0 ``PDFontDescriptor`` exposes
        only the read side (:meth:`get_panose`). Accepts either a
        :class:`PDPanose` wrapper or a raw 12-byte buffer. Passing ``None``
        removes the /Panose entry; if /Style becomes empty afterwards the
        /Style dict is removed too.
        """
        try:
            from pypdfbox.cos import COSString
        except ImportError:  # pragma: no cover - circular safety
            return
        existing = self._dict.get_dictionary_object(_STYLE)
        style = existing if isinstance(existing, COSDictionary) else None
        if panose is None:
            if style is None:
                return
            style.remove_item(_PANOSE)
            if len(style) == 0:
                self._dict.remove_item(_STYLE)
            return
        data = panose.get_bytes() if isinstance(panose, PDPanose) else bytes(panose)
        if style is None:
            style = COSDictionary()
            self._dict.set_item(_STYLE, style)
        style.set_item(_PANOSE, COSString(data))

    def get_font_family_class(self) -> int | None:
        """Return the PANOSE family-kind byte (byte 0 of the 10-byte
        PANOSE block under ``/Style/Panose``), or ``None`` when no
        PANOSE entry is present.

        pypdfbox extension. Distinct from :meth:`get_font_family`
        (which returns the ``/FontFamily`` *string* on the descriptor —
        the PDF 32000-1 §9.8.2 Table 122 ``preferred font family
        name``). Both accessors are spec-defined but reference
        different metadata: the string is human-readable typeface
        family (e.g. ``"Times"``), the integer is the OS/2 PANOSE
        family-kind classifier (e.g.
        :attr:`PDPanoseClassification.FAMILY_KIND_LATIN_TEXT`).
        Returning ``int`` instead of going through the
        :class:`PDPanoseClassification` wrapper lets callers branch on
        family kind without paying for the 12-byte slice + 10-byte
        copy.
        """
        panose = self.get_panose()
        if panose is None:
            return None
        return panose.get_panose().get_family_kind()

    def is_panose_symbolic_consistent(self) -> bool | None:
        """Return whether the PANOSE family-kind classifier agrees with
        the ``/Flags`` SYMBOLIC / NON-SYMBOLIC bit pair.

        pypdfbox extension. The PDF 32000-1 §9.8.2 Table 123 SYMBOLIC
        flag and the OS/2 PANOSE family-kind byte are independent
        metadata sources for the same property; well-formed font
        descriptors agree on the classification. This helper returns
        ``True`` when both sources say "symbolic" or both say
        "non-symbolic", ``False`` when they disagree, and ``None``
        when no PANOSE entry is present (consistency cannot be
        evaluated). A descriptor is considered SYMBOLIC by PANOSE
        when ``family_kind ==`` :attr:`PDPanoseClassification.FAMILY_KIND_LATIN_SYMBOL`,
        and NON-SYMBOLIC for the Latin Text / Hand Written /
        Decorative families; the universal :attr:`FAMILY_KIND_ANY` /
        :attr:`FAMILY_KIND_NO_FIT` values are unclassified and treated
        as agreeing with whatever ``/Flags`` says.
        """
        family_class = self.get_font_family_class()
        if family_class is None:
            return None
        # FAMILY_KIND_ANY / FAMILY_KIND_NO_FIT carry no opinion — defer
        # to /Flags by reporting "consistent".
        if family_class in (
            PDPanoseClassification.FAMILY_KIND_ANY,
            PDPanoseClassification.FAMILY_KIND_NO_FIT,
        ):
            return True
        panose_says_symbolic = (
            family_class == PDPanoseClassification.FAMILY_KIND_LATIN_SYMBOL
        )
        flags_say_symbolic = self.is_symbolic()
        return panose_says_symbolic == flags_say_symbolic

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

    # ---------- /Type ----------

    def get_type(self) -> str | None:
        """Return the ``/Type`` entry as a string (typically "FontDescriptor").

        pypdfbox extension — upstream relies on the package-private
        constructor to write ``COSName.FONT_DESC`` and never re-reads it.
        Wrappers built from a hand-rolled :class:`COSDictionary` may omit
        the ``/Type`` entry entirely; this accessor surfaces that fact
        (returns ``None``) so callers performing Table 122 conformance
        checks can distinguish "missing" from "malformed".
        """
        return self._dict.get_name(_TYPE)

    def set_type(self, value: str | None = "FontDescriptor") -> None:
        """Write the ``/Type`` entry (defaults to ``"FontDescriptor"``).

        pypdfbox extension — symmetric with :meth:`get_type`. Passing
        ``None`` removes the ``/Type`` entry entirely; the default
        argument writes the spec-mandated value so callers can repair a
        descriptor that lost its ``/Type`` during a hand-rolled parse.
        """
        if value is None:
            self._dict.remove_item(_TYPE)
            return
        self._dict.set_name(_TYPE, value)

    # ---------- identity / containers ----------

    def __eq__(self, other: object) -> bool:
        """Two ``PDFontDescriptor`` wrappers compare equal iff they wrap
        the *same* underlying :class:`COSDictionary` instance.

        pypdfbox extension — mirrors :meth:`PDFont.__eq__` (Java-style
        reference identity). Two distinct dicts with identical contents
        are *not* equal because subsequent mutation could diverge them.
        """
        return (
            isinstance(other, PDFontDescriptor) and other.get_cos_object() is self._dict
        )

    def __hash__(self) -> int:
        """Hash by the underlying ``COSDictionary``'s identity. Matches
        :meth:`__eq__` so ``PDFontDescriptor`` is usable as a dict key.
        """
        return id(self._dict)

    def __contains__(self, key: object) -> bool:
        """Pythonic key-existence check on the underlying dictionary.

        pypdfbox extension — lets callers write ``"FontFile2" in fd`` or
        ``COSName.get_pdf_name("CIDSet") in fd`` instead of reaching
        through ``fd.get_cos_object().contains_key(...)``. Accepts the
        same key types as :meth:`COSDictionary.__contains__`.
        """
        return key in self._dict

    # ---------- debug ----------

    def __repr__(self) -> str:
        """Human-readable summary surfacing the font name and flags.

        pypdfbox extension — upstream PDFontDescriptor inherits Java's
        default ``toString``. The summary is purely diagnostic and is not
        intended to round-trip through the parser.
        """
        name = self.get_font_name()
        return f"PDFontDescriptor(font_name={name!r}, flags={self.get_flags()})"


class PDPanoseClassification:
    """10-byte PANOSE classification block.

    Mirrors ``org.apache.pdfbox.pdmodel.font.PDPanoseClassification``. The
    PANOSE classification number is documented at
    https://monotype.de/services/pan2 and at
    https://www.microsoft.com/typography/otspec/os2.htm#pan.
    """

    LENGTH: int = 10

    # Family-kind values per Microsoft OS/2 PANOSE specification — the
    # first byte of the classification picks one of these six broad
    # script families. Surfaced as named constants so callers can branch
    # on family kind without having to spell the magic numbers literally.
    # pypdfbox extension — upstream defines neither the values nor any
    # named constants on PDPanoseClassification; the same magic numbers
    # are used in raw form by FontMapperImpl when scoring substitution
    # candidates (see family-kind comparisons there).
    FAMILY_KIND_ANY: int = 0
    FAMILY_KIND_NO_FIT: int = 1
    FAMILY_KIND_LATIN_TEXT: int = 2
    FAMILY_KIND_LATIN_HAND_WRITTEN: int = 3
    FAMILY_KIND_LATIN_DECORATIVE: int = 4
    FAMILY_KIND_LATIN_SYMBOL: int = 5

    # Per-byte sub-classification constants (PANOSE 2.0 — Microsoft OS/2
    # specification). Only ``Any`` (0) and ``No Fit`` (1) are universal
    # across every category; the named buckets beyond that are specific to
    # the Latin Text family kind, which is the only one whose
    # sub-classification is enumerated in PDF descriptors in practice.
    # pypdfbox extension — upstream PDFBox exposes none of these as named
    # constants. Surfaced so callers branching on PANOSE bytes can use the
    # spec terminology instead of magic numbers (see ``debugger/flagbitspane/
    # panose_flag.py`` for the labels these values render to).
    ANY: int = 0
    NO_FIT: int = 1

    # ---- Byte 1: Serif Style (Latin Text family) ----
    SERIF_STYLE_COVE: int = 2
    SERIF_STYLE_OBTUSE_COVE: int = 3
    SERIF_STYLE_SQUARE_COVE: int = 4
    SERIF_STYLE_OBTUSE_SQUARE_COVE: int = 5
    SERIF_STYLE_SQUARE: int = 6
    SERIF_STYLE_THIN: int = 7
    SERIF_STYLE_BONE: int = 8
    SERIF_STYLE_EXAGGERATED: int = 9
    SERIF_STYLE_TRIANGLE: int = 10
    SERIF_STYLE_NORMAL_SANS: int = 11
    SERIF_STYLE_OBTUSE_SANS: int = 12
    SERIF_STYLE_PERP_SANS: int = 13
    SERIF_STYLE_FLARED: int = 14
    SERIF_STYLE_ROUNDED: int = 15

    # ---- Byte 2: Weight ----
    WEIGHT_VERY_LIGHT: int = 2
    WEIGHT_LIGHT: int = 3
    WEIGHT_THIN: int = 4
    WEIGHT_BOOK: int = 5
    WEIGHT_MEDIUM: int = 6
    WEIGHT_DEMI: int = 7
    WEIGHT_BOLD: int = 8
    WEIGHT_HEAVY: int = 9
    WEIGHT_BLACK: int = 10
    WEIGHT_NORD: int = 11

    # ---- Byte 3: Proportion ----
    PROPORTION_OLD_STYLE: int = 2
    PROPORTION_MODERN: int = 3
    PROPORTION_EVEN_WIDTH: int = 4
    PROPORTION_EXPANDED: int = 5
    PROPORTION_CONDENSED: int = 6
    PROPORTION_USUAL_WIDTH: int = 7
    PROPORTION_VERY_EXPANDED: int = 8
    PROPORTION_VERY_CONDENSED: int = 9
    PROPORTION_MONOSPACED: int = 10

    # ---- Byte 4: Contrast ----
    CONTRAST_NONE: int = 2
    CONTRAST_VERY_LOW: int = 3
    CONTRAST_LOW: int = 4
    CONTRAST_MEDIUM_LOW: int = 5
    CONTRAST_MEDIUM: int = 6
    CONTRAST_MEDIUM_HIGH: int = 7
    CONTRAST_HIGH: int = 8
    CONTRAST_VERY_HIGH: int = 9

    # ---- Byte 5: Stroke Variation ----
    STROKE_VARIATION_NO_VARIATION: int = 2
    STROKE_VARIATION_GRADUAL_DIAGONAL: int = 3
    STROKE_VARIATION_GRADUAL_TRANSITIONAL: int = 4
    STROKE_VARIATION_GRADUAL_VERTICAL: int = 5
    STROKE_VARIATION_GRADUAL_HORIZONTAL: int = 6
    STROKE_VARIATION_RAPID_VERTICAL: int = 7
    STROKE_VARIATION_RAPID_HORIZONTAL: int = 8
    STROKE_VARIATION_INSTANT_VERTICAL: int = 9
    STROKE_VARIATION_INSTANT_HORIZONTAL: int = 10

    # ---- Byte 6: Arm Style ----
    ARM_STYLE_STRAIGHT_ARMS_HORZ: int = 2
    ARM_STYLE_STRAIGHT_ARMS_WEDGE: int = 3
    ARM_STYLE_STRAIGHT_ARMS_VERT: int = 4
    ARM_STYLE_STRAIGHT_ARMS_SINGLE_SERIF: int = 5
    ARM_STYLE_STRAIGHT_ARMS_DOUBLE_SERIF: int = 6
    ARM_STYLE_NON_STRAIGHT_ARMS_HORZ: int = 7
    ARM_STYLE_NON_STRAIGHT_ARMS_WEDGE: int = 8
    ARM_STYLE_NON_STRAIGHT_ARMS_VERT: int = 9
    ARM_STYLE_NON_STRAIGHT_ARMS_SINGLE_SERIF: int = 10
    ARM_STYLE_NON_STRAIGHT_ARMS_DOUBLE_SERIF: int = 11

    # ---- Byte 7: Letterform ----
    LETTERFORM_NORMAL_CONTACT: int = 2
    LETTERFORM_NORMAL_WEIGHTED: int = 3
    LETTERFORM_NORMAL_BOXED: int = 4
    LETTERFORM_NORMAL_FLATTENED: int = 5
    LETTERFORM_NORMAL_ROUNDED: int = 6
    LETTERFORM_NORMAL_OFF_CENTER: int = 7
    LETTERFORM_NORMAL_SQUARE: int = 8
    LETTERFORM_OBLIQUE_CONTACT: int = 9
    LETTERFORM_OBLIQUE_WEIGHTED: int = 10
    LETTERFORM_OBLIQUE_BOXED: int = 11
    LETTERFORM_OBLIQUE_FLATTENED: int = 12
    LETTERFORM_OBLIQUE_ROUNDED: int = 13
    LETTERFORM_OBLIQUE_OFF_CENTER: int = 14
    LETTERFORM_OBLIQUE_SQUARE: int = 15

    # ---- Byte 8: Midline ----
    MIDLINE_STANDARD_TRIMMED: int = 2
    MIDLINE_STANDARD_POINTED: int = 3
    MIDLINE_STANDARD_SERIFED: int = 4
    MIDLINE_HIGH_TRIMMED: int = 5
    MIDLINE_HIGH_POINTED: int = 6
    MIDLINE_HIGH_SERIFED: int = 7
    MIDLINE_CONSTANT_TRIMMED: int = 8
    MIDLINE_CONSTANT_POINTED: int = 9
    MIDLINE_CONSTANT_SERIFED: int = 10
    MIDLINE_LOW_TRIMMED: int = 11
    MIDLINE_LOW_POINTED: int = 12
    MIDLINE_LOW_SERIFED: int = 13

    # ---- Byte 9: X-Height ----
    X_HEIGHT_CONSTANT_SMALL: int = 2
    X_HEIGHT_CONSTANT_STANDARD: int = 3
    X_HEIGHT_CONSTANT_LARGE: int = 4
    X_HEIGHT_DUCKING_SMALL: int = 5
    X_HEIGHT_DUCKING_STANDARD: int = 6
    X_HEIGHT_DUCKING_LARGE: int = 7

    # Byte offsets — surfaced as named constants so the setter helpers can
    # reference them without re-typing magic indices. pypdfbox extension.
    _BYTE_FAMILY_KIND: int = 0
    _BYTE_SERIF_STYLE: int = 1
    _BYTE_WEIGHT: int = 2
    _BYTE_PROPORTION: int = 3
    _BYTE_CONTRAST: int = 4
    _BYTE_STROKE_VARIATION: int = 5
    _BYTE_ARM_STYLE: int = 6
    _BYTE_LETTERFORM: int = 7
    _BYTE_MIDLINE: int = 8
    _BYTE_X_HEIGHT: int = 9

    __slots__ = ("_bytes",)

    def __init__(self, data: bytes | bytearray) -> None:
        # Upstream stores the byte array verbatim — no length validation in
        # the constructor. Match that for behavioral parity (callers may
        # reasonably pass 10 bytes; PDFontDescriptor.get_panose() guards the
        # length before constructing this object).
        self._bytes = bytes(data)

    def get_bytes(self) -> bytes:
        return self._bytes

    def _signed_byte_at(self, index: int) -> int:
        value = self._bytes[index]
        return value - 0x100 if value >= 0x80 else value

    def get_family_kind(self) -> int:
        return self._signed_byte_at(0)

    def get_serif_style(self) -> int:
        return self._signed_byte_at(1)

    def get_weight(self) -> int:
        return self._signed_byte_at(2)

    def get_proportion(self) -> int:
        return self._signed_byte_at(3)

    def get_contrast(self) -> int:
        return self._signed_byte_at(4)

    def get_stroke_variation(self) -> int:
        return self._signed_byte_at(5)

    def get_arm_style(self) -> int:
        return self._signed_byte_at(6)

    def get_letterform(self) -> int:
        return self._signed_byte_at(7)

    def get_midline(self) -> int:
        return self._signed_byte_at(8)

    def get_x_height(self) -> int:
        return self._signed_byte_at(9)

    # ---------- per-byte setters (pypdfbox extension) ----------
    # Upstream ``PDPanoseClassification`` is read-only — the Java class
    # exposes only ``getBytes()`` plus the 10 per-byte getters. pypdfbox
    # adds matched setters so callers can author or repair classifications
    # without having to round-trip through ``bytes`` and the constructor.
    # Each setter accepts a signed int in the range ``-128..255`` (Java's
    # ``byte`` is signed, but PANOSE values are unsigned by spec — we
    # accept both so round-trips via :meth:`get_*` work).

    def _set_byte_at(self, index: int, value: int) -> None:
        if not -0x80 <= int(value) <= 0xFF:
            raise ValueError(
                f"PANOSE byte {value!r} out of range (-128..255); each "
                "category is a single signed/unsigned byte per the OS/2 "
                "PANOSE specification."
            )
        unsigned = int(value) & 0xFF
        buf = bytearray(self._bytes)
        # Pad with zeros if the underlying buffer is shorter than the byte
        # we're trying to write (upstream tolerates short buffers in the
        # constructor; matching that asymmetry would surprise callers).
        if index >= len(buf):
            buf.extend(b"\x00" * (index + 1 - len(buf)))
        buf[index] = unsigned
        self._bytes = bytes(buf)

    def set_family_kind(self, value: int) -> None:
        """Mirror :meth:`get_family_kind` — write byte 0 of the
        classification.

        pypdfbox extension. Use one of the :attr:`FAMILY_KIND_*` constants
        for spec-compliant values.
        """
        self._set_byte_at(self._BYTE_FAMILY_KIND, value)

    def set_serif_style(self, value: int) -> None:
        """Mirror :meth:`get_serif_style` — write byte 1 of the classification.

        pypdfbox extension. Use one of the :attr:`SERIF_STYLE_*` constants
        for Latin Text family values (other families list ``Any`` / ``No Fit``).
        """
        self._set_byte_at(self._BYTE_SERIF_STYLE, value)

    def set_weight(self, value: int) -> None:
        """Mirror :meth:`get_weight` — write byte 2 of the classification.

        pypdfbox extension. Use one of the :attr:`WEIGHT_*` constants.
        """
        self._set_byte_at(self._BYTE_WEIGHT, value)

    def set_proportion(self, value: int) -> None:
        """Mirror :meth:`get_proportion` — write byte 3 of the classification.

        pypdfbox extension. Use one of the :attr:`PROPORTION_*` constants.
        """
        self._set_byte_at(self._BYTE_PROPORTION, value)

    def set_contrast(self, value: int) -> None:
        """Mirror :meth:`get_contrast` — write byte 4 of the classification.

        pypdfbox extension. Use one of the :attr:`CONTRAST_*` constants.
        """
        self._set_byte_at(self._BYTE_CONTRAST, value)

    def set_stroke_variation(self, value: int) -> None:
        """Mirror :meth:`get_stroke_variation` — write byte 5 of the
        classification.

        pypdfbox extension. Use one of the :attr:`STROKE_VARIATION_*`
        constants.
        """
        self._set_byte_at(self._BYTE_STROKE_VARIATION, value)

    def set_arm_style(self, value: int) -> None:
        """Mirror :meth:`get_arm_style` — write byte 6 of the classification.

        pypdfbox extension. Use one of the :attr:`ARM_STYLE_*` constants.
        """
        self._set_byte_at(self._BYTE_ARM_STYLE, value)

    def set_letterform(self, value: int) -> None:
        """Mirror :meth:`get_letterform` — write byte 7 of the classification.

        pypdfbox extension. Use one of the :attr:`LETTERFORM_*` constants.
        """
        self._set_byte_at(self._BYTE_LETTERFORM, value)

    def set_midline(self, value: int) -> None:
        """Mirror :meth:`get_midline` — write byte 8 of the classification.

        pypdfbox extension. Use one of the :attr:`MIDLINE_*` constants.
        """
        self._set_byte_at(self._BYTE_MIDLINE, value)

    def set_x_height(self, value: int) -> None:
        """Mirror :meth:`get_x_height` — write byte 9 of the classification.

        pypdfbox extension. Use one of the :attr:`X_HEIGHT_*` constants.
        """
        self._set_byte_at(self._BYTE_X_HEIGHT, value)

    def get_byte(self, index: int) -> int:
        """Generic per-byte getter (0-based index into the 10-byte block).

        pypdfbox extension — symmetric with :meth:`set_byte` and useful
        for callers iterating over the categories programmatically.
        Returns the signed byte value to match the per-category getters.
        """
        if not 0 <= int(index) < PDPanoseClassification.LENGTH:
            raise IndexError(
                f"PANOSE byte index {index!r} out of range "
                f"(0..{PDPanoseClassification.LENGTH - 1})"
            )
        return self._signed_byte_at(int(index))

    def set_byte(self, index: int, value: int) -> None:
        """Generic per-byte setter (0-based index into the 10-byte block).

        pypdfbox extension — symmetric with :meth:`get_byte`.
        """
        if not 0 <= int(index) < PDPanoseClassification.LENGTH:
            raise IndexError(
                f"PANOSE byte index {index!r} out of range "
                f"(0..{PDPanoseClassification.LENGTH - 1})"
            )
        self._set_byte_at(int(index), value)

    # ---------- family-kind predicates ----------

    def is_any(self) -> bool:
        """``True`` when ``family_kind == 0`` ("Any" — unclassified).

        pypdfbox extension — upstream callers compare ``getFamilyKind() == 0``
        directly (see ``FontMapperImpl`` line 581). Surface the predicate
        so callers don't have to remember the magic constant.
        """
        return self.get_family_kind() == self.FAMILY_KIND_ANY

    def is_no_fit(self) -> bool:
        """``True`` when ``family_kind == 1`` ("No Fit" — classification
        attempted but no family applies).

        pypdfbox extension. Symmetric to :meth:`is_any` and :meth:`is_latin_text`.
        """
        return self.get_family_kind() == self.FAMILY_KIND_NO_FIT

    def is_latin_text(self) -> bool:
        """``True`` when ``family_kind == 2`` ("Latin Text" — the family
        most PDF body text falls under).

        pypdfbox extension. The ``Latin Text`` family is the only one
        whose serif-style sub-classification is defined by the PANOSE
        specification; other families list ``Any`` / ``No Fit`` in their
        sub-classification slots.
        """
        return self.get_family_kind() == self.FAMILY_KIND_LATIN_TEXT

    def is_latin_hand_written(self) -> bool:
        """``True`` when ``family_kind == 3`` ("Latin Hand Written" —
        script / calligraphic typefaces).

        pypdfbox extension. Symmetric to :meth:`is_latin_text`. Hand
        written family fonts list their own per-byte sub-classification
        slots in the OS/2 PANOSE specification (Tool Kind, Spacing,
        Aspect Ratio, etc.) which we surface only via the generic
        :meth:`get_byte` accessor — pypdfbox does not promote the
        hand-written-specific bucket constants because no shipping
        upstream Java caller branches on them.
        """
        return self.get_family_kind() == self.FAMILY_KIND_LATIN_HAND_WRITTEN

    def is_latin_decorative(self) -> bool:
        """``True`` when ``family_kind == 4`` ("Latin Decorative" —
        display / decorative typefaces).

        pypdfbox extension. Symmetric to :meth:`is_latin_text`.
        """
        return self.get_family_kind() == self.FAMILY_KIND_LATIN_DECORATIVE

    def is_latin_symbol(self) -> bool:
        """``True`` when ``family_kind == 5`` ("Latin Symbol" —
        symbol / pi / dingbat typefaces).

        pypdfbox extension. Symmetric to :meth:`is_latin_text`. Fonts
        in this family are typically also marked ``/Flags`` SYMBOLIC
        on the host :class:`PDFontDescriptor`; use
        :meth:`PDFontDescriptor.is_panose_symbolic_consistent` to
        cross-check the two metadata sources.
        """
        return self.get_family_kind() == self.FAMILY_KIND_LATIN_SYMBOL

    def __bytes__(self) -> bytes:
        """Pythonic alias for :meth:`get_bytes` — enables ``bytes(classification)``."""
        return self._bytes

    def __len__(self) -> int:
        """Number of bytes actually stored (typically :attr:`LENGTH` == 10)."""
        return len(self._bytes)

    def to_string(self) -> str:
        """Mirror upstream ``PDPanoseClassification.toString()``.

        Upstream format (Java lines 98-107):
        ``"{ FamilyKind = " + getFamilyKind() + ", SerifStyle = " +
        getSerifStyle() + ", Weight = " + getWeight() + ", Proportion = " +
        getProportion() + ", Contrast = " + getContrast() +
        ", StrokeVariation = " + getStrokeVariation() + ", ArmStyle = " +
        getArmStyle() + ", Letterform = " + getLetterform() + ", Midline = " +
        getMidline() + ", XHeight = " + getXHeight() + "}"``.
        """
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

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"PDPanoseClassification({self._bytes!r})"

    def __eq__(self, other: object) -> bool:
        """Value equality based on the underlying byte buffer.

        pypdfbox extension — upstream relies on Java's default identity
        ``equals``. Treating these wrappers as value types lets callers
        compare PANOSE classifications cheaply (e.g. in test assertions).
        """
        if not isinstance(other, PDPanoseClassification):
            return NotImplemented
        return self._bytes == other._bytes

    def __hash__(self) -> int:
        return hash(self._bytes)


class PDPanose:
    """The 12-byte Panose entry of a FontDescriptor's /Style dictionary.

    Mirrors ``org.apache.pdfbox.pdmodel.font.PDPanose``. The first two bytes
    hold the TrueType ``sFamilyClass`` value (signed 16-bit big-endian); the
    remaining 10 bytes are the PANOSE classification number, exposed via
    :class:`PDPanoseClassification`.
    """

    LENGTH: int = 12

    # Byte offset where the embedded :class:`PDPanoseClassification` slice
    # begins inside the 12-byte block. pypdfbox extension — upstream
    # hard-codes the literal ``2`` in :meth:`get_panose` (Java
    # ``Arrays.copyOfRange(bytes, 2, 12)``); the named constant lets
    # callers slice the buffer themselves without re-typing the magic
    # number.
    CLASSIFICATION_OFFSET: int = 2

    __slots__ = ("_bytes",)

    def __init__(self, data: bytes | bytearray) -> None:
        # Upstream stores the array directly without length checks. Mirror
        # that — accept any length the caller hands in and let the per-byte
        # accessors raise IndexError if the buffer is short.
        self._bytes = bytes(data)

    @classmethod
    def from_family_class_and_classification(
        cls,
        family_class: int,
        classification: PDPanoseClassification | bytes | bytearray,
    ) -> PDPanose:
        """Build a :class:`PDPanose` from a signed 16-bit ``sFamilyClass``
        plus the 10-byte PANOSE classification.

        pypdfbox extension — upstream PDPanose ships only the raw
        ``byte[]`` constructor. This convenience factory is symmetric to
        :meth:`get_family_class` (which decodes the leading 2 bytes as a
        signed 16-bit big-endian int) and saves callers from having to
        pack the integer themselves before reaching for the byte
        constructor.

        Negative ``family_class`` values are accepted — they round-trip
        through :meth:`get_family_class` exactly. Out-of-range values
        (outside ``-0x8000..0x7FFF``) raise :class:`ValueError`, matching
        what ``struct.pack(">h", ...)`` would do.
        """
        if not -0x8000 <= int(family_class) <= 0x7FFF:
            raise ValueError(
                f"family_class {family_class!r} does not fit in a signed "
                "16-bit big-endian int (range -0x8000 .. 0x7FFF)"
            )
        if isinstance(classification, PDPanoseClassification):
            payload = classification.get_bytes()
        else:
            payload = bytes(classification)
        # Encode as signed 16-bit big-endian — equivalent to
        # ``struct.pack(">h", family_class)`` but expressed inline so the
        # negative-int round-trip stays in plain view of the reader.
        unsigned = int(family_class) & 0xFFFF
        head = bytes(((unsigned >> 8) & 0xFF, unsigned & 0xFF))
        return cls(head + bytes(payload))

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
        if len(self._bytes) < self.CLASSIFICATION_OFFSET:
            raise IndexError("PDPanose buffer is too short for a classification slice")
        payload = self._bytes[
            self.CLASSIFICATION_OFFSET : self.CLASSIFICATION_OFFSET
            + PDPanoseClassification.LENGTH
        ]
        return PDPanoseClassification(
            payload + b"\x00" * (PDPanoseClassification.LENGTH - len(payload))
        )

    def with_panose_classification(
        self, classification: PDPanoseClassification | bytes | bytearray
    ) -> PDPanose:
        """Return a new :class:`PDPanose` with bytes 2-11 replaced.

        pypdfbox extension — upstream PDPanose is read-only. Returns a
        fresh wrapper so callers can update only the PANOSE-10 portion
        while preserving the leading 2-byte sFamilyClass. The original
        wrapper is left untouched (immutable value semantics).
        """
        if isinstance(classification, PDPanoseClassification):
            payload = classification.get_bytes()
        else:
            payload = bytes(classification)
        # Preserve the leading 2 bytes (sFamilyClass) verbatim; pad if the
        # source buffer was shorter than expected.
        head = (
            self._bytes[:2]
            if len(self._bytes) >= 2
            else self._bytes + b"\x00" * (2 - len(self._bytes))
        )
        return PDPanose(head + bytes(payload))

    def __bytes__(self) -> bytes:
        """Pythonic alias for :meth:`get_bytes` — enables ``bytes(panose)``."""
        return self._bytes

    def __len__(self) -> int:
        """Number of bytes actually stored (typically :attr:`LENGTH` == 12)."""
        return len(self._bytes)

    def __repr__(self) -> str:
        return f"PDPanose({self._bytes!r})"

    def __eq__(self, other: object) -> bool:
        """Value equality based on the underlying 12-byte buffer.

        pypdfbox extension — see :meth:`PDPanoseClassification.__eq__`.
        """
        if not isinstance(other, PDPanose):
            return NotImplemented
        return self._bytes == other._bytes

    def __hash__(self) -> int:
        return hash(self._bytes)


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
