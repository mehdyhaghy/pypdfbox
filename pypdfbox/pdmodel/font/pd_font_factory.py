from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.fontbox.font_box_font import FontBoxFont
from pypdfbox.fontbox.font_mapper import FontMapper
from pypdfbox.fontbox.font_mappers import FontMappers
from pypdfbox.fontbox.font_mapping import FontMapping

from .pd_cid_font import PDCIDFont
from .pd_cid_font_type0 import PDCIDFontType0
from .pd_cid_font_type2 import PDCIDFontType2
from .pd_font import PDFont
from .pd_mm_type1_font import PDMMType1Font
from .pd_simple_font import PDSimpleFont
from .pd_true_type_font import PDTrueTypeFont
from .pd_type0_font import PDType0Font
from .pd_type1_font import PDType1Font
from .pd_type1c_font import PDType1CFont
from .pd_type3_font import PDType3Font
from .standard14_fonts import Standard14Fonts

if TYPE_CHECKING:
    from .pd_font_descriptor import PDFontDescriptor

_LOG = logging.getLogger(__name__)

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_FONT: COSName = COSName.get_pdf_name("Font")
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FONT_FILE: COSName = COSName.get_pdf_name("FontFile")
_FONT_FILE2: COSName = COSName.get_pdf_name("FontFile2")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")
_DESCENDANT_FONTS: COSName = COSName.get_pdf_name("DescendantFonts")
_TYPE1C: str = "Type1C"
_CID_FONT_TYPE0C: str = "CIDFontType0C"

# Header-kind labels returned by :meth:`PDFontFactory.get_font_program_kind`.
# These match the upstream private constants used as routing keys in
# ``PDFontFactory.getFontTypeFromFont``. Surfaced as named module
# constants so callers can compare against them without re-typing the
# strings.
_KIND_TRUE_TYPE: str = "TrueType"
_KIND_TRUE_TYPE_COLLECTION: str = "TrueTypeCollection"
_KIND_OPEN_TYPE: str = "OpenType"
_KIND_TYPE1: str = "Type1"
_KIND_PFB: str = "PFB"
_KIND_CFF: str = "CFF"

# Set of /Subtype name strings the factory dispatches on. Mirrors the
# upstream ``PDFontFactory.createFont`` switch (Type1 / Type1C / MMType1
# / TrueType / Type3 / Type0 / CIDFontType0 / CIDFontType2). ``Type1C``
# is not a top-level /Subtype in valid PDFs (it appears on
# /FontFile3 /Subtype) but PDFBox keeps it in the supported set for
# defensive parsing of malformed files.
_SUPPORTED_SUBTYPES: frozenset[str] = frozenset(
    {
        PDType0Font.SUB_TYPE,
        PDType1Font.SUB_TYPE,
        _TYPE1C,
        PDMMType1Font.SUB_TYPE,
        PDType3Font.SUB_TYPE,
        PDTrueTypeFont.SUB_TYPE,
        PDCIDFontType0.SUB_TYPE,
        PDCIDFontType2.SUB_TYPE,
    }
)


def _font_file3_subtype(font_dict: COSDictionary) -> str | None:
    """Return ``font_dict /FontDescriptor /FontFile3 /Subtype`` as a name
    string, or ``None`` if any link in the chain is absent or the wrong
    type. Uses typed accessors only — does not assume any particular
    dict layout beyond what ``COSDictionary`` exposes.
    """
    descriptor = font_dict.get_dictionary_object(_FONT_DESCRIPTOR)
    if not isinstance(descriptor, COSDictionary):
        return None
    font_file3 = descriptor.get_dictionary_object(_FONT_FILE3)
    if not isinstance(font_file3, COSStream):
        return None
    return font_file3.get_name(_SUBTYPE)


def _has_font_file2(font_dict: COSDictionary) -> bool:
    """Return ``True`` when ``font_dict /FontDescriptor /FontFile2`` is a
    stream — i.e. the descriptor carries an embedded TrueType program.
    Used to disambiguate top-level /CIDFontType2 dispatch (the bare
    /CIDFontType2 case is reached via the /Type0 descendant path; only
    when the descriptor proves a TrueType program is embedded do we
    wrap it directly here).
    """
    descriptor = font_dict.get_dictionary_object(_FONT_DESCRIPTOR)
    if not isinstance(descriptor, COSDictionary):
        return False
    return isinstance(descriptor.get_dictionary_object(_FONT_FILE2), COSStream)


