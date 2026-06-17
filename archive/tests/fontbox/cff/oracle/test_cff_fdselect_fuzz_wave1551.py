"""Differential fuzz of the CID-keyed CFF /FDSelect glyph->font-dict mapping
algorithm against the live Apache PDFBox 3.0.7 oracle.

The sibling oracle ``test_cff_cid_fdselect_oracle`` parses *whole, well-formed*
raw CID-CFF programs and walks ``getFDIndex`` over their real GID range. This
module fuzzes the resolution algorithm itself under malformed / edge inputs
that a normal CFF parse would never produce (or would reject before the
FDSelect is built): Format 0 arrays shorter/longer than the swept range; Format
3 ranges out of order, overlapping, ``first != 0``, count mismatch, sentinel
smaller than the last range's first, zero sentinel; FD indices past any
/FDArray bound; and negative / far-past-sentinel glyph indices.

The probe ``CffFdSelectFuzzProbe`` constructs PDFBox's own concrete
``CFFParser$Format0FDSelect(int[])`` and ``CFFParser$Format3FDSelect(Range3[],
int)`` via reflection and emits ``getFDIndex`` over a fixed sweep, so the
oracle test compares the two engines line-for-line on identical synthetic
payloads. The pypdfbox side builds the matching :class:`Format0FDSelect` /
:class:`Format3FDSelect` objects directly.

When the live oracle is unavailable the value-based tests still run against
expected values transcribed from PDFBox 3.0.7's verified behaviour (recorded by
running the probe and confirmed against a disassembly of
``CFFParser$Format0FDSelect`` / ``Format3FDSelect`` ``getFDIndex``).

Honest divergences pinned here:

* **Format 0 negative GID** — upstream indexes ``fds[gid]`` directly with no
  lower-bound guard, so a negative GID throws ``ArrayIndexOutOfBoundsException``
  in Java. pypdfbox's :class:`Format0FDSelect` guards ``gid < 0`` and returns 0
  defensively (never throws). The sweep excludes negative GIDs from the
  exact-match comparison and pins each side's documented behaviour separately.

The wave-1551 fix this exercises: :meth:`Format3FDSelect.get_fd_index` used to
short-circuit to 0 when ``sentinel <= 0``, diverging from upstream for any GID
that lands in the last range of a zero-sentinel FDSelect (upstream returns -1).
The guard was dropped; only ``gid < 0`` and an empty range array short-circuit.
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.fd_select import Format0FDSelect, Format3FDSelect
from tests.oracle.harness import requires_oracle, run_probe_text

# The sweep the probe walks for every case (mirrors CffFdSelectFuzzProbe.SWEEP).
_SWEEP = [-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 50, 255, 256, 1000]

# Format 0 cases: name -> flat per-GID FD byte array.
_FORMAT0_CASES: dict[str, list[int]] = {
    "f0_empty": [],
    "f0_single": [0],
    "f0_simple4": [0, 0, 1, 1],
    "f0_three": [0, 0, 0, 1, 1, 2, 2, 2],
    "f0_short": [2, 1],
    "f0_fd_oob": [0, 5, 99, 200],
    "f0_zigzag": [3, 0, 2, 1, 4, 0, 1, 3],
    "f0_alln": [7, 7, 7, 7],
}

# Format 3 cases: name -> (ranges [(first, fd), ...], sentinel).
_FORMAT3_CASES: dict[str, tuple[list[tuple[int, int]], int]] = {
    "f3_simple": ([(0, 0), (2, 1)], 4),
    "f3_three": ([(0, 0), (3, 1), (5, 2)], 8),
    "f3_first_not_zero": ([(2, 1), (5, 2)], 8),
    "f3_sentinel_eq_last": ([(0, 0), (4, 1)], 4),
    "f3_sentinel_lt_last": ([(0, 0), (6, 1)], 4),
    "f3_sentinel_zero": ([(0, 0), (2, 1)], 0),
    "f3_out_of_order": ([(5, 2), (2, 1), (0, 0)], 8),
    "f3_overlap": ([(0, 0), (0, 1), (3, 2)], 6),
    "f3_overlap2": ([(0, 0), (2, 1), (1, 2)], 6),
    "f3_empty_ranges": ([], 4),
    "f3_empty_zero": ([], 0),
    "f3_single_all": ([(0, 0)], 256),
    "f3_single_offset": ([(3, 1)], 8),
    "f3_fd_oob": ([(0, 9), (2, 200)], 4),
    "f3_dup_first": ([(0, 0), (2, 1), (2, 2)], 5),
    "f3_big_sentinel": ([(0, 0), (2, 1)], 1000),
    "f3_first_beyond_sentinel": ([(10, 0), (20, 1)], 5),
    "f3_sentinel_256": ([(0, 0), (128, 1)], 256),
    "f3_negative_fd": ([(0, -1), (2, 0)], 4),
    "f3_tight": ([(0, 0), (1, 1), (2, 0), (3, 1)], 4),
}


# --------------------------------------------------------------------------- #
# PDFBox-3.0.7-verified expected getFDIndex values (transcribed from the live
# probe; confirmed against a disassembly of CFFParser$Format0/3FDSelect).
# Each value is the FD index for the SWEEP gid at the same position; ``None``
# marks a Java ArrayIndexOutOfBoundsException (Format 0 negative GID only).
# --------------------------------------------------------------------------- #
# SWEEP order:  -2 -1 0 1 2 3 4 5 6 7 8 9 10 15 20 50 255 256 1000
_N = None  # Java ArrayIndexOutOfBoundsException marker (Format 0 negative GID)
# fmt: off
_EXPECTED: dict[str, list[int | None]] = {
    "f0_empty": [_N, _N, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f0_single": [_N, _N, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f0_simple4": [_N, _N, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f0_three": [_N, _N, 0, 0, 0, 1, 1, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f0_short": [_N, _N, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f0_fd_oob": [_N, _N, 0, 5, 99, 200, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f0_zigzag": [_N, _N, 3, 0, 2, 1, 4, 0, 1, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f0_alln": [_N, _N, 7, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f3_simple": [0, 0, 0, 0, 1, 1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_three": [0, 0, 0, 0, 0, 1, 1, 2, 2, 2, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_first_not_zero": [0, 0, 0, 0, 1, 1, 1, 2, 2, 2, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_sentinel_eq_last": [0, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_sentinel_lt_last": [0, 0, 0, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_sentinel_zero": [0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_out_of_order": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_overlap": [0, 0, 1, 1, 1, 2, 2, 2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_overlap2": [0, 0, 0, 0, 2, 2, 2, 2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_empty_ranges": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f3_empty_zero": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f3_single_all": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1, -1],
    "f3_single_offset": [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_fd_oob": [0, 0, 9, 9, 200, 200, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_dup_first": [0, 0, 0, 0, 2, 2, 2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_big_sentinel": [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1],
    "f3_first_beyond_sentinel": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1],
    "f3_sentinel_256": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, -1, -1],
    "f3_negative_fd": [0, 0, -1, -1, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_tight": [0, 0, 0, 1, 0, 1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
}
# fmt: on


# --------------------------------------------------------------------------- #
# Value-based tests (always run; no oracle needed).
# --------------------------------------------------------------------------- #


def test_format0_matches_pdfbox_values() -> None:
    """Format 0 getFDIndex over the fuzz sweep matches PDFBox 3.0.7 for every
    non-negative GID. Negative GIDs are the documented divergence: Java throws
    ArrayIndexOutOfBoundsException (expected ``None``), pypdfbox returns 0."""
    for name, fds in _FORMAT0_CASES.items():
        sel = Format0FDSelect(fds)
        expected = _EXPECTED[name]
        for gid, want in zip(_SWEEP, expected, strict=True):
            if gid < 0:
                # Documented divergence: Java AIOOBE (None) vs pypdfbox 0.
                assert want is None, (name, gid, want)
                assert sel.get_fd_index(gid) == 0, (name, gid)
                continue
            assert sel.get_fd_index(gid) == want, (name, gid, want)


def test_format3_matches_pdfbox_values() -> None:
    """Format 3 getFDIndex over the fuzz sweep matches PDFBox 3.0.7 exactly for
    every GID, including the sentinel -1 quirk and the zero-sentinel walk."""
    for name, (ranges, sentinel) in _FORMAT3_CASES.items():
        sel = Format3FDSelect(ranges, sentinel)
        expected = _EXPECTED[name]
        for gid, want in zip(_SWEEP, expected, strict=True):
            assert want is not None, (name, gid)  # no AIOOBE in Format 3
            assert sel.get_fd_index(gid) == want, (name, gid, want)


def test_format3_zero_sentinel_walks_ranges_regression() -> None:
    """Regression for the wave-1551 fix: a zero/empty sentinel must NOT
    short-circuit the range walk. A GID landing in the last range of a
    zero-sentinel FDSelect returns -1 (upstream), not 0."""
    sel = Format3FDSelect([(0, 0), (2, 1)], 0)
    assert sel.get_fd_index(0) == 0  # first range, gid < next.first
    assert sel.get_fd_index(1) == 0
    assert sel.get_fd_index(2) == -1  # last range, gid >= sentinel(0)
    assert sel.get_fd_index(3) == -1


# --------------------------------------------------------------------------- #
# Live differential test against the running PDFBox oracle.
# --------------------------------------------------------------------------- #


def _parse_probe(text: str) -> dict[str, dict[int, str]]:
    """Parse CffFdSelectFuzzProbe output into ``{case: {gid: value}}`` where
    value is the FD index string or ``ERR:<Exception>``."""
    out: dict[str, dict[int, str]] = {}
    current: str | None = None
    for line in text.splitlines():
        cols = line.split("\t")
        if cols[0] == "CASE":
            current = cols[1]
            out.setdefault(current, {})
        elif cols[0] == "FD" and len(cols) >= 4:
            out[cols[1]][int(cols[2])] = cols[3]
        elif cols[0] == "ERR":
            # whole-case construction error (not expected for our inputs)
            out.setdefault(cols[1], {})["__case_err__"] = cols[2]  # type: ignore[index]
    return out


@requires_oracle
def test_fdselect_getfdindex_matches_live_pdfbox() -> None:
    """Line-for-line: pypdfbox Format0/3 FDSelect.get_fd_index equals Apache
    PDFBox 3.0.7's getFDIndex over the whole fuzz sweep on identical synthetic
    payloads. Negative GIDs for Format 0 are excluded (documented divergence:
    Java throws AIOOBE, pypdfbox returns 0)."""
    java = _parse_probe(run_probe_text("CffFdSelectFuzzProbe", "sweep"))

    for name, fds in _FORMAT0_CASES.items():
        assert name in java, f"probe missing case {name}"
        sel = Format0FDSelect(fds)
        for gid in _SWEEP:
            jval = java[name][gid]
            if gid < 0:
                # Documented divergence: Java AIOOBE, pypdfbox returns 0.
                assert jval.startswith("ERR:"), (name, gid, jval)
                assert sel.get_fd_index(gid) == 0, (name, gid)
                continue
            assert str(sel.get_fd_index(gid)) == jval, (name, gid, jval)

    for name, (ranges, sentinel) in _FORMAT3_CASES.items():
        assert name in java, f"probe missing case {name}"
        sel = Format3FDSelect(ranges, sentinel)
        for gid in _SWEEP:
            jval = java[name][gid]
            assert not jval.startswith("ERR:"), (name, gid, jval)
            assert str(sel.get_fd_index(gid)) == jval, (name, gid, jval)
