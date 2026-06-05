"""Live differential oracle for :func:`pypdfbox.cos.cos_float.float_to_string`.

Compiles + runs ``FloatToStringProbe`` against Apache PDFBox 3.0.7 / the local
JDK and asserts that pypdfbox's ``float_to_string`` reproduces Java's raw
``Float.toString`` byte-for-byte across the full edge-value sweep (1e7 / 1e-3
boundaries, exact powers of ten, negatives, subnormals, ``Float.MAX_VALUE``,
signed zero) and that the Matrix / Vector ``toString`` lines match too.

Skips cleanly when the oracle jar / JDK is unavailable (developer-machine
opt-in, not a hard CI gate).
"""

from __future__ import annotations

import struct

try:
    from tests.oracle.harness import requires_oracle, run_probe_text
except Exception:  # pragma: no cover - harness import guard
    import pytest

    requires_oracle = pytest.mark.skip(reason="oracle harness unavailable")

    def run_probe_text(*_a: str, **_k: object) -> str:  # type: ignore[misc]
        raise RuntimeError("oracle unavailable")


from pypdfbox.cos.cos_float import float_to_string
from pypdfbox.util.matrix import Matrix
from pypdfbox.util.vector import Vector

# Mirror of the float literals emitted by FloatToStringProbe.java, keyed by the
# probe's label so each line can be checked against the matching pypdfbox value.
_PROBE_FLOATS: dict[str, float] = {
    "just_below_1e7": 9999999.0,
    "at_1e7": 1.0e7,
    "just_above_1e7": 1.0000001e7,
    "ten_million_one": 10000001.0,
    "at_1e_3": 0.001,
    "just_below_1e_3": 9.999999e-4,
    "just_above_1e_3": 0.0010001,
    "pow_1e6": 1.0e6,
    "pow_1e7": 1.0e7,
    "pow_1e8": 1.0e8,
    "pow_1e_2": 1.0e-2,
    "pow_1e_3": 1.0e-3,
    "pow_1e_4": 1.0e-4,
    "pow_1e10": 1.0e10,
    "pow_1e_10": 1.0e-10,
    "pow_1e20": 1.0e20,
    "pow_1e_20": 1.0e-20,
    "neg_4p2e10": -4.2e10,
    "neg_1e8": -1.0e8,
    "neg_1p23e_4": -1.23e-4,
    "neg_small": -7.5e-5,
    "one_third": 1.0 / 3.0,
    "pi": 3.141592653589793,
    "big_full": 1.2345678e9,
    "small_full": 1.2345678e-5,
    "e_mantissa": 1.23e-4,
    "min_value": 1.401298464324817e-45,  # Float.MIN_VALUE
    "subnormal_2": 2.8e-45,
    "min_normal": 1.1754943508222875e-38,  # Float.MIN_NORMAL
    "max_value": 3.4028234663852886e38,  # Float.MAX_VALUE
    "neg_max_value": -3.4028234663852886e38,
    "pos_zero": 0.0,
    "neg_zero": -0.0,
    "one": 1.0,
    "hundred": 100.0,
    "one_million": 1000000.0,
    "frac": 0.5,
    "rot_cos": 0.9950042,
}


def _f32(value: float) -> float:
    return struct.unpack("f", struct.pack("f", value))[0]


@requires_oracle
def test_float_to_string_matches_live_oracle() -> None:
    lines = run_probe_text("FloatToStringProbe").splitlines()
    by_label = dict(line.split("=", 1) for line in lines if "=" in line)

    for label, value in _PROBE_FLOATS.items():
        assert label in by_label, f"probe missing label {label!r}"
        java = by_label[label]
        # ``-0.0`` keeps its sign bit; everything else narrows to float32.
        py_value = -0.0 if label == "neg_zero" else _f32(value)
        assert float_to_string(py_value) == java, label

    # Matrix / Vector toString route through float_to_string.
    assert by_label["matrix_big"] == repr(
        Matrix(1.0e8, 0.0, 0.0, 1.0e-4, 0.0, 0.0)
    )
    assert by_label["vector_big"] == Vector(1.0e8, 1.4e-45).to_string()
