"""Fuzz the CID-keyed CFF /FDSelect **byte reader** parser path
(``CFFParser.read_fd_select`` -> ``read_format0_fd_select`` /
``read_format3_fd_select``) and the /FDArray per-FD Private DICT integration,
against Apache PDFBox 3.0.7.

This complements the sibling oracle test
``tests/fontbox/cff/oracle/test_cff_fdselect_fuzz_wave1551``: that wave fuzzes
the resolution algorithm by constructing the concrete
:class:`Format0FDSelect` / :class:`Format3FDSelect` objects *directly*. Here we
go one layer earlier and feed raw on-disk FDSelect **bytes** through the parser
reader — the format byte, the Format-0 per-glyph FD array, and the Format-3
``nRanges`` + ``[first, fd]`` records + sentinel — exactly as a real CFF parse
walks them. That exercises the parser's wrapper-class choice, the 2-byte
``first``/``sentinel`` field widths (vs the 1-byte ``fd``), and the dispatch on
an unknown format byte.

Expected ``getFDIndex`` values transcribed from the live PDFBox 3.0.7 oracle
(``CffFdSelectBytesProbe``) and confirmed against a disassembly of
``CFFParser.readFDSelect`` / ``readFormat0FDSelect`` / ``readFormat3FDSelect``.

Verified parity facts pinned here:

* ``readFDSelect`` for an **unknown format byte** throws
  ``IllegalArgumentException`` upstream (no-arg ctor). pypdfbox's
  :meth:`CFFParser.read_fd_select` raises ``ValueError`` — the project's
  standard ``IllegalArgumentException`` -> ``ValueError`` mapping.
* ``readFormat0FDSelect`` reads exactly ``nGlyphs`` FD bytes; a GID past
  ``nGlyphs`` returns 0 (out of the materialised array). A negative GID throws
  ``ArrayIndexOutOfBoundsException`` upstream; pypdfbox guards it to 0
  (documented divergence, excluded from the exact-match comparison).
* Format-3 ``first`` and ``sentinel`` are Card16 (2 bytes); ``fd`` is Card8
  (1 byte). The ``f3_high_first`` case (first = 255 / 256) proves the field
  widths are read correctly.

The FDArray section parses the real multi-FD CID-CFF fixtures and confirms each
FD's Private DICT (defaultWidthX / nominalWidthX / local subrs) is selected
per-GID through /FDSelect.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray
from pypdfbox.fontbox.cff.fd_select import Format0FDSelect, Format3FDSelect
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "cff"

# GIDs swept for every byte-reader case (mirrors CffFdSelectBytesProbe.SWEEP).
_SWEEP = [-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100, 255, 256, 1000]


# --------------------------------------------------------------------------- #
# Synthetic on-disk FDSelect byte builders.
# --------------------------------------------------------------------------- #


def _format0_bytes(fds: list[int]) -> bytes:
    """On-disk Format 0 FDSelect: format byte (0) + one FD byte per glyph."""
    return bytes([0, *(b & 0xFF for b in fds)])


def _format3_bytes(ranges: list[tuple[int, int]], sentinel: int) -> bytes:
    """On-disk Format 3 FDSelect: format(0x03) + nRanges(Card16) +
    nRanges * (first Card16 + fd Card8) + sentinel(Card16)."""
    out = bytearray([3])
    out += struct.pack(">H", len(ranges))
    for first, fd in ranges:
        out += struct.pack(">H", first)
        out.append(fd & 0xFF)
    out += struct.pack(">H", sentinel)
    return bytes(out)


# --------------------------------------------------------------------------- #
# Format 0 byte-reader cases.  name -> (fds, n_glyphs).
# --------------------------------------------------------------------------- #
_FORMAT0_CASES: dict[str, tuple[list[int], int]] = {
    "f0_single": ([0], 1),
    "f0_simple4": ([0, 0, 1, 1], 4),
    "f0_three": ([0, 0, 0, 1, 1, 2, 2, 2], 8),
    "f0_fd_oob": ([0, 5, 99, 200], 4),
    "f0_high_fd": ([255, 0, 255], 3),
    # On-disk array longer than n_glyphs: reader reads only n_glyphs bytes.
    "f0_nglyphs_short": ([3, 2, 1, 0], 2),
}

# --------------------------------------------------------------------------- #
# Format 3 byte-reader cases.  name -> (ranges, sentinel).
# --------------------------------------------------------------------------- #
_FORMAT3_CASES: dict[str, tuple[list[tuple[int, int]], int]] = {
    "f3_simple": ([(0, 0), (2, 1)], 4),
    "f3_three": ([(0, 0), (3, 1), (5, 2)], 8),
    "f3_single_all": ([(0, 0)], 256),
    "f3_first_not_zero": ([(2, 1), (5, 2)], 8),
    # first > 255 / 256 -> proves 2-byte Card16 read of the first GID.
    "f3_high_first": ([(0, 0), (255, 1), (256, 2)], 300),
    "f3_sentinel_eq_last": ([(0, 0), (4, 1)], 4),
    "f3_zero_ranges": ([], 4),
    # fd = 255 -> proves single-byte Card8 read of the fd index.
    "f3_fd_byte_max": ([(0, 255), (2, 0)], 4),
}


# --------------------------------------------------------------------------- #
# PDFBox-3.0.7-verified getFDIndex over the sweep (from CffFdSelectBytesProbe).
# Each value is the FD index for the SWEEP gid at the same position; ``None``
# marks a Java ArrayIndexOutOfBoundsException (Format 0 negative GID only).
# SWEEP order: -1 0 1 2 3 4 5 6 7 8 9 10 100 255 256 1000
# --------------------------------------------------------------------------- #
_N = None  # Java ArrayIndexOutOfBoundsException marker (Format 0 negative GID)
# fmt: off
_EXPECTED: dict[str, list[int | None]] = {
    "f0_single": [_N, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f0_simple4": [_N, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f0_three": [_N, 0, 0, 0, 1, 1, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0],
    "f0_fd_oob": [_N, 0, 5, 99, 200, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f0_high_fd": [_N, 255, 0, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f0_nglyphs_short": [_N, 3, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f3_simple": [0, 0, 0, 1, 1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_three": [0, 0, 0, 0, 1, 1, 2, 2, 2, -1, -1, -1, -1, -1, -1, -1],
    "f3_single_all": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1, -1],
    "f3_first_not_zero": [0, 0, 0, 1, 1, 1, 2, 2, 2, -1, -1, -1, -1, -1, -1, -1],
    "f3_high_first": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, -1],
    "f3_sentinel_eq_last": [0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    "f3_zero_ranges": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "f3_fd_byte_max": [0, 255, 255, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
}
# fmt: on


# --------------------------------------------------------------------------- #
# Value-based byte-reader tests (always run; no oracle needed).
# --------------------------------------------------------------------------- #


def test_read_format0_byte_reader_wrapper_class() -> None:
    """``read_fd_select`` on a Format 0 payload yields a Format0FDSelect
    materialising exactly ``n_glyphs`` FD bytes."""
    for _name, (fds, n_glyphs) in _FORMAT0_CASES.items():
        sel = CFFParser.read_fd_select(
            DataInputByteArray(_format0_bytes(fds)), n_glyphs
        )
        assert isinstance(sel, Format0FDSelect)
        assert sel.get_format() == 0
        assert sel.get_num_glyphs() == n_glyphs
        assert sel.get_fds() == fds[:n_glyphs]


def test_read_format0_byte_reader_matches_pdfbox() -> None:
    """Format 0: ``read_fd_select`` -> get_fd_index over the sweep matches
    PDFBox 3.0.7. Negative GID is the documented divergence (Java AIOOBE,
    pypdfbox returns 0)."""
    for name, (fds, n_glyphs) in _FORMAT0_CASES.items():
        sel = CFFParser.read_fd_select(
            DataInputByteArray(_format0_bytes(fds)), n_glyphs
        )
        for gid, want in zip(_SWEEP, _EXPECTED[name], strict=True):
            if gid < 0:
                # Documented divergence: Java AIOOBE (None) vs pypdfbox 0.
                assert want is None, (name, gid)
                assert sel.get_fd_index(gid) == 0, (name, gid)
                continue
            assert sel.get_fd_index(gid) == want, (name, gid, want)


def test_read_format3_byte_reader_wrapper_class() -> None:
    """``read_fd_select`` on a Format 3 payload yields a Format3FDSelect with
    the parsed ranges + sentinel."""
    for _name, (ranges, sentinel) in _FORMAT3_CASES.items():
        sel = CFFParser.read_fd_select(
            DataInputByteArray(_format3_bytes(ranges, sentinel)), 0
        )
        assert isinstance(sel, Format3FDSelect)
        assert sel.get_format() == 3
        assert sel.get_ranges() == ranges
        assert sel.get_sentinel() == sentinel
        assert sel.get_num_ranges() == len(ranges)


def test_read_format3_byte_reader_matches_pdfbox() -> None:
    """Format 3: ``read_fd_select`` -> get_fd_index over the sweep matches
    PDFBox 3.0.7 exactly, including the sentinel -1 quirk and the 2-byte
    first/sentinel field widths."""
    for name, (ranges, sentinel) in _FORMAT3_CASES.items():
        sel = CFFParser.read_fd_select(
            DataInputByteArray(_format3_bytes(ranges, sentinel)), 0
        )
        for gid, want in zip(_SWEEP, _EXPECTED[name], strict=True):
            assert want is not None, (name, gid)  # no AIOOBE in Format 3
            assert sel.get_fd_index(gid) == want, (name, gid, want)


def test_read_format3_high_first_proves_card16_widths() -> None:
    """The first GID and sentinel are Card16; a first of 256 must NOT be
    truncated to a byte (which would alias to 0). gid 256 maps to fd 2."""
    sel = CFFParser.read_fd_select(
        DataInputByteArray(_format3_bytes([(0, 0), (255, 1), (256, 2)], 300)), 0
    )
    assert sel.get_fd_index(254) == 0
    assert sel.get_fd_index(255) == 1
    assert sel.get_fd_index(256) == 2
    assert sel.get_fd_index(299) == 2
    assert sel.get_fd_index(300) == -1  # at the sentinel -> last-range -1


def test_read_fd_select_unknown_format_raises() -> None:
    """An unknown format byte raises ValueError — the project's mapping of
    upstream ``IllegalArgumentException`` (which ``readFDSelect`` throws via
    its no-arg ctor for the switch default)."""
    for fmt in (1, 2, 4, 255):
        with pytest.raises(ValueError):
            CFFParser.read_fd_select(DataInputByteArray(bytes([fmt])), 4)


def test_read_format3_empty_ranges_sentinel_only() -> None:
    """A Format 3 payload with zero ranges (nRanges = 0) parses to an empty
    range table; every GID resolves to 0 (loop never runs)."""
    sel = CFFParser.read_fd_select(DataInputByteArray(_format3_bytes([], 4)), 0)
    assert sel.get_num_ranges() == 0
    assert sel.get_sentinel() == 4
    for gid in (-1, 0, 1, 3, 4, 100):
        assert sel.get_fd_index(gid) == 0


def test_read_format0_single_fd_font() -> None:
    """A single-FD font: every covered GID resolves to FD 0."""
    sel = CFFParser.read_fd_select(
        DataInputByteArray(_format0_bytes([0, 0, 0, 0, 0])), 5
    )
    for gid in range(5):
        assert sel.get_fd_index(gid) == 0
    assert sel.get_fd_index(5) == 0  # past n_glyphs


def test_read_format0_then_format3_round_trip_equivalence() -> None:
    """Format 0 and Format 3 that encode the same logical mapping resolve
    identically across the in-range sweep (a font writer might emit either)."""
    # Logical mapping: gid 0,1 -> 0 ; gid 2,3 -> 1.
    f0 = CFFParser.read_fd_select(
        DataInputByteArray(_format0_bytes([0, 0, 1, 1])), 4
    )
    f3 = CFFParser.read_fd_select(
        DataInputByteArray(_format3_bytes([(0, 0), (2, 1)], 4)), 0
    )
    for gid in range(4):
        assert f0.get_fd_index(gid) == f3.get_fd_index(gid), gid


# --------------------------------------------------------------------------- #
# /FDArray per-FD Private DICT integration on real multi-FD CID-CFF fixtures.
# --------------------------------------------------------------------------- #

# fixture -> (fd_array_size, fdselect_num_glyphs, per-fd (dW, nW)).
_FIXTURE_EXPECT: dict[str, tuple[int, int, list[tuple[float, float]]]] = {
    "cid_multifd_subr.cff": (2, 4, [(100.0, 50.0), (200.0, 80.0)]),
    "cid_multifd_3fd.cff": (3, 8, [(100.0, 50.0), (200.0, 80.0), (333.0, 111.0)]),
    "cid_multifd_localsubr_bias.cff": (2, 4, [(100.0, 50.0), (200.0, 80.0)]),
}


@pytest.mark.parametrize("fixture", sorted(_FIXTURE_EXPECT))
def test_fdarray_per_fd_private_dicts(fixture: str) -> None:
    """Each FD in /FDArray exposes its own Private DICT (defaultWidthX /
    nominalWidthX), selected per-GID through /FDSelect."""
    data = (_FIXTURES / fixture).read_bytes()
    font = CFFCIDFont.from_bytes(data)
    fda = font.get_fd_array()
    sel = font.get_fd_select()
    size, num_glyphs, widths = _FIXTURE_EXPECT[fixture]

    assert fda.size() == size
    assert sel.get_num_glyphs() == num_glyphs
    for fd, (dw, nw) in enumerate(widths):
        assert fda.get_default_width_x(fd) == dw, fd
        assert fda.get_nominal_width_x(fd) == nw, fd


@pytest.mark.parametrize("fixture", sorted(_FIXTURE_EXPECT))
def test_per_gid_width_routes_through_fdselect(fixture: str) -> None:
    """``get_default_width_x_for_gid`` / ``get_nominal_width_x_for_gid`` resolve
    each GID's FD via /FDSelect and read that FD's Private DICT width."""
    data = (_FIXTURES / fixture).read_bytes()
    font = CFFCIDFont.from_bytes(data)
    fda = font.get_fd_array()
    sel = font.get_fd_select()
    _, num_glyphs, widths = _FIXTURE_EXPECT[fixture]

    for gid in range(num_glyphs):
        fd = font.get_fd_index_for_gid(gid)
        assert fd == sel.get_fd_index(gid)
        assert font.get_default_width_x_for_gid(gid) == fda.get_default_width_x(fd)
        assert font.get_nominal_width_x_for_gid(gid) == fda.get_nominal_width_x(fd)
        assert font.get_default_width_x_for_gid(gid) == widths[fd][0]


def test_gid0_and_max_gid_fd_resolution() -> None:
    """GID 0 maps to its FD; the max GID (num_glyphs - 1) maps to a valid FD;
    a GID at num_glyphs (out of range) returns 0."""
    data = (_FIXTURES / "cid_multifd_3fd.cff").read_bytes()
    font = CFFCIDFont.from_bytes(data)
    sel = font.get_fd_select()
    ng = sel.get_num_glyphs()
    assert font.get_fd_index_for_gid(0) == 0
    max_fd = font.get_fd_index_for_gid(ng - 1)
    assert 0 <= max_fd < font.get_fd_array().size()
    # Past the covered range -> 0 (out of the materialised Format 0 array).
    assert font.get_fd_index_for_gid(ng) == 0


def test_per_fd_local_subr_index_selection() -> None:
    """Each FD that carries a /Subrs INDEX exposes its own local subrs;
    ``get_local_subr_index`` routes a GID to the right FD's subrs."""
    data = (_FIXTURES / "cid_multifd_localsubr_bias.cff").read_bytes()
    font = CFFCIDFont.from_bytes(data)
    fda = font.get_fd_array()
    sel = font.get_fd_select()
    # Both FDs in this fixture carry local subrs (FD1 a large biased set).
    assert fda.get_local_subrs(0) > 0
    assert fda.get_local_subrs(1) > 0
    for gid in range(sel.get_num_glyphs()):
        fd = font.get_fd_index_for_gid(gid)
        assert font.get_local_subr_index_for_gid(gid) == fda.get_local_subr_index(fd)


