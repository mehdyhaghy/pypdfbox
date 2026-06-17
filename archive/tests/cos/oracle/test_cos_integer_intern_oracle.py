"""Live PDFBox differential parity for ``COSInteger.get(long)`` interning.

Drives Apache PDFBox 3.0.7's :meth:`COSInteger.get` static factory directly
(via the ``CosIntegerInternProbe`` Java oracle) over a battery of long values,
then asserts pypdfbox's :meth:`COSInteger.get` reproduces the same:

* singleton-cache identity — ``get(n) is get(n)`` is True only for values in
  the cached range (upstream caches a small contiguous band; the probe reports
  the reference-identity flag so the boundary is pinned by the oracle itself,
  not by a hand-copied constant);
* ``int_value`` / ``long_value`` (the ``(int)`` narrowing wrap beyond 32 bits);
* ``float_value`` as an IEEE-754 bit pattern;
* value-equality (``equals``) and ``hash_code``;
* ``to_string`` text.
"""

from __future__ import annotations

import json
import struct

import pytest

from pypdfbox.cos.cos_integer import COSInteger
from tests.oracle.harness import requires_oracle, run_probe_text


def _fbits_hex(value: float) -> str:
    """float32 bit pattern, lowercase hex, no leading zeros — matches Java
    ``Integer.toHexString(Float.floatToIntBits(f))``."""
    bits = struct.unpack(">I", struct.pack(">f", value))[0]
    return f"{bits:x}"


def _to_int32(value: int) -> int:
    """Truncate to a signed 32-bit int — Java ``intValue()`` wraps modulo
    2**32 on a ``(int)`` narrowing cast, whereas Python ints are unbounded."""
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        value -= 0x1_0000_0000
    return value


def _to_int32_hash(value: int) -> int:
    """Java ``hashCode()`` returns a signed 32-bit int; pypdfbox's
    ``hash_code`` already truncates, so this just normalises the type."""
    return _to_int32(value)


def _pypdfbox_record(lit: str) -> dict[str, object]:
    """Build the same JSON-shaped record the ``CosIntegerInternProbe`` emits."""
    value = int(lit)
    a = COSInteger.get(value)
    b = COSInteger.get(value)
    rec: dict[str, object] = {}
    rec["interned"] = a is b
    rec["int"] = _to_int32(a.int_value())
    rec["long"] = a.long_value()
    rec["fbits"] = _fbits_hex(a.float_value())
    rec["eq"] = a.equals(b)
    rec["hash"] = _to_int32_hash(a.hash_code())
    rec["str"] = a.to_string()
    return rec


# Each literal is a Java long; doubles as the parametrize id.
_VALUES: list[str] = [
    # cached-range interior + the ZERO/ONE/TWO/THREE constants
    "0", "1", "2", "3", "-1", "-5", "10", "100", "255", "256",
    # cached-range boundaries: upstream caches roughly -100..256.
    # Just inside / on / just outside each edge so the oracle pins the bound.
    "-99", "-100", "-101", "257",
    # well outside the cache (distinct instances) — small + large
    "1000", "-1000", "65535", "1000000",
    # 32-bit boundaries: intValue() narrowing wrap
    "2147483647", "2147483648", "-2147483648", "-2147483649",
    "4294967296",
    # Long extremes
    "9223372036854775807", "-9223372036854775808",
    # values whose float32 cast loses precision (repr-independent fbits check)
    "16777217", "16777216", "33554435",
]


@requires_oracle
@pytest.mark.parametrize("lit", _VALUES, ids=[repr(s) for s in _VALUES])
def test_cos_integer_get_matches_pdfbox(lit: str) -> None:
    java = json.loads(run_probe_text("CosIntegerInternProbe", lit).strip())
    py = _pypdfbox_record(lit)
    assert py == java
