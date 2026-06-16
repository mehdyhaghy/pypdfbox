"""Wave 1399 — close residual partial branches across four font modules.

Targets:

* ``pd_true_type_font.py`` — 13 partials in glyph-width, glyph-path,
  symbolic ``_code_to_gid``, ``_code_to_gid_via_unicode_subtable``
  fallbacks, ``extract_cmap_table`` platform-skip arms, ``_CmapPlatformView``
  unknown-glyph branch, and the ``_BASE_FONT`` / ``/FontName`` tag-prefix
  paths in ``_embed_subset_bytes``.
* ``font_mapper_impl.py`` — 11 partials in ``get_open_type_font`` /
  ``get_cid_font`` ``font is None`` arms and the freshly-scanned-font
  cache walks inside ``_try_fetch_noto_cjk`` and ``_load_bundled_path``.
* ``pd_type0_font.py`` — 12 partials in get-path / encode-glyph /
  ``read_encoding`` / ``fetch_c_map_ucs2`` / accessor short-circuits and
  the ``_unicode_from_embedded_cmap`` is-embedded branch.
* ``encoding/dictionary_encoding.py`` — 3 partials in ``apply_differences``
  (empty differences arm) and ``set_base_encoding`` (COSName + plain-string
  resolved arms + Encoding-with-name).

Tests are behavioural: real ``LiberationSans-Regular.ttf`` for the
TTF-driven branches, fontTools-synthesised cmap subtables for the
extract-cmap arms, and monkeypatch-controlled stub ``FontProvider`` /
descendant fonts for the mapper / type0 arms.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.font import PDFontDescriptor, PDTrueTypeFont
from pypdfbox.pdmodel.font.encoding import (
    StandardEncoding,
    WinAnsiEncoding,
)
from pypdfbox.pdmodel.font.encoding.dictionary_encoding import DictionaryEncoding
from pypdfbox.pdmodel.font.font_mapper_impl import FontMapperImpl
from pypdfbox.pdmodel.font.pd_font_descriptor import FLAG_SYMBOLIC
from pypdfbox.pdmodel.font.pd_true_type_font import (
    _CmapPlatformView,
    _embed_subset_bytes,
)
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

_FIXTURE_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


# ---------- fixtures + helpers ----------------------------------------------


@pytest.fixture(scope="module")
def liberation_bytes() -> bytes:
    if not _FIXTURE_TTF.exists():
        pytest.skip(f"fixture font missing: {_FIXTURE_TTF}")
    return _FIXTURE_TTF.read_bytes()


def _embedded_font(font_bytes: bytes, *, symbolic: bool = False) -> PDTrueTypeFont:
    """Build a :class:`PDTrueTypeFont` carrying a fully embedded TTF."""
    font = PDTrueTypeFont()
    descriptor = PDFontDescriptor()
    if symbolic:
        descriptor.set_flags(FLAG_SYMBOLIC)
    stream = COSStream()
    stream.set_raw_data(font_bytes)
    descriptor.set_font_file2(stream)
    font.set_font_descriptor(descriptor)
    font.set_true_type_font(TrueTypeFont.from_bytes(font_bytes))
    return font


class _CmapSub:
    """Minimal stand-in for a fontTools cmap subtable."""

    def __init__(self, plat: int, enc: int, mapping: dict[int, str]) -> None:
        self.platformID = plat  # noqa: N815  # mirrors fontTools naming
        self.platEncID = enc  # noqa: N815
        self.cmap = mapping


class _FakeCmapTable:
    def __init__(self, tables: list[_CmapSub]) -> None:
        self.tables = tables


class _FakeTt:
    """Dict-like wrapper that exposes a ``cmap`` table and a glyph order."""

    def __init__(
        self, subtables: list[_CmapSub], glyph_order: list[str] | None = None
    ) -> None:
        self._cmap = _FakeCmapTable(subtables)
        self._glyph_order = glyph_order or [".notdef"]

    def __contains__(self, key: str) -> bool:
        return key == "cmap"

    def __getitem__(self, key: str) -> Any:
        if key == "cmap":
            return self._cmap
        raise KeyError(key)

    def getGlyphOrder(self) -> list[str]:  # noqa: N802  # fontTools name
        return list(self._glyph_order)


# ---------- pd_true_type_font: get_glyph_width 325->328 ---------------------


def test_get_glyph_width_falls_through_when_code_out_of_widths(
    liberation_bytes: bytes,
) -> None:
    """``idx < 0 or idx >= len(widths)`` falls through to font program."""
    font = _embedded_font(liberation_bytes)
    font.set_first_char(0x41)
    font.set_widths([500.0, 600.0])
    # code 0x41 hits widths[0] (covers 325->326). Code 0x50 is far outside,
    # forcing the fall-through arm 325->328.
    assert font.get_glyph_width(0x41) == 500.0
    width = font.get_glyph_width(0x50)
    # Falling back to the font program returns the hmtx advance — not 600.0
    # (which would be widths[15]) and not the placeholder 0.0.
    assert width != 600.0


# ---------- pd_true_type_font: get_path 411->413 ---------------------------


def test_get_glyph_path_falls_through_when_by_name_yields_empty_path(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the glyph name is non-empty but :func:`_draw_glyph_by_name`
    returns ``[]``, control flows to the GID-based fallback (411->413).

    Targets ``PDTrueTypeFont.get_glyph_path`` (not the by-name ``get_path``).
    """
    from pypdfbox.pdmodel.font import pd_true_type_font as ttf_mod

    font = _embedded_font(liberation_bytes)
    font._encoding_typed = WinAnsiEncoding.INSTANCE  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    # Force the by-name path to fail so the GID path runs.
    monkeypatch.setattr(ttf_mod, "_draw_glyph_by_name", lambda _ttf, _name: [])
    # 0x41 has a name (``"A"``) and a non-zero GID. by-name returns [],
    # 411 False arm leads to 413 (GID-based path).
    path = font.get_glyph_path(0x41)
    assert isinstance(path, list)


# ---------- pd_true_type_font: symbolic _code_to_gid 643->652 ---------------


