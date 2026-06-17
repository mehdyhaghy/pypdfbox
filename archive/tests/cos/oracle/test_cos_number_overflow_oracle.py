"""Live PDFBox differential parity for the numeric-literal TOKENIZER path
(``BaseParser.parseCOSNumber``), as distinct from the direct
``COSNumber.get(String)`` API pinned by ``test_cos_number_oracle.py``.

Apache PDFBox's ``BaseParser.parseCOSNumber`` accumulates the literal's bytes
into a ``StringBuilder`` and hands the string to ``COSNumber.get``. The shared
tokenizer backs both the content-stream parser (``PDFStreamParser``) and the
document-body parser (``COSParser``). The ``CosNumberOverflowProbe`` Java oracle
feeds each literal through ``PDFStreamParser.parseNextToken`` and emits the
resulting COS leaf's type, validity, ``longValue``, ``floatValue`` bit pattern,
and ``toString``.

The load-bearing case is the **Long-overflow fallback** (PDFBOX-5176): an
integer literal beyond Java ``Long`` range does NOT become a wide integer — it
becomes the ``OUT_OF_RANGE_MAX`` / ``OUT_OF_RANGE_MIN`` ``COSInteger`` sentinel,
whose value is clamped to ``Long.MAX_VALUE`` / ``Long.MIN_VALUE`` and whose
``isValid()`` is ``False``. pypdfbox has unbounded ints, so the **value-level
contract** PDFBox exposes (``long_value`` clamped + ``is_valid()`` False) is the
thing we pin, not the literal Python integer.

Both pypdfbox number-parsing surfaces are asserted against the same Java signal:
the content-stream tokenizer (``PDFStreamParser``) and the document-body parser
(``COSParser`` — fixed this wave to route ``_wrap_number`` through
``COSNumber.get`` so the overflow sentinel matches upstream).
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.cos_parser import COSParser
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text


def _fbits_hex(value: float) -> str:
    """IEEE-754 single-precision bit pattern, lowercase hex with no leading
    zeros — matches Java ``Integer.toHexString(Float.floatToIntBits(f))``."""
    bits = struct.unpack(">I", struct.pack(">f", value))[0]
    return f"{bits:x}"


def _signal_from_token(tok: object) -> str:
    """Render the same per-arg signal string the Java probe emits."""
    if isinstance(tok, COSInteger):
        return (
            f"int|valid={'true' if tok.is_valid() else 'false'}"
            f"|long={tok.long_value()}"
            f"|fbits={_fbits_hex(tok.float_value())}"
            f"|str={tok.to_string()}"
        )
    if isinstance(tok, COSFloat):
        return (
            f"float|long={tok.long_value()}"
            f"|fbits={_fbits_hex(tok.float_value())}"
            f"|str={tok.to_string()}"
        )
    if tok is None:
        return "none"
    return f"other:{type(tok).__name__}"


def _stream_signal(lit: str) -> str:
    """Tokenize ``lit`` (trailing space, matching the probe) through pypdfbox's
    content-stream parser and render the first token's signal."""
    try:
        parser = PDFStreamParser.from_bytes((lit + " ").encode("latin-1"))
        tok = parser.parse_next_token()
        return _signal_from_token(tok)
    except Exception:  # noqa: BLE001 — mirror the probe's catch-all -> "error"
        return "error"


def _body_signal(lit: str) -> str:
    """Tokenize ``lit`` through pypdfbox's document-body parser (``COSParser``)
    and render the resulting COS number's signal."""
    try:
        src = RandomAccessReadBuffer((lit + " ").encode("latin-1"))
        tok = COSParser(src).parse_cos_number()
        return _signal_from_token(tok)
    except Exception:  # noqa: BLE001 — same catch-all framing as the probe
        return "error"


# Each literal doubles as the parametrize id.
_LITERALS: list[str] = [
    # plain integers + sign / leading-zero forms
    "10",
    "+3",
    "007",
    "0",
    "5",
    "-0",
    "+100",
    "0000123",
    # Long boundary + overflow (OUT_OF_RANGE_* sentinels, flagged invalid)
    "9223372036854775807",
    "9223372036854775808",
    "-9223372036854775808",
    "-9223372036854775809",
    "100000000000000000000",
    "+100000000000000000000",
    "-100000000000000000000",
    "999999999999999999999999999999",
    # floats: leading/trailing dot, signs (NO exponent — wave 1453 covered exp)
    "1.5",
    ".5",
    "5.",
    "-.5",
    "+.5",
    "12.",
    "-0.0",
    "0.0",
    "0.5",
    "100.0",
    # very large real (float32 saturation), still no exponent in the literal
    "340282350000000000000000000000000000000.0",
]


@requires_oracle
@pytest.mark.parametrize("lit", _LITERALS, ids=[repr(s) for s in _LITERALS])
def test_stream_parse_number_matches_pdfbox(lit: str) -> None:
    """pypdfbox ``PDFStreamParser`` (content-stream tokenizer) parity."""
    java = run_probe_text("CosNumberOverflowProbe", lit).strip()
    assert _stream_signal(lit) == java


@requires_oracle
@pytest.mark.parametrize("lit", _LITERALS, ids=[repr(s) for s in _LITERALS])
def test_body_parse_number_matches_pdfbox(lit: str) -> None:
    """pypdfbox ``COSParser`` (document-body tokenizer) parity — the surface
    fixed this wave so Long-overflow yields the clamped invalid sentinel."""
    java = run_probe_text("CosNumberOverflowProbe", lit).strip()
    assert _body_signal(lit) == java
