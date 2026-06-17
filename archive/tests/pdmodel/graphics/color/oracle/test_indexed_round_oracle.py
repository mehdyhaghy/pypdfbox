"""Live PDFBox differential parity for ``PDIndexed.toRGB`` index rounding and
clamping on a DeviceRGB base.

The Java side is ``oracle/probes/IndexedRoundProbe.java``. With a DeviceRGB
base the palette bytes pass straight through (no CMM), so the only behaviour
exercised is upstream's ``int index = Math.round(value[0])`` followed by
``Math.max(index, 0)`` / ``Math.min(index, actualMaxIndex)``
(PDIndexed.java line 182).

The subtle parity point: ``Math.round(float)`` is ``(int) Math.floor(a + 0.5f)``
— round-half-UP. Python's built-in ``round`` is banker's rounding, so a naive
``int(round(value[0]))`` port diverges on every half-integer tint (Java
``0.5 -> 1``, ``2.5 -> 3``; Python ``round(0.5) == 0``, ``round(2.5) == 2``).
pypdfbox uses ``math.floor(value[0] + 0.5)`` to mirror Java exactly. This test
pins that against the live jar across a battery of fractional and
out-of-range tint values.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName, COSString
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from tests.oracle.harness import requires_oracle, run_probe_text

# 4-entry palette, hival = 3 — must mirror IndexedRoundProbe.java exactly.
_PALETTE = bytes([0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255])

_VALUES = [
    -1.0, -0.5, 0.0, 0.4, 0.5, 0.6,
    1.0, 1.4, 1.5, 1.6,
    2.0, 2.4, 2.5, 2.6,
    3.0, 3.4, 3.5, 3.6,
    4.0, 5.0, 100.0,
]


def _indexed() -> PDIndexed:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    arr.add(COSInteger.get(3))
    arr.add(COSString(_PALETTE))
    return PDIndexed(arr)


def _rgb255(cs: PDIndexed, value: float) -> tuple[int, int, int]:
    r, g, b = cs.to_rgb([value])
    return (round(r * 255.0), round(g * 255.0), round(b * 255.0))


def _parse_probe(text: str) -> dict[float, tuple[int, int, int]]:
    out: dict[float, tuple[int, int, int]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        left, right = line.split("->")
        value = float(left.strip())
        r, g, b = (int(x) for x in right.split())
        out[value] = (r, g, b)
    return out


@requires_oracle
def test_indexed_round_matches_pdfbox() -> None:
    """pypdfbox ``PDIndexed.to_rgb`` index rounding == PDFBox byte-for-byte
    across fractional and out-of-range tint values (round-half-UP parity)."""
    java = _parse_probe(run_probe_text("IndexedRoundProbe"))
    cs = _indexed()
    assert len(java) == len(_VALUES), f"probe emitted {len(java)} rows"
    for value in _VALUES:
        assert value in java, f"probe missing value {value}"
        py = _rgb255(cs, value)
        assert py == java[value], (
            f"index {value}: pypdfbox {py} != PDFBox {java[value]}"
        )
