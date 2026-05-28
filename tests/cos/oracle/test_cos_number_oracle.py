"""Live PDFBox differential parity for COSNumber boundary behaviour.

Drives Apache PDFBox 3.0.7's numeric COS leaf classes directly (via the
``CosNumberProbe`` Java oracle) on a battery of raw numeric literal strings,
then asserts pypdfbox's :meth:`COSNumber.get` produces the same dispatch,
``isValid`` flag, ``intValue`` / ``longValue`` truncation, ``floatValue``
(compared as its IEEE-754 single-precision bit pattern, repr-independent), and
``toString`` text — or the same error outcome.

This is the ``COSNumber.get(String)`` boundary contract that the wider parser
leans on: single-character fast-path dispatch (``"-"`` / ``"."`` → ZERO,
``""`` → OUT_OF_RANGE_MAX), the ``isFloat`` int-vs-float decision (only ``.``
and lowercase ``e`` route to ``COSFloat`` — a bare uppercase ``E`` does not),
Long-overflow fallback to the ``OUT_OF_RANGE_*`` sentinels (PDFBOX-5176), and
malformed-real recovery (``--16.33``, ``0.-262``).
"""

from __future__ import annotations

import json
import struct

import pytest

from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_number import COSNumber
from tests.oracle.harness import requires_oracle, run_probe_text


def _fbits_hex(value: float) -> str:
    """IEEE-754 single-precision bit pattern, lowercase hex with no leading
    zeros — matches Java ``Integer.toHexString(Float.floatToIntBits(f))``."""
    bits = struct.unpack(">I", struct.pack(">f", value))[0]
    return f"{bits:x}"


def _pypdfbox_record(lit: str) -> dict[str, object]:
    """Build the same JSON-shaped record the ``CosNumberProbe`` emits."""
    try:
        n = COSNumber.get(lit)
    except (OSError, TypeError):
        return {"kind": "error", "msg": "IOException"}
    rec: dict[str, object] = {}
    if isinstance(n, COSInteger):
        rec["kind"] = "int"
        rec["valid"] = n.is_valid()
    elif isinstance(n, COSFloat):
        rec["kind"] = "float"
    else:
        rec["kind"] = "other"
    rec["int"] = _to_int32(n.int_value())
    rec["long"] = n.long_value()
    rec["fbits"] = _fbits_hex(n.float_value())
    rec["str"] = n.to_string()
    return rec


def _to_int32(value: int) -> int:
    """Truncate to a signed 32-bit int — Java ``intValue()`` wraps modulo
    2**32 on a ``(int)`` narrowing cast, whereas Python ints are unbounded."""
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        value -= 0x1_0000_0000
    return value


# Each literal doubles as the parametrize id (sanitised for pytest below).
_LITERALS: list[str] = [
    # plain integers + sign / leading-zero forms
    "10", "-5", "+3", "+5", "007", "0", "-0",
    # single-character fast path
    "1", "-", ".",
    # Long boundary + overflow (OUT_OF_RANGE_* sentinels, flagged invalid)
    "9223372036854775807", "9223372036854775808",
    "-9223372036854775808", "-9223372036854775809",
    "100000000000000000000", "+100000000000000000000",
    # floats: leading/trailing dot, signs, exponent (lowercase e only)
    "1.5", ".5", "5.", "+.5", "12.", "-0.0", "0.0",
    "1000000.0", "10000000.0", "0.0001", "0.0009",
    "1.0e3", "1.5e2", "0.1", "100.0", "3.14159265358979",
    # float32 saturation / subnormal flush
    "3.4028235e38", "1e40", "1.4e-45", "1e-45",
    # malformed-real recovery (PDFBOX-2990 / -3500 family)
    "--16.33", "0.-262",
    # error / non-number inputs
    "", "+", "abc", "--", "1.2.3", "0x10", ".e3",
    # uppercase E is NOT a float to upstream isFloat -> integer branch fails
    "1E2",
    # multiple leading '+' -> only one is stripped upstream -> error
    "++5",
]


@requires_oracle
@pytest.mark.parametrize(
    "lit", _LITERALS, ids=[repr(s) for s in _LITERALS]
)
def test_cos_number_get_matches_pdfbox(lit: str) -> None:
    java = json.loads(run_probe_text("CosNumberProbe", lit).strip())
    py = _pypdfbox_record(lit)
    assert py == java
