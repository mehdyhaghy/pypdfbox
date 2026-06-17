"""Live PDFBox differential parity for COS *name / string ESCAPING* on write.

This is the escaping facet of ``COSWriter`` serialization, complementary to
``test_write_scalar_oracle.py`` (which spot-checks a handful of names/strings as
part of the all-scalar surface). Here the focus is the escape *decisions* that
are most likely to silently corrupt a PDF:

* **COSName ``#XX`` escape table** — which bytes pass through the printable
  allowlist (``A-Z a-z 0-9 $ * + - . ; @ _``) and which become ``#XX``
  (whitespace, the delimiters ``()<>[]{}/%``, ``#`` itself, every control byte,
  and every byte ``>= 0x7F``). A byte that *should* be escaped but is emitted
  raw produces a corrupt name; the wrong ``#XX`` set or wrong case is equally
  fatal.  We assert byte-equality against PDFBox for **every** byte 0x00..0xFF.
* **COSString literal ``(...)`` vs hex ``<...>`` selection** — PDFBox writes hex
  iff any byte is ``>= 0x80`` or is a CR/LF EOL byte; otherwise literal.
* **Paren handling** — PDFBox escapes *every* ``(`` and ``)`` with a backslash
  regardless of balance (it does **not** keep balanced parens unescaped), plus
  ``\\`` backslash escaping.
* **Control-byte emission** — tab / backspace / formfeed / DEL are emitted
  **raw** inside a literal string (PDFBox uses no ``\\n \\r \\t \\b \\f``
  mnemonic escapes in ``writeString``); only CR/LF force the hex branch.
* **UTF-16BE BOM string** — a ``FEFF``-prefixed string serializes as hex.
* **Forced-hex form** — ``setForceHexForm(true)`` overrides the literal choice.

The oracle is ``oracle/probes/CosEscapeProbe.java``, which drives PDFBox's own
``COSName.writePDF`` and ``COSWriter.writeString`` over a fixed battery and
prints ``<tag> <inputHex>: <outputHex>`` per case. Names in the probe are built
from raw bytes via ``new String(bytes, ISO_8859_1)`` (one byte -> one code
point); the Python side mirrors this with ``raw.decode("latin-1")`` before
``COSName.get_pdf_name`` so both encode the identical name string.

Result of this wave: pypdfbox is byte-identical to PDFBox 3.0.7 across all 291
cases — no divergence, benign or otherwise.  The round-trip tests additionally
prove the escaped form re-parses to the original COS value.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSName, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.base_parser import BaseParser
from pypdfbox.pdfwriter.cos_writer import COSWriter
from tests.oracle.harness import requires_oracle, run_probe_text


def _emit(obj: object) -> bytes:
    """Serialize a single COS leaf through ``COSWriter`` exactly as the visitor
    pipeline would, capturing the raw written bytes."""
    sink = io.BytesIO()
    writer = COSWriter(sink)
    obj.accept(writer)  # type: ignore[attr-defined]
    writer.close()
    return sink.getvalue()


def _name_bytes(raw_hex: str) -> bytes:
    """pypdfbox serialization of a name built from ``raw_hex`` the same way the
    Java probe does: decode latin-1 (one byte -> one code point), then
    ``get_pdf_name`` (which UTF-8 re-encodes for the escape table)."""
    name_str = bytes.fromhex(raw_hex).decode("latin-1") if raw_hex else ""
    return _emit(COSName.get_pdf_name(name_str))


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
    text = run_probe_text("CosEscapeProbe")
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


def _ids(prefix: str, items: list[tuple[str, str, str]]) -> list[str]:
    return [f"{prefix}_{in_hex or 'empty'}" for _tag, in_hex, _out in items]


_NAME_CASES = [c for c in _BATTERY if c[0] in ("name", "namem")]
_STRLIT_CASES = [c for c in _BATTERY if c[0] == "strlit"]
_STRHEX_CASES = [c for c in _BATTERY if c[0] == "strhex"]


# ---------------------------------------------------------- name escaping ----


@requires_oracle
@pytest.mark.parametrize(
    ("tag", "in_hex", "out_hex"),
    _NAME_CASES,
    ids=_ids("name", _NAME_CASES),
)
def test_name_escape_matches_pdfbox(tag: str, in_hex: str, out_hex: str) -> None:
    """Every name byte 0x00..0xFF plus structural multi-byte names serialize to
    exactly PDFBox's escaped form (printable allowlist vs uppercase ``#XX``)."""
    assert _name_bytes(in_hex).hex() == out_hex


