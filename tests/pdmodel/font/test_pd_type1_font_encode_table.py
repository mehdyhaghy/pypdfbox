"""``PDType1Font.encode`` bulk path (``str.translate`` over the
per-codepoint cache) must match the per-character resolution exactly."""

import copy

import pytest

from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

FontName = Standard14Fonts.FontName

_TEXT = (
    "Hello, World! (parens) \\ café €•— ÿ "
    "α一\U0001f600 \ud800 fiﬁ"
)


def _per_char(font: PDType1Font, text: str) -> bytes:
    return b"".join(PDSimpleFont.encode(font, ch) for ch in text)


@pytest.mark.parametrize("name", list(FontName), ids=lambda n: n.name)
def test_bulk_encode_matches_per_character(name: FontName) -> None:
    font = PDType1Font(name)
    expected = _per_char(PDType1Font(name), _TEXT)
    assert font.encode(_TEXT) == expected
    # Second call is served from the cache and is unchanged.
    assert font.encode(_TEXT) == expected
    assert font.encode("") == b""


def test_cache_entries_are_bytes_per_codepoint() -> None:
    font = PDType1Font(FontName.HELVETICA)
    font.encode("AB•")
    assert font._codepoint_encoding == {
        ord("A"): b"A",
        ord("B"): b"B",
        0x2022: b"\x95",
    }


def test_precached_entry_is_honoured() -> None:
    font = PDType1Font(FontName.HELVETICA)
    font._codepoint_encoding[ord("Z")] = b"\x01"
    assert font.encode("ZZ") == b"\x01\x01"


def test_cleared_or_replaced_cache_is_rebuilt() -> None:
    font = PDType1Font(FontName.HELVETICA)
    assert font.encode("AB") == b"AB"
    font._codepoint_encoding.clear()
    font._codepoint_encoding[ord("A")] = b"\x02"
    assert font.encode("A") == b"\x02"
    font._codepoint_encoding = {ord("A"): b"\x03"}
    assert font.encode("A") == b"\x03"


def test_copied_font_uses_its_own_cache() -> None:
    font = PDType1Font(FontName.HELVETICA)
    font.encode("A")
    clone = copy.copy(font)
    clone._codepoint_encoding = {}
    assert clone.encode("AB") == b"AB"
    assert set(clone._codepoint_encoding) == {ord("A"), ord("B")}


class _Boom(PDType1Font):
    def __init__(self, error: BaseException) -> None:
        super().__init__(FontName.HELVETICA)
        self.error = error

    def _encode_codepoint_uncached(self, ch: str) -> bytes:
        if ch == "x":
            raise self.error
        return super()._encode_codepoint_uncached(ch)


@pytest.mark.parametrize(
    "error",
    [KeyError("x"), IndexError("x"), ValueError("x")],
    ids=["KeyError", "IndexError", "ValueError"],
)
def test_resolution_errors_propagate_unchanged(error: BaseException) -> None:
    font = _Boom(error)
    with pytest.raises(type(error)) as info:
        font.encode("abxc")
    assert info.value is error
    # Characters before the failure were cached, the failing one was not.
    assert ord("a") in font._codepoint_encoding
    assert ord("x") not in font._codepoint_encoding
