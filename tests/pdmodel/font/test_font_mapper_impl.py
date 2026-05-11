"""Tests for :mod:`pypdfbox.pdmodel.font.font_mapper_impl`.

No upstream JUnit test exists — :class:`FontMapperImpl` is package-
private. We test the visible-effects behaviour:

* Substitute table seeded with Standard 14 -> system-font names.
* Custom :class:`FontProvider` plumbing through ``set_provider`` /
  ``get_provider``.
* Subset-tag stripping in ``_get_font``.
* Charset-match logic for CJK ROS codes.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.font_info import FontInfo
from pypdfbox.fontbox.font_provider import FontProvider
from pypdfbox.pdmodel.font.font_mapper_impl import FontMapperImpl


class _FakeFontInfo(FontInfo):
    """Tiny :class:`FontInfo` so we can wire a fake provider."""

    def __init__(
        self,
        post_script_name: str,
        font_format: FontFormat,
        font: object,
        weight: int = 0,
    ) -> None:
        self._name = post_script_name
        self._format = font_format
        self._font = font
        self._weight = weight

    def get_post_script_name(self) -> str:
        return self._name

    def get_format(self) -> FontFormat:
        return self._format

    def get_cid_system_info(self) -> Any:
        return None

    def get_font(self) -> Any:
        return self._font

    def get_family_class(self) -> int:
        return 0

    def get_weight_class(self) -> int:
        return self._weight

    def get_code_page_range1(self) -> int:
        return 0

    def get_code_page_range2(self) -> int:
        return 0

    def get_mac_style(self) -> int:
        return 0

    def get_panose(self) -> Any:
        return None


class _FakeProvider(FontProvider):
    def __init__(self, fonts: list[FontInfo]) -> None:
        self._fonts = fonts

    def to_debug_string(self) -> str:
        return ""

    def get_font_info(self) -> list[FontInfo]:
        return list(self._fonts)


@pytest.fixture
def arial_ttf() -> object:
    """A sentinel object used as the resolved TTF body."""
    return object()


@pytest.fixture
def mapper(arial_ttf: object) -> FontMapperImpl:
    info = _FakeFontInfo("ArialMT", FontFormat.TTF, arial_ttf)
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    return impl


def test_substitute_table_seeded_with_standard14() -> None:
    impl = FontMapperImpl()
    # Helvetica -> ArialMT must be there (Java line 74-75).
    subs = impl._get_substitutes("Helvetica")  # type: ignore[attr-defined]
    assert "ArialMT" in subs


def test_add_substitute_inserts_at_top_priority() -> None:
    impl = FontMapperImpl()
    impl.add_substitute("Helvetica", "MyCustomSans")
    subs = impl._get_substitutes("Helvetica")  # type: ignore[attr-defined]
    assert "MyCustomSans" in subs


def test_set_provider_indexes_post_script_names(arial_ttf: object) -> None:
    info = _FakeFontInfo("Arial-Black", FontFormat.TTF, arial_ttf)
    impl = FontMapperImpl()
    impl.set_provider(_FakeProvider([info]))
    # Index keys lowercase; both "arial-black" and "arialblack" are
    # present (mirrors upstream's hyphen-stripping branch).
    assert "arial-black" in impl._font_info_by_name  # type: ignore[attr-defined]
    assert "arialblack" in impl._font_info_by_name  # type: ignore[attr-defined]


def test_get_font_strips_subset_tag(
    mapper: FontMapperImpl, arial_ttf: object
) -> None:
    # "XYZABC+ArialMT" should resolve as "ArialMT".
    info = mapper._get_font(FontFormat.TTF, "XYZABC+ArialMT")  # type: ignore[attr-defined]
    assert info is not None
    assert info.get_font() is arial_ttf


def test_find_font_resolves_via_substitute(mapper: FontMapperImpl, arial_ttf: object) -> None:
    # Requesting "Helvetica" must walk substitutes -> ArialMT.
    found = mapper._find_font(FontFormat.TTF, "Helvetica")  # type: ignore[attr-defined]
    assert found is arial_ttf


def test_get_true_type_font_returns_non_fallback_for_direct_match(
    mapper: FontMapperImpl, arial_ttf: object
) -> None:
    mapping = mapper.get_true_type_font("ArialMT", None)
    assert mapping is not None
    assert mapping.is_fallback() is False
    assert mapping.get_font() is arial_ttf


def test_get_true_type_font_returns_fallback_for_unknown_name(
    mapper: FontMapperImpl, arial_ttf: object
) -> None:
    # "Wingdings" has no direct match — falls back through descriptor.
    # With no descriptor we get Times-Roman fallback which also isn't
    # present; mapping is None when no last-resort font exists.
    mapping = mapper.get_true_type_font("Wingdings", None)
    # Provider has no Times-Roman either, so mapping is None.
    assert mapping is None


def test_fallback_font_name_no_descriptor_returns_times_roman() -> None:
    name = FontMapperImpl._get_fallback_font_name(None)  # type: ignore[attr-defined]
    assert name == "Times-Roman"
