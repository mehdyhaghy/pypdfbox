"""Adversarial / fuzz parity tests for the JBIG2 MMR (ITU-T T.6 / CCITT-G4) decoder.

Wave 1499 fuzz wave. The happy-path strips (``test_mmr_decompressor.py`` +
``oracle/test_mmr_oracle.py``) are produced by Pillow/libtiff and therefore only
ever exercise *valid* Group-4 data, leaving the decoder's defensive residue
uncovered:

* the ``except Exception → MMRConstants.EOF`` block that mirrors upstream's
  ``catch (Throwable)`` in ``uncompress2D`` (MMRDecompressor.java:459-488),
* the ``code is None`` truncated-table-walk branches (mode loop + the two H-mode
  inner loops, MMRDecompressor.java:314-318, 344-345, 368-369),
* the default / "Should not happen" branch and its 1-D EOL fallback
  (MMRDecompressor.java:417-432),
* the negative-run terminator branches inside H mode
  (MMRDecompressor.java:350-355, 374-378).

These are reachable only with *hand-assembled* adversarial MMR bitstreams, built
here bit-by-bit per the ITU-T T.6 2-D code tables (mode/white/black). Each stream
is driven through BOTH the upstream Apache PDFBox decoder (via
``oracle/probes/MmrProbe.java``) and pypdfbox, asserting:

* byte parity where Java decodes a (possibly partial) bitmap — including the
  ``catch(Throwable)→EOF`` path, which leaves the remaining lines zero-filled;
* error-class parity where the corrupt stream makes Java throw an UNCAUGHT
  ``ArrayIndexOutOfBoundsException`` (the array-init at the top of ``uncompress2D``
  runs OUTSIDE the try, so a negative ``refRunLength`` from a previous EOL line
  escapes) — pypdfbox must raise the equivalent ``IndexError`` rather than
  silently wrapping the negative list index and decoding on (wave-1499 bug fix).

Bit convention: codes are MSB-first within each byte, matching the little-endian
two-level lookup tables; trailing bits are zero-padded to the byte boundary.
"""

from __future__ import annotations

import subprocess

import pytest

from pypdfbox.jbig2.decoder.mmr.mmr_constants import MMRConstants
from pypdfbox.jbig2.decoder.mmr.mmr_decompressor import Code, MMRDecompressor
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from tests.oracle.harness import requires_oracle, run_probe_text


def _py_decode(strip_hex: str, width: int, height: int) -> str:
    """Decode with pypdfbox, formatted like MmrProbe: 'w h stride hexbytes'."""
    iis = ImageInputStream(bytes.fromhex(strip_hex))
    bitmap = MMRDecompressor(width, height, iis).uncompress()
    return (
        f"{bitmap.get_width()} {bitmap.get_height()} {bitmap.get_row_stride()} "
        f"{bytes(bitmap.get_byte_array()).hex()}"
    )