# --------------------------------------------- string literal/hex escaping ----


@requires_oracle
@pytest.mark.parametrize(
    ("tag", "in_hex", "out_hex"),
    _STRLIT_CASES,
    ids=_ids("strlit", _STRLIT_CASES),
)
def test_string_literal_escape_matches_pdfbox(
    tag: str, in_hex: str, out_hex: str
) -> None:
    """Literal-vs-hex selection, paren/backslash escaping, raw control bytes,
    CR/LF forcing hex, the UTF-16BE BOM string, and the empty string all match
    PDFBox byte-for-byte."""
    assert _string_bytes(in_hex, force_hex=False).hex() == out_hex


@requires_oracle
@pytest.mark.parametrize(
    ("tag", "in_hex", "out_hex"),
    _STRHEX_CASES,
    ids=_ids("strhex", _STRHEX_CASES),
)
def test_string_forced_hex_matches_pdfbox(
    tag: str, in_hex: str, out_hex: str
) -> None:
    """``setForceHexForm(true)`` overrides the literal choice identically."""
    assert _string_bytes(in_hex, force_hex=True).hex() == out_hex


# --------------------------------------------------------- round-trip proof ----
# The escaped serialized form must re-parse to the original COS value. This is
# the safety net behind the byte-equality assertions: even where two valid
# encodings exist, the chosen form must be parseable back to the same bytes.


def _parse_name(serialized: bytes) -> COSName:
    return BaseParser(RandomAccessReadBuffer(serialized)).parse_cos_name()


def _parse_string(serialized: bytes) -> COSString:
    return BaseParser(RandomAccessReadBuffer(serialized)).parse_cos_string()


_NAME_ROUNDTRIP = [
    "Type",
    "A B",
    "A#B",
    "Name(1)",
    "Slash/Sub",
    "Pct%X",
    "br[a]ce{s}",
    "lt<gt>",
    "z\x00end",
    "é",  # e-acute -> UTF-8 multi-byte name bytes
]


@pytest.mark.parametrize("name", _NAME_ROUNDTRIP)
def test_name_escape_round_trips(name: str) -> None:
    original = COSName.get_pdf_name(name)
    serialized = _emit(original)
    parsed = _parse_name(serialized)
    assert parsed.get_bytes() == original.get_bytes()


_STRING_ROUNDTRIP = [
    b"",
    b"Hello",
    b"()",
    b"a(b)c)",
    b"(abc",
    b"a)b)",
    b"\\",
    b"a(b)\\c",
    b"\t",
    b"\x08",
    b"\x0c",
    b"\r",
    b"\n",
    b"\r\n",
    b"\x00\x01\x02\x03",
    b"\xff",
    b"ABC\xe9",
    b"\x7f",
    bytes.fromhex("feff006800e9006c006c006f"),
]


@pytest.mark.parametrize(
    "data",
    _STRING_ROUNDTRIP,
    ids=[d.hex() or "empty" for d in _STRING_ROUNDTRIP],
)
def test_string_escape_round_trips(data: bytes) -> None:
    original = COSString(data)
    serialized = _emit(original)
    parsed = _parse_string(serialized)
    assert parsed.get_bytes() == data


@pytest.mark.parametrize(
    "data",
    [b"Hello", b"()", b"", b"\xff", b"\x00\x01\x02\x03"],
    ids=["hello", "parens", "empty", "high", "binary"],
)
def test_forced_hex_round_trips(data: bytes) -> None:
    original = COSString(data)
    original.set_force_hex_form(True)
    serialized = _emit(original)
    # Forced-hex emits ``<...>``; parser must recover the identical bytes.
    assert serialized.startswith(b"<") and serialized.endswith(b">")
    parsed = _parse_string(serialized)
    assert parsed.get_bytes() == data
