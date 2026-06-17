"""Live PDFBox differential parity for ``COSString`` serialization by ``COSWriter``.

This pins the *string write* surface alone — how ``COSWriter.writeString`` decides
between the literal ``(...)`` and hex ``<...>`` forms and how it escapes the
literal form — against Apache PDFBox 3.0.7 byte-for-byte.

Complementary to ``test_cos_escape_oracle.py`` (which shares a fixed battery with
COSName escaping): here the probe ``oracle/probes/CosStringWriteProbe.java``
sweeps **every** single byte 0x00..0xFF as a one-byte string, so the per-byte
literal-vs-hex boundary is nailed at the granularity a hand-picked battery skips
(0x05, 0x10, 0x1F, 0x7F, 0x80, 0x9F, ...). PDFBox's rule, confirmed by this sweep:

* hex iff any byte is ``>= 0x80`` or is a CR (0x0D) / LF (0x0A) EOL byte;
* otherwise literal, with ``(`` ``)`` ``\\`` backslash-escaped (every paren,
  regardless of balance) and every other control byte (tab, backspace, formfeed,
  DEL 0x7F, NUL, ...) emitted **raw**;
* ``setForceHexForm(true)`` overrides the choice to hex unconditionally.

The multi-byte cases add paren-balance permutations and mixed payloads with
embedded EOL / high bytes. The round-trip tests prove the escaped form re-parses
to the original bytes.

Result: pypdfbox is byte-identical to PDFBox 3.0.7 across the full 0x00..0xFF
sweep and every multi-byte / forced-hex case — confirmed parity, no divergence.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.base_parser import BaseParser
from pypdfbox.pdfwriter.cos_writer import COSWriter
from tests.oracle.harness import requires_oracle, run_probe_text


def _emit(obj: COSString) -> bytes:
    """Serialize a single ``COSString`` through ``COSWriter`` exactly as the
    visitor pipeline would, capturing the raw written bytes."""
    sink = io.BytesIO()
    writer = COSWriter(sink)
    obj.accept(writer)
    writer.close()
    return sink.getvalue()


def _string_bytes(raw_hex: str, *, force_hex: bool) -> bytes:
    s = COSString(bytes.fromhex(raw_hex) if raw_hex else b"")
    if force_hex:
        s.set_force_hex_form(True)
    return _emit(s)


# ---------------------------------------------------------------------------
# Parse the probe battery once per session; each line becomes a parametrize id.
# ---------------------------------------------------------------------------


def _load_battery() -> list[tuple[str, str, str]]:
    """Return ``(tag, input_hex, output_hex)`` triples from the probe output."""
    text = run_probe_text("CosStringWriteProbe")
    cases: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        tag, rest = line.split(" ", 1)
        in_hex, out_hex = rest.split(": ")
        cases.append((tag, in_hex, out_hex))
    return cases


def _battery() -> list[tuple[str, str, str]]:
    try:
        return _load_battery()
    except Exception:  # noqa: BLE001 — oracle unavailable; requires_oracle skips
        return []


_BATTERY = _battery()

_SINGLE_CASES = [c for c in _BATTERY if c[0] == "single"]
_MULTI_CASES = [c for c in _BATTERY if c[0] == "multi"]
_FORCEHEX_CASES = [c for c in _BATTERY if c[0] == "forcehex"]


def _ids(prefix: str, items: list[tuple[str, str, str]]) -> list[str]:
    return [f"{prefix}_{in_hex or 'empty'}" for _tag, in_hex, _out in items]


# ------------------------------------------ exhaustive single-byte sweep ----


@requires_oracle
@pytest.mark.parametrize(
    ("tag", "in_hex", "out_hex"),
    _SINGLE_CASES,
    ids=_ids("single", _SINGLE_CASES),
)
def test_single_byte_string_matches_pdfbox(
    tag: str, in_hex: str, out_hex: str
) -> None:
    """Every byte 0x00..0xFF as a one-byte string serializes to exactly PDFBox's
    form — pinning the per-byte literal-vs-hex boundary (hex iff >= 0x80 or
    CR/LF; raw otherwise) and the ``( ) \\`` escapes."""
    assert _string_bytes(in_hex, force_hex=False).hex() == out_hex


# ----------------------------------------- multi-byte literal/hex cases ----


@requires_oracle
@pytest.mark.parametrize(
    ("tag", "in_hex", "out_hex"),
    _MULTI_CASES,
    ids=_ids("multi", _MULTI_CASES),
)
def test_multi_byte_string_matches_pdfbox(
    tag: str, in_hex: str, out_hex: str
) -> None:
    """Paren-balance permutations, backslash escapes, raw control bytes, and
    mixed payloads with embedded EOL / high bytes (forcing hex) all match
    PDFBox byte-for-byte."""
    assert _string_bytes(in_hex, force_hex=False).hex() == out_hex


# ------------------------------------------------------ forced-hex form ----


@requires_oracle
@pytest.mark.parametrize(
    ("tag", "in_hex", "out_hex"),
    _FORCEHEX_CASES,
    ids=_ids("forcehex", _FORCEHEX_CASES),
)
def test_forced_hex_string_matches_pdfbox(
    tag: str, in_hex: str, out_hex: str
) -> None:
    """``setForceHexForm(true)`` overrides the literal choice to hex identically."""
    assert _string_bytes(in_hex, force_hex=True).hex() == out_hex


# --------------------------------------------------------- round-trip proof ----
# The escaped serialized form must re-parse to the original byte payload — the
# safety net behind the byte-equality assertions above.


def _parse_string(serialized: bytes) -> COSString:
    return BaseParser(RandomAccessReadBuffer(serialized)).parse_cos_string()


_ROUNDTRIP = [
    b"",
    b"(",
    b")",
    b"()",
    b")(",
    b"(()",
    b"(())",
    b"\\(",
    b"\\\\",
    b"a(b)\\c",
    b"Hello World",
    b"ABC\rD",
    b"ABC\nD",
    b"ABC\xffD",
    b"\x00(\n)\xff",
    b"\t\x08\x08",
    b"\x7f",
    b"\x00\x05\x10\x1f",
]


@pytest.mark.parametrize(
    "data",
    _ROUNDTRIP,
    ids=[d.hex() or "empty" for d in _ROUNDTRIP],
)
def test_string_write_round_trips(data: bytes) -> None:
    original = COSString(data)
    serialized = _emit(original)
    parsed = _parse_string(serialized)
    assert parsed.get_bytes() == data
