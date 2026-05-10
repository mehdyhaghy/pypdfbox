"""Wave 1273 round-out: ``PDFDocEncoding.set()`` module-level helper."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.pdfdoc_encoding import (
    decode_bytes,
    encode_bytes,
    get_char_code,
)
from pypdfbox.pdmodel.common.pdfdoc_encoding import (
    set as set_encoding,  # ``set`` shadows the builtin — alias on import.
)


def test_set_updates_both_directions() -> None:
    # Use the undefined slot ``0x7F`` (mapped to ``U+FFFD``) and a
    # private-use Unicode character that is not in the standard
    # PDFDocEncoding table, so we don't perturb real entries.
    private_char = ""  # Unicode Private Use Area
    original_char = decode_bytes(bytes([0x7F]))
    assert get_char_code(private_char) is None
    try:
        set_encoding(0x7F, private_char)
        assert decode_bytes(bytes([0x7F])) == private_char
        assert get_char_code(private_char) == 0x7F
        assert encode_bytes(private_char) == bytes([0x7F])
    finally:
        # Restore the original mapping so subsequent tests aren't
        # perturbed. The forward slot is restored; the reverse entry
        # for our throw-away private-use character is harmless to
        # leave in the table.
        set_encoding(0x7F, original_char)


def test_set_rejects_out_of_range_code() -> None:
    with pytest.raises(ValueError):
        set_encoding(-1, "A")
    with pytest.raises(ValueError):
        set_encoding(256, "A")


def test_set_rejects_multi_character_unicode() -> None:
    with pytest.raises(ValueError):
        set_encoding(0x7F, "ab")
    with pytest.raises(ValueError):
        set_encoding(0x7F, "")
