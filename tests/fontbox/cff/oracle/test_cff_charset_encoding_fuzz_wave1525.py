"""Differential fuzz of the CFF **charset + encoding table readers** vs Apache
FontBox 3.0.7 (wave 1525).

Unlike the sibling charset/encoding oracles — which feed well-formed,
fontTools-compiled whole fonts through ``CFFParser.parse`` (a path that on the
pypdfbox side delegates to fontTools and therefore never touches the hand-ported
table readers) — this oracle drives the *private byte-level table readers*
directly on raw, hostile buffers:

* ``CFFParser.read_charset`` / ``read_format0_charset`` / ``read_format1_charset``
  / ``read_format2_charset`` (dispatch on the format byte; SID/CID-per-GID map);
* ``CFFParser.read_encoding`` / ``read_format0_encoding`` /
  ``read_format1_encoding`` / ``read_supplement`` (Format 0/1 plus the 0x80
  supplement bit; code->name map and the Format0/Format1 class identity).

The Java side reaches the same private methods by reflection
(``oracle/probes/CffCharsetEncodingFuzzProbe.java``); both engines consume the
*identical* bytes wrapped in a ``DataInputByteArray`` and are compared on a
stable projection (``OK`` + the resolved maps, or the sole line ``ERR`` on any
throw from the reader). Custom SIDs stay in the CFF Standard-String range
(<= 390) so ``read_string`` resolves identically without a populated STRING
INDEX.

Fuzz angles exercised (all confirmed byte-for-byte identical to PDFBox 3.0.7):
truncated Format 0 charset, Format 1/2 range ``nLeft`` overflow running past
``nGlyphs``, Format 2 word-sized ``nLeft``, predefined/unknown format bytes, CID
vs non-CID charset paths, range-write overshoot past ``nGlyphs``, empty buffer,
encoding Format 0 ``nCodes`` truncation, Format 1 ``nRanges`` overflow, the 0x80
supplement bit (Format 0 and Format 1), supplement SID out of the standard range,
truncated supplement, and unknown encoding base format. No production divergence
was found — this oracle pins the parity so a future re-sync cannot drift it.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.cff_charset_type1 import CFFCharsetType1
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "CffCharsetEncodingFuzzProbe"


# --------------------------------------------------------------------------- #
# pypdfbox-side projection — mirrors the Java probe field-for-field.
# --------------------------------------------------------------------------- #


def _py_charset(n_glyphs: int, is_cid: bool, data: bytes) -> str:
    parser = CFFParser()
    try:
        charset = parser.read_charset(DataInputByteArray(data), n_glyphs, is_cid)
    except Exception:  # noqa: BLE001 - any reader throw projects to ERR
        return "ERR"
    lines = ["OK", f"CID\t{str(charset.is_cid_font()).lower()}"]
    for gid in range(n_glyphs):
        try:
            sid = charset.get_sid_for_gid(gid)
        except Exception:  # noqa: BLE001 - mirror Java safeSid catch
            sid = -1
        lines.append(f"SID\t{gid}\t{sid}")
        if is_cid:
            try:
                cid = charset.get_cid_for_gid(gid)
            except Exception:  # noqa: BLE001 - mirror Java safeCid catch
                cid = -1
            lines.append(f"CIDG\t{gid}\t{cid}")
        else:
            try:
                name = charset.get_name_for_gid(gid)
            except Exception:  # noqa: BLE001 - mirror Java safeName catch
                name = "-1"
            lines.append(f"NAME\t{gid}\t{name}")
    return "\n".join(lines)


def _build_type1_charset(n_glyphs: int) -> CFFCharsetType1:
    charset = CFFCharsetType1()
    charset.add_sid(0, 0, ".notdef")
    for gid in range(1, n_glyphs):
        sid = ((gid - 1) % 390) + 1
        charset.add_sid(gid, sid, f"sid{sid}")
    return charset


def _py_encoding(n_glyphs: int, data: bytes) -> str:
    parser = CFFParser()
    charset = _build_type1_charset(n_glyphs)
    try:
        encoding = parser.read_encoding(DataInputByteArray(data), charset)
    except Exception:  # noqa: BLE001 - any reader throw projects to ERR
        return "ERR"
    lines = ["OK", f"ECLS\t{type(encoding).__name__}"]
    for code in range(256):
        name = encoding.get_name(code)
        if name and name != ".notdef":
            lines.append(f"ENAME\t{code}\t{name}")
    return "\n".join(lines)


def _run_java(mode: str, n_glyphs: int, is_cid: bool, data: bytes, tmp_path) -> str:  # noqa: ANN001
    bin_path = tmp_path / "buf.bin"
    bin_path.write_bytes(data)
    if mode == "charset":
        out = run_probe_text(
            _PROBE,
            "charset",
            str(n_glyphs),
            "true" if is_cid else "false",
            str(bin_path),
        )
    else:
        out = run_probe_text(_PROBE, "encoding", str(n_glyphs), str(bin_path))
    return out.rstrip("\n")


# --------------------------------------------------------------------------- #
# Charset corpus: (id, n_glyphs, is_cid, bytes).
# --------------------------------------------------------------------------- #

_CHARSET_CASES = [
    ("f0_ok", 4, False, b"\x00\x00\x01\x00\x02\x00\x03"),
    ("f0_truncated", 4, False, b"\x00\x00\x01"),
    ("f0_extra_data", 3, False, b"\x00\x00\x01\x00\x02\x00\x03\x00\x04"),
    ("f0_cid", 3, True, b"\x00\x00\x05\x00\x06"),
    ("f0_only_notdef", 1, False, b"\x00"),
    ("f0_zero_glyphs", 0, False, b"\x00"),
    ("f0_empty_buffer", 4, False, b""),
    ("f1_exact", 4, False, b"\x01\x00\x01\x02"),
    ("f1_nleft_overflow", 4, False, b"\x01\x00\x01\xff"),
    ("f1_truncated", 6, False, b"\x01\x00\x01\x02"),
    ("f1_overshoot_write", 3, False, b"\x01\x00\x01\x05"),
    ("f1_only_notdef", 1, False, b"\x01\x00\x01\x02"),
    ("f1_cid", 4, True, b"\x01\x00\x05\x02"),
    ("f1_cid_nleft_overflow", 4, True, b"\x01\x00\x05\xff"),
    ("f2_word_nleft", 4, False, b"\x02\x00\x01\x00\x02"),
    ("f2_nleft_overflow", 4, False, b"\x02\x00\x01\xff\xff"),
    ("f2_cid", 4, True, b"\x02\x00\x05\x00\x02"),
    ("f2_cid_nleft_overflow", 4, True, b"\x02\x00\x05\xff\xff"),
    ("unknown_format", 4, False, b"\x09"),
]

# Encoding corpus: (id, n_glyphs, bytes).
_ENCODING_CASES = [
    ("f0_ok", 3, b"\x00\x02\x41\x42"),
    ("f0_ncodes_truncated", 3, b"\x00\x05\x41"),
    ("f0_ncodes_zero", 3, b"\x00\x00"),
    ("f0_supplement", 3, b"\x80\x02\x41\x42\x01\x43\x00\x05"),
    ("f0_supplement_hi_sid", 3, b"\x80\x01\x41\x01\x42\x05\x00"),
    ("f0_supplement_truncated", 3, b"\x80\x01\x41\x05\x42"),
    ("f1_ok", 4, b"\x01\x01\x41\x02"),
    ("f1_supplement", 3, b"\x81\x01\x41\x01\x01\x43\x00\x09"),
    ("f1_nranges_overflow", 3, b"\x01\xff\x41\x02"),
    ("f1_rangeleft_big", 3, b"\x01\x01\x41\xff"),
    ("f1_multi_range", 5, b"\x01\x02\x41\x01\x50\x01"),
    ("unknown_base_format", 3, b"\x02"),
]


@requires_oracle
@pytest.mark.parametrize(
    ("n_glyphs", "is_cid", "data"),
    [(n, c, d) for _, n, c, d in _CHARSET_CASES],
    ids=[cid for cid, *_ in _CHARSET_CASES],
)
def test_charset_reader_matches_pdfbox(n_glyphs, is_cid, data, tmp_path) -> None:  # noqa: ANN001
    """``read_charset`` byte-level parity with FontBox 3.0.7 under malformed
    Format 0/1/2 charset tables (truncation, ``nLeft`` overflow, overshoot,
    CID vs non-CID, predefined/unknown format byte)."""
    java = _run_java("charset", n_glyphs, is_cid, data, tmp_path)
    py = _py_charset(n_glyphs, is_cid, data)
    assert py == java, (py, java)


@requires_oracle
@pytest.mark.parametrize(
    ("n_glyphs", "data"),
    [(n, d) for _, n, d in _ENCODING_CASES],
    ids=[cid for cid, *_ in _ENCODING_CASES],
)
def test_encoding_reader_matches_pdfbox(n_glyphs, data, tmp_path) -> None:  # noqa: ANN001
    """``read_encoding`` byte-level parity with FontBox 3.0.7 under malformed
    Format 0/1 encoding tables (``nCodes``/``nRanges`` overflow + truncation,
    the 0x80 supplement bit, supplement SID out of standard range, unknown
    base format)."""
    java = _run_java("encoding", n_glyphs, False, data, tmp_path)
    py = _py_encoding(n_glyphs, data)
    assert py == java, (py, java)
