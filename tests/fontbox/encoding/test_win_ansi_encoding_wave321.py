from __future__ import annotations

from pypdfbox.fontbox.encoding import WinAnsiEncoding


def test_wave321_bullet_fill_codes_exclude_explicit_bullet() -> None:
    enc = WinAnsiEncoding.INSTANCE

    assert enc.get_name(0o201) == "bullet"
    assert enc.is_bullet_fill_code(0o201)
    assert 0o201 in enc.get_bullet_fill_codes()

    assert enc.get_name(enc.EXPLICIT_BULLET_CODE) == "bullet"
    assert not enc.is_bullet_fill_code(enc.EXPLICIT_BULLET_CODE)
    assert enc.EXPLICIT_BULLET_CODE not in enc.get_bullet_fill_codes()


def test_wave321_bullet_fill_codes_are_immutable() -> None:
    fill_codes = WinAnsiEncoding.INSTANCE.get_bullet_fill_codes()

    assert isinstance(fill_codes, frozenset)
    assert fill_codes == WinAnsiEncoding.INSTANCE.get_bullet_fill_codes()


def test_wave321_explicit_code_distinguishes_table_entries() -> None:
    enc = WinAnsiEncoding.INSTANCE

    assert enc.is_explicit_code(0o101)
    assert enc.is_explicit_code(enc.EXPLICIT_BULLET_CODE)
    assert not enc.is_explicit_code(0o201)
    assert not enc.is_explicit_code(0)
