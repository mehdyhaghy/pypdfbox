"""Wave 1275 — small parity misses on the TTF table cluster."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.ttf_table import TTFTable


def test_ttf_table_read_headers_is_no_op_on_base() -> None:
    # Base ``TTFTable.read_headers`` mirrors upstream's empty-bodied
    # default — it should not raise and should not touch ``initialized``.
    table = TTFTable()
    table.read_headers(None, None, None)  # type: ignore[arg-type]
    assert not table.get_initialized()


def test_ttf_table_read_headers_callable_signature() -> None:
    # The override point must be present on the base class so the parser's
    # fast path can dispatch generically without isinstance checks.
    assert hasattr(TTFTable, "read_headers")
    assert callable(TTFTable.read_headers)