def test_symbolic_code_to_gid_skips_win_unicode_when_absent(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Symbolic branch where ``_cmap_win_unicode is None`` and only
    ``_cmap_win_symbol`` resolves the code — exercises 643->652."""

    font = _embedded_font(liberation_bytes, symbolic=True)
    ttf = font.get_true_type_font()
    assert ttf is not None
    win_symbol = _CmapSub(3, 0, {0xF041: "A"})
    monkeypatch.setattr(ttf, "_tt", _FakeTt([win_symbol], [".notdef", "A"]))
    font._cmap_initialized = False  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001
    font.extract_cmap_table()
    assert font._cmap_win_unicode is None  # noqa: SLF001
    assert font._cmap_win_symbol is not None  # noqa: SLF001
    # code 0x41 + START_RANGE_F000 == 0xF041, so the F000 retry hits.
    gid = font._code_to_gid(0x41, ttf)  # noqa: SLF001
    assert gid == 1


def test_non_symbolic_code_to_gid_skips_win_unicode_when_absent(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-symbolic branch where ``_cmap_win_unicode is None`` so the
    name->unicode lookup at 643 is skipped — exercises 643->652."""

    font = _embedded_font(liberation_bytes)  # non-symbolic
    ttf = font.get_true_type_font()
    assert ttf is not None
    # Provide a Mac-Roman subtable only — no Win-Unicode.
    mac_roman = _CmapSub(1, 0, {0x41: "A"})
    monkeypatch.setattr(ttf, "_tt", _FakeTt([mac_roman], [".notdef", "A"]))
    font._cmap_initialized = False  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001
    # Force a real encoding so the 632/634 arms steer into 643.
    font._encoding_typed = WinAnsiEncoding.INSTANCE  # noqa: SLF001
    font._encoding_resolved = True  # noqa: SLF001
    font.extract_cmap_table()
    assert font._cmap_win_unicode is None  # noqa: SLF001
    assert font._cmap_mac_roman is not None  # noqa: SLF001
    gid = font._code_to_gid(0x41, ttf)  # noqa: SLF001
    # MacOSRomanEncoding maps "A" -> 0x41 which hits the Mac-Roman cmap.
    assert gid == 1


# ---------- pd_true_type_font: _code_to_gid_via_unicode_subtable -----------
# Branches: 724->730, 726->730, 728->730, 730->743, 735->743


def test_via_unicode_subtable_no_encoding_falls_through_to_direct_cmap(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``encoding is None``: skips lines 720-729 and goes straight to
    the direct-cmap lookup (the 730 arm)."""
    font = _embedded_font(liberation_bytes, symbolic=True)
    # Force the fallback path by stripping all platform views.
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001
    # Pretend the unicode cmap subtable returned an entry for 0x41.

    class _Cmap:
        def get_glyph_id(self, code: int) -> int:
            return 7 if code == 0x41 else 0

    monkeypatch.setattr(font, "_get_unicode_cmap", lambda _ttf: _Cmap())
    # Also force get_encoding_typed to return None (covers encoding=None arm).
    monkeypatch.setattr(font, "get_encoding_typed", lambda: None)
    font._encoding_resolved = True  # noqa: SLF001
    font._encoding_typed = None  # noqa: SLF001
    ttf = font.get_true_type_font()
    assert ttf is not None
    assert font._code_to_gid_via_unicode_subtable(0x41, ttf) == 7  # noqa: SLF001


def test_via_unicode_subtable_name_notdef_falls_through(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """encoding present, ``name == ".notdef"`` skips the by-name lookup
    (covers 724->730: name truthy + non-".notdef" branch is the False side)."""
    font = _embedded_font(liberation_bytes)
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001

    class _NotdefEncoding:
        def get_name(self, _code: int) -> str:
            return ".notdef"

    class _Cmap:
        def get_glyph_id(self, code: int) -> int:
            return 11 if code == 0x10 else 0

    monkeypatch.setattr(font, "_get_unicode_cmap", lambda _ttf: _Cmap())
    monkeypatch.setattr(font, "get_encoding_typed", lambda: _NotdefEncoding())
    ttf = font.get_true_type_font()
    assert ttf is not None
    # name == ".notdef" -> 724->730 false arm -> direct cmap returns 11.
    assert font._code_to_gid_via_unicode_subtable(0x10, ttf) == 11  # noqa: SLF001


def test_via_unicode_subtable_glyph_name_no_unicode_mapping_falls_through(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """encoding returns a name with no unicode mapping (e.g.
    ``"customGlyph"``) so 726->730 false arm runs."""
    font = _embedded_font(liberation_bytes)
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001

    class _CustomEncoding:
        def get_name(self, _code: int) -> str:
            # A glyph name that the bundled GlyphList does NOT recognise.
            return "totallyMadeUpGlyph"

    class _Cmap:
        def get_glyph_id(self, code: int) -> int:
            return 22 if code == 0x20 else 0

    monkeypatch.setattr(font, "_get_unicode_cmap", lambda _ttf: _Cmap())
    monkeypatch.setattr(font, "get_encoding_typed", lambda: _CustomEncoding())
    ttf = font.get_true_type_font()
    assert ttf is not None
    assert font._code_to_gid_via_unicode_subtable(0x20, ttf) == 22  # noqa: SLF001


def test_via_unicode_subtable_unicode_resolves_to_zero_gid(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """glyph-name → unicode succeeds, but the cmap returns 0; 728->730 false
    arm (gid == 0) routes to the direct-cmap line."""
    font = _embedded_font(liberation_bytes)
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001

    class _Cmap:
        def __init__(self) -> None:
            self._calls = 0

        def get_glyph_id(self, code: int) -> int:
            self._calls += 1
            # First call (via name->unicode 0x41) returns 0 — the False arm.
            # Second call (direct code lookup of 0x41) returns 33.
            return 33 if self._calls >= 2 else 0

    cmap = _Cmap()
    monkeypatch.setattr(font, "_get_unicode_cmap", lambda _ttf: cmap)
    monkeypatch.setattr(font, "get_encoding_typed", lambda: WinAnsiEncoding.INSTANCE)
    ttf = font.get_true_type_font()
    assert ttf is not None
    assert font._code_to_gid_via_unicode_subtable(0x41, ttf) == 33  # noqa: SLF001


def test_via_unicode_subtable_non_symbolic_returns_zero(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Direct-cmap returns 0 and ``is_symbolic()`` is False: 730->743 arm
    (skips the F000/F100/F200 retries) returns 0."""
    font = _embedded_font(liberation_bytes)  # non-symbolic
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001

    class _AllZeroCmap:
        def get_glyph_id(self, _code: int) -> int:
            return 0

    monkeypatch.setattr(font, "_get_unicode_cmap", lambda _ttf: _AllZeroCmap())
    monkeypatch.setattr(font, "get_encoding_typed", lambda: WinAnsiEncoding.INSTANCE)
    ttf = font.get_true_type_font()
    assert ttf is not None
    assert font._code_to_gid_via_unicode_subtable(0x99, ttf) == 0  # noqa: SLF001


def test_via_unicode_subtable_no_cmap_returns_zero(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_get_unicode_cmap`` returns None — the unicode-cmap arms are False.

    Wave 1576: the legacy fallback now mirrors upstream's non-symbolic
    ``post``-table last resort (``if (gid == 0) gid = nameToGID(name)``),
    so a code whose glyph name *is* in the font's ``post`` table resolves
    (``A`` -> the Liberation 'A' GID). To still exercise the
    return-zero exit we map code 0x01 -> ``.notdef`` (no glyph anywhere).
    """
    font = _embedded_font(liberation_bytes)
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001

    monkeypatch.setattr(font, "_get_unicode_cmap", lambda _ttf: None)
    monkeypatch.setattr(font, "get_encoding_typed", lambda: WinAnsiEncoding.INSTANCE)
    ttf = font.get_true_type_font()
    assert ttf is not None
    # 0x01 -> WinAnsi name is ".notdef"/None -> no post-table glyph -> 0.
    assert font._code_to_gid_via_unicode_subtable(0x01, ttf) == 0  # noqa: SLF001
    # 0x41 -> "A" -> post-table name_to_gid resolves (upstream last resort).
    assert font._code_to_gid_via_unicode_subtable(0x41, ttf) > 0  # noqa: SLF001


def test_via_unicode_subtable_symbolic_all_retries_miss(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``is_symbolic()`` True, every F000/F100/F200 retry misses — 735->743
    arm (the loop's normal exit) returns 0."""
    font = _embedded_font(liberation_bytes, symbolic=True)
    font._cmap_initialized = True  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001

    class _ZeroCmap:
        def get_glyph_id(self, _code: int) -> int:
            return 0

    monkeypatch.setattr(font, "_get_unicode_cmap", lambda _ttf: _ZeroCmap())
    monkeypatch.setattr(font, "get_encoding_typed", lambda: None)
    ttf = font.get_true_type_font()
    assert ttf is not None
    assert font._code_to_gid_via_unicode_subtable(0x99, ttf) == 0  # noqa: SLF001


# ---------- pd_true_type_font: extract_cmap_table skip arms ----------------
# 800->794, 807->794


def test_extract_cmap_table_skips_unsupported_windows_subtable(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Windows-platform cmap with an unsupported encoding (e.g. Shift-JIS,
    enc=2) falls through both inner ``if`` branches and the loop continues
    (800->794)."""
    font = _embedded_font(liberation_bytes)
    ttf = font.get_true_type_font()
    assert ttf is not None
    shift_jis = _CmapSub(3, 2, {0x41: "A"})  # PLATFORM_WINDOWS + Shift-JIS
    win_unicode = _CmapSub(3, 1, {0x42: "B"})  # also include a (3,1) so we have a
    # mappable result and exercise the skip arm in tandem.
    monkeypatch.setattr(
        ttf, "_tt", _FakeTt([shift_jis, win_unicode], [".notdef", "A", "B"])
    )
    font._cmap_initialized = False  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001
    font.extract_cmap_table()
    # Shift-JIS slot didn't capture anywhere; Win-Unicode did.
    assert font._cmap_win_unicode is not None  # noqa: SLF001
    assert font._cmap_win_symbol is None  # noqa: SLF001
    assert font._cmap_mac_roman is None  # noqa: SLF001


def test_extract_cmap_table_skips_mac_non_roman_subtable(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Mac-platform cmap with a non-Roman encoding (e.g. enc=4 / Arabic)
    falls through the Mac inner branch — exercises 807->794."""
    font = _embedded_font(liberation_bytes)
    ttf = font.get_true_type_font()
    assert ttf is not None
    mac_arabic = _CmapSub(1, 4, {0x41: "A"})  # PLATFORM_MACINTOSH but not Roman
    monkeypatch.setattr(ttf, "_tt", _FakeTt([mac_arabic], [".notdef", "A"]))
    font._cmap_initialized = False  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001
    font.extract_cmap_table()
    # The Mac-Arabic subtable does not land in any slot.
    assert font._cmap_win_unicode is None  # noqa: SLF001
    assert font._cmap_win_symbol is None  # noqa: SLF001
    assert font._cmap_mac_roman is None  # noqa: SLF001


# ---------- pd_true_type_font: _CmapPlatformView 1118->1116 ----------------


def test_cmap_platform_view_skips_glyph_when_name_missing_from_order() -> None:
    """``_chars`` contains a name that's *not* in ``glyph_order``; the
    ``gid is None`` arm continues the for loop (1118->1116)."""

    class _Sub:
        cmap = {0x41: "A", 0x42: "ghost"}  # "ghost" not in glyph_order

    view = _CmapPlatformView(_Sub(), glyph_order=[".notdef", "A"])
    assert view.get_glyph_id(0x41) == 1
    # "ghost" was filtered out — get_glyph_id falls back to default 0.
    assert view.get_glyph_id(0x42) == 0


# ---------- pd_true_type_font: _embed_subset_bytes BaseFont/FontName paths --
# 1316->1330, 1331->exit


def _make_descriptor_with_stream() -> PDFontDescriptor:
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_raw_data(b"placeholder")
    descriptor.set_font_file2(stream)
    return descriptor


def test_embed_subset_skips_basefont_when_missing() -> None:
    """``current_base`` empty: line 1316's ``if current_base:`` False arm
    short-circuits — covers 1316->1330 (skipping straight to FontName)."""
    cos = COSDictionary()
    descriptor = _make_descriptor_with_stream()
    descriptor.set_font_name("HelveticaNeue")

    class _Font:
        def get_name(self) -> str | None:
            return None

        def get_cos_object(self) -> COSDictionary:
            return cos

        def get_font_descriptor(self) -> PDFontDescriptor:
            return descriptor

    _embed_subset_bytes(_Font(), b"\x00\x01OTTO", "ABCDEF")
    # /BaseFont stays absent.
    assert cos.get_name("BaseFont") is None
    # /FontName got the prefix applied.
    assert descriptor.get_font_name() == "ABCDEF+HelveticaNeue"


def test_embed_subset_skips_fontname_when_descriptor_has_none() -> None:
    """``current_font_name`` empty/None: 1331's ``if`` False arm — covers
    1331->exit."""
    cos = COSDictionary()
    cos.set_name("BaseFont", "MyFont")
    descriptor = _make_descriptor_with_stream()
    # Descriptor has no /FontName entry — get_font_name returns None.

    class _Font:
        def get_name(self) -> str | None:
            return "MyFont"

        def get_cos_object(self) -> COSDictionary:
            return cos

        def get_font_descriptor(self) -> PDFontDescriptor:
            return descriptor

    _embed_subset_bytes(_Font(), b"\x00\x01OTTO", "ABCDEF")
    # /BaseFont got the tag prefix.
    assert cos.get_name("BaseFont") == "ABCDEF+MyFont"
    # /FontName stays None (skipped).
    assert descriptor.get_font_name() is None


# ---------- font_mapper_impl: stub provider scaffolding --------------------


class _StubProvider:
    """Bare-bones :class:`FontProvider` used by the mapper tests below."""

    def __init__(self) -> None:
        self._infos: list[Any] = []
        self.scanned: list[Any] = []

    def to_debug_string(self) -> str | None:
        return None

    def get_font_info(self) -> list[Any]:
        return list(self._infos)

    def scan_fonts(self, paths: list[Any]) -> None:
        self.scanned.extend(paths)


class _StubFontInfo:
    def __init__(
        self,
        name: str,
        fmt: FontFormat,
        font: Any,
        cid: Any | None = None,
        file: Any | None = None,
    ) -> None:
        self._name = name
        self._fmt = fmt
        self._font = font
        self._cid = cid
        self.file = file

    def get_post_script_name(self) -> str:
        return self._name

    def get_format(self) -> FontFormat:
        return self._fmt

    def get_cid_system_info(self) -> Any | None:
        return self._cid

    def get_font(self) -> Any:
        return self._font

    def get_family_class(self) -> int:
        return 0

    def get_weight_class(self) -> int:
        return -1

    def get_code_page_range1(self) -> int:
        return 0

    def get_code_page_range2(self) -> int:
        return 0

    def get_mac_style(self) -> int:
        return 0

    def get_panose(self) -> Any | None:
        return None


class _StubDescriptor:
    def __init__(self, name: str = "Helvetica") -> None:
        self._name = name

    def is_fixed_pitch(self) -> bool:
        return False

    def is_serif(self) -> bool:
        return False

    def is_italic(self) -> bool:
        return False

    def get_font_weight(self) -> float:
        return 0.0

    def get_font_name(self) -> str | None:
        return self._name

    def get_font_family(self) -> str | None:
        return None


# ---------- font_mapper_impl: get_open_type_font 346->348 ------------------


def test_get_open_type_font_fallback_name_hits_index() -> None:
    """``_find_font(OTF, fallback_name)`` returns a hit — the
    ``if otf is None`` False arm runs (346->348)."""
    impl = FontMapperImpl()
    sentinel = object()
    provider = _StubProvider()
    # Helvetica's fallback list includes ``ArialMT``; populate the
    # provider with an OTF named ArialMT so the fallback lookup
    # succeeds.
    provider._infos.append(_StubFontInfo("ArialMT", FontFormat.OTF, sentinel))
    impl.set_provider(provider)
    mapping = impl.get_open_type_font("__no_such_font__", _StubDescriptor())
    assert mapping is not None
    assert mapping.get_font() is sentinel
    assert mapping.is_fallback() is True


# ---------- font_mapper_impl: get_cid_font 398->405, 406->408 --------------


def test_get_cid_font_picks_descriptor_match_when_get_font_returns_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The scored queue's best entry has ``get_font() -> not None`` —
    covers 398->399 True arm (398->405 False)."""
    impl = FontMapperImpl()
    sentinel = object()

    class _Match:
        class _Info:
            @staticmethod
            def get_font() -> Any:
                return sentinel

        info = _Info()

        def __lt__(self, _other: object) -> bool:
            return True

    monkeypatch.setattr(impl, "_get_font_matches", lambda _d, _c: [_Match()])

    class _CSI:
        def get_registry(self) -> str:
            return "Adobe"

        def get_ordering(self) -> str:
            return "Japan1"

    mapping = impl.get_cid_font("Foo", _StubDescriptor(), _CSI())
    assert mapping is not None
    # Match goes through the TTF slot (CIDFontMapping(None, font, True)).
    assert mapping.get_true_type_font() is sentinel
    assert mapping.is_cid_font() is False


def test_get_cid_font_falls_through_when_match_returns_none_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Best match's ``get_font()`` returns ``None`` — 398->405 True arm
    falls through to the Noto auto-download attempt and last-resort font."""
    impl = FontMapperImpl()

    class _Match:
        class _Info:
            @staticmethod
            def get_font() -> Any:
                return None

        info = _Info()

        def __lt__(self, _other: object) -> bool:
            return True

    monkeypatch.setattr(impl, "_get_font_matches", lambda _d, _c: [_Match()])
    # Disable the Noto auto-download attempt so we surface the
    # last-resort font.
    monkeypatch.setattr(impl, "_try_fetch_noto_cjk", lambda _ord: None)

    class _CSI:
        def get_registry(self) -> str:
            return "Adobe"

        def get_ordering(self) -> str:
            return "Korea1"

    mapping = impl.get_cid_font("Foo", _StubDescriptor(), _CSI())
    # Last-resort path produces a CID mapping with a font.
    assert mapping is not None
    assert mapping.get_true_type_font() is not None


def test_get_cid_font_uses_noto_autodownload_when_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Noto auto-download returns a font — 406->407 True arm."""
    impl = FontMapperImpl()
    fetched = object()

    monkeypatch.setattr(impl, "_get_font_matches", lambda _d, _c: [])
    monkeypatch.setattr(impl, "_try_fetch_noto_cjk", lambda _ord: fetched)

    class _CSI:
        def get_registry(self) -> str:
            return "Adobe"

        def get_ordering(self) -> str:
            return "GB1"

    mapping = impl.get_cid_font("Foo", _StubDescriptor(), _CSI())
    assert mapping is not None
    # Noto fetch is routed through the TTF substitute slot.
    assert mapping.get_true_type_font() is fetched
    assert mapping.is_cid_font() is False


# ---------- font_mapper_impl: _try_fetch_noto_cjk 451-456 ------------------


def test_try_fetch_noto_cjk_stem_match_returns_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A freshly-scanned font whose key matches ``path.stem.lower()`` and
    whose ``get_font()`` returns a font — covers 451->452."""
    from pypdfbox.fontbox import cjk_loader

    impl = FontMapperImpl()
    sentinel = object()
    fake_path = Path("NotoSansJP-Regular.ttf")
    monkeypatch.setattr(
        cjk_loader, "ensure_language", lambda _ord: fake_path
    )
    provider = _StubProvider()
    provider._infos.append(
        _StubFontInfo("NotoSansJP-Regular", FontFormat.TTF, sentinel)
    )
    impl.set_provider(provider)
    out = impl._try_fetch_noto_cjk("Japan1")  # noqa: SLF001
    assert out is sentinel
    assert provider.scanned == [fake_path]


def test_try_fetch_noto_cjk_stem_match_falls_through_when_font_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stem key matches but ``get_font()`` returns ``None``: 451->453 arm
    (False) routes to the NotoSans regular search."""
    from pypdfbox.fontbox import cjk_loader

    impl = FontMapperImpl()
    fake_path = Path("NotoSansJP-Regular.ttf")
    monkeypatch.setattr(
        cjk_loader, "ensure_language", lambda _ord: fake_path
    )
    provider = _StubProvider()
    # First entry: stem matches but get_font returns None.
    provider._infos.append(
        _StubFontInfo("NotoSansJP-Regular", FontFormat.TTF, None)
    )
    # Second entry: notosans*regular fallback — get_font returns a sentinel.
    sentinel = object()
    provider._infos.append(
        _StubFontInfo("NotoSansCJK-Regular", FontFormat.TTF, sentinel)
    )
    impl.set_provider(provider)
    out = impl._try_fetch_noto_cjk("Japan1")  # noqa: SLF001
    assert out is sentinel


def test_try_fetch_noto_cjk_fallback_skips_when_font_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both the stem entry and a notosans-regular candidate return ``None``
    from ``get_font()`` — the function returns ``None`` (covers 454->455
    + 456->453 fall-throughs)."""
    from pypdfbox.fontbox import cjk_loader

    impl = FontMapperImpl()
    fake_path = Path("NotoSansJP-Regular.ttf")
    monkeypatch.setattr(
        cjk_loader, "ensure_language", lambda _ord: fake_path
    )
    provider = _StubProvider()
    # Stem matches but get_font returns None.
    provider._infos.append(
        _StubFontInfo("NotoSansJP-Regular", FontFormat.TTF, None)
    )
    # NotoSans-regular fallback also returns None.
    provider._infos.append(
        _StubFontInfo("NotoSansCJK-Regular", FontFormat.TTF, None)
    )
    impl.set_provider(provider)
    assert impl._try_fetch_noto_cjk("Japan1") is None  # noqa: SLF001


def test_try_fetch_noto_cjk_fallback_skips_non_matching_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fallback scan encounters a non-Noto, non-Regular entry — the
    454 False arm continues the loop (covers 454->453)."""
    from pypdfbox.fontbox import cjk_loader

    impl = FontMapperImpl()
    fake_path = Path("NotoSansJP-Regular.ttf")
    monkeypatch.setattr(
        cjk_loader, "ensure_language", lambda _ord: fake_path
    )
    sentinel = object()
    provider = _StubProvider()
    # Stem entry: get_font returns None.
    provider._infos.append(
        _StubFontInfo("NotoSansJP-Regular", FontFormat.TTF, None)
    )
    # Junk entry that the fallback should skip (covers 454 False arm).
    provider._infos.append(_StubFontInfo("Helvetica-Bold", FontFormat.TTF, sentinel))
    # Notosans-regular match that finally resolves.
    sentinel_noto = object()
    provider._infos.append(
        _StubFontInfo("NotoSansCJK-Regular", FontFormat.TTF, sentinel_noto)
    )
    impl.set_provider(provider)
    out = impl._try_fetch_noto_cjk("Japan1")  # noqa: SLF001
    assert out is sentinel_noto


# ---------- font_mapper_impl: _get_font fallback 529->531 -------------------


def test_find_font_uses_short_post_script_name_when_comma_present() -> None:
    """``post_script_name`` contains ``,`` and the short form resolves —
    covers 529->530 True arm."""
    impl = FontMapperImpl()
    sentinel = object()
    provider = _StubProvider()
    provider._infos.append(_StubFontInfo("ArialMT", FontFormat.TTF, sentinel))
    impl.set_provider(provider)
    # post_script_name "ArialMT,Bold" -> after replace(",","-") => not in
    # index, then short = "ArialMT" matches.
    out = impl._find_font(FontFormat.TTF, "ArialMT,Bold")  # noqa: SLF001
    assert out is sentinel


def test_find_font_falls_through_short_form_to_regular_suffix() -> None:
    """``post_script_name`` contains ``,`` and the short form does *not*
    resolve, falling through to the ``-Regular`` suffix retry — covers
    529->531 False arm."""
    impl = FontMapperImpl()
    sentinel = object()
    provider = _StubProvider()
    # No "UnknownShort" entry — but a "UnknownShort,Bold-Regular" entry
    # picks up via the suffix fallback.
    provider._infos.append(
        _StubFontInfo("UnknownShort,Bold-Regular", FontFormat.TTF, sentinel)
    )
    impl.set_provider(provider)
    out = impl._find_font(FontFormat.TTF, "UnknownShort,Bold")  # noqa: SLF001
    assert out is sentinel


# ---------- font_mapper_impl: _load_bundled_path 826, 837, 846, 848 ---------


def test_load_bundled_path_returns_none_when_indexed_font_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``info.get_font()`` returns ``None`` on the stem-keyed hit, the
    ``-regular`` strip also fails, and the file-scan fallback finds
    nothing — covers 826->828, 837->839, 846->844 fall-through."""
    impl = FontMapperImpl()
    fake_path = Path("UnindexedFont-Regular.ttf")
    provider = _StubProvider()
    # Stem-keyed entry: get_font returns None (826 False arm).
    provider._infos.append(
        _StubFontInfo(
            "UnindexedFont-Regular", FontFormat.TTF, None, file=Path("OtherPath.ttf")
        )
    )
    impl.set_provider(provider)
    monkeypatch.setattr(impl, "set_provider", lambda _p: None)
    out = impl._load_bundled_path(fake_path)  # noqa: SLF001
    assert out is None


def test_load_bundled_path_short_form_hit_returns_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stem entry returns None (get_font), short-form entry returns a
    sentinel — covers 837->838 True / 836 True arm."""
    impl = FontMapperImpl()
    fake_path = Path("LiberationSans-Regular.ttf")
    sentinel = object()
    provider = _StubProvider()
    # Stem entry exists but font is None.
    provider._infos.append(
        _StubFontInfo("LiberationSans-Regular", FontFormat.TTF, None)
    )
    # Short form (without -Regular suffix) hits.
    provider._infos.append(_StubFontInfo("LiberationSans", FontFormat.TTF, sentinel))
    impl.set_provider(provider)
    monkeypatch.setattr(impl, "set_provider", lambda _p: None)
    out = impl._load_bundled_path(fake_path)  # noqa: SLF001
    assert out is sentinel


def test_load_bundled_path_short_form_returns_none_falls_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Short-form entry's ``get_font()`` returns ``None`` — covers 837->839
    False arm; file-scan fallback then finds the path."""
    impl = FontMapperImpl()
    fake_path = Path("LiberationSans-Regular.ttf")
    sentinel = object()
    provider = _StubProvider()
    # Stem entry: font is None.
    provider._infos.append(
        _StubFontInfo("LiberationSans-Regular", FontFormat.TTF, None)
    )
    # Short-form entry: font is None too.
    provider._infos.append(_StubFontInfo("LiberationSans", FontFormat.TTF, None))
    # File-path fallback: matching path with a real font.
    provider._infos.append(
        _StubFontInfo("MysteryName", FontFormat.TTF, sentinel, file=fake_path)
    )
    impl.set_provider(provider)
    monkeypatch.setattr(impl, "set_provider", lambda _p: None)
    out = impl._load_bundled_path(fake_path)  # noqa: SLF001
    assert out is sentinel


def test_load_bundled_path_file_scan_skips_none_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The file-scan loop finds a candidate but ``get_font()`` returns
    ``None`` — covers 848->844 False arm (continue iteration); function
    falls off the end and returns ``None``."""
    impl = FontMapperImpl()
    fake_path = Path("Foo-Regular.ttf")
    provider = _StubProvider()
    # File-path matches but the font is None.
    provider._infos.append(
        _StubFontInfo("Foo-Regular", FontFormat.TTF, None, file=fake_path)
    )
    impl.set_provider(provider)
    monkeypatch.setattr(impl, "set_provider", lambda _p: None)
    out = impl._load_bundled_path(fake_path)  # noqa: SLF001
    assert out is None


# ---------- pd_type0_font: helpers ----------------------------------------


def _build_minimal_type0(
    *, encoding_name: str = "Identity-H", with_descendant: bool = True
) -> PDType0Font:
    """Construct a Type 0 font dict with a CIDFontType2 descendant."""
    type0_dict = COSDictionary()
    type0_dict.set_name("Type", "Font")
    type0_dict.set_name("Subtype", "Type0")
    type0_dict.set_name("BaseFont", "Identity-Sans")
    type0_dict.set_name("Encoding", encoding_name)
    if with_descendant:
        descendant_dict = COSDictionary()
        descendant_dict.set_name("Type", "Font")
        descendant_dict.set_name("Subtype", "CIDFontType2")
        descendant_dict.set_name("BaseFont", "Identity-Sans")
        # /CIDSystemInfo
        csi = COSDictionary()
        csi.set_string("Registry", "Adobe")
        csi.set_string("Ordering", "Identity")
        csi.set_int("Supplement", 0)
        descendant_dict.set_item("CIDSystemInfo", csi)
        arr = COSArray()
        arr.add(descendant_dict)
        type0_dict.set_item("DescendantFonts", arr)
    return PDType0Font(type0_dict)


# ---------- pd_type0_font: _unicode_from_embedded_cmap 565->596 ------------


def test_unicode_from_embedded_cmap_returns_none_when_descendant_not_type2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Descendant is *not* a :class:`PDCIDFontType2`: lines 723-726 short-
    circuit returning ``None``."""
    font = _build_minimal_type0()

    class _NotType2:
        pass

    monkeypatch.setattr(font, "get_descendant_font", lambda: _NotType2())
    assert font._unicode_from_embedded_cmap(0x41) is None  # noqa: SLF001


def test_unicode_from_embedded_cmap_returns_none_when_no_ttf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Type2 descendant but ``get_true_type_font() is None`` — lines
    724-726 hit the ``return None`` arm."""
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    font = _build_minimal_type0()

    class _NoTtf(PDCIDFontType2):
        def __init__(self) -> None:
            pass

        def get_true_type_font(self) -> Any:
            return None

    monkeypatch.setattr(font, "get_descendant_font", lambda: _NoTtf())
    assert font._unicode_from_embedded_cmap(0x41) is None  # noqa: SLF001


def test_to_unicode_falls_through_when_ucs2_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ucs2`` has unicode mappings but ``to_unicode`` returns None for
    ``code_to_cid(code)`` — covers 704->709 False arm."""

    class _Ucs2:
        def has_unicode_mappings(self) -> bool:
            return True

        def to_unicode(self, _cid: int) -> str | None:
            return None

    font = _build_minimal_type0()
    monkeypatch.setattr(font, "get_to_unicode_cmap", lambda: None)
    monkeypatch.setattr(font, "get_cmap", lambda: None)
    monkeypatch.setattr(font, "get_cmap_ucs2", lambda: _Ucs2())
    monkeypatch.setattr(font, "code_to_cid", lambda code: code)
    # Falls through to ``_unicode_from_embedded_cmap`` which has no
    # descendant TTF → returns None.
    assert font.to_unicode(0x41) is None


def test_unicode_from_embedded_cmap_returns_none_when_gid_zero(
    monkeypatch: pytest.MonkeyPatch, liberation_bytes: bytes
) -> None:
    """``code_to_gid`` resolves to 0 — line 741 early-return path."""
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    font = _build_minimal_type0()
    ttf = TrueTypeFont.from_bytes(liberation_bytes)

    class _Zero(PDCIDFontType2):
        def __init__(self) -> None:
            pass

        def get_true_type_font(self) -> Any:
            return ttf

        def is_embedded(self) -> bool:
            return True

        def code_to_gid(self, _cid: int) -> int:
            return 0

    monkeypatch.setattr(font, "get_descendant_font", lambda: _Zero())
    monkeypatch.setattr(font, "code_to_cid", lambda code: code)
    assert font._unicode_from_embedded_cmap(0x41) is None  # noqa: SLF001


def test_unicode_from_embedded_cmap_uses_non_embedded_descendant_cid(
    monkeypatch: pytest.MonkeyPatch, liberation_bytes: bytes
) -> None:
    """Descendant ``is_embedded()`` returns False — code_to_cid path
    (734-737) runs in place of code_to_gid (732-733)."""
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    font = _build_minimal_type0()
    ttf = TrueTypeFont.from_bytes(liberation_bytes)

    class _NotEmbedded(PDCIDFontType2):
        def __init__(self) -> None:
            self.calls: list[str] = []

        def get_true_type_font(self) -> Any:
            return ttf

        def is_embedded(self) -> bool:
            return False

        def code_to_cid(self, code: int) -> int:
            self.calls.append(f"cid({code})")
            return code

    stub = _NotEmbedded()
    monkeypatch.setattr(font, "get_descendant_font", lambda: stub)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code)
    # Returns None (no embedded TTF unicode mapping for synthesised GID 0),
    # but the call shape exercises 734-737.
    font._unicode_from_embedded_cmap(0x41)  # noqa: SLF001
    assert "cid(65)" in stub.calls


# ---------- pd_type0_font: read_code 741 -----------------------------------


def test_read_code_falls_back_to_single_byte_without_cmap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``get_cmap()`` returns None — the fallback ``(byte, 1)`` arm runs."""
    font = _build_minimal_type0()
    monkeypatch.setattr(font, "get_cmap", lambda: None)
    code, consumed = font.read_code(b"\xAB", 0)
    assert (code, consumed) == (0xAB, 1)


# ---------- pd_type0_font: get_path/get_normalized_path None branches -----
# 853, 857, 870, 874


def test_get_path_returns_empty_list_when_no_descendant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``get_descendant_font() is None`` short-circuits to ``[]``."""
    font = _build_minimal_type0()
    monkeypatch.setattr(font, "get_descendant_font", lambda: None)
    assert font.get_path(0x41) == []


def test_get_path_returns_empty_when_descendant_lacks_get_glyph_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Descendant present but ``get_glyph_path`` non-callable — line 856."""
    font = _build_minimal_type0()

    class _NoGlyphPath:
        get_glyph_path = "not callable"

    monkeypatch.setattr(font, "get_descendant_font", lambda: _NoGlyphPath())
    assert font.get_path(0x41) == []


def test_get_normalized_path_returns_empty_when_no_descendant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _build_minimal_type0()
    monkeypatch.setattr(font, "get_descendant_font", lambda: None)
    assert font.get_normalized_path(0x41) == []


def test_get_normalized_path_returns_empty_when_descendant_lacks_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _build_minimal_type0()

    class _NoNorm:
        get_normalized_path = None

    monkeypatch.setattr(font, "get_descendant_font", lambda: _NoNorm())
    assert font.get_normalized_path(0x41) == []


def test_get_normalized_path_delegates_to_descendant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy-path: descendant has ``get_normalized_path`` callable — line 874."""
    font = _build_minimal_type0()
    expected = [("moveTo", (0.0, 0.0)), ("closePath", ())]

    class _Norm:
        def get_normalized_path(self, cid: int) -> list[tuple[Any, ...]]:
            assert cid == 0x41
            return list(expected)

    monkeypatch.setattr(font, "get_descendant_font", lambda: _Norm())
    monkeypatch.setattr(font, "code_to_cid", lambda code: code)
    assert font.get_normalized_path(0x41) == expected


def test_get_gsub_data_delegates_to_internal_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``get_gsub_data`` delegates to ``_get_gsub_table`` — line 886."""
    sentinel = object()
    font = _build_minimal_type0()
    monkeypatch.setattr(font, "_get_gsub_table", lambda: sentinel)
    assert font.get_gsub_data() is sentinel


def test_get_standard14_width_raises_not_implemented() -> None:
    """``get_standard14_width`` always raises (Type 0 has no Standard14
    width table) — lines 930-931."""
    font = _build_minimal_type0()
    with pytest.raises(NotImplementedError):
        font.get_standard14_width(0x41)


def test_pd_type0_subset_skips_basefont_rename_when_name_missing(
    liberation_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``self.get_name()`` returns ``None``: 1475 False arm — covers
    1475->1489 by short-circuiting straight to the cache invalidation."""
    font = PDType0Font.load(None, liberation_bytes)
    # Remove /BaseFont so get_name() returns None.
    font.get_cos_object().remove_item(COSName.get_pdf_name("BaseFont"))
    assert font.get_name() is None
    font.add_to_subset(0x41)
    out = font.subset(prefix="ABCDEF")
    # Subset still produced bytes; /BaseFont stays missing.
    assert isinstance(out, bytes)
    assert font.get_cos_object().get_name("BaseFont") is None


def test_pd_type0_load_dispatches_to_load_ttf(liberation_bytes: bytes) -> None:
    """``PDType0Font.load`` is a thin wrapper around ``load_ttf`` — line 1570."""
    font = PDType0Font.load(None, liberation_bytes)
    assert isinstance(font, PDType0Font)
    assert font.get_descendant_font() is not None


def test_pd_type0_load_vertical_swaps_to_identity_v(
    liberation_bytes: bytes,
) -> None:
    """``load_vertical`` builds a Type 0 font with ``/Encoding /Identity-V``
    — lines 1592-1604."""
    font = PDType0Font.load_vertical(None, liberation_bytes)
    assert isinstance(font, PDType0Font)
    cos = font.get_cos_object()
    assert cos.get_name("Encoding") == "Identity-V"
    assert font.is_vertical() is True


# ---------- pd_type0_font: _apply_ligature_run branches --------------------


def test_apply_ligature_run_skips_out_of_range_gid() -> None:
    """``gid`` is outside ``glyph_order``: 565 False arm — replacement
    stays equal to gid, no lookup happens (covers 565->596)."""

    class _Lookup:
        SubTable: list[Any] = []

    glyph_order = [".notdef", "a"]
    name_to_gid = {".notdef": 0, "a": 1}
    out = PDType0Font._apply_ligature_run(  # noqa: SLF001
        _Lookup(), [99, 1], glyph_order, name_to_gid
    )
    # gid 99 is out of range; lookup is skipped; replacement == 99.
    assert out == [99, 1]


def test_apply_ligature_run_continues_when_lig_glyph_unmapped() -> None:
    """The matching ligature's ``LigGlyph`` is not in ``name_to_gid``;
    the inner ``if new_gid is not None`` False arm leaves the subtable
    loop running (covers 592->567)."""

    class _Lig:
        def __init__(self, comps: list[str], lig: str) -> None:
            self.Component = comps  # noqa: N815  # mirrors fontTools
            self.LigGlyph = lig  # noqa: N815

    class _ResolvableSub:
        # First subtable lacks the lig output in name_to_gid (forces 592 False).
        ligatures = {"a": [_Lig(["b"], "ghost")]}

    class _RealSub:
        # Second subtable has the real ligature — succeeds.
        ligatures = {"a": [_Lig(["b"], "ab")]}

    class _Lookup:
        SubTable = [_ResolvableSub(), _RealSub()]

    glyph_order = [".notdef", "a", "b", "ab"]
    name_to_gid = {".notdef": 0, "a": 1, "b": 2, "ab": 3}
    out = PDType0Font._apply_ligature_run(  # noqa: SLF001
        _Lookup(), [1, 2], glyph_order, name_to_gid
    )
    # First subtable: best_lig_name="ghost", not in name_to_gid -> continue.
    # Second subtable: best_lig_name="ab" -> replaces both inputs with GID 3.
    assert out == [3]


# ---------- pd_type0_font: get_cmap_lookup paths 886, 903 ------------------


def test_get_cmap_lookup_returns_none_when_descendant_not_type2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Descendant is not a CIDFontType2 — short-circuit (line 900)."""
    font = _build_minimal_type0()

    class _Other:
        pass

    monkeypatch.setattr(font, "get_descendant_font", lambda: _Other())
    assert font.get_cmap_lookup() is None


def test_get_cmap_lookup_returns_none_when_no_ttf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Type2 descendant but no embedded TTF — line 903."""
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    font = _build_minimal_type0()

    class _NoTtf(PDCIDFontType2):
        def __init__(self) -> None:
            pass

        def get_true_type_font(self) -> Any:
            return None

    monkeypatch.setattr(font, "get_descendant_font", lambda: _NoTtf())
    assert font.get_cmap_lookup() is None


# ---------- pd_type0_font: has_explicit_width 953 --------------------------


def test_has_explicit_width_returns_false_when_no_descendant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``descendant is None`` short-circuits (line 948-949)."""
    font = _build_minimal_type0()
    monkeypatch.setattr(font, "get_descendant_font", lambda: None)
    assert font.has_explicit_width(0x41) is False


def test_has_explicit_width_returns_false_when_has_method_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Descendant has no callable ``has_explicit_width`` (line 951-952)."""
    font = _build_minimal_type0()

    class _NoHas:
        has_explicit_width = 42  # not callable

    monkeypatch.setattr(font, "get_descendant_font", lambda: _NoHas())
    assert font.has_explicit_width(0x41) is False


def test_has_explicit_width_delegates_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Descendant supplies ``has_explicit_width`` — line 953 True arm."""
    font = _build_minimal_type0()

    class _Has:
        def has_explicit_width(self, code: int) -> bool:
            return code == 0x41

    monkeypatch.setattr(font, "get_descendant_font", lambda: _Has())
    assert font.has_explicit_width(0x41) is True
    assert font.has_explicit_width(0x42) is False


# ---------- pd_type0_font: read_encoding / fetch_c_map_ucs2 970-973, 986-987


def test_read_encoding_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both ``get_cmap`` and ``get_cmap_ucs2`` raise — they're suppressed
    (lines 970-973)."""
    font = _build_minimal_type0()

    def _boom() -> None:
        raise RuntimeError("forced")

    monkeypatch.setattr(font, "get_cmap", _boom)
    monkeypatch.setattr(font, "get_cmap_ucs2", _boom)
    # No exception — both ``with suppress(Exception)`` arms run.
    font.read_encoding()


def test_fetch_c_map_ucs2_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """``get_cmap_ucs2`` raises — suppressed (lines 986-987)."""
    font = _build_minimal_type0()

    def _boom() -> None:
        raise RuntimeError("forced")

    monkeypatch.setattr(font, "get_cmap_ucs2", _boom)
    font.fetch_c_map_ucs2()


# ---------- pd_type0_font: get_c_map / get_c_map_ucs2 aliases 997, 1004 ----


def test_get_c_map_alias_returns_same_object(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()
    font = _build_minimal_type0()
    monkeypatch.setattr(font, "get_cmap", lambda: sentinel)
    assert font.get_c_map() is sentinel


def test_get_c_map_ucs2_alias_returns_same_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    font = _build_minimal_type0()
    monkeypatch.setattr(font, "get_cmap_ucs2", lambda: sentinel)
    assert font.get_c_map_ucs2() is sentinel


# ---------- pd_type0_font: encode_glyph_id 1125->1127 ----------------------


def test_encode_glyph_id_falls_back_to_two_byte_when_no_descendant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``descendant is None`` — line 1127 BE encoding fallback runs."""
    font = _build_minimal_type0()
    monkeypatch.setattr(font, "get_descendant_font", lambda: None)
    assert font.encode_glyph_id(0x1234) == b"\x12\x34"


def test_encode_glyph_id_falls_back_when_descendant_lacks_encoder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Descendant has no callable ``encode_glyph_id`` — line 1127 runs."""
    font = _build_minimal_type0()

    class _NoEncoder:
        encode_glyph_id = "not callable"

    monkeypatch.setattr(font, "get_descendant_font", lambda: _NoEncoder())
    assert font.encode_glyph_id(0xFFFF) == b"\xff\xff"


def test_encode_glyph_id_uses_descendant_encoder_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Descendant supplies an ``encode_glyph_id`` callable — 1125->1126."""
    font = _build_minimal_type0()

    class _WithEnc:
        def encode_glyph_id(self, gid: int) -> bytes:
            return bytes([gid & 0xFF, (gid >> 8) & 0xFF, 0xAB])

    monkeypatch.setattr(font, "get_descendant_font", lambda: _WithEnc())
    assert font.encode_glyph_id(0x1234) == b"\x34\x12\xab"


# ---------- pd_type0_font: get_path with valid descendant exercises 1475 ---


def test_get_path_delegates_to_descendant_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Coverage for the happy path 855 / 857 True arm — descendant returns
    a non-empty glyph path."""
    font = _build_minimal_type0()
    expected = [("moveTo", (0.0, 0.0)), ("closePath", ())]

    class _Good:
        def get_glyph_path(self, _cid: int) -> list[tuple[Any, ...]]:
            return list(expected)

    monkeypatch.setattr(font, "get_descendant_font", lambda: _Good())
    monkeypatch.setattr(font, "code_to_cid", lambda code: code)
    assert font.get_path(0x41) == expected


# ---------- dictionary_encoding: apply_differences 125->exit ---------------


def test_apply_differences_with_no_differences_array_is_noop() -> None:
    """``/Differences`` absent: line 125's ``if diffs is not None`` False
    arm short-circuits (125->exit)."""
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    # No /Differences entry on the underlying dict.
    assert enc.get_differences_array() is None
    enc.apply_differences()
    # After the no-op, the differences view is empty.
    assert enc.get_differences() == {}


def test_apply_differences_with_real_array_repopulates_differences() -> None:
    """Sanity coverage for the True arm of 125 — ``apply_differences``
    re-walks an existing /Differences array."""
    diffs = COSArray()
    diffs.add(COSInteger.get(65))
    diffs.add(COSName.get_pdf_name("Alpha"))
    diffs.add(COSName.get_pdf_name("Beta"))
    enc = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding"),
        differences=diffs,
    )
    # Mutate via the cached helper to confirm idempotency.
    enc.apply_differences()
    assert enc.get_differences() == {65: "Alpha", 66: "Beta"}


# ---------- dictionary_encoding: set_base_encoding branches ----------------
# Lines 224, 231-234


def test_set_base_encoding_with_encoding_lacking_name_removes_entry() -> None:
    """``value`` is an :class:`Encoding` whose ``get_encoding_name`` returns
    ``None`` — line 224 removes /BaseEncoding."""

    class _Anon(StandardEncoding):
        def get_encoding_name(self) -> str | None:  # type: ignore[override]
            return None

    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.get_cos_object().get_name("BaseEncoding") == "WinAnsiEncoding"
    enc.set_base_encoding(_Anon())
    # /BaseEncoding was removed (line 224).
    assert enc.get_cos_object().get_name("BaseEncoding") is None
    assert isinstance(enc.get_base_encoding(), _Anon)


def test_set_base_encoding_with_cos_name_resolves_and_rebuilds() -> None:
    """``value`` is a :class:`COSName` — lines 227-233 run, /BaseEncoding
    is stored, base encoding is rebuilt."""
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    new_base = COSName.get_pdf_name("MacRomanEncoding")
    enc.set_base_encoding(new_base)
    assert enc.get_cos_object().get_name("BaseEncoding") == "MacRomanEncoding"
    base = enc.get_base_encoding()
    assert base is not None
    assert base.get_encoding_name() == "MacRomanEncoding"


def test_set_base_encoding_with_invalid_cos_name_raises() -> None:
    """Invalid encoding name as :class:`COSName` — raises ``ValueError``
    (line 229-230)."""
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    with pytest.raises(ValueError, match="Invalid encoding"):
        enc.set_base_encoding(COSName.get_pdf_name("NotARealEncoding"))
