"""Wave 1275 — CFFType1Font.get_parser / set_encoding parity."""

from __future__ import annotations

from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font


def test_get_parser_caches_instance() -> None:
    font = CFFType1Font()
    p1 = font.get_parser()
    p2 = font.get_parser()
    assert p1 is p2  # cache hit on second call


def test_set_encoding_overrides_top_dict_value() -> None:
    font = CFFType1Font()
    # Default with no Top DICT loaded is None.
    assert font.get_encoding() is None
    font.set_encoding("CustomEnc")
    assert font.get_encoding() == "CustomEnc"


def test_set_encoding_accepts_list_shape() -> None:
    font = CFFType1Font()
    custom = [".notdef"] * 256
    custom[65] = "A"
    font.set_encoding(custom)
    enc = font.get_encoding()
    assert enc is custom
    # Predicate parity: now reports as custom (list) — not predefined.
    assert font.is_custom_encoding() is True
    assert font.is_standard_encoding() is False
