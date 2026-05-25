"""Wave 1403 — branch round-out for :meth:`CMapParser.parse_beginbfrange`.

Closes two partial arcs in the bfrange parser:

* ``[469,443]`` — the ``array and len(array) >= end - start`` False
  branch: an empty (or too-short) array-form target list is ignored and
  the range loop continues.
* ``[473,443]`` — the ``len(token_bytes) > 0`` False branch: an empty
  ``<>`` destination token is ignored and the range loop continues.
"""

from __future__ import annotations

from pypdfbox.fontbox.cmap import CMap, CMapParser


def _parse(snippet: bytes) -> CMap:
    return CMapParser().parse(snippet)


def test_bfrange_empty_array_target_is_ignored() -> None:
    """An empty array-form target ``[]`` is falsy, so the
    ``array and ...`` guard takes its False arc ([469,443]); no mapping
    is registered for the range and parsing completes cleanly."""
    cmap = _parse(
        b"""
        1 begincodespacerange <00> <FF> endcodespacerange
        1 beginbfrange
        <01> <03> []
        endbfrange
        endcmap
        """
    )
    # Nothing was mapped from the empty array.
    assert cmap.to_unicode_bytes(b"\x01") is None
    assert cmap.to_unicode_bytes(b"\x02") is None


def test_bfrange_empty_destination_token_is_ignored() -> None:
    """An empty ``<>`` destination token has zero length, so the
    ``len(token_bytes) > 0`` guard takes its False arc ([473,443]); the
    range is skipped without error."""
    cmap = _parse(
        b"""
        1 begincodespacerange <00> <FF> endcodespacerange
        1 beginbfrange
        <01> <03> <>
        endbfrange
        endcmap
        """
    )
    assert cmap.to_unicode_bytes(b"\x01") is None
    assert cmap.to_unicode_bytes(b"\x02") is None
