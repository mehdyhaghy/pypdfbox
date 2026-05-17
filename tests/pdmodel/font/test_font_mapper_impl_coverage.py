"""Coverage-boost tests for :mod:`pypdfbox.pdmodel.font.font_mapper_impl`.

Targets branches that the original ``test_font_mapper_impl.py`` leaves
unexplored: public wrapper methods, fallback-name flag combinations,
CID-font resolution paths, charset-match permutations, scoring,
substitute walks (comma / `-Regular` / hyphen-stripped), the barcode
heuristic, and the printer-debug helper.

All tests use hand-built fakes for :class:`FontInfo` /
:class:`FontProvider` plus a :class:`PDFontDescriptor` populated via the
public setters — no on-disk fonts required.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from pypdfbox.fontbox.cid_font_mapping import CIDFontMapping
from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.font_info import FontInfo
from pypdfbox.fontbox.font_provider import FontProvider
from pypdfbox.pdmodel.font.font_cache import FontCache
from pypdfbox.pdmodel.font.font_mapper_impl import (
    FontMapperImpl,
    get_post_script_names,
)
from pypdfbox.pdmodel.font.font_match import FontMatch
from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor

# ---------- fakes ----------


class _FakeCID:
    def __init__(self, registry: str, ordering: str) -> None:
        self._registry = registry
        self._ordering = ordering

    def get_registry(self) -> str:
        return self._registry

    def get_ordering(self) -> str:
        return self._ordering


class _FakeFontInfo(FontInfo):
    def __init__(  # noqa: PLR0913
        self,
        post_script_name: str,
        font_format: FontFormat,
        font: object,
        weight: int = 0,
        cid_system_info: Any = None,
        code_page_range1: int = 0,
        code_page_range2: int = 0,
    ) -> None:
        self._name = post_script_name
        self._format = font_format
        self._font = font
        self._weight = weight
        self._cid = cid_system_info
        self._cp1 = code_page_range1
        self._cp2 = code_page_range2

    def get_post_script_name(self) -> str:
        return self._name

    def get_format(self) -> FontFormat:
        return self._format

    def get_cid_system_info(self) -> Any:
        return self._cid

    def get_font(self) -> Any:
        return self._font

    def get_family_class(self) -> int:
        return 0

    def get_weight_class(self) -> int:
        return self._weight

    def get_code_page_range1(self) -> int:
        return self._cp1

    def get_code_page_range2(self) -> int:
        return self._cp2

    def get_mac_style(self) -> int:
        return 0

    def get_panose(self) -> Any:
        return None


class _FakeProvider(FontProvider):
    def __init__(self, fonts: list[FontInfo]) -> None:
        self._fonts = fonts
        self._cache = FontCache()

    def to_debug_string(self) -> str:
        return ""

    def get_font_info(self) -> list[FontInfo]:
        return list(self._fonts)

    def get_cache(self) -> FontCache:
        return self._cache


class _NoCacheProvider(FontProvider):
    """Provider without a ``get_cache`` method (forces fresh-cache branch)."""

    def __init__(self, fonts: list[FontInfo]) -> None:
        self._fonts = fonts

    def to_debug_string(self) -> str:
        return ""

    def get_font_info(self) -> list[FontInfo]:
        return list(self._fonts)


def _descriptor(
    *,
    serif: bool = False,
    italic: bool = False,
    fixed: bool = False,
    weight: float = 0.0,
    name: str | None = None,
    family: str | None = None,
) -> PDFontDescriptor:
    fd = PDFontDescriptor()
    fd.set_serif(serif)
    fd.set_italic(italic)
    fd.set_fixed_pitch(fixed)
    if weight:
        fd.set_font_weight(weight)
    if name is not None:
        fd.set_font_name(name)
    if family is not None:
        fd.set_font_family(family)
    return fd


# ---------- module-level helpers ----------


def test_get_post_script_names_returns_both_spellings() -> None:
    assert get_post_script_names("Arial-Black") == {"Arial-Black", "ArialBlack"}


def test_static_wrapper_post_script_names_matches() -> None:
    assert FontMapperImpl.get_post_script_names("Arial-Black") == {
        "Arial-Black",
        "ArialBlack",
    }


def test_is_fallback_font_loaded_false() -> None:
    assert FontMapperImpl.is_fallback_font_loaded() is False


# ---------- substitute table public APIs ----------


def test_add_substitutes_extends_list() -> None:
    impl = FontMapperImpl()
    impl.add_substitutes("Helvetica", ["MyExtra1", "MyExtra2"])
    subs = impl.get_substitutes("Helvetica")
    assert subs[-2:] == ["MyExtra1", "MyExtra2"]


def test_get_substitutes_handles_unknown_name() -> None:
    impl = FontMapperImpl()
    assert impl.get_substitutes("DoesNotExist") == []


def test_get_substitutes_strips_spaces() -> None:
    impl = FontMapperImpl()
    # "Helvetica" subs are seeded; the lookup tolerates spaces.
    assert impl.get_substitutes("Helvet ica")


# ---------- provider plumbing ----------


def test_get_font_cache_uses_provider_cache() -> None:
    impl = FontMapperImpl()
    info = _FakeFontInfo("ArialMT", FontFormat.TTF, object())
    impl.set_provider(_FakeProvider([info]))
    cache_a = impl.get_font_cache()
    cache_b = impl.get_font_cache()
    assert cache_a is cache_b  # same provider, same cache


def test_get_font_cache_returns_fresh_when_provider_lacks_get_cache() -> None:
    impl = FontMapperImpl()
    impl.set_provider(_NoCacheProvider([]))
    cache = impl.get_font_cache()
    assert isinstance(cache, FontCache)


def test_create_font_info_by_name_static_wrapper() -> None:
    info = _FakeFontInfo("Arial-Black", FontFormat.TTF, object())
    by_name = FontMapperImpl.create_font_info_by_name([info])
    assert "arial-black" in by_name
    assert "arialblack" in by_name


# ---------- _find_font branches ----------


def test_find_font_returns_none_for_none_name() -> None:
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([]))
    assert impl.find_font(FontFormat.TTF, None) is None


def test_find_font_box_font_returns_none_for_none() -> None:
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([]))
    assert impl.find_font_box_font(None) is None


def test_find_font_walks_hyphen_stripped_branch() -> None:
    sentinel = object()
    info = _FakeFontInfo("ArialBlack", FontFormat.TTF, sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    # Direct lookup misses; hyphen-stripped lookup hits.
    assert impl.find_font(FontFormat.TTF, "Arial-Black") is sentinel


def test_find_font_walks_comma_to_dash_branch() -> None:
    sentinel = object()
    info = _FakeFontInfo("Garamond-Bold", FontFormat.TTF, sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    # "Garamond,Bold" -> "Garamond-Bold".
    assert impl.find_font(FontFormat.TTF, "Garamond,Bold") is sentinel


def test_find_font_walks_comma_short_branch() -> None:
    sentinel = object()
    info = _FakeFontInfo("Garamond", FontFormat.TTF, sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    # "Garamond,Bold" -> after comma-to-dash miss, falls to short form.
    assert impl.find_font(FontFormat.TTF, "Garamond,Bold") is sentinel


def test_find_font_walks_regular_suffix_branch() -> None:
    sentinel = object()
    info = _FakeFontInfo("Foo-Regular", FontFormat.TTF, sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    assert impl.find_font(FontFormat.TTF, "Foo") is sentinel


def test_find_font_returns_none_when_no_branch_hits() -> None:
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([]))
    assert impl.find_font(FontFormat.TTF, "TotallyMissing") is None


def test_find_font_box_font_walks_pfb_ttf_otf() -> None:
    pfb_obj = object()
    ttf_obj = object()
    otf_obj = object()
    impl_pfb = FontMapperImpl()
    impl_pfb.set_provider(
        _FakeProvider([_FakeFontInfo("MyFont", FontFormat.PFB, pfb_obj)])
    )
    assert impl_pfb.find_font_box_font("MyFont") is pfb_obj
    impl_ttf = FontMapperImpl()
    impl_ttf.set_provider(
        _FakeProvider([_FakeFontInfo("MyFont", FontFormat.TTF, ttf_obj)])
    )
    assert impl_ttf.find_font_box_font("MyFont") is ttf_obj
    impl_otf = FontMapperImpl()
    impl_otf.set_provider(
        _FakeProvider([_FakeFontInfo("MyFont", FontFormat.OTF, otf_obj)])
    )
    assert impl_otf.find_font_box_font("MyFont") is otf_obj


# ---------- get_font wrapper + format mismatch ----------


def test_get_font_format_mismatch_returns_none() -> None:
    impl = FontMapperImpl()
    info = _FakeFontInfo("Foo", FontFormat.TTF, object())
    impl.set_provider(_FakeProvider([info]))
    # Request OTF for a TTF-formatted entry -> format guard returns None.
    assert impl.get_font(FontFormat.OTF, "Foo") is None


def test_get_font_public_wrapper_strips_subset() -> None:
    sentinel = object()
    impl = FontMapperImpl()
    impl.set_provider(
        _FakeProvider([_FakeFontInfo("Helvetica", FontFormat.TTF, sentinel)])
    )
    info = impl.get_font(FontFormat.TTF, "ABCDEF+Helvetica")
    assert info is not None
    assert info.get_font() is sentinel


# ---------- get_true_type_font / get_open_type_font / get_font_box_font ----------


def test_get_open_type_font_direct_match() -> None:
    sentinel = object()
    info = _FakeFontInfo("Foo", FontFormat.OTF, sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    mapping = impl.get_open_type_font("Foo", None)
    assert mapping is not None
    assert mapping.get_font() is sentinel
    assert mapping.is_fallback() is False


def test_get_open_type_font_missing_returns_none_without_last_resort() -> None:
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([]))
    assert impl.get_open_type_font("Nothing", None) is None


def test_get_font_box_font_direct_match() -> None:
    sentinel = object()
    info = _FakeFontInfo("Foo", FontFormat.PFB, sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    mapping = impl.get_font_box_font("Foo", None)
    assert mapping is not None
    assert mapping.get_font() is sentinel
    assert mapping.is_fallback() is False


def test_get_font_box_font_missing_returns_none() -> None:
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([]))
    assert impl.get_font_box_font("Nothing", None) is None


def test_get_true_type_font_fallback_via_descriptor() -> None:
    # Provider seeds "ArialMT"; "ArialMT" is a substitute for "Helvetica".
    sentinel = object()
    impl = FontMapperImpl()
    impl.set_provider(
        _FakeProvider([_FakeFontInfo("ArialMT", FontFormat.TTF, sentinel)])
    )
    fd = _descriptor()  # default => Helvetica fallback name
    mapping = impl.get_true_type_font("Unknown", fd)
    assert mapping is not None
    assert mapping.get_font() is sentinel
    assert mapping.is_fallback() is True


# ---------- get_cid_font branches ----------


def test_get_cid_font_otf_direct_match() -> None:
    sentinel = object()
    info = _FakeFontInfo("Foo", FontFormat.OTF, sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    mapping = impl.get_cid_font("Foo", None, None)
    assert isinstance(mapping, CIDFontMapping)
    assert mapping.is_cid_font() is True
    assert mapping.is_fallback() is False


def test_get_cid_font_ttf_direct_match() -> None:
    sentinel = object()
    info = _FakeFontInfo("Foo", FontFormat.TTF, sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    mapping = impl.get_cid_font("Foo", None, None)
    assert isinstance(mapping, CIDFontMapping)
    assert mapping.get_true_type_font() is sentinel
    assert mapping.is_cid_font() is False
    assert mapping.is_fallback() is False


def test_get_cid_font_missing_returns_none_without_last_resort() -> None:
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([]))
    assert impl.get_cid_font("Nothing", None, None) is None


def test_get_cid_font_scoring_path_picks_best_match() -> None:
    # Provider has a Japan1-tagged CID font; descriptor + Japan1 collection
    # should walk the scoring branch.
    sentinel = object()
    info = _FakeFontInfo(
        "MyCJK",
        FontFormat.OTF,
        sentinel,
        weight=400,
        cid_system_info=_FakeCID("Adobe", "Japan1"),
    )
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    fd = _descriptor(weight=400)
    cid = PDCIDSystemInfo("Adobe", "Japan1", 6)
    mapping = impl.get_cid_font("Unknown", fd, cid)
    assert mapping is not None
    assert mapping.get_true_type_font() is sentinel
    assert mapping.is_fallback() is True


def test_get_cid_font_scoring_skipped_for_non_adobe_collection() -> None:
    sentinel = object()
    info = _FakeFontInfo("Foo", FontFormat.OTF, sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    fd = _descriptor()
    cid = PDCIDSystemInfo("Custom", "Other", 0)
    # No matching base font; collection not in adobe set; no last-resort.
    assert impl.get_cid_font("Bar", fd, cid) is None


# ---------- _get_fallback_font_name branches ----------


def test_fallback_courier_bold_italic() -> None:
    fd = _descriptor(fixed=True, italic=True, name="Heavy")
    assert FontMapperImpl.get_fallback_font_name(fd) == "Courier-BoldOblique"


def test_fallback_courier_bold() -> None:
    fd = _descriptor(fixed=True, name="Bold")
    assert FontMapperImpl.get_fallback_font_name(fd) == "Courier-Bold"


def test_fallback_courier_italic_only() -> None:
    fd = _descriptor(fixed=True, italic=True)
    assert FontMapperImpl.get_fallback_font_name(fd) == "Courier-Oblique"


def test_fallback_courier_plain() -> None:
    fd = _descriptor(fixed=True)
    assert FontMapperImpl.get_fallback_font_name(fd) == "Courier"


def test_fallback_times_bold_italic() -> None:
    fd = _descriptor(serif=True, italic=True, name="Heavy")
    assert FontMapperImpl.get_fallback_font_name(fd) == "Times-BoldItalic"


def test_fallback_times_bold_only() -> None:
    fd = _descriptor(serif=True, name="MyBlack")
    assert FontMapperImpl.get_fallback_font_name(fd) == "Times-Bold"


def test_fallback_times_italic_only() -> None:
    fd = _descriptor(serif=True, italic=True)
    assert FontMapperImpl.get_fallback_font_name(fd) == "Times-Italic"


def test_fallback_times_roman_default() -> None:
    fd = _descriptor(serif=True)
    assert FontMapperImpl.get_fallback_font_name(fd) == "Times-Roman"


def test_fallback_helvetica_bold_italic() -> None:
    fd = _descriptor(italic=True, name="Bold")
    assert FontMapperImpl.get_fallback_font_name(fd) == "Helvetica-BoldOblique"


def test_fallback_helvetica_oblique() -> None:
    fd = _descriptor(italic=True)
    assert FontMapperImpl.get_fallback_font_name(fd) == "Helvetica-Oblique"


def test_fallback_descriptor_with_missing_font_name() -> None:
    """Descriptor whose ``get_font_name`` raises AttributeError still works."""

    class _BrokenName:
        def get_font_name(self) -> str:  # noqa: D401
            raise AttributeError("no font name")

        def is_fixed_pitch(self) -> bool:
            return False

        def is_italic(self) -> bool:
            return False

        def is_serif(self) -> bool:
            return False

    # Static call; we just need to exercise the except-AttributeError branch.
    name = FontMapperImpl.get_fallback_font_name(_BrokenName())  # type: ignore[arg-type]
    assert name == "Helvetica"


# ---------- charset-match branches ----------


def test_charset_match_empty_ordering_false() -> None:
    info = _FakeFontInfo("Foo", FontFormat.OTF, object())
    cid = PDCIDSystemInfo("Adobe", "", 0)
    assert FontMapperImpl.is_char_set_match(cid, info) is False


def test_charset_match_via_info_cid_system_info() -> None:
    info = _FakeFontInfo(
        "Foo",
        FontFormat.OTF,
        object(),
        cid_system_info=_FakeCID("Adobe", "Japan1"),
    )
    cid = PDCIDSystemInfo("Adobe", "Japan1", 6)
    assert FontMapperImpl.is_char_set_match(cid, info) is True


def test_charset_match_via_info_cid_mismatch() -> None:
    info = _FakeFontInfo(
        "Foo",
        FontFormat.OTF,
        object(),
        cid_system_info=_FakeCID("Adobe", "Korea1"),
    )
    cid = PDCIDSystemInfo("Adobe", "Japan1", 6)
    assert FontMapperImpl.is_char_set_match(cid, info) is False


def test_charset_match_gb1_via_code_page_range() -> None:
    info = _FakeFontInfo(
        "Foo", FontFormat.OTF, object(), code_page_range1=1 << 18
    )
    cid = PDCIDSystemInfo("Adobe", "GB1", 0)
    assert FontMapperImpl.is_char_set_match(cid, info) is True


def test_charset_match_cns1_via_code_page_range() -> None:
    info = _FakeFontInfo(
        "Foo", FontFormat.OTF, object(), code_page_range1=1 << 20
    )
    cid = PDCIDSystemInfo("Adobe", "CNS1", 0)
    assert FontMapperImpl.is_char_set_match(cid, info) is True


def test_charset_match_japan1_via_code_page_range() -> None:
    info = _FakeFontInfo(
        "Foo", FontFormat.OTF, object(), code_page_range1=1 << 17
    )
    cid = PDCIDSystemInfo("Adobe", "Japan1", 0)
    assert FontMapperImpl.is_char_set_match(cid, info) is True


def test_charset_match_korea1_wansung() -> None:
    info = _FakeFontInfo(
        "Foo", FontFormat.OTF, object(), code_page_range1=1 << 19
    )
    cid = PDCIDSystemInfo("Adobe", "Korea1", 0)
    assert FontMapperImpl.is_char_set_match(cid, info) is True


def test_charset_match_korea1_johab() -> None:
    info = _FakeFontInfo(
        "Foo", FontFormat.OTF, object(), code_page_range1=1 << 21
    )
    cid = PDCIDSystemInfo("Adobe", "Korea1", 0)
    assert FontMapperImpl.is_char_set_match(cid, info) is True


def test_charset_match_unknown_ordering_false() -> None:
    info = _FakeFontInfo(
        "Foo", FontFormat.OTF, object(), code_page_range1=0xFFFFFFFF
    )
    cid = PDCIDSystemInfo("Adobe", "Wat", 0)
    assert FontMapperImpl.is_char_set_match(cid, info) is False


def test_charset_match_malgun_semilight_mask() -> None:
    # ``MalgunGothic-Semilight`` strips the Japan/CN bits and so should
    # fail Japan1 charset even with the bit set.
    info = _FakeFontInfo(
        "MalgunGothic-Semilight",
        FontFormat.OTF,
        object(),
        code_page_range1=(1 << 17) | (1 << 19),
    )
    cid = PDCIDSystemInfo("Adobe", "Japan1", 0)
    assert FontMapperImpl.is_char_set_match(cid, info) is False
    # Korea1 wansung bit is preserved.
    korea_cid = PDCIDSystemInfo("Adobe", "Korea1", 0)
    assert FontMapperImpl.is_char_set_match(korea_cid, info) is True


# ---------- barcode heuristic ----------


def test_probably_barcode_font_family_starts_with_code() -> None:
    fd = _descriptor(family="Code128")
    assert FontMapperImpl.probably_barcode_font(fd) is True


def test_probably_barcode_font_family_contains_barcode() -> None:
    fd = _descriptor(family="MyBarcodeFont")
    assert FontMapperImpl.probably_barcode_font(fd) is True


def test_probably_barcode_font_name_starts_with_code() -> None:
    fd = _descriptor(name="Code39")
    assert FontMapperImpl.probably_barcode_font(fd) is True


def test_probably_barcode_font_name_contains_barcode() -> None:
    fd = _descriptor(name="SuperBarcodeSet")
    assert FontMapperImpl.probably_barcode_font(fd) is True


def test_probably_barcode_font_negative() -> None:
    fd = _descriptor(name="Helvetica", family="Helvetica")
    assert FontMapperImpl.probably_barcode_font(fd) is False


def test_probably_barcode_font_handles_attribute_error() -> None:
    class _Plain:
        pass

    assert FontMapperImpl.probably_barcode_font(_Plain()) is False  # type: ignore[arg-type]


# ---------- scoring + queue ----------


def test_score_weight_handles_attribute_error() -> None:
    class _NoWeight:
        pass

    info = _FakeFontInfo("Foo", FontFormat.TTF, object(), weight=400)
    match = FontMatch(info)
    FontMapperImpl._score_weight(match, _NoWeight(), info)  # type: ignore[arg-type]
    assert match.score == 0.0


def test_score_weight_adds_positive_when_weights_close() -> None:
    info = _FakeFontInfo("Foo", FontFormat.TTF, object(), weight=400)
    fd = _descriptor(weight=400)
    match = FontMatch(info)
    FontMapperImpl._score_weight(match, fd, info)
    # Distance 0 -> +1.0.
    assert match.score == pytest.approx(1.0)


def test_get_font_matches_returns_queue() -> None:
    sentinel = object()
    info = _FakeFontInfo("Foo", FontFormat.OTF, sentinel, weight=400)
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    fd = _descriptor(weight=400)
    queue = impl.get_font_matches(fd, None)
    assert queue
    assert queue[0].info.get_font() is sentinel


def test_get_font_matches_filters_by_charset() -> None:
    # Two infos: only the Japan1-tagged one survives the cid filter.
    keep_obj = object()
    skip_obj = object()
    keep = _FakeFontInfo(
        "Keep",
        FontFormat.OTF,
        keep_obj,
        weight=400,
        cid_system_info=_FakeCID("Adobe", "Japan1"),
    )
    skip = _FakeFontInfo(
        "Skip",
        FontFormat.OTF,
        skip_obj,
        weight=400,
        cid_system_info=_FakeCID("Adobe", "Korea1"),
    )
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([keep, skip]))
    fd = _descriptor(weight=400)
    cid = PDCIDSystemInfo("Adobe", "Japan1", 6)
    queue = impl.get_font_matches(fd, cid)
    fonts = {m.info.get_font() for m in queue}
    assert fonts == {keep_obj}


def test_print_matches_empty_returns_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert FontMapperImpl.print_matches([]) is None


def test_print_matches_logs_and_returns_first(
    caplog: pytest.LogCaptureFixture,
) -> None:
    a = FontMatch(_FakeFontInfo("A", FontFormat.TTF, object()))
    a.score = 5.0
    b = FontMatch(_FakeFontInfo("B", FontFormat.TTF, object()))
    b.score = 1.0
    with caplog.at_level(logging.DEBUG, logger="pypdfbox.pdmodel.font.font_mapper_impl"):
        best = FontMapperImpl.print_matches([a, b])
    assert best is a


# ---------- last-resort + provider auto-init ----------


def test_get_last_resort_font_returns_none() -> None:
    impl = FontMapperImpl()
    # Force the cache miss + early-return branch.
    assert impl._get_last_resort_font() is None  # type: ignore[attr-defined]


def test_get_last_resort_font_returns_cached_value() -> None:
    impl = FontMapperImpl()
    sentinel = object()
    impl._last_resort_font = sentinel  # type: ignore[attr-defined]
    assert impl._get_last_resort_font() is sentinel  # type: ignore[attr-defined]
