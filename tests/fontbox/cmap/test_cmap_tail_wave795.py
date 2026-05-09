from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import BFCharRange, CMap, CMapManager, CMapParser
from pypdfbox.fontbox.cmap.cmap_parser import _increment


def test_use_cmap_updates_max_code_length_from_parent_cmap() -> None:
    parent = CMap("parent")
    parent.add_codespace_range(b"\x81\x02\x00", b"\x81\x02\xff")
    parent.add_base_font_character(b"\x81\x02\x03", "long")

    child = CMap("child")
    child.add_codespace_range(b"\x00", b"\x7f")

    child.use_cmap(parent)

    assert child.get_min_code_length() == 1
    assert child.get_max_code_length() == 3
    assert child.read_code(b"\x81\x02\x03") == (0x810203, 3)
    assert child.get_codes_from_unicode("long") == b"\x81\x02\x03"


def test_cmap_manager_returns_existing_cached_canonical_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached = CMap("Canonical-CMap")
    parsed = CMap("Canonical-CMap")

    CMapManager.clear_cache()
    CMapManager._CMAP_CACHE["Canonical-CMap"] = cached
    monkeypatch.setattr(CMapParser, "parse_predefined", staticmethod(lambda _name: parsed))

    try:
        assert CMapManager.get_predefined_cmap("Alias-CMap") is cached
    finally:
        CMapManager.clear_cache()


def test_cmap_parser_parse_unicode_rejects_missing_data() -> None:
    with pytest.raises(OSError, match="ToUnicode CMap data is missing"):
        CMapParser().parse_unicode_cmap(None)  # type: ignore[arg-type]


def test_increment_strict_overflow_and_non_strict_carry() -> None:
    strict_value = bytearray(b"\x00\xff")
    loose_value = bytearray(b"\x00\xff")

    assert _increment(strict_value, 1, True) is False
    assert strict_value == b"\x00\xff"

    assert _increment(loose_value, 1, False) is True
    assert loose_value == b"\x01\x00"


def test_bf_char_range_expands_multichar_target_and_hashes() -> None:
    first = BFCharRange(b"\x10", b"\x12", target="A\u0300")
    same = BFCharRange(b"\x10", b"\x12", target="A\u0300")

    assert [(entry.get_code(), entry.get_unicode()) for entry in first] == [
        (b"\x10", "A\u0300"),
        (b"\x11", "A\u0301"),
        (b"\x12", "A\u0302"),
    ]
    assert first == same
    assert hash(first) == hash(same)
    assert "BFCharRange(<10>-<12>" in repr(first)


def test_bf_char_range_rejects_missing_or_short_target_lists() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        BFCharRange(b"\x01", b"\x01")

    with pytest.raises(ValueError, match="too short"):
        BFCharRange(b"\x01", b"\x03", targets=["A", "B"])