# --------------------------------------------------------------------------- #
# Streams where Java decodes a (partial) bitmap; pypdfbox must match byte-exact.
# Each tuple: (name, strip_hex, width, height).
# --------------------------------------------------------------------------- #
_DECODES = [
    # An explicit EOL (000000000001) used as a MID-DATA mode code: hits the
    # default / "Should not happen" branch (offset != 12 so NOT the 1-D
    # fallback), which sets currentLineBitPosition = width and continues.
    ("eol_mode_midline", "8008", 8, 2),
    # EXT2D (runLength 9) and EXT1D (runLength 10) as mode codes also fall into
    # the default branch.
    ("ext2d_mode", "81e0", 8, 2),
    ("ext1d_mode", "8078", 8, 2),
    # H mode then a negative-run terminator (EOF code, runLength < 0) in the
    # first inner (white) loop: runOffsets[..] = pos, code = None, break.
    ("h_white_neg", "2000", 8, 1),
    # H mode, valid first half, then a negative-run terminator in the second
    # (black) inner loop: the other null/negative H branch.
    ("h_secondhalf_neg", "2e0000", 8, 1),
    # A lone EOL on a 1-row bitmap: detect_and_skip_eol territory, code == None
    # at top of the mode loop -> uncompress2D returns EOL, count handled.
    ("only_eol", "0010", 8, 1),
    # 8-bit prefix 00000001 maps to a None mode-table slot -> code is None at the
    # very top of the decode loop (offset++ ; break ; return EOL). 1-row keeps
    # refRunLength from going negative on a following line.
    ("modenone_h1", "01", 8, 1),
    ("clean_then_none", "8080", 8, 2),
    # PASS-mode / VR1 storms: the reference-offset walk eventually terminates the
    # line cleanly (count == 0) leaving the bitmap zero-filled. Cheap valid-shape
    # corrupt inputs that still must byte-match upstream.
    ("pass_storm_blank", "11" * 30, 20, 3),
    (
        "vr1_storm_blank",
        "6db6db6db6db6db6db6db6db6db6db6db6db6db6db6db6db6db6db6db6db",
        30,
        3,
    ),
    # Mixed / single vertical-2 and vertical-3 modes (VR2/VL2/VR3/VL3) — the
    # less-travelled vertical-mode bodies. Valid 2-D coding, decodes a real
    # (non-blank) bitmap that must byte-match upstream.
    ("vmix_vr2_vl2_vr3_vl3", "040c20e081841c10308380", 24, 3),
    ("vl2_only", "082841420a", 24, 3),
    ("vl3_only", "040a08141028", 24, 3),
    # H mode whose run crosses a reference-line transition before reaching width:
    # exercises the H-mode trailing reference-offset advance.
    ("h_ref_advance", "314e50", 24, 2),
    # A leading EOL at offset 0 (12 bits) triggers the legacy 1-D EOL fallback
    # (uncompress1D x3). With a white-then-black run per 1-D line, the inner loop
    # reads the BLACK code table -- the only route into that branch.
    ("eol_1d_fallback_black", "001c0b817028000000000000", 16, 1),
]


# --------------------------------------------------------------------------- #
# Streams that overflow run_offsets INSIDE the try -> upstream catch(Throwable)
# returns EOF (MMRDecompressor.java:459-488) -> uncompress() breaks the line loop
# and the remaining rows stay zero-filled. Upstream also dumps a multi-line
# diagnostic to stdout before the bitmap line, so we compare only the final
# 'w h stride hex' line. A long run of vertical-left-1 (010) codes emits one
# run-offset per code until current_buffer_offset overruns the (width + 5) array.
# --------------------------------------------------------------------------- #
# 200 vertical-left-1 mode codes (010) packed MSB-first -> "492" * 50.
_VL1_STORM = "492" * 50
_CATCH_EOF = [
    ("vl1_storm_catch_eof_w8", _VL1_STORM, 8, 2),
    ("vl1_storm_catch_eof_w16", _VL1_STORM, 16, 3),
]


# --------------------------------------------------------------------------- #
# Streams where the corrupt data makes Java throw an UNCAUGHT
# ArrayIndexOutOfBoundsException (probe exits non-zero); pypdfbox must raise the
# equivalent IndexError. (name, strip_hex, width, height).
# --------------------------------------------------------------------------- #
_CRASHES = [
    # Line 0 returns EOL (code None at top), so refRunLength becomes -1; line 1's
    # array-init (reference_offsets[-1], OUTSIDE the try) is the divergence site.
    ("modenone_then_line_crash", "0180", 8, 2),
    # Truncated H makeup run on a multi-line bitmap: same negative-refRunLength
    # escape on the next line.
    ("truncated_h_crash", "3b", 200, 4),
    # All-zero stream: degenerate codes drive a line to EOL then crash next line.
    ("allzero_crash", "0000000000000000", 16, 4),
    # Leading EOL with offset == 12 triggers the 1-D EOL fallback
    # (uncompress1D x3); the fabricated 1-D runs overrun the bitmap row ->
    # both Java (Bitmap.setByte) and pypdfbox throw an index-out-of-bounds error.
    ("eol_1d_fallback_crash", "0019ce60000000000000", 8, 1),
    # Vertical-left storm whose first line ends in EOL -> negative refRunLength
    # crash on line 2.
    ("vl_storm_crash", "0408102040", 16, 2),
]


