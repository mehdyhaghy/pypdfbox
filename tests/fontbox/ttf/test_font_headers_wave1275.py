"""Wave 1275 — FontHeaders: strict-snake gcid142 accessor parity."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.ttf_parser import FontHeaders


def test_get_non_otf_table_gcid142_default_none() -> None:
    h = FontHeaders()
    assert h.get_non_otf_table_gcid142() is None


def test_set_non_otf_gcid142_round_trips_through_strict_getter() -> None:
    h = FontHeaders()
    payload = b"\x00" * FontHeaders.BYTES_GCID
    h.set_non_otf_gcid142(payload)
    assert h.get_non_otf_table_gcid142() == payload
    # Old underscore-prefixed spellings still see the same payload —
    # the two name sets share the same underlying field.
    assert h.get_non_otf_table_gcid_142() == payload


def test_strict_and_underscore_setters_share_state() -> None:
    h = FontHeaders()
    h.set_non_otf_gcid_142(b"abc")
    assert h.get_non_otf_table_gcid142() == b"abc"
