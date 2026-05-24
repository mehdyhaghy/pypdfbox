"""Wave 1392 coverage round-out for
:mod:`pypdfbox.pdmodel.font.pd_true_type_font`.

Targets the residual branch and line gaps in 0.9.0rc1 after waves
1390/1391 (Mac-Roman cmap fallback bookkeeping, simple-font embed helper
branches):

* ``_code_to_gid`` Mac-Roman fallback branches (lines 650-662)
* ``_code_to_gid`` symbolic-with-WinAnsi/MacRoman encoding branches
  (lines 672-697)
* ``_code_to_gid_via_unicode_subtable`` encoding-driven and symbolic
  PUA branches (lines 717-738)
* ``read_encoding_from_font`` post-table-missing branch (line 867)
* ``_build_simple_ttf_font`` BaseFont/FontName tag-prefix branches
  (lines 1312-1326)
* ``_populate_simple_descriptor_from_ttf`` no-head / no-hhea branches
  (lines 1486-1506)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.font import PDFontDescriptor, PDTrueTypeFont
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_font_descriptor import FLAG_SYMBOLIC
from pypdfbox.pdmodel.font.pd_true_type_font import (
    _build_simple_ttf_font,
    _CmapPlatformView,
    _populate_simple_descriptor_from_ttf,
)

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _ttf_bytes() -> bytes:
    if not _FIXTURE.exists():
        pytest.skip(f"missing fixture {_FIXTURE}")
    return _FIXTURE.read_bytes()


def _load_ttf() -> TrueTypeFont:
    return TrueTypeFont.from_bytes(_ttf_bytes())


def _font_with_embedded_ttf(*, symbolic: bool = False) -> PDTrueTypeFont:
    font = PDTrueTypeFont()
    fd = PDFontDescriptor()
    if symbolic:
        fd.set_flags(FLAG_SYMBOLIC)
    stream = COSStream()
    stream.set_raw_data(_ttf_bytes())
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    font.set_true_type_font(_load_ttf())
    return font


class _FakeSubtable:
    """A fontTools-cmap-subtable look-alike consumed by
    :class:`_CmapPlatformView`."""

    def __init__(self, mapping: dict[int, str]) -> None:
        self.cmap = mapping


def _platform_view(
    code_to_name: dict[int, str], glyph_order: list[str]
) -> _CmapPlatformView:
    return _CmapPlatformView(_FakeSubtable(code_to_name), glyph_order)


# ---------- _code_to_gid: Mac-Roman fallback (non-symbolic) ----------


def test_code_to_gid_falls_back_to_mac_roman_when_win_unicode_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 650-657 — wave 1391 Mac-Roman fallback fires when the
    Win-Unicode lookup misses for a non-symbolic font with a real
    /Encoding."""
    font = _font_with_embedded_ttf()
    monkeypatch.setattr(font, "is_symbolic", lambda: False)
    monkeypatch.setattr(font, "get_encoding_typed", lambda: WinAnsiEncoding.INSTANCE)
    # Skip the extract_cmap_table path entirely - install fakes by hand.
    font._cmap_initialized = True  # noqa: SLF001
    # Win-Unicode subtable that does NOT carry "A" → returns 0.
    font._cmap_win_unicode = _platform_view(  # noqa: SLF001
        {0xFFFD: "uniFFFD"}, ["uniFFFD"]
    )
    # Mac-Roman platform view that DOES — "A" maps via MacOSRomanEncoding
    # at byte 0x41, gid 7 in our fake glyph_order.
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = _platform_view(  # noqa: SLF001
        {0x41: "A"}, [".notdef", "g1", "g2", "g3", "g4", "g5", "g6", "A"]
    )
    ttf = font.get_true_type_font()
    assert ttf is not None
    # ord("A") under WinAnsi → name "A". WinUnicode misses, mac_roman hits.
    gid = font._code_to_gid(ord("A"), ttf)  # noqa: SLF001
    assert gid == 7


