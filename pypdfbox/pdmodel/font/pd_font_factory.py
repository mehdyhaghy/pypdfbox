from __future__ import annotations

import logging

from pypdfbox.cos import COSDictionary, COSName, COSStream
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

_LOG = logging.getLogger(__name__)

_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FONT_FILE2: COSName = COSName.get_pdf_name("FontFile2")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")
_TYPE1C: str = "Type1C"
_CID_FONT_TYPE0C: str = "CIDFontType0C"

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
        font_descriptor: object | None = None,
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


__all__ = ["PDFontFactory"]
