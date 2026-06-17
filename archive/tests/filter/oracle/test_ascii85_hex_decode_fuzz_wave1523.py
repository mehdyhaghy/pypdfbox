"""Differential ASCII85 / ASCIIHex DECODE fuzz vs Apache PDFBox 3.0.7 (wave 1523).

A deeper, filter-specific complement to the generic wave-1505
``test_filter_decode_fuzz_oracle`` corpus. Where that file mutates one clean
body per filter, this one hand-builds the ASCII85- and ASCIIHex-specific edge
cases that only surface on these two codecs:

* ASCII85: the Adobe ``<~`` intro marker (present / absent / lone), the ``~``
  end-of-data byte and its single-byte termination, the ``z`` 4-zero shorthand
  at vs. away from a group boundary, partial final groups of 1..4 chars, a
  5-char group whose base-85 value exceeds 2^32 (wrap), chars outside
  ``!``..``u`` (including bytes above ``~``), embedded NUL/TAB/FF/VT (which
  upstream does NOT treat as whitespace), interleaved real whitespace, garbage
  after EOD, and the empty / lone-EOD bodies.
* ASCIIHex: odd trailing nibble (zero-padded), whitespace splitting a pair,
  non-hex chars (which upstream tolerates, feeding ``-1`` into the nibble math),
  case folding, embedded NUL / high byte, whitespace-only, garbage after the
  ``>`` EOD, and the empty / lone-EOD bodies.

Both engines decode the *identical* bytes and are compared on the same stable
projection ``FilterFuzzProbe`` uses (``oracle/probes/Ascii85HexDecodeFuzzProbe``
is the Java side):

    ok=true
    len=<decoded byte count>
    sha=<first 8 hex of SHA-256 of the decoded bytes>

or the sole line ``ok=false`` on a decode-time throw. For the byte-stream ASCII
filters both sides share the same algorithm, so the projection is pinned EXACT
(ok + len + sha) — except the one documented missing-``~>`` artifact below.

REAL bug this wave found + fixed (``pypdfbox/filter/ascii85_decode.py``):
``ASCII85Decode`` stopped only at the two-byte ``~>`` marker, but upstream's
``ASCII85InputStream`` ends the stream at the FIRST ``~`` byte alone (the ``>``
is incidental framing). So ``87cURD~X`` and the Adobe ``<~`` intro (whose ``~``
sits at index 1) diverged. Now ``_decode_bytes`` truncates at the first ``~``,
matching upstream byte-for-byte. ``<~`` is not special-cased — ``<`` is an
ordinary base-85 digit and the following ``~`` terminates, exactly as upstream.

PINNED-LOOSE divergence (``a85_no_eod_full``, mode ``ok``): a full body with
NO ``~`` terminator. Upstream's ``ASCII85InputStream`` reads past EOF and
over-extends the final partial group (one extra byte) while pypdfbox stops at
the buffer end. This is the same harness-only artifact the module header and the
wave-1505 ``a85_truncated_final_group`` mutant document; real PDF ASCII85
streams always carry the terminator. Only the ``ok`` boolean is compared.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import tempfile

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.filter import FilterFactory
from tests.oracle.harness import requires_oracle, run_probe_text

# Adobe-framed ASCII85 of b"Hello world" (base64.a85encode(..., adobe=True)).
_HW = b"<~87cURD]j7BEbo7~>"
_HW_NO_INTRO = b"87cURD]j7BEbo7~>"
_HW_NO_EOD = b"87cURD]j7BEbo7"


# Each entry: (name, filter_name, encoded_bytes, mode).
# mode "exact" -> compare ok+len+sha; mode "ok" -> compare only the ok boolean.
_Case = tuple[str, str, bytes, str]


def _ascii85_cases() -> list[_Case]:
    out: list[_Case] = []

    def add(name: str, body: bytes, mode: str = "exact") -> None:
        out.append((name, "ASCII85Decode", body, mode))

    add("a85_empty", b"")
    add("a85_lone_eod", b"~>")
    add("a85_lone_tilde", b"~")
    # Adobe <~ intro: the '~' at index 1 terminates -> a lone leading '<'
    # digit (partial group of 1) -> zero bytes. Upstream does NOT strip <~.
    add("a85_intro_present", _HW)
    add("a85_intro_no_eod", b"<~87cURD]j7BEbo7")
    add("a85_intro_only", b"<~~>")
    add("a85_lt_tilde_alone", b"<~")
    add("a85_no_intro_eod", _HW_NO_INTRO)
    add("a85_data_before_intro", b"\n<~87cURD~>")
    # '<' is an ordinary base-85 digit (0x3c - '!' = 27) when no '~' follows.
    add("a85_lt_only_no_tilde", b"<87cURD~>")
    add("a85_five_lt_group", b"<<<<<~>")
    # The '~' byte terminates on its own, '>' not required / what follows ignored.
    add("a85_tilde_then_char", b"87cURD~X")
    add("a85_double_tilde", b"87cURD~~")
    add("a85_tilde_mid_group", b"87cU~RD~>")
    add("a85_group4_then_tilde", b"87cU~")
    # z 4-zero shorthand.
    add("a85_z_at_start", b"z~>")
    add("a85_z_then_tilde", b"z~")
    add("a85_z_midgroup", b"8z7c~>")
    add("a85_z_after_full_group", b"87cURz~>")
    add("a85_z_with_data_after", b"zz87cU~>")
    # partial final groups of 1..4 chars (1 -> dropped, n -> n-1 bytes).
    add("a85_partial_1char", b"8~>")
    add("a85_partial_2char", b"87~>")
    add("a85_partial_3char", b"87c~>")
    add("a85_partial_4char", b"87cU~>")
    # 5-char group whose base-85 value overflows 2^32 (32-bit wrap).
    add("a85_5char_overflow", b"s8W-!~>")
    add("a85_all_u_group", b"uuuuu~>")
    # chars outside !..u (but <= ~ are valid digits; > ~ is invalid).
    add("a85_char_v_above_u", b"87cUv~>")
    add("a85_char_brace", b"87cU{~>")
    add("a85_char_0x7f", b"87cU\x7f~>")
    # NUL / TAB / FF / VT are NOT whitespace upstream — they are digits/invalid.
    add("a85_null_byte", b"87\x00cU~>")
    add("a85_tab_byte", b"87\tcU~>")
    add("a85_ff_byte", b"87\x0ccU~>")
    add("a85_vt_byte", b"87\x0bcU~>")
    # real whitespace (LF CR SP) interleaved is ignored.
    add("a85_ws_interleave", b"8 7\nc\rU RD~>")
    add("a85_garbage_after_eod", b"87cURD~>GARBAGE")
    # Missing terminator entirely -> read-past-EOF artifact, pinned loose.
    add("a85_no_eod_full", _HW_NO_EOD, "ok")
    return out


def _asciihex_cases() -> list[_Case]:
    out: list[_Case] = []

    def add(name: str, body: bytes, mode: str = "exact") -> None:
        out.append((name, "ASCIIHexDecode", body, mode))

    add("ahx_empty", b"")
    add("ahx_eod_only", b">")
    add("ahx_clean", b"48656c6c6f>")
    add("ahx_no_eod", b"48656c6c6f")
    add("ahx_odd_digits", b"4865c>")
    add("ahx_odd_no_eod", b"4865c")
    add("ahx_single_nibble", b"4>")
    add("ahx_single_nibble_no_eod", b"4")
    add("ahx_uppercase", b"48656C6C6F>")
    add("ahx_lowercase", b"48656c6c6f>")
    add("ahx_mixed_case", b"48656C6c6F>")
    add("ahx_ws_between", b"48 65\n6c\t6c\r6f>")
    add("ahx_ws_split_pair", b"4 8 6 5>")
    add("ahx_nonhex_char", b"48ZZ6c>")
    add("ahx_nonhex_single", b"4G65>")
    add("ahx_nul_inside", b"48\x0065>")
    add("ahx_high_byte", b"48\xff65>")
    add("ahx_only_ws", b" \n\t\r>")
    add("ahx_only_ws_no_eod", b" \n\t\r")
    add("ahx_garbage_after_eod", b"4865>GARBAGE")
    add("ahx_odd_three_digits", b"486>")
    return out


_CORPUS: list[_Case] = _ascii85_cases() + _asciihex_cases()
_CORPUS_IDS = [c[0] for c in _CORPUS]


def _sha_prefix(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def _py_dump(filter_name: str, encoded: bytes, mode: str) -> str:
    try:
        flt = FilterFactory.get(filter_name)
        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("Filter"), COSName.get_pdf_name(filter_name))
        out = io.BytesIO()
        flt.decode(io.BytesIO(encoded), out, d, 0)
        decoded = out.getvalue()
    except Exception:
        return "ok=false\n"
    if mode == "ok":
        return "ok=true\n"
    return f"ok=true\nlen={len(decoded)}\nsha={_sha_prefix(decoded)}\n"


def _java_dump(filter_name: str, encoded: bytes, mode: str) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
        raw = run_probe_text("Ascii85HexDecodeFuzzProbe", tmp, filter_name)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
    if mode == "ok":
        return "ok=false\n" if raw.startswith("ok=false") else "ok=true\n"
    return raw


@requires_oracle
@pytest.mark.parametrize(
    ("name", "filter_name", "encoded", "mode"),
    _CORPUS,
    ids=_CORPUS_IDS,
)
def test_ascii85_hex_decode_fuzz_parity(
    name: str, filter_name: str, encoded: bytes, mode: str
) -> None:
    java = _java_dump(filter_name, encoded, mode)
    py = _py_dump(filter_name, encoded, mode)
    assert py == java, (
        f"divergence on {filter_name} mutant {name!r} (mode={mode}):\n"
        f" java={java!r}\n  py={py!r}"
    )


def test_clean_bodies_round_trip() -> None:
    """A corpus-build regression must not turn every mutant into a vacuous pass."""

    def decode(filter_name: str, encoded: bytes) -> bytes:
        out = io.BytesIO()
        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("Filter"), COSName.get_pdf_name(filter_name))
        FilterFactory.get(filter_name).decode(io.BytesIO(encoded), out, d, 0)
        return out.getvalue()

    assert decode("ASCII85Decode", _HW_NO_INTRO) == b"Hello world"
    assert decode("ASCIIHexDecode", b"48656c6c6f>") == b"Hello"
