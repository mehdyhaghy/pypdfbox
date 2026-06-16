"""Differential fuzz of the Type 1 PFB *segment* + eexec-boundary parser.

Targets the IBM-style ``0x80 type size_le32 payload`` record framing shared by
``PfbParser`` (``pypdfbox.fontbox.pfb.pfb_parser``) and the inline splitter in
``Type1Font.create_with_pfb`` — distinct from wave 1546, which fuzzed the
charstring *interpreter*. We feed ~30 malformed / edge PFB byte streams and
pin, for each, whether ``PfbParser`` throws (type + message) or yields its
three segment lengths, plus what ``Type1Font.create_with_pfb`` makes of the
same bytes (name / #glyphs / #subrs or exception).

Expected values were captured from Apache PDFBox 3.0.7 via
``oracle/probes/Type1PfbSegmentFuzzProbe.java`` (``PfbParser(byte[])`` +
``Type1Font.createWithPFB(byte[])``) and asserted as literals so the suite is
green without the oracle; the trailing ``@requires_oracle`` test reproduces the
probe's canonical lines from pypdfbox and compares them verbatim.

Cases are constructed deterministically from a genuine ``.pfb`` fixture's three
records (``DemoType1.pfb``) so segment lengths are reproducible.

Honest divergences (pinned, not "fixed"):

* ``create_with_pfb`` is *tolerant* of an empty / segment-less PFB and a lone
  trailing ``0x80`` marker — it returns a font with an empty name where PDFBox
  raises ``IOException`` (the documented "tolerant defaults" posture of
  ``Type1Parser.parse``; see CHANGES.md). PDFBox's ``PfbParser`` itself agrees
  with us on the *segment* result for the empty case (``[0, 0, 0]``).
* For a lone trailing ``0x80`` marker, PDFBox's ``PfbParser`` reads ``-1`` past
  EOF and reports ``Incorrect record type: -1``; pypdfbox's stream-based reader
  detects the short read first and reports ``EOF while reading PFB header``.
  Both reject — only the message differs (Python has no ``read() -> -1`` idiom).

Bug fixed this wave: ``PfbParser.parse_pfb`` decoded the 4-byte size field as
*unsigned*, so a record whose top size byte had the high bit set surfaced as a
huge positive size and tripped the "would be larger than the input" guard
instead of upstream's "is negative" guard. ``create_with_pfb`` already used a
signed decode; ``PfbParser`` now matches (see ``size_high_bit_negative`` /
``size_negative_big``).
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pypdfbox.fontbox.pfb.pfb_parser import PfbParser
from pypdfbox.fontbox.type1.type1_font import Type1Font
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "type1"
_EOF = bytes([0x80, 0x03])


def _records(pfb: bytes) -> list[tuple[int, bytes]]:
    """Split a genuine .pfb into ``(type, payload)`` records (ignores EOF)."""
    out: list[tuple[int, bytes]] = []
    pos = 0
    while pos < len(pfb):
        if pfb[pos] != 0x80:
            break
        kind = pfb[pos + 1]
        if kind == 0x03:
            break
        size = int.from_bytes(pfb[pos + 2 : pos + 6], "little")
        out.append((kind, pfb[pos + 6 : pos + 6 + size]))
        pos += 6 + size
    return out


def _rec(kind: int, payload: bytes) -> bytes:
    return bytes([0x80, kind]) + struct.pack("<i", len(payload)) + payload


_DEMO = _records((_FIXTURES / "DemoType1.pfb").read_bytes())
_A1, _B, _A2 = _DEMO[0][1], _DEMO[1][1], _DEMO[2][1]


def _build_cases() -> dict[str, bytes]:
    """Construct the malformed / edge PFB byte streams (~30 cases)."""
    cases: dict[str, bytes] = {}
    valid = _rec(1, _A1) + _rec(2, _B) + _rec(1, _A2) + _EOF
    cases["valid_pfb"] = valid
    cases["no_eof_marker"] = _rec(1, _A1) + _rec(2, _B) + _rec(1, _A2)

    bad = bytearray(valid)
    bad[0] = 0x81
    cases["wrong_start_marker"] = bytes(bad)

    two = _rec(1, _A1) + _rec(2, _B) + _rec(1, _A2) + _EOF
    bad2 = bytearray(two)
    bad2[6 + len(_A1)] = 0x7F
    cases["wrong_start_marker_rec2"] = bytes(bad2)

    cases["bad_record_type"] = _rec(5, _A1) + _EOF
    cases["record_type_zero"] = _rec(0, _A1) + _EOF
    cases["size_larger_than_input"] = (
        bytes([0x80, 1]) + struct.pack("<i", len(_A1) * 40) + _A1[:10]
    )
    cases["size_high_bit_negative"] = bytes([0x80, 1, 0, 0, 0, 0x80]) + _A1
    cases["size_negative_big"] = bytes([0x80, 2, 1, 0, 0, 0x80]) + _B
    cases["truncated_mid_payload"] = (
        bytes([0x80, 1]) + struct.pack("<i", len(_A1)) + _A1[: len(_A1) // 2]
    )
    cases["truncated_size_field"] = bytes([0x80, 1, 0x10, 0x00]) + bytes(14)
    cases["eof_immediately"] = _EOF + bytes(20)
    cases["too_short"] = bytes([0x80, 1, 0, 0, 0, 0])
    cases["zeros_18"] = bytes(18)
    cases["trailing_lone_marker"] = (
        _rec(1, _A1) + _rec(2, _B) + _rec(1, _A2) + bytes([0x80])
    )
    cases["extra_ascii_segment"] = (
        _rec(1, _A1) + _rec(2, _B) + _rec(1, b"extra ") + _rec(1, _A2) + _EOF
    )
    cases["two_binary_segments"] = (
        _rec(1, _A1)
        + _rec(2, _B[: len(_B) // 2])
        + _rec(2, _B[len(_B) // 2 :])
        + _rec(1, _A2)
        + _EOF
    )
    cases["zero_len_first"] = (
        _rec(1, b"") + _rec(1, _A1) + _rec(2, _B) + _rec(1, _A2) + _EOF
    )
    cases["no_trailing_cleartomark"] = _rec(1, _A1) + _rec(2, _B) + _EOF
    cases["trailing_no_cleartomark_word"] = (
        _rec(1, _A1) + _rec(2, _B) + _rec(1, b"junkjunk no keyword here " * 5) + _EOF
    )
    cases["large_cleartomark_seg"] = (
        _rec(1, _A1)
        + _rec(2, _B)
        + _rec(2, b"")
        + _rec(1, b"cleartomark " + b"x" * 650)
        + _EOF
    )
    cases["records_after_eof"] = _rec(1, _A1) + _EOF + _rec(2, _B) + _rec(1, _A2)
    cases["zero_size_binary"] = _rec(1, _A1) + _rec(2, b"") + _rec(1, _A2) + _EOF
    cases["corrupt_eexec_first_byte"] = (
        _rec(1, _A1) + _rec(2, bytes([_B[0] ^ 0xFF]) + _B[1:]) + _rec(1, _A2) + _EOF
    )
    cases["eexec_below_warmup"] = _rec(1, _A1) + _rec(2, _B[:3]) + _rec(1, _A2) + _EOF
    cases["swapped_segments"] = _rec(2, _A1) + _rec(1, _B) + _rec(1, _A2) + _EOF
    cases["marker_then_eof"] = _rec(1, _A1) + _EOF
    cases["only_ascii"] = _rec(1, _A1) + _EOF
    ct599 = b"cleartomark " + b"y" * 587
    assert len(ct599) == 599
    cases["cleartomark_599"] = _rec(1, _A1) + _rec(2, _B) + _rec(1, ct599) + _EOF
    return cases


_CASES = _build_cases()

# Oracle-confirmed (PDFBox 3.0.7) canonical lines per case.
#   "PFB OK l0 l1 l2"  | "PFB ERR <ExceptionSimpleName> <message>"
#   "FONT OK <name> <nglyphs> <nsubrs>" | "FONT ERR <ExceptionSimpleName>"
_EXPECTED: dict[str, tuple[str, str]] = {
    "valid_pfb": ("PFB OK 501 523 552", "FONT OK DemoType1 5 0"),
    "no_eof_marker": ("PFB OK 501 523 552", "FONT OK DemoType1 5 0"),
    "wrong_start_marker": (
        "PFB ERR IOException Start marker missing",
        "FONT ERR IOException",
    ),
    "wrong_start_marker_rec2": (
        "PFB ERR IOException Start marker missing",
        "FONT ERR IOException",
    ),
    "bad_record_type": (
        "PFB ERR IOException Incorrect record type: 5",
        "FONT ERR IOException",
    ),
    "record_type_zero": (
        "PFB ERR IOException Incorrect record type: 0",
        "FONT ERR IOException",
    ),
    "size_larger_than_input": (
        "PFB ERR IOException PFB header missing",
        "FONT ERR IOException",
    ),
    "size_high_bit_negative": (
        "PFB ERR IOException record size -2147483648 is negative",
        "FONT ERR IOException",
    ),
    "size_negative_big": (
        "PFB ERR IOException record size -2147483647 is negative",
        "FONT ERR IOException",
    ),
    "truncated_mid_payload": (
        "PFB ERR IOException record size 501 would be larger than the input",
        "FONT ERR IOException",
    ),
    "truncated_size_field": (
        "PFB ERR EOFException EOF while reading PFB font",
        "FONT ERR EOFException",
    ),
    "eof_immediately": ("PFB OK 0 0 0", "FONT ERR IOException"),
    "too_short": ("PFB ERR IOException PFB header missing", "FONT ERR IOException"),
    "zeros_18": ("PFB ERR IOException Start marker missing", "FONT ERR IOException"),
    "trailing_lone_marker": (
        "PFB ERR IOException Incorrect record type: -1",
        "FONT ERR IOException",
    ),
    "extra_ascii_segment": ("PFB OK 507 523 552", "FONT OK DemoType1 5 0"),
    "two_binary_segments": ("PFB OK 501 523 552", "FONT OK DemoType1 5 0"),
    "zero_len_first": ("PFB OK 501 523 552", "FONT OK DemoType1 5 0"),
    "no_trailing_cleartomark": ("PFB OK 501 523 0", "FONT OK DemoType1 5 0"),
    "trailing_no_cleartomark_word": ("PFB OK 626 523 0", "FONT OK DemoType1 5 0"),
    "large_cleartomark_seg": ("PFB OK 1163 523 0", "FONT OK DemoType1 5 0"),
    "records_after_eof": ("PFB OK 501 0 0", "FONT OK DemoType1 0 0"),
    "zero_size_binary": ("PFB OK 501 0 552", "FONT OK DemoType1 0 0"),
    "corrupt_eexec_first_byte": ("PFB OK 501 523 552", "FONT ERR IOException"),
    "eexec_below_warmup": ("PFB OK 501 3 552", "FONT ERR IOException"),
    "swapped_segments": ("PFB OK 523 501 552", "FONT ERR IOException"),
    "marker_then_eof": ("PFB OK 501 0 0", "FONT OK DemoType1 0 0"),
    "only_ascii": ("PFB OK 501 0 0", "FONT OK DemoType1 0 0"),
    "cleartomark_599": ("PFB OK 501 523 599", "FONT OK DemoType1 5 0"),
}

# Cases where pypdfbox's *tolerant* parse deliberately diverges from PDFBox on
# the FONT line (see module docstring). The PFB (segment) line still matches.
_FONT_DIVERGENCE = {
    # PDFBox raises on empty/segment-less PFB; pypdfbox returns an empty-name
    # font (Type1Parser tolerant defaults).
    "eof_immediately": "FONT OK  0 0",
    # PDFBox's PfbParser reports "Incorrect record type: -1" (read() == -1);
    # pypdfbox's stream reader reports the short read first AND create_with_pfb
    # tolerates the lone trailing marker, parsing the font.
    "trailing_lone_marker": "FONT OK DemoType1 5 0",
    # Corrupt / sub-warmup eexec ciphertext: PDFBox runs its private-dict
    # interpreter over the decrypted bytes and raises when they are garbage;
    # pypdfbox does NOT run that interpreter (it stores the raw decrypted bytes
    # and lets accessor-side defaults stand), so the valid cleartext segment 1
    # still yields the font name with an empty CharStrings/Subrs surface. This
    # is the documented "tolerant defaults" posture (see CHANGES.md). Segment 1
    # is intact in both cases, so the name survives; #glyphs / #subrs are 0.
    "corrupt_eexec_first_byte": "FONT OK DemoType1 0 0",
    "eexec_below_warmup": "FONT OK DemoType1 0 0",
    # Segments swapped (binary eexec bytes fed to segment 1, cleartext header
    # fed to segment 2): PDFBox's interpreter raises; pypdfbox tolerantly lexes
    # the binary "header" (no /FontName surfaces -> empty name) and yields an
    # empty surface. Pinned here mainly as the regression anchor for the
    # infinite-loop / hex-string crash fixes this wave (a stray ``)`` and a
    # stray ``<`` in binary bytes no longer hang / crash the cleartext lexer).
    "swapped_segments": "FONT OK  0 0",
}

# Cases where the *PFB* (segment) error message differs (read()==-1 vs short
# read) even though both reject.
_PFB_DIVERGENCE = {
    "trailing_lone_marker": "PFB ERR OSError EOF while reading PFB header",
}

_CASE_NAMES = sorted(_CASES)


def _pfb_line(blob: bytes) -> str:
    try:
        lengths = PfbParser(blob).get_lengths()
    except (OSError, EOFError) as exc:
        return f"PFB ERR {type(exc).__name__} {exc}"
    return f"PFB OK {lengths[0]} {lengths[1]} {lengths[2]}"


def _font_line(blob: bytes) -> str:
    try:
        font = Type1Font.create_with_pfb(blob)
    except (OSError, EOFError) as exc:
        return f"FONT ERR {type(exc).__name__}"
    n_glyphs = len(font.get_char_strings_dict())
    return f"FONT OK {font.get_name()} {n_glyphs} {font.get_subrs()}"


def _normalise_java_exc(line: str) -> str:
    """Fold Java exception class names onto Python's for comparison.

    The probe emits ``IOException`` / ``EOFException``; pypdfbox raises
    ``OSError`` (and ``EOFError`` for the truncated-payload short read, which is
    itself an ``OSError`` subclass). Compare on the message, not the class.
    """
    return (
        line.replace(" IOException ", " OSError ")
        .replace(" EOFException ", " EOFError ")
        .replace(" IOException", " OSError")
        .replace(" EOFException", " EOFError")
    )


@pytest.mark.parametrize("name", _CASE_NAMES)
def test_pfb_segment_line(name: str) -> None:
    expected = _PFB_DIVERGENCE.get(name) or _normalise_java_exc(_EXPECTED[name][0])
    assert _pfb_line(_CASES[name]) == expected


@pytest.mark.parametrize("name", _CASE_NAMES)
def test_pfb_font_line(name: str) -> None:
    expected = _FONT_DIVERGENCE.get(name) or _normalise_java_exc(_EXPECTED[name][1])
    assert _font_line(_CASES[name]) == expected


def test_size_high_bit_decoded_as_signed() -> None:
    """Regression: a top-bit-set size byte must surface as a *negative* size
    (matching upstream + ``create_with_pfb``), not a huge positive one."""
    blob = bytes([0x80, 1, 0, 0, 0, 0x80]) + _A1
    with pytest.raises(OSError, match=r"record size -2147483648 is negative"):
        PfbParser(blob)


def test_pfb_parser_and_create_with_pfb_agree_on_negative_size() -> None:
    """Both PFB-splitting paths must reject a negative size identically."""
    blob = bytes([0x80, 2, 1, 0, 0, 0x80]) + _B
    msg = r"record size -2147483647 is negative"
    with pytest.raises(OSError, match=msg):
        PfbParser(blob)
    with pytest.raises(OSError, match=msg):
        Type1Font.create_with_pfb(blob)


# --------------------------------------------------------------------------
# Live differential: reproduce the probe's canonical lines from pypdfbox.
# --------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize("name", _CASE_NAMES)
def test_pfb_segment_fuzz_matches_oracle(name: str) -> None:
    import base64  # noqa: PLC0415

    blob = _CASES[name]
    oracle = run_probe_text(
        "Type1PfbSegmentFuzzProbe", base64.b64encode(blob).decode("ascii")
    ).splitlines()
    assert len(oracle) == 2
    pfb_oracle, font_oracle = oracle

    # PFB (segment) line: pinned exact unless a documented message-only
    # divergence (read()==-1 vs short read).
    if name in _PFB_DIVERGENCE:
        assert _pfb_line(blob) == _PFB_DIVERGENCE[name]
    else:
        assert _pfb_line(blob) == _normalise_java_exc(pfb_oracle)

    # FONT line: pinned exact unless a documented tolerant-parse divergence.
    if name in _FONT_DIVERGENCE:
        assert _font_line(blob) == _FONT_DIVERGENCE[name]
    else:
        assert _font_line(blob) == _normalise_java_exc(font_oracle)