@requires_oracle
@pytest.mark.parametrize(
    ("name", "strip_hex", "width", "height"),
    _DECODES,
    ids=[c[0] for c in _DECODES],
)
def test_adversarial_decode_matches_pdfbox(name, strip_hex, width, height):
    java_out = run_probe_text("MmrProbe", strip_hex, str(width), str(height)).strip()
    py_out = _py_decode(strip_hex, width, height)
    assert py_out == java_out


@requires_oracle
@pytest.mark.parametrize(
    ("name", "strip_hex", "width", "height"),
    _CATCH_EOF,
    ids=[c[0] for c in _CATCH_EOF],
)
def test_catch_eof_partial_bitmap_matches_pdfbox(name, strip_hex, width, height):
    # Upstream dumps a diagnostic before the bitmap line; compare the last line
    # only (the 'w h stride hex' record).
    java_last = (
        run_probe_text("MmrProbe", strip_hex, str(width), str(height))
        .strip()
        .splitlines()[-1]
    )
    py_out = _py_decode(strip_hex, width, height)
    assert py_out == java_last


@requires_oracle
@pytest.mark.parametrize(
    ("name", "strip_hex", "width", "height"),
    _CRASHES,
    ids=[c[0] for c in _CRASHES],
)
def test_adversarial_crash_matches_pdfbox(name, strip_hex, width, height):
    # Upstream throws an uncaught exception -> the probe process exits non-zero.
    with pytest.raises(subprocess.CalledProcessError):
        run_probe_text("MmrProbe", strip_hex, str(width), str(height))
    # pypdfbox must raise the equivalent index-out-of-bounds error, NOT silently
    # wrap a negative list index and decode a bogus bitmap.
    with pytest.raises(IndexError):
        _py_decode(strip_hex, width, height)


# --------------------------------------------------------------------------- #
# Pure-Python branch coverage (no oracle needed) for the same residue, so the
# defensive paths stay covered on machines without the jar.
# --------------------------------------------------------------------------- #
def test_vl1_storm_hits_catch_eof_block(caplog):
    """run_offsets overflow INSIDE the try -> except -> EOF, partial zero bitmap.

    Asserts the upstream-mirrored diagnostic dump is logged (proving the
    ``except Exception`` block, not a clean exit, produced the blank bitmap).
    """
    import logging

    with caplog.at_level(logging.WARNING):
        bitmap = MMRDecompressor(8, 2, ImageInputStream(bytes.fromhex(_VL1_STORM))).uncompress()
    assert bytes(bitmap.get_byte_array()) == bytes(bitmap.get_length())
    assert any("whiteRun" in r.getMessage() for r in caplog.records)


def test_negative_ref_run_length_raises_index_error():
    """A line that returns EOL must crash the next line (Java AIOOBE parity)."""
    with pytest.raises(IndexError):
        MMRDecompressor(8, 2, ImageInputStream(bytes.fromhex("0180"))).uncompress()


def test_code_none_single_line_returns_blank_bitmap():
    """code is None at the top of the mode loop -> EOL, no crash on a 1-row map."""
    bitmap = MMRDecompressor(8, 1, ImageInputStream(bytes.fromhex("01"))).uncompress()
    assert bytes(bitmap.get_byte_array()) == b"\x00"


@pytest.mark.parametrize("strip_hex", ["8008", "81e0", "8078"], ids=["eol", "ext2d", "ext1d"])
def test_default_branch_mode_codes(strip_hex):
    """EOL/EXT2D/EXT1D as a mid-data mode code -> default branch, blank line."""
    bitmap = MMRDecompressor(8, 2, ImageInputStream(bytes.fromhex(strip_hex))).uncompress()
    assert bytes(bitmap.get_byte_array()) == b"\x00\x00"


@pytest.mark.parametrize(
    ("strip_hex", "expected"),
    [
        # Captured from upstream Apache PDFBox 3.0.7 (see oracle test above).
        ("040c20e081841c10308380", "000000000000000018"),  # VR2/VL2/VR3/VL3 mix
        ("082841420a", "000000000003000000"),  # VL2
        ("040a08141028", "000000000007000000"),  # VL3
    ],
    ids=["vmix", "vl2", "vl3"],
)
def test_vertical_2_3_mode_bodies(strip_hex, expected):
    """VR2/VL2/VR3/VL3 vertical-mode bodies decode a real bitmap."""
    bitmap = MMRDecompressor(24, 3, ImageInputStream(bytes.fromhex(strip_hex))).uncompress()
    assert bytes(bitmap.get_byte_array()).hex() == expected


