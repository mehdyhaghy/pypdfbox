"""PDFBOX-6251 — inherited (``usecmap``) mappings must not override a
CMap's own CID mappings.

Upstream (3.0 branch, r1938041) stopped merging the used CMap's
``codeToCid`` map and ``codeToCidRanges`` list into the importing CMap.
The used CMap is kept as a parent instead and consulted only for codes
the importing CMap does not map itself, so a ``usecmap`` chain resolves
nearest-first and a CMap's own mappings always win.

The upstream JUnit cases are ported in
``tests/fontbox/cmap/upstream/test_cmap_parser.py``; these are the
pypdfbox-side tests for the same behaviour, including the parser path
(the bundled ``Identity-V`` resource declares no CID mappings of its own
and answers purely through ``usecmap``).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.fontbox.cmap import CMap, CMapParser

_IDENTITY_V = (
    Path(__file__).resolve().parents[3]
    / "pypdfbox"
    / "fontbox"
    / "cmap"
    / "resources"
    / "Identity-V"
)


def test_own_cid_mapping_beats_the_inherited_one() -> None:
    used = CMap("used")
    used.add_cid_mapping(b"\x41", 100)
    used.add_cid_mapping(b"\x42", 101)

    cmap = CMap("importer")
    cmap.use_cmap(used)
    cmap.add_cid_mapping(b"\x41", 300)

    assert cmap.to_cid_with_length(0x41, 1) == 300
    assert cmap.to_cid_bytes(b"\x41") == 300
    # A code the importer says nothing about still resolves through the parent.
    assert cmap.to_cid_with_length(0x42, 1) == 101
    # The used CMap keeps answering for itself.
    assert used.to_cid_with_length(0x41, 1) == 100


def test_own_cid_range_beats_the_inherited_range() -> None:
    used = CMap("used")
    used.add_cid_range(b"\x00", b"\xff", 500)

    cmap = CMap("importer")
    cmap.use_cmap(used)
    cmap.add_cid_range(b"\x40", b"\x4f", 200)

    assert cmap.to_cid_with_length(0x41, 1) == 201
    assert cmap.to_cid_with_length(0x50, 1) == 580
    assert used.to_cid_with_length(0x41, 1) == 565


def test_use_cmap_does_not_mutate_the_used_cmap() -> None:
    """The parent is referenced, not copied — so nothing written into the
    importer may reach back into it."""
    used = CMap("used")
    used.add_cid_mapping(b"\x41", 100)
    used.add_cid_range(b"\x50", b"\x5f", 200)
    used_ranges = list(used._code_to_cid_ranges)

    cmap = CMap("importer")
    cmap.use_cmap(used)
    cmap.add_cid_mapping(b"\x41", 300)
    cmap.add_cid_range(b"\x50", b"\x5f", 400)

    assert used._code_to_cid[1] == {0x41: 100}
    assert used._code_to_cid_ranges == used_ranges
    assert used.to_cid_with_length(0x41, 1) == 100
    assert used.to_cid_with_length(0x55, 1) == 205
    assert cmap.to_cid_with_length(0x41, 1) == 300
    assert cmap.to_cid_with_length(0x55, 1) == 405


def test_importer_does_not_copy_the_parents_cid_state() -> None:
    used = CMap("used")
    used.add_cid_mapping(b"\x41", 100)
    used.add_cid_range(b"\x50", b"\x5f", 200)

    cmap = CMap("importer")
    cmap.use_cmap(used)

    # No merge: the importer's own containers stay empty, yet it reports (and
    # resolves) CID mappings through the parent.
    assert cmap._code_to_cid == {}
    assert cmap._code_to_cid_ranges == []
    assert cmap._parent_cmaps == [used]
    assert cmap.has_cid_mappings() is True
    assert cmap.has_cid_mapping() is True
    assert cmap.to_cid_with_length(0x41, 1) == 100
    assert cmap.to_cid_with_length(0x55, 1) == 205


def test_own_mapping_to_cid_zero_is_not_a_fallthrough() -> None:
    """CID 0 is ``.notdef``; mapping a code to it deliberately is a mapping,
    not the absence of one, so it must outrank the parent."""
    used = CMap("used")
    used.add_cid_range(b"\x00", b"\xff", 500)

    cmap = CMap("importer")
    cmap.use_cmap(used)
    cmap.add_cid_mapping(b"\x41", 0)

    assert cmap.to_cid_with_length(0x41, 1) == 0
    assert cmap.to_cid_bytes(b"\x41") == 0
    assert cmap.to_cid_with_length(0x42, 1) == 566


def test_length_guessing_overload_walks_the_chain() -> None:
    used = CMap("used")
    used.add_cid_mapping(b"\x00\x41", 700)

    cmap = CMap("importer")
    cmap.use_cmap(used)

    assert cmap.get_min_cid_length() == 2
    assert cmap.get_max_cid_length() == 2
    assert cmap.to_cid(0x41) == 700


def test_empty_cmap_reports_no_cid_mappings_and_resolves_to_zero() -> None:
    cmap = CMap()
    assert cmap.has_cid_mappings() is False
    assert cmap.to_cid(0x41) == 0
    assert cmap.to_cid_with_length(0x41, 1) == 0
    assert cmap.to_cid_bytes(b"\x41") == 0


def test_to_cid_from_ranges_keeps_the_zero_sentinel_and_ignores_parents() -> None:
    """The public range-only probe is a pypdfbox enrichment: it still reports
    "no mapping" as 0 (upstream's private helper now returns -1) and it looks
    only at the ranges this CMap declares."""
    used = CMap("used")
    used.add_cid_range(b"\x00", b"\xff", 500)

    cmap = CMap("importer")
    cmap.use_cmap(used)

    assert cmap.to_cid_from_ranges(0x41, 1) == 0
    assert cmap.to_cid_from_ranges(b"\x41") == 0
    assert used.to_cid_from_ranges(0x41, 1) == 565
    assert used.to_cid_from_ranges(b"\x41") == 565


def test_parsed_identity_v_resolves_only_through_its_parent() -> None:
    """The bundled ``Identity-V`` file declares ``/Identity-H usecmap`` and no
    CID mappings of its own. Parsing it directly (rather than through
    ``parse_predefined``, which short-circuits to the programmatic identity
    builder) exercises the real ``usecmap`` path."""
    cmap = CMapParser().parse(_IDENTITY_V.read_bytes())

    assert cmap.get_name() == "Identity-V"
    assert cmap.get_wmode() == 1
    assert cmap._code_to_cid == {}
    assert cmap._code_to_cid_ranges == []
    assert [p.get_name() for p in cmap._parent_cmaps] == ["Identity-H"]

    assert cmap.has_cid_mappings() is True
    assert cmap.to_cid_bytes(b"\x00\x41") == 65
    assert cmap.to_cid_bytes(b"\x30\x39") == 12345
    assert cmap.to_cid_bytes(b"\xff\xff") == 0xFFFF
    assert cmap.to_cid_with_length(0x3039, 2) == 12345
