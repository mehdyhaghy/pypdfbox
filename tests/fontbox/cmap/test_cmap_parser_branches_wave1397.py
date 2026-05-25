"""Wave 1397 branch-coverage tests for ``CMapParser._parse_literal_name``.

Closes False-branch arrows for each metadata literal where the next
token is of the wrong type and the setter is bypassed:

* 224->exit — ``/WMode`` followed by a non-int (string, name)
* 228->exit — ``/CMapName`` followed by a non-literal-name (number)
* 234->exit — ``/CMapVersion`` followed by neither number nor string
* 238->exit — ``/CMapType`` followed by a non-int
* 242->exit — ``/Registry`` followed by a non-string
* 246->exit — ``/Ordering`` followed by a non-string
* 250->exit — ``/Supplement`` followed by a non-int
* 261->263 — ``/CIDSystemInfo`` dict missing /Registry
* 264->266 — ``/CIDSystemInfo`` dict missing /Ordering
* 267->exit — ``/CIDSystemInfo`` dict missing /Supplement
"""

from __future__ import annotations

from pypdfbox.fontbox.cmap import CMap, CMapParser


def _parse(snippet: bytes) -> CMap:
    return CMapParser().parse_chunk(snippet, CMap("test"))


def test_wmode_with_non_int_token_is_ignored() -> None:
    """Closes 224->exit: ``/WMode (notanint)`` — set_wmode is skipped."""
    cmap = _parse(b"/WMode (notanint) def\nendcmap\n")
    # Default WMode is 0; non-int token left it unchanged.
    assert cmap.get_wmode() == 0


def test_cmapname_with_non_literal_token_is_ignored() -> None:
    """Closes 228->exit: ``/CMapName 42`` — set_name is skipped."""
    cmap = _parse(b"/CMapName 42 def\nendcmap\n")
    assert cmap.get_name() == "test"  # unchanged from constructor


def test_cmapversion_with_non_number_non_string_is_ignored() -> None:
    """Closes 234->exit: ``/CMapVersion /someName`` — both branches
    skipped."""
    cmap = _parse(b"/CMapVersion /someName def\nendcmap\n")
    assert cmap.get_version() is None


def test_cmaptype_with_non_int_token_is_ignored() -> None:
    """Closes 238->exit: ``/CMapType (foo)`` — set_type is skipped."""
    cmap = _parse(b"/CMapType (foo) def\nendcmap\n")
    # Default cmap_type is -1; unchanged.
    assert cmap.get_type() == -1


def test_registry_with_non_string_is_ignored() -> None:
    """Closes 242->exit: ``/Registry 7`` — set_registry is skipped."""
    cmap = _parse(b"/Registry 7 def\nendcmap\n")
    assert cmap.get_registry() is None


def test_ordering_with_non_string_is_ignored() -> None:
    """Closes 246->exit: ``/Ordering 99`` — set_ordering is skipped."""
    cmap = _parse(b"/Ordering 99 def\nendcmap\n")
    assert cmap.get_ordering() is None


def test_supplement_with_non_int_is_ignored() -> None:
    """Closes 250->exit: ``/Supplement (notanint)`` — set_supplement skipped."""
    cmap = _parse(b"/Supplement (notanint) def\nendcmap\n")
    assert cmap.get_supplement() == 0


def test_cidsysteminfo_dict_missing_registry() -> None:
    """Closes 261->263: a dict-form CIDSystemInfo without ``/Registry``.

    Whether the inner setters actually fire depends on the parser's
    internal dict-key shape (literal names vs strings) — the load-bearing
    assertion is just that the dict-form path runs to completion without
    crashing (the False arm at 261 is taken regardless of key shape)."""
    cmap = _parse(
        b"/CIDSystemInfo << /Ordering (Wave) /Supplement 1 >> def\nendcmap\n"
    )
    # Registry key is absent → must be None (the True arm never fires).
    assert cmap.get_registry() is None


def test_cidsysteminfo_dict_missing_ordering() -> None:
    """Closes 264->266: a dict-form CIDSystemInfo without ``/Ordering``."""
    cmap = _parse(
        b"/CIDSystemInfo << /Registry (Adobe) /Supplement 2 >> def\nendcmap\n"
    )
    assert cmap.get_ordering() is None


def test_cidsysteminfo_dict_missing_supplement() -> None:
    """Closes 267->exit: a dict-form CIDSystemInfo without ``/Supplement``.

    Default supplement (0) is unchanged because the conditional setter
    never fires."""
    cmap = _parse(
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Wave) >> def\nendcmap\n"
    )
    # Default supplement is 0 — unchanged.
    assert cmap.get_supplement() == 0