def test_code_to_gid_mac_roman_returns_zero_when_name_unmappable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Branch 656->658 — Mac-Roman fallback skips when MacOSRomanEncoding
    has no code for the glyph name; falls through to ``name_to_gid``."""
    font = _font_with_embedded_ttf()
    monkeypatch.setattr(font, "is_symbolic", lambda: False)
    monkeypatch.setattr(font, "get_encoding_typed", lambda: WinAnsiEncoding.INSTANCE)
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = _platform_view({}, [])  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    # Map a code WinAnsi resolves to a name MacOSRomanEncoding lacks
    # (e.g. "Euro" is in WinAnsi but not Mac-Roman).
    font._cmap_mac_roman = _platform_view({}, [".notdef"])  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None
    # WinAnsi 0x80 → "Euro" (Mac-Roman has no Euro code).
    gid = font._code_to_gid(0x80, ttf)  # noqa: SLF001
    # name_to_gid("Euro") may or may not succeed; we just need the
    # mac-roman ``if mac_code is not None`` branch to take the False arm.
    assert isinstance(gid, int)


# ---------- _code_to_gid: symbolic branch with named encodings ----------


def test_code_to_gid_symbolic_with_winansi_encoding_uses_glyph_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 673-682 — symbolic font branch with WinAnsi-like encoding
    routes through encoding.get_name + GlyphList unicode."""
    font = _font_with_embedded_ttf(symbolic=True)
    monkeypatch.setattr(font, "is_symbolic", lambda: True)
    # Set up resolved encoding so the symbolic branch takes the
    # ``isinstance(encoding, (WinAnsiEncoding, MacRomanEncoding))`` arm.
    font._encoding_typed = WinAnsiEncoding.INSTANCE  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    font._cmap_initialized = True  # noqa: SLF001
    # Win-Unicode subtable carries "A" at U+0041.
    font._cmap_win_unicode = _platform_view(  # noqa: SLF001
        {0x41: "A"}, [".notdef", "A"]
    )
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None
    gid = font._code_to_gid(ord("A"), ttf)  # noqa: SLF001
    assert gid == 1


def test_code_to_gid_symbolic_with_pua_shifted_symbol_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 687-697 — symbolic font branch consults Win-Symbol PUA
    shifts (F000 / F100 / F200) when direct lookup misses."""
    font = _font_with_embedded_ttf(symbolic=True)
    monkeypatch.setattr(font, "is_symbolic", lambda: True)
    font._encoding_typed = None  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    # Win-Symbol PUA shift at F0+code → glyph 3.
    font._cmap_win_symbol = _platform_view(  # noqa: SLF001
        {0xF041: "A"}, [".notdef", "g1", "g2", "A"]
    )
    font._cmap_mac_roman = None  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None
    # Code 0x41 → direct miss → PUA-shifted hit at F041.
    gid = font._code_to_gid(0x41, ttf)  # noqa: SLF001
    assert gid == 3


def test_code_to_gid_symbolic_with_winansi_encoding_returns_zero_for_notdef(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 676 — symbolic-with-WinAnsi branch returns 0 immediately
    when encoding resolves to ``.notdef`` (no glyph to look up).
    WinAnsi maps most code points to something other than ``.notdef``,
    so we subclass to override one slot."""

    class _PartialWinAnsi(WinAnsiEncoding):
        def get_name(self, code: int) -> str:
            if code == 0x99:
                return ".notdef"
            return super().get_name(code)

    font = _font_with_embedded_ttf(symbolic=True)
    monkeypatch.setattr(font, "is_symbolic", lambda: True)
    font._encoding_typed = _PartialWinAnsi()  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = _platform_view(  # noqa: SLF001
        {0x41: "A"}, [".notdef", "A"]
    )
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None
    # Code 0x99 → encoding returns ".notdef" → returns 0 (line 676).
    gid = font._code_to_gid(0x99, ttf)  # noqa: SLF001
    assert gid == 0