class PDFontFactory:
    """Static dispatch from a font ``COSDictionary`` to the right
    ``PDFont`` subclass, keyed on ``/Subtype`` (with ``/FontDescriptor
    /FontFile3 /Subtype`` consulted to disambiguate Type1C / CIDFontType0C
    embedded CFF programs). Mirrors PDFBox
    ``PDFontFactory.createFont(COSDictionary)``.
    """

    @staticmethod
    def create_font(
        font_dict: COSDictionary,
        resource_cache: object | None = None,
    ) -> PDFont | None:
        # ``resource_cache`` mirrors the upstream second argument to
        # ``PDFontFactory.createFont`` — used by callers that want font
        # instances pooled across pages. We don't currently consult it
        # (all dispatch arms construct fresh wrappers); the parameter is
        # accepted for signature parity so PDFBox-shaped calls don't break.
        del resource_cache
        if font_dict is None:
            return None
        if not isinstance(font_dict, COSDictionary):
            raise TypeError(
                f"PDFontFactory.create_font expects COSDictionary, "
                f"got {type(font_dict).__name__}"
            )
        # Mirrors upstream's first defensive check: a font dictionary
        # ought to carry /Type /Font. PDFBox logs an error and *still*
        # proceeds with subtype dispatch (the wrapper is permissive); we
        # match that — the warning helps log scrapers spot malformed
        # files without breaking text extraction.
        explicit_type = font_dict.get_name(_TYPE)
        if explicit_type is not None and explicit_type != _FONT.name:
            _LOG.error(
                "Expected 'Font' dictionary but found %r", explicit_type
            )
        sub_type = font_dict.get_name(_SUBTYPE)
        if sub_type == PDType1Font.SUB_TYPE:
            # /Type1 with /FontDescriptor /FontFile3 /Subtype /Type1C is
            # a CFF-backed Type 1 font; route to PDType1CFont so the CFF
            # program is consulted for widths / outlines. Plain /Type1
            # (no FontFile3, or FontFile3 of /Subtype /OpenType etc.)
            # stays on PDType1Font.
            if _font_file3_subtype(font_dict) == _TYPE1C:
                return PDType1CFont(font_dict)
            return PDType1Font(font_dict)
        if sub_type == PDTrueTypeFont.SUB_TYPE:
            return PDTrueTypeFont(font_dict)
        if sub_type == PDType0Font.SUB_TYPE:
            return PDType0Font(font_dict)
        if sub_type == PDType3Font.SUB_TYPE:
            return PDType3Font(font_dict)
        if sub_type == PDMMType1Font.SUB_TYPE:
            # MMType1 with /FontDescriptor /FontFile3 /Subtype /Type1C is
            # a CFF-backed multiple-master Type 1 font; route to
            # PDType1CFont so the CFF program is consulted (mirrors
            # upstream PDFontFactory.createFont — the MMType1 + FontFile3
            # branch returns PDType1CFont).
            if _font_file3_subtype(font_dict) == _TYPE1C:
                return PDType1CFont(font_dict)
            return PDMMType1Font(font_dict)
        if sub_type == PDCIDFontType0.SUB_TYPE:
            # CIDFontType0 is normally reached via PDType0Font.get_descendant_font;
            # when it appears as the top-level /Subtype with a CFF /FontFile3
            # (/Subtype /CIDFontType0C) we wrap it directly. Without that
            # marker we leave it to the Type0 descendant path (returns None).
            if _font_file3_subtype(font_dict) == _CID_FONT_TYPE0C:
                return PDCIDFontType0(font_dict)
            return None
        if sub_type == PDCIDFontType2.SUB_TYPE:
            # Symmetric to the CIDFontType0 arm: bare /CIDFontType2 is
            # reached via PDType0Font.get_descendant_font; only when the
            # descriptor carries an embedded TrueType program (/FontFile2)
            # do we wrap it directly here. Without that marker we return
            # ``None`` so the Type0 descendant path stays authoritative.
            if _has_font_file2(font_dict):
                return PDCIDFontType2(font_dict)
            return None
        if sub_type is None:
            # Mirrors upstream PDFontFactory: missing /Subtype is a
            # malformed font dictionary; rather than fail outright PDFBox
            # logs a warning and falls back to PDType1Font so callers can
            # still attempt rendering / text extraction with the Standard
            # 14 metrics for whatever /BaseFont might be present.
            _LOG.warning(
                "Invalid font subtype 'None', will be handled as Type1"
            )
            return PDType1Font(font_dict)
        # Unknown subtype — log and return ``None`` so the caller can
        # decide whether to skip this font dictionary entirely. (Upstream
        # falls back to PDType1Font here as well, but that would mask
        # /CIDFontType2 dispatch for callers relying on the bare-CID
        # contract documented above.)
        _LOG.warning(
            "Invalid font subtype '%s', skipping font dictionary", sub_type
        )
        return None

    # ---------- descendant-CIDFont dispatch ----------

    @staticmethod
    def create_descendant_font(
        font_dict: COSDictionary,
        parent: PDType0Font | None = None,
    ) -> PDCIDFont | None:
        """Build a :class:`PDCIDFont` from a Type0 descendant font dict.

        Mirrors PDFBox's package-private
        ``PDFontFactory.createDescendantFont(COSDictionary, PDType0Font)``
        — used internally by :class:`PDType0Font` to wrap the entry in
        ``/DescendantFonts``. Surfaced publicly here because pypdfbox
        callers occasionally need to wrap a descendant dict from the
        outside (e.g. when stitching a Type0 chain together post-parse).

        ``font_dict`` must be a font dictionary (``/Type /Font``) whose
        ``/Subtype`` is ``CIDFontType0`` or ``CIDFontType2``. ``parent``
        is the wrapping :class:`PDType0Font` and is forwarded so the
        descendant can resolve its parent CMap when answering
        ``code_to_cid`` / ``code_to_gid``.

        Returns ``None`` for ``None`` / non-dictionary inputs (matching
        the lenient pattern :meth:`create_font` follows). Raises
        :class:`OSError` for valid font dicts whose ``/Subtype`` is
        neither ``CIDFontType0`` nor ``CIDFontType2`` — upstream raises
        ``IOException`` ("Invalid font type") in the same situation.
        """
        if font_dict is None:
            return None
        if not isinstance(font_dict, COSDictionary):
            raise TypeError(
                "PDFontFactory.create_descendant_font expects "
                f"COSDictionary, got {type(font_dict).__name__}"
            )
        sub_type = font_dict.get_name(_SUBTYPE)
        if sub_type == PDCIDFontType0.SUB_TYPE:
            return PDCIDFontType0(font_dict, parent)
        if sub_type == PDCIDFontType2.SUB_TYPE:
            return PDCIDFontType2(font_dict, parent)
        raise OSError(
            f"Invalid descendant font type: {sub_type!r} "
            "(expected /CIDFontType0 or /CIDFontType2)"
        )

    # ---------- typed-result convenience wrappers ----------

    @staticmethod
    def create_simple_font(font_dict: COSDictionary) -> PDSimpleFont | None:
        """Return the dispatched font only if it's a :class:`PDSimpleFont`
        (Type1 / Type1C / MMType1 / TrueType / Type3); otherwise ``None``.

        Mirrors PDFBox ``PDFontFactory.createSimpleFont`` — convenience
        for callers that already know the slot must be a simple font and
        want a typed handle without an isinstance check at every call
        site.
        """
        font = PDFontFactory.create_font(font_dict)
        return font if isinstance(font, PDSimpleFont) else None

    @staticmethod
    def create_cid_font(font_dict: COSDictionary) -> PDCIDFont | None:
        """Return the dispatched font only if it's a :class:`PDCIDFont`
        (CIDFontType0 / CIDFontType2); otherwise ``None``.

        Mirrors PDFBox ``PDFontFactory.createCIDFont``. Note that the
        top-level :meth:`create_font` only returns a CID font directly
        when /Subtype is ``CIDFontType0`` *and* the descriptor carries a
        CFF /FontFile3; bare ``CIDFontType2`` is reached via the Type0
        descendant path and will return ``None`` here.
        """
        font = PDFontFactory.create_font(font_dict)
        return font if isinstance(font, PDCIDFont) else None

    # ---------- standard-14 default-font convenience ----------

    @staticmethod
    def create_default_font(name: str = Standard14Fonts.HELVETICA) -> PDFont:
        """Build a :class:`PDType1Font` for one of the 14 PDF Standard
        fonts. Falls back to ``Helvetica`` when ``name`` does not resolve
        to a Standard 14 font (canonical name or registered alias).

        Mirrors PDFBox ``PDFontFactory.createDefaultFont`` — used by
        appearance-stream generators and form-flattening helpers that
        need *some* usable font without forcing the caller to construct
        a font dictionary by hand.
        """
        canonical = Standard14Fonts.get_mapped_font_name(name)
        if canonical is None:
            canonical = Standard14Fonts.HELVETICA
        font_dict = COSDictionary()
        font_dict.set_name(_SUBTYPE, PDType1Font.SUB_TYPE)
        font_dict.set_name(_BASE_FONT, canonical)
        return PDType1Font(font_dict)

    # ---------- font-mapper hooks ----------

    @staticmethod
    def get_font_mapper() -> FontMapper:
        """Return the active :class:`FontMapper` singleton.

        Thin convenience over :meth:`FontMappers.instance`; lets callers
        reach the mapper without importing the fontbox package. Mirrors
        the spirit of upstream callers that do
        ``FontMappers.instance().getFontBoxFont(...)`` directly.
        """
        return FontMappers.instance()

    @staticmethod
    def set_font_mapper(font_mapper: FontMapper | None) -> None:
        """Install ``font_mapper`` as the active mapper.

        Pass-through to :meth:`FontMappers.set`. ``None`` resets to the
        default mapper. Callers that need to swap in a richer
        substitution policy (for example one backed by a real on-disk
        font scanner) should use this rather than monkey-patching.
        """
        FontMappers.set(font_mapper)

    @staticmethod
    def find_font_box_font(
        base_font: str,
        font_descriptor: PDFontDescriptor | None = None,
    ) -> FontMapping[FontBoxFont] | None:
        """Resolve ``base_font`` through the active mapper.

        Convenience wrapper used by appearance-stream generators / text
        extraction when they only need *some* FontBox font for a given
        PostScript name (Standard 14 hits the bundled AFMs; misses
        return a style-driven Helvetica fallback). Returns ``None``
        only if a future replacement mapper does — the default mapper
        always returns a mapping.
        """
        return FontMappers.instance().get_font_box_font(base_font, font_descriptor)

    # ---------- subtype predicate ----------

    @staticmethod
    def is_supported_subtype(subtype: str | None) -> bool:
        """Return ``True`` for any /Subtype value :meth:`create_font` knows
        how to dispatch on. Mirrors PDFBox
        ``PDFontFactory.isSupportedSubtype`` — useful for parsers that
        want to skip / log unknown font dictionaries before instantiating
        a wrapper.
        """
        if subtype is None:
            return False
        return subtype in _SUPPORTED_SUBTYPES

    # ---------- descendant / descriptor helpers ----------

    # File-program magic-number constants used by upstream when sniffing
    # the bytes of an embedded font program. The pypdfbox port surfaces
    # them as named strings (parity with the upstream private constants
    # ``FONT_TYPE1C`` / ``FONT_OPEN_TYPE`` / ``FONT_TTF_COLLECTION`` /
    # ``FONT_TRUE_TYPE`` / ``TTF_HEADER``) so callers can hand-roll their
    # own header detection without re-typing the literals.
    FONT_TYPE1C: str = _TYPE1C
    FONT_OPEN_TYPE: str = "OTTO"
    FONT_TTF_COLLECTION: str = "ttcf"
    FONT_TRUE_TYPE: str = "true"
    TTF_HEADER: bytes = b"\x00\x01\x00\x00"

    @staticmethod
    def get_descendant_font_dict(
        font_dict: COSDictionary,
    ) -> COSDictionary | None:
        """Return the first ``COSDictionary`` in ``font_dict``'s
        ``/DescendantFonts`` array, or ``None`` when the entry is absent
        / empty / non-dictionary.

        Mirrors upstream ``PDFontFactory.getDescendantFont`` (private
        helper). Surfaced publicly here because pypdfbox callers parsing
        Type 0 chains by hand (e.g. font-fallback heuristics) want a
        single typed accessor rather than reaching into the array
        manually. ``font_dict=None`` returns ``None`` rather than raising
        — keeps the helper composable in lenient parsing paths.
        """
        if font_dict is None:
            return None
        if not isinstance(font_dict, COSDictionary):
            raise TypeError(
                f"PDFontFactory.get_descendant_font_dict expects "
                f"COSDictionary, got {type(font_dict).__name__}"
            )
        descendant_fonts = font_dict.get_dictionary_object(_DESCENDANT_FONTS)
        if not isinstance(descendant_fonts, COSArray):
            return None
        if descendant_fonts.size() == 0:
            return None
        first = descendant_fonts.get_object(0)
        if isinstance(first, COSDictionary):
            return first
        return None

    @staticmethod
    def get_font_descriptor_dict(
        font_dict: COSDictionary,
    ) -> COSDictionary | None:
        """Return ``font_dict /FontDescriptor`` (typed as ``COSDictionary``),
        falling back to the first descendant font's ``/FontDescriptor``
        when absent.

        Mirrors upstream ``PDFontFactory.getFontDescriptor`` (private
        helper). The descendant fallback matches the upstream order: a
        ``/Type0`` parent dict normally has no descriptor of its own —
        the descriptor lives on the descendant CIDFont per PDF 32000-1
        §9.7.3 — so the caller gets the descendant's descriptor without
        having to plumb the array entry by hand.
        """
        if font_dict is None:
            return None
        if not isinstance(font_dict, COSDictionary):
            raise TypeError(
                f"PDFontFactory.get_font_descriptor_dict expects "
                f"COSDictionary, got {type(font_dict).__name__}"
            )
        descriptor = font_dict.get_dictionary_object(_FONT_DESCRIPTOR)
        if isinstance(descriptor, COSDictionary):
            return descriptor
        descendant = PDFontFactory.get_descendant_font_dict(font_dict)
        if descendant is None:
            return None
        descendant_descriptor = descendant.get_dictionary_object(
            _FONT_DESCRIPTOR
        )
        if isinstance(descendant_descriptor, COSDictionary):
            return descendant_descriptor
        return None

    # ---------- font-program header sniffing ----------

    @staticmethod
    def is_true_type_header(header: bytes | bytearray | memoryview) -> bool:
        """Return ``True`` when the first 4 bytes of an embedded font
        program identify a TrueType outline file.

        Mirrors upstream ``PDFontFactory.isTrueTypeFile`` (private). A
        TrueType outline file begins with the version sfnt tag
        ``0x00010000`` or the four ASCII bytes ``"true"``.
        """
        if header is None or len(header) < 4:
            return False
        first_four = bytes(header[:4])
        if first_four == PDFontFactory.TTF_HEADER:
            return True
        try:
            return first_four.decode("ascii") == PDFontFactory.FONT_TRUE_TYPE
        except UnicodeDecodeError:
            return False

    @staticmethod
    def is_true_type_collection_header(
        header: bytes | bytearray | memoryview,
    ) -> bool:
        """Return ``True`` when the first 4 bytes spell ``"ttcf"`` (the
        TrueType collection magic number).

        Mirrors upstream ``PDFontFactory.isTrueTypeCollectionFile``.
        """
        if header is None or len(header) < 4:
            return False
        try:
            return (
                bytes(header[:4]).decode("ascii")
                == PDFontFactory.FONT_TTF_COLLECTION
            )
        except UnicodeDecodeError:
            return False

    @staticmethod
    def is_open_type_header(header: bytes | bytearray | memoryview) -> bool:
        """Return ``True`` when the first 4 bytes spell ``"OTTO"`` (the
        CFF-flavoured OpenType magic number).

        Mirrors upstream ``PDFontFactory.isOpenTypeFile``. Note that
        TrueType-flavoured OpenType files are detected by
        :meth:`is_true_type_header` instead (sfnt-tagged TrueType outlines
        and OpenType wrap each other in PDF 32000-1's classification).
        """
        if header is None or len(header) < 4:
            return False
        try:
            return (
                bytes(header[:4]).decode("ascii")
                == PDFontFactory.FONT_OPEN_TYPE
            )
        except UnicodeDecodeError:
            return False

    @staticmethod
    def is_type1_header(header: bytes | bytearray | memoryview) -> bool:
        """Return ``True`` when the first 2 bytes are ``%!`` — the
        ASCII Type 1 program prologue.

        Mirrors upstream ``PDFontFactory.isType1File``. All Type 1 font
        programs begin with the comment ``%!`` (0x25 + 0x21) per the
        Adobe Type 1 specification.
        """
        if header is None or len(header) < 2:
            return False
        return header[0] == 0x25 and header[1] == 0x21

    @staticmethod
    def is_pfb_header(header: bytes | bytearray | memoryview) -> bool:
        """Return ``True`` when the first 2 bytes mark a PFB-wrapped Type
        1 font (``0x80`` followed by ``0x01`` or ``0x02``).

        Mirrors upstream ``PDFontFactory.isPfbFile``. PFB segment-record
        markers always start with ``0x80``; the second byte is the
        segment type (1 = ASCII, 2 = binary, 3 = EOF).
        """
        if header is None or len(header) < 2:
            return False
        return header[0] == 0x80 and header[1] in (0x01, 0x02)

    @staticmethod
    def is_cff_header(header: bytes | bytearray | memoryview) -> bool:
        """Return ``True`` when the first 4 bytes are a plausible CFF
        header (major version >= 1 and offset size in [1, 4]).

        Mirrors upstream ``PDFontFactory.isCFFFile``. The CFF header is
        more permissive than the other checks (no fixed magic), so
        upstream and pypdfbox both call this last in the sniffing chain
        to avoid mis-classifying a TrueType or OpenType program with a
        version-1 sfnt tag as CFF.
        """
        if header is None or len(header) < 4:
            return False
        return header[0] >= 1 and 1 <= header[3] <= 4

    # ---------- header-kind labels & font-program inspection ----------

    KIND_TRUE_TYPE: str = _KIND_TRUE_TYPE
    KIND_TRUE_TYPE_COLLECTION: str = _KIND_TRUE_TYPE_COLLECTION
    KIND_OPEN_TYPE: str = _KIND_OPEN_TYPE
    KIND_TYPE1: str = _KIND_TYPE1
    KIND_PFB: str = _KIND_PFB
    KIND_CFF: str = _KIND_CFF

    @staticmethod
    def get_font_program_kind(
        header: bytes | bytearray | memoryview | None,
    ) -> str | None:
        """Classify a 4-byte font-program ``header`` and return the kind
        as a label string (one of the ``KIND_*`` constants), or ``None``
        when the header doesn't match any known program format.

        Mirrors the dispatch chain inside upstream
        ``PDFontFactory.getFontTypeFromFont`` — TTF / TTC first, then
        OpenType, then Type 1 (raw) / PFB-wrapped Type 1, with CFF last
        because its header check is permissive enough to match other
        formats by accident. Surfaced publicly here because pypdfbox
        callers parsing or repairing embedded font streams want a single
        entry point that produces the same answer the dispatch arm
        would.
        """
        if header is None or len(header) < 4:
            return None
        if PDFontFactory.is_true_type_header(header):
            return _KIND_TRUE_TYPE
        if PDFontFactory.is_true_type_collection_header(header):
            return _KIND_TRUE_TYPE_COLLECTION
        if PDFontFactory.is_open_type_header(header):
            return _KIND_OPEN_TYPE
        if PDFontFactory.is_type1_header(header):
            return _KIND_TYPE1
        if PDFontFactory.is_pfb_header(header):
            return _KIND_PFB
        if PDFontFactory.is_cff_header(header):
            return _KIND_CFF
        return None

    @staticmethod
    def get_font_program_header(
        font_descriptor: COSDictionary | None,
    ) -> bytes | None:
        """Return the first 4 decoded bytes of the embedded font program reachable
        from ``font_descriptor`` — checks ``/FontFile`` then ``/FontFile2``
        then ``/FontFile3`` (matching upstream's preference order).

        Returns ``None`` when:

        * ``font_descriptor`` is ``None``.
        * No ``/FontFile*`` entry resolves to a ``COSStream``.
        * The stream resolves but is shorter than 4 bytes.

        Mirrors PDFBox ``PDFontFactory.getFontHeader`` (private). Used
        together with :meth:`get_font_program_kind` to reproduce the
        upstream private ``getFontTypeFromFont`` repair routine without
        forcing callers to reach into ``COSStream`` themselves.

        ``font_descriptor`` is intentionally typed as a raw
        ``COSDictionary`` (not a ``PDFontDescriptor`` wrapper) — the
        repair routines that consume this also operate on the underlying
        dict.
        """
        if font_descriptor is None:
            return None
        if not isinstance(font_descriptor, COSDictionary):
            raise TypeError(
                f"PDFontFactory.get_font_program_header expects "
                f"COSDictionary, got {type(font_descriptor).__name__}"
            )
        for key in (_FONT_FILE, _FONT_FILE2, _FONT_FILE3):
            stream = font_descriptor.get_dictionary_object(key)
            if isinstance(stream, COSStream):
                data = stream.to_byte_array()
                if len(data) < 4:
                    return None
                return bytes(data[:4])
        return None

    @staticmethod
    def fix_type0_subtype(
        descendant_font: COSDictionary,
        font_descriptor: COSDictionary,
        new_subtype: str | COSName,
    ) -> None:
        """Repair a Type 0 descendant font dictionary so its ``/Subtype``
        and matching font-program key (``/FontFile2`` for CIDFontType2,
        ``/FontFile3`` for CIDFontType0) line up.

        Mirrors PDFBox ``PDFontFactory.fixType0Subtype``. When the new
        subtype is ``CIDFontType0`` and the descriptor only has
        ``/FontFile2`` (TrueType marker) we move the stream to
        ``/FontFile3``; symmetrically, when the new subtype is
        ``CIDFontType2`` and the descriptor only has ``/FontFile3`` we
        move it to ``/FontFile2``. Either way the descendant's
        ``/Subtype`` is then set to ``new_subtype``.

        ``new_subtype`` may be a ``COSName`` or a plain string — the
        helper normalises to a name. Other subtypes are accepted
        (descendant ``/Subtype`` is updated) but no FontFile shuffling is
        performed; this matches upstream's narrow repair scope.
        """
        if not isinstance(descendant_font, COSDictionary):
            raise TypeError(
                "PDFontFactory.fix_type0_subtype expects "
                f"COSDictionary descendant_font, "
                f"got {type(descendant_font).__name__}"
            )
        if not isinstance(font_descriptor, COSDictionary):
            raise TypeError(
                "PDFontFactory.fix_type0_subtype expects "
                f"COSDictionary font_descriptor, "
                f"got {type(font_descriptor).__name__}"
            )
        if isinstance(new_subtype, COSName):
            new_subtype_str = new_subtype.name
        elif isinstance(new_subtype, str):
            new_subtype_str = new_subtype
        else:
            raise TypeError(
                "PDFontFactory.fix_type0_subtype expects "
                f"str | COSName new_subtype, "
                f"got {type(new_subtype).__name__}"
            )
        _LOG.warning(
            "Try to fix different descendant font types for font %r",
            font_descriptor.get_name(COSName.get_pdf_name("FontName")),
        )
        if (
            new_subtype_str == PDCIDFontType0.SUB_TYPE
            and not font_descriptor.contains_key(_FONT_FILE3)
            and font_descriptor.contains_key(_FONT_FILE2)
        ):
            font_descriptor.set_item(
                _FONT_FILE3, font_descriptor.get_item(_FONT_FILE2)
            )
            font_descriptor.remove_item(_FONT_FILE2)
        if (
            new_subtype_str == PDCIDFontType2.SUB_TYPE
            and font_descriptor.contains_key(_FONT_FILE3)
            and not font_descriptor.contains_key(_FONT_FILE2)
        ):
            font_descriptor.set_item(
                _FONT_FILE2, font_descriptor.get_item(_FONT_FILE3)
            )
            font_descriptor.remove_item(_FONT_FILE3)
        descendant_font.set_name(_SUBTYPE, new_subtype_str)


__all__ = ["PDFontFactory"]
