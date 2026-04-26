from __future__ import annotations

from pypdfbox.fontbox.encoding import WinAnsiEncoding


def test_singleton_instance() -> None:
    assert WinAnsiEncoding.INSTANCE is WinAnsiEncoding.INSTANCE


def test_encoding_name() -> None:
    assert WinAnsiEncoding.INSTANCE.get_encoding_name() == "WinAnsiEncoding"


def test_basic_mappings() -> None:
    enc = WinAnsiEncoding.INSTANCE
    assert enc.get_name(65) == "A"
    assert enc.get_name(32) == "space"
    assert enc.get_code("space") == 32
    assert enc.get_code("A") == 65


def test_extra_pdf_spec_mappings() -> None:
    enc = WinAnsiEncoding.INSTANCE
    # PDF Appendix D additions
    assert enc.get_name(0o240) == "nbspace"
    assert enc.get_name(0o255) == "sfthyphen"


def test_unused_code_above_040_maps_to_bullet() -> None:
    enc = WinAnsiEncoding.INSTANCE
    # 0o201 has no explicit table entry — must default to bullet
    assert enc.get_name(0o201) == "bullet"
    # 0o217 is unused too
    assert enc.get_name(0o217) == "bullet"


def test_codes_at_or_below_040_are_not_filled() -> None:
    enc = WinAnsiEncoding.INSTANCE
    assert enc.get_name(0o40) == "space"  # explicit
    # 0 is below 0o41 and not in table — stays unmapped
    assert enc.get_name(0) == ".notdef"
    assert enc.get_name(1) == ".notdef"


def test_euro_symbol() -> None:
    enc = WinAnsiEncoding.INSTANCE
    assert enc.get_name(0o200) == "Euro"
    assert enc.get_code("Euro") == 0o200