# --------------------------------------------------------------------------- #
# Live differential test against the running PDFBox oracle (byte reader path).
# --------------------------------------------------------------------------- #


def _parse_probe(text: str) -> dict[str, dict[str, object]]:
    """Parse CffFdSelectBytesProbe output into
    ``{case: {"cls": str, gid: value}}``."""
    out: dict[str, dict[str, object]] = {}
    current: str | None = None
    for line in text.splitlines():
        cols = line.split("\t")
        if cols[0] == "CASE":
            current = cols[1]
            out.setdefault(current, {})["cls"] = cols[2]
        elif cols[0] == "FD" and len(cols) >= 4 and current is not None:
            out[current][int(cols[2])] = cols[3]
        elif cols[0] == "ERR":
            out.setdefault(cols[1], {})["cls"] = "ERR:" + cols[2]
    return out


@requires_oracle
def test_byte_reader_matches_live_pdfbox() -> None:
    """Line-for-line: pypdfbox ``read_fd_select`` -> get_fd_index equals Apache
    PDFBox 3.0.7's ``readFDSelect`` -> getFDIndex over the byte-reader sweep on
    identical synthetic payloads. Negative GIDs for Format 0 are the documented
    divergence (Java AIOOBE, pypdfbox returns 0). Unknown format bytes throw on
    both sides (Java IllegalArgumentException, pypdfbox ValueError)."""
    java = _parse_probe(run_probe_text("CffFdSelectBytesProbe", "sweep"))

    for name, (fds, n_glyphs) in _FORMAT0_CASES.items():
        assert name in java, f"probe missing case {name}"
        sel = CFFParser.read_fd_select(
            DataInputByteArray(_format0_bytes(fds)), n_glyphs
        )
        for gid in _SWEEP:
            jval = java[name][gid]
            if gid < 0:
                assert isinstance(jval, str) and jval.startswith("ERR:"), (
                    name,
                    gid,
                    jval,
                )
                assert sel.get_fd_index(gid) == 0, (name, gid)
                continue
            assert str(sel.get_fd_index(gid)) == jval, (name, gid, jval)

    for name, (ranges, sentinel) in _FORMAT3_CASES.items():
        assert name in java, f"probe missing case {name}"
        sel = CFFParser.read_fd_select(
            DataInputByteArray(_format3_bytes(ranges, sentinel)), 0
        )
        for gid in _SWEEP:
            jval = java[name][gid]
            assert isinstance(jval, str) and not jval.startswith("ERR:"), (
                name,
                gid,
                jval,
            )
            assert str(sel.get_fd_index(gid)) == jval, (name, gid, jval)

    # Unknown format bytes: Java throws IllegalArgumentException; pypdfbox
    # raises ValueError. Both sides reject the payload.
    for fmt_name in ("unknown_fmt1", "unknown_fmt2", "unknown_fmt255"):
        jcls = java[fmt_name]["cls"]
        assert isinstance(jcls, str) and "IllegalArgumentException" in jcls, jcls
        fmt = int(fmt_name.removeprefix("unknown_fmt"))
        with pytest.raises(ValueError):
            CFFParser.read_fd_select(DataInputByteArray(bytes([fmt])), 4)