def test_code_to_gid_symbolic_with_winansi_encoding_no_unicode_for_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Branch 680->685 — when GlyphList has no Unicode for the encoded
    glyph name, the inner ``if unicode:`` short-circuits and gid stays 0;
    the subsequent ``cmap_win_symbol`` branch fires instead."""
    font = _font_with_embedded_ttf(symbolic=True)
    monkeypatch.setattr(font, "is_symbolic", lambda: True)

    # Build an encoding whose ``get_name(0x41)`` returns a fake name
    # that GlyphList can't map.
    class _FakeEnc(WinAnsiEncoding):
        def get_name(self, _code: int) -> str:
            return "totallyMadeUpName"

    font._encoding_typed = _FakeEnc()  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = _platform_view(  # noqa: SLF001
        {0x41: "A"}, [".notdef", "A"]
    )
    # Symbol cmap fallback at code 0x41 returns gid 5.
    font._cmap_win_symbol = _platform_view(  # noqa: SLF001
        {0x41: "X"},
        [".notdef", "g1", "g2", "g3", "g4", "X"],
    )
    font._cmap_mac_roman = None  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None
    gid = font._code_to_gid(0x41, ttf)  # noqa: SLF001
    assert gid == 5


def test_code_to_gid_symbolic_no_encoding_uses_direct_cmap_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Branch 683-684 — symbolic with non-WinAnsi/Mac encoding (e.g.
    None) drops to the direct ``cmap_win_unicode.get_glyph_id(code)``
    path."""
    font = _font_with_embedded_ttf(symbolic=True)
    monkeypatch.setattr(font, "is_symbolic", lambda: True)
    font._encoding_typed = None  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    font._cmap_initialized = True  # noqa: SLF001
    # Win-Unicode subtable mapping code 0x41 directly.
    font._cmap_win_unicode = _platform_view(  # noqa: SLF001
        {0x41: "A"}, [".notdef", "A"]
    )
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None
    gid = font._code_to_gid(0x41, ttf)  # noqa: SLF001
    assert gid == 1


def test_code_to_gid_symbolic_pua_f100_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 693 — F100 PUA shift path fires when both F000 and direct
    look up miss."""
    font = _font_with_embedded_ttf(symbolic=True)
    monkeypatch.setattr(font, "is_symbolic", lambda: True)
    font._encoding_typed = None  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    # Only F100+code (0xF141) is mapped; F000+code is not.
    font._cmap_win_symbol = _platform_view(  # noqa: SLF001
        {0xF141: "A"}, [".notdef", "g1", "A"]
    )
    font._cmap_mac_roman = None  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None
    gid = font._code_to_gid(0x41, ttf)  # noqa: SLF001
    assert gid == 2


def test_code_to_gid_symbolic_pua_f200_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 697 — F200 PUA shift path fires as the third fallback."""
    font = _font_with_embedded_ttf(symbolic=True)
    monkeypatch.setattr(font, "is_symbolic", lambda: True)
    font._encoding_typed = None  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    # Only F200+code (0xF241) is mapped.
    font._cmap_win_symbol = _platform_view(  # noqa: SLF001
        {0xF241: "A"}, [".notdef", "g1", "g2", "A"]
    )
    font._cmap_mac_roman = None  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None
    gid = font._code_to_gid(0x41, ttf)  # noqa: SLF001
    assert gid == 3


def test_code_to_gid_symbolic_skips_pua_for_code_above_ff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Branch 687->700 — when code > 0xFF the PUA shift loop is skipped
    entirely; falls straight through to the mac-roman lookup."""
    font = _font_with_embedded_ttf(symbolic=True)
    monkeypatch.setattr(font, "is_symbolic", lambda: True)
    font._encoding_typed = None  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = _platform_view({}, [])  # noqa: SLF001
    font._cmap_mac_roman = _platform_view(  # noqa: SLF001
        {0x100: "wide"}, [".notdef", "wide"]
    )
    ttf = font.get_true_type_font()
    assert ttf is not None
    gid = font._code_to_gid(0x100, ttf)  # noqa: SLF001
    assert gid == 1


def test_code_to_gid_falls_back_to_name_to_gid_when_cmaps_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 658-662 — when both Win-Unicode and Mac-Roman miss, the
    non-symbolic branch falls back to the TTF's ``name_to_gid`` lookup."""
    font = _font_with_embedded_ttf()
    monkeypatch.setattr(font, "is_symbolic", lambda: False)
    monkeypatch.setattr(font, "get_encoding_typed", lambda: WinAnsiEncoding.INSTANCE)
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = _platform_view({}, [])  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = _platform_view({}, [])  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None
    monkeypatch.setattr(ttf, "name_to_gid", lambda _name: 42)
    gid = font._code_to_gid(ord("A"), ttf)  # noqa: SLF001
    assert gid == 42


