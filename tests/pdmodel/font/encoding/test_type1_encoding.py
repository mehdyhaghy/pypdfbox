"""Tests for :mod:`pypdfbox.pdmodel.font.encoding.type1_encoding`.

No upstream JUnit test exists for ``Type1Encoding``. We cover the three
constructor paths plus the inherited :class:`Encoding` accessors.
"""

from __future__ import annotations

from pypdfbox.pdmodel.font.encoding.type1_encoding import Type1Encoding


def test_empty_constructor_has_no_mappings() -> None:
    enc = Type1Encoding()
    assert enc.get_code(b"A") is None  # type: ignore[arg-type]


def test_encoding_name_matches_upstream() -> None:
    # Upstream returns "built-in (Type 1)" (Type1Encoding.java line 73).
    assert Type1Encoding().get_encoding_name() == "built-in (Type 1)"


def test_get_cos_object_returns_none() -> None:
    # Upstream returns null (Type1Encoding.java line 66-69).
    assert Type1Encoding().get_cos_object() is None


def test_from_font_box_copies_mapping() -> None:
    class _FakeEncoding:
        def get_code_to_name_map(self) -> dict[int, str]:
            return {65: "A", 66: "B", 67: "C"}

    enc = Type1Encoding.from_font_box(_FakeEncoding())
    assert enc.get_name(65) == "A"
    assert enc.get_name(66) == "B"
    assert enc.get_name(67) == "C"
    assert enc.get_code("A") == 65


def test_from_font_metrics_constructor() -> None:
    class _Metric:
        def __init__(self, code: int, name: str) -> None:
            self._code = code
            self._name = name

        def get_character_code(self) -> int:
            return self._code

        def get_name(self) -> str:
            return self._name

    class _Metrics:
        def get_char_metrics(self) -> list[_Metric]:
            return [_Metric(65, "A"), _Metric(66, "B"), _Metric(-1, "unencoded")]

    enc = Type1Encoding(font_metrics=_Metrics())
    assert enc.get_name(65) == "A"
    assert enc.get_name(66) == "B"
    # -1-coded glyphs are skipped (CHANGES.md note).
    assert enc.get_code("unencoded") is None
