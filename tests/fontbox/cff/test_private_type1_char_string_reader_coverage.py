"""Coverage-boost tests for the default CID reader inner class
(``_CFFCIDDefaultReader``) in
``pypdfbox.fontbox.cff.private_type1_char_string_reader``.
"""
from __future__ import annotations

from pypdfbox.fontbox.cff.private_type1_char_string_reader import (
    PrivateType1CharStringReader,
    _CFFCIDDefaultReader,
)


class _StubCFFFont:
    """Minimal stand-in for a CFF font with a ``get_type2_char_string``
    accessor — records the requested GID and returns a sentinel."""

    def __init__(self) -> None:
        self.requests: list[int] = []
        self.notdef = object()

    def get_type2_char_string(self, gid: int) -> object:
        self.requests.append(gid)
        return self.notdef


def test_default_reader_is_subclass_of_interface() -> None:
    assert issubclass(_CFFCIDDefaultReader, PrivateType1CharStringReader)


def test_default_reader_always_returns_notdef_glyph() -> None:
    font = _StubCFFFont()
    reader = _CFFCIDDefaultReader(font)

    result = reader.get_type1_char_string("A")
    assert result is font.notdef
    assert font.requests == [0]


def test_default_reader_ignores_requested_name() -> None:
    """Mirror of the upstream "CID fonts always return gid 0" rule —
    the requested glyph name has zero effect on the result.
    """
    font = _StubCFFFont()
    reader = _CFFCIDDefaultReader(font)

    for name in ("A", "B", "ZapfDingbats", "", "/notdef"):
        reader.get_type1_char_string(name)

    assert font.requests == [0, 0, 0, 0, 0]


def test_default_reader_holds_reference_to_font() -> None:
    font = _StubCFFFont()
    reader = _CFFCIDDefaultReader(font)
    assert reader._font is font