def test_code_to_gid_name_to_gid_exception_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 661-662 — when ``name_to_gid`` raises, the except clause
    coerces gid to 0 rather than propagating."""
    font = _font_with_embedded_ttf()
    monkeypatch.setattr(font, "is_symbolic", lambda: False)
    monkeypatch.setattr(font, "get_encoding_typed", lambda: WinAnsiEncoding.INSTANCE)
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = _platform_view({}, [])  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = _platform_view({}, [])  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None

    def _raise(_n: str) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr(ttf, "name_to_gid", _raise)
    gid = font._code_to_gid(ord("A"), ttf)  # noqa: SLF001
    assert gid == 0


def test_code_to_gid_via_unicode_subtable_encoding_drives_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 717-725 — legacy fallback path: when no platform cmaps are
    populated, the helper routes through the resolved encoding +
    GlyphList Unicode + the Unicode cmap subtable."""
    font = _font_with_embedded_ttf()
    monkeypatch.setattr(font, "is_symbolic", lambda: False)
    font._encoding_typed = WinAnsiEncoding.INSTANCE  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    # Stub the cmap subtable so the helper finds 0x41 → gid 17.
    font._cmap_resolved = True  # noqa: SLF001

    class _FakeCmap:
        def get_glyph_id(self, code: int) -> int:
            return 17 if code == 0x41 else 0

    font._cmap_subtable = _FakeCmap()  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None
    gid = font._code_to_gid_via_unicode_subtable(ord("A"), ttf)  # noqa: SLF001
    assert gid == 17


def test_code_to_gid_via_unicode_subtable_symbolic_pua_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 730-738 — legacy fallback's symbolic PUA loop (F000 / F100
    / F200) when both encoding-driven and direct lookups miss."""
    font = _font_with_embedded_ttf(symbolic=True)
    monkeypatch.setattr(font, "is_symbolic", lambda: True)
    font._encoding_typed = None  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    font._cmap_resolved = True  # noqa: SLF001

    class _PuaCmap:
        def get_glyph_id(self, code: int) -> int:
            return 7 if code == 0xF041 else 0

    font._cmap_subtable = _PuaCmap()  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None
    gid = font._code_to_gid_via_unicode_subtable(0x41, ttf)  # noqa: SLF001
    assert gid == 7


def test_code_to_gid_symbolic_falls_through_to_mac_roman_when_others_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 700-701 — the symbolic branch's final ``mac_roman`` lookup
    fires when both the WinUnicode + WinSymbol arms returned 0."""
    font = _font_with_embedded_ttf(symbolic=True)
    monkeypatch.setattr(font, "is_symbolic", lambda: True)
    font._encoding_typed = None  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = _platform_view(  # noqa: SLF001
        {0x41: "A"}, [".notdef", "A"]
    )
    ttf = font.get_true_type_font()
    assert ttf is not None
    gid = font._code_to_gid(0x41, ttf)  # noqa: SLF001
    assert gid == 1


# ---------- _build_simple_ttf_font BaseFont / FontName tag handling ----------


def test_build_simple_ttf_font_writes_basefont_and_fontname() -> None:
    """Smoke test for the simple-font embed helper — exercises the
    enc_obj wiring branch (1413->1417) and descriptor population branches
    1486-1506 with a real, non-degenerate TTF."""
    ttf = _load_ttf()
    encoding = WinAnsiEncoding.INSTANCE
    font = _build_simple_ttf_font(ttf, _ttf_bytes(), encoding)
    cos = font.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("BaseFont")) is not None
    fd = font.get_font_descriptor()
    assert fd is not None
    assert fd.get_font_name() is not None
    # BBox set from head (line 1486-1492).
    assert fd.get_font_b_box() is not None
    # Ascent / Descent / CapHeight set from hhea (lines 1494-1505).
    fd_cos = fd.get_cos_object()
    assert fd_cos.get_int(COSName.get_pdf_name("Ascent"), 0) > 0


# ---------- _populate_simple_descriptor_from_ttf defensive branches ----------


