from __future__ import annotations

from pypdfbox.pdmodel.common.filespecification import PDEmbeddedFile


def test_wave349_creation_date_with_invalid_offset_hour_returns_none() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_creation_date("D:20260101000000+24'00'")

    assert embedded.get_creation_date() is None


def test_wave349_mod_date_with_invalid_offset_minute_returns_none() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_mod_date("D:20260101000000-05'60'")

    assert embedded.get_mod_date() is None