def test_eol_1d_fallback_decodes_via_black_table():
    """Leading EOL (offset==12) -> 1-D fallback exercising the black code table."""
    bitmap = MMRDecompressor(
        16, 1, ImageInputStream(bytes.fromhex("001c0b817028000000000000"))
    ).uncompress()
    assert bytes(bitmap.get_byte_array()) == b"\x00\x00"


def test_h_mode_reference_offset_advance():
    """H run crossing a reference transition advances the reference offset."""
    bitmap = MMRDecompressor(24, 2, ImageInputStream(bytes.fromhex("314e50"))).uncompress()
    assert bytes(bitmap.get_byte_array()).hex() == "1c0000070000"


def test_h_mode_negative_run_terminators():
    """H mode then a negative-run code (EOF terminator) in each inner loop."""
    # First inner (white) loop negative-run -> code=None, break.
    b1 = MMRDecompressor(8, 1, ImageInputStream(bytes.fromhex("2000"))).uncompress()
    assert bytes(b1.get_byte_array()) == b"\x00"
    # Valid first half, negative-run in the second (black) inner loop.
    b2 = MMRDecompressor(8, 1, ImageInputStream(bytes.fromhex("2e0000"))).uncompress()
    assert bytes(b2.get_byte_array()) == b"\x00"


# --------------------------------------------------------------------------- #
# RunData buffer-management error residue, exercised with stub streams that
# raise at the I/O boundaries the upstream RunData guards.
# --------------------------------------------------------------------------- #
class _RaiseOnLengthStream(ImageInputStream):
    """ImageInputStream whose length() raises -> RunData.__init__ except OSError."""

    def __init__(self) -> None:
        super().__init__(b"\x00\x00\x00")

    def length(self) -> int:
        raise OSError("boom")


class _EofOnReadFullStream(ImageInputStream):
    """read_full raises EOFError immediately -> fill_buffer buffer_top = -1."""

    def __init__(self) -> None:
        super().__init__(b"\x00\x00\x00")

    def read_full(self, b, off=0, length=None):
        raise EOFError


class _PartialThenEofStream(ImageInputStream):
    """read_full returns a short count, then read() raises EOFError.

    Drives fill_buffer's partial-fill loop (-1 < buffer_top < 3) whose
    ``stream.read()`` raises EOFError -> read substituted with -1 (zero byte).
    """

    def __init__(self) -> None:
        super().__init__(b"\x01\x02\x03")

    def read_full(self, b, off=0, length=None):
        b[0] = 0x01
        return 1  # short read -> triggers the partial-fill top-up loop

    def read(self) -> int:
        raise EOFError


def test_run_data_init_handles_length_oserror():
    """stream.length() raising leaves a tiny fallback buffer (no crash)."""
    rd = MMRDecompressor.RunData(_RaiseOnLengthStream())
    assert len(rd.buffer) == 10


def test_fill_buffer_handles_read_full_eof():
    """read_full raising EOFError -> buffer_top sentinel + zero-pad fill."""
    rd = MMRDecompressor.RunData(_EofOnReadFullStream())
    assert rd.buffer_top == len(rd.buffer) - 3


def test_fill_buffer_partial_then_read_eof():
    """Short read_full then read() EOFError -> the partial-fill EOF substitution."""
    rd = MMRDecompressor.RunData(_PartialThenEofStream())
    # 1 real byte read, then 2 zero-substituted bytes; top -= 3 -> 0.
    assert rd.buffer_top == 0
    assert rd.buffer[0] == 0x01


def test_code_hash_matches_equality():
    """Code.__hash__ is consistent with __eq__ (usable as a dict/set key)."""
    a = Code([4, 0x1, MMRConstants.CODE_P])
    b = Code([4, 0x1, MMRConstants.CODE_P])
    assert hash(a) == hash(b)
    assert len({a, b}) == 1