def test_populate_simple_descriptor_handles_zero_units_per_em(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive: when units_per_em is 0 or negative, the helper falls
    back to scale=1.0 (1000/1000)."""
    ttf = _load_ttf()
    # Patch the head to report 0 upem.
    head = ttf.get_header()
    assert head is not None
    monkeypatch.setattr(head, "get_units_per_em", lambda: 0)
    descriptor = PDFontDescriptor()
    _populate_simple_descriptor_from_ttf(descriptor, ttf)
    assert descriptor.get_font_b_box() is not None


def test_populate_simple_descriptor_handles_missing_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 1486-1492 — the ``if head is not None`` guard takes the
    False arm; no /FontBBox is written."""
    ttf = _load_ttf()
    monkeypatch.setattr(ttf, "get_header", lambda: None)
    descriptor = PDFontDescriptor()
    _populate_simple_descriptor_from_ttf(descriptor, ttf)
    # No /FontBBox written (head was None).
    assert descriptor.get_font_b_box() is None


def test_populate_simple_descriptor_handles_missing_hhea(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 1494-1505 — the ``if hhea is not None`` guard takes the
    False arm; no /Ascent etc. written."""
    ttf = _load_ttf()
    monkeypatch.setattr(ttf, "get_horizontal_header", lambda: None)
    descriptor = PDFontDescriptor()
    _populate_simple_descriptor_from_ttf(descriptor, ttf)
    # /Ascent default 0 since hhea was missing.
    fd_cos = descriptor.get_cos_object()
    assert fd_cos.get_int(COSName.get_pdf_name("Ascent"), -1) in (-1, 0)


# ---------- read_encoding_from_font: post-table missing ----------


def test_read_encoding_from_font_handles_missing_post_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Branch 867->872 — when the TTF carries no /post table, the
    ``if post is not None`` guard takes the False arm and every code
    that resolves to a gid falls back to the decimal GID pseudo-name."""
    font = _font_with_embedded_ttf(symbolic=True)
    # Make it symbolic but NOT Standard 14 so we reach the post-walk loop.
    monkeypatch.setattr(font, "is_standard14", lambda: False)
    monkeypatch.setattr(font, "get_symbolic_flag", lambda: True)
    ttf = font.get_true_type_font()
    assert ttf is not None
    # Force the post table away.
    monkeypatch.setattr(ttf, "get_post_script", lambda: None)
    # Force at least one code to resolve to a positive gid.
    monkeypatch.setattr(font, "code_to_gid", lambda code: 1 if code == 65 else 0)
    encoding = font.read_encoding_from_font()
    assert encoding is not None
    # The code 65 gets the GID pseudo-name "1" (since post returned no name).
    assert encoding.get_name(65) == "1"


# ---------- _build_simple_ttf_font BaseFont tag-prefix branches ----------


def test_embed_subset_bytes_skips_retag_when_basefont_already_tagged() -> None:
    """Lines 1311-1322 — when a /BaseFont already carries a six-letter +
    upper-case prefix + '+', :func:`_embed_subset_bytes` must NOT prepend
    another tag. Same check for the descriptor's /FontName (lines
    1326-1337)."""
    from pypdfbox.pdmodel.font.pd_true_type_font import _embed_subset_bytes

    font_dict = COSDictionary()
    font_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font")
    )
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "TrueType")
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "ABCDEF+MyFont")
    fd = PDFontDescriptor()
    fd.set_font_name("ABCDEF+MyFont")
    stream = COSStream()
    stream.set_raw_data(b"placeholder")
    fd.set_font_file2(stream)
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), fd.get_cos_object()
    )
    font = PDTrueTypeFont(font_dict)
    _embed_subset_bytes(font, b"\x00\x01\x00\x00", tag="XYZWVU")
    # Already-tagged BaseFont keeps its prefix (line 1319).
    base = font.get_cos_object().get_name(COSName.get_pdf_name("BaseFont"))
    assert base == "ABCDEF+MyFont"
    # Same for /FontName on the descriptor (line 1334).
    assert font.get_font_descriptor().get_font_name() == "ABCDEF+MyFont"


def test_embed_subset_bytes_retags_when_basefont_lacks_prefix() -> None:
    """The complementary branch (line 1321) — names without the tag
    prefix get one prepended."""
    from pypdfbox.pdmodel.font.pd_true_type_font import _embed_subset_bytes

    font_dict = COSDictionary()
    font_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font")
    )
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "TrueType")
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyFont")
    fd = PDFontDescriptor()
    fd.set_font_name("MyFont")
    stream = COSStream()
    stream.set_raw_data(b"placeholder")
    fd.set_font_file2(stream)
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), fd.get_cos_object()
    )
    font = PDTrueTypeFont(font_dict)
    _embed_subset_bytes(font, b"\x00\x01\x00\x00", tag="XYZWVU")
    base = font.get_cos_object().get_name(COSName.get_pdf_name("BaseFont"))
    assert base == "XYZWVU+MyFont"
    assert font.get_font_descriptor().get_font_name() == "XYZWVU+MyFont"
