"""Live PDFBox differential parity for the TrueType ``hhea`` table.

Recent fontbox oracle waves pinned ``hmtx`` (advance + LSB), ``head``/``maxp``,
the ``OS/2`` Windows metrics table, ``vhea``/``vmtx`` (vertical writing-mode
metrics), and ``post``. This wave targets the remaining required horizontal
header table:

* **``hhea``** — ``org.apache.fontbox.ttf.HorizontalHeaderTable`` (reached via
  ``TrueTypeFont.getHorizontalHeader()``): version, ascender, descender,
  lineGap, advanceWidthMax, minLeftSideBearing, minRightSideBearing,
  xMaxExtent, the caret slope (rise/run/offset-as-reserved1) fields, the five
  reserved shorts, metricDataFormat, and ``numberOfHMetrics`` — the count that
  drives the ``hmtx`` table's (advanceWidth, LSB)-pair vs. trailing-LSB layout.

The one parity subtlety pinned here is **float formatting**: ``getVersion``
returns a Java 32-bit ``float`` (16.16 fixed). Java's ``Float.toString`` emits
the shortest decimal that round-trips to that ``float``, whereas a Python
``repr`` of the same value uses the wider double-precision shortest form. The
probe is compared against a ``_java_float_str`` helper that reproduces Java's
float32 shortest repr.

Note: upstream's ``hhea`` struct has a ``caretOffset`` field at the position
pypdfbox/FontBox both label ``reserved1`` (the OpenType spec renamed reserved
slot 0 to ``caretOffset`` in v1.0); FontBox keeps the historical
``reserved1``..``reserved5`` naming, so this probe mirrors that.

Both ``LiberationSans-Regular`` and ``DejaVuSansMono`` carry standard ``hhea``
tables and are already bundled under permissive licenses.

``HheaProbe`` output is reconstructed line-for-line on the Python side and
compared verbatim against Apache PDFBox 3.0.7.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXDIR = (
    Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "fontbox" / "ttf"
)
_LIBERATION = _FIXDIR / "LiberationSans-Regular.ttf"
_DEJAVU_MONO = _FIXDIR / "DejaVuSansMono.ttf"


def _java_float_str(value: float) -> str:
    """Reproduce Java ``Float.toString`` for a 16.16-fixed value.

    The parsed value is first coerced to a 32-bit ``float`` (matching Java's
    ``read32Fixed`` cast), then rendered as the shortest decimal string that
    round-trips back to the same ``float`` — Java's ``Float.toString``
    contract. An integral value renders with a trailing ``.0``.
    """
    f32 = struct.unpack("f", struct.pack("f", float(value)))[0]
    if f32 == int(f32):
        return f"{f32:.1f}"
    for precision in range(1, 18):
        candidate = f"{f32:.{precision}g}"
        if struct.unpack("f", struct.pack("f", float(candidate)))[0] == f32:
            return candidate
    return repr(f32)


def _py_hhea(font_path: Path) -> str:
    """Reconstruct ``HheaProbe`` output from pypdfbox (line-for-line)."""
    ttf = TTFParser().parse(font_path)
    try:
        hhea = ttf.get_horizontal_header()
        if hhea is None:
            return "hhea\tabsent\n"
        lines = [
            "hhea\tpresent",
            f"hhea.version\t{_java_float_str(hhea.get_version())}",
            f"hhea.ascender\t{hhea.get_ascender()}",
            f"hhea.descender\t{hhea.get_descender()}",
            f"hhea.lineGap\t{hhea.get_line_gap()}",
            f"hhea.advanceWidthMax\t{hhea.get_advance_width_max()}",
            f"hhea.minLeftSideBearing\t{hhea.get_min_left_side_bearing()}",
            f"hhea.minRightSideBearing\t{hhea.get_min_right_side_bearing()}",
            f"hhea.xMaxExtent\t{hhea.get_x_max_extent()}",
            f"hhea.caretSlopeRise\t{hhea.get_caret_slope_rise()}",
            f"hhea.caretSlopeRun\t{hhea.get_caret_slope_run()}",
            f"hhea.reserved1\t{hhea.get_reserved1()}",
            f"hhea.reserved2\t{hhea.get_reserved2()}",
            f"hhea.reserved3\t{hhea.get_reserved3()}",
            f"hhea.reserved4\t{hhea.get_reserved4()}",
            f"hhea.reserved5\t{hhea.get_reserved5()}",
            f"hhea.metricDataFormat\t{hhea.get_metric_data_format()}",
            f"hhea.numberOfHMetrics\t{hhea.get_number_of_h_metrics()}",
        ]
        return "\n".join(lines) + "\n"
    finally:
        ttf.close()


def _assert_parity(font_path: Path) -> None:
    assert font_path.is_file(), f"missing fixture: {font_path}"
    java = run_probe_text("HheaProbe", str(font_path)).splitlines()
    py = _py_hhea(font_path).splitlines()

    assert len(java) == len(py), (
        f"line-count mismatch: java={len(java)} py={len(py)}\n"
        f"first java: {java[:3]}\nfirst py:   {py[:3]}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, "hhea parity broken:\n" + "\n".join(diffs[:40])


@requires_oracle
@pytest.mark.parametrize(
    "font_path",
    [_LIBERATION, _DEJAVU_MONO],
    ids=["liberation_sans", "dejavu_sans_mono"],
)
def test_hhea_matches_pdfbox(font_path: Path) -> None:
    """Every ``hhea`` accessor — including the float-typed version field and
    the ``numberOfHMetrics`` count that drives ``hmtx`` layout — must match
    Apache PDFBox 3.0.7 byte-for-byte.
    """
    _assert_parity(font_path)
