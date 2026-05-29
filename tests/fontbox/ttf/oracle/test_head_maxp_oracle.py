"""Live PDFBox differential parity for the TrueType ``head`` + ``maxp`` tables.

Recent fontbox oracle waves covered ``hmtx`` (advance + LSB), ``glyf``
composite components, ``cmap`` lookup (incl. format 14), the legacy ``kern``
table, ``post``, ``name``, glyph paths, and the ``OS/2`` Windows metrics
table. This wave targets the two remaining required head tables:

* **``head``** — ``org.apache.fontbox.ttf.HeaderTable``: version, fontRevision,
  checkSumAdjustment, magicNumber, flags, unitsPerEm, created/modified (the
  ``LONGDATETIME`` instants), the glyph-data bbox xMin/yMin/xMax/yMax, macStyle,
  lowestRecPPEM, fontDirectionHint, indexToLocFormat, glyphDataFormat;
* **``maxp``** — ``org.apache.fontbox.ttf.MaximumProfileTable``: version,
  numGlyphs and the version-1.0-gated maxima (points, contours, composite
  points/contours, zones, twilight points, storage, function/instruction defs,
  stack elements, size-of-instructions, component elements/depth).

Two parity subtleties pinned here:

* **float formatting.** ``getVersion`` / ``getFontRevision`` are Java
  ``float`` (32-bit). Java's ``Float.toString`` emits the shortest decimal
  that round-trips to that ``float`` (e.g. ``2.0999908``), whereas a Python
  ``repr`` of the same value uses the wider double-precision shortest form
  (``2.0999908447265625``). The probe is compared against a
  ``_java_float_str`` helper that reproduces Java's float32 shortest repr.
* **dates.** ``head.created`` / ``head.modified`` are emitted as the absolute
  epoch-millisecond instant (``Calendar.getTimeInMillis()`` on the Java side),
  so the comparison is timezone-independent — pypdfbox keeps the dates as
  UTC-aware ``datetime`` and ``int(dt.timestamp() * 1000)`` yields the same
  absolute instant.

Both ``LiberationSans-Regular`` and ``DejaVuSansMono`` carry version-1.0
``maxp`` tables (so the gated maxima are populated) and standard ``head``
tables; both are already bundled under permissive licenses.

``HeadMaxpProbe`` output is reconstructed line-for-line on the Python side and
compared verbatim against Apache PDFBox 3.0.7.
"""

from __future__ import annotations

import struct
from datetime import datetime
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


def _millis(dt: datetime | None) -> str:
    """Epoch milliseconds of a UTC ``datetime`` (matches ``getTimeInMillis``)."""
    if dt is None:
        return "null"
    return str(int(dt.timestamp() * 1000))


def _py_head_maxp(font_path: Path) -> str:
    """Reconstruct ``HeadMaxpProbe`` output from pypdfbox (line-for-line)."""
    ttf = TTFParser().parse(font_path)
    try:
        lines: list[str] = []

        head = ttf.get_header()
        if head is None:
            lines.append("head\tabsent")
        else:
            lines.append("head\tpresent")
            lines.append(f"head.version\t{_java_float_str(head.get_version())}")
            lines.append(
                f"head.fontRevision\t{_java_float_str(head.get_font_revision())}"
            )
            lines.append(
                f"head.checkSumAdjustment\t{head.get_check_sum_adjustment()}"
            )
            lines.append(f"head.magicNumber\t{head.get_magic_number()}")
            lines.append(f"head.flags\t{head.get_flags()}")
            lines.append(f"head.unitsPerEm\t{head.get_units_per_em()}")
            lines.append(f"head.created\t{_millis(head.get_created())}")
            lines.append(f"head.modified\t{_millis(head.get_modified())}")
            lines.append(f"head.xMin\t{head.get_x_min()}")
            lines.append(f"head.yMin\t{head.get_y_min()}")
            lines.append(f"head.xMax\t{head.get_x_max()}")
            lines.append(f"head.yMax\t{head.get_y_max()}")
            lines.append(f"head.macStyle\t{head.get_mac_style()}")
            lines.append(f"head.lowestRecPPEM\t{head.get_lowest_rec_ppem()}")
            lines.append(f"head.fontDirectionHint\t{head.get_font_direction_hint()}")
            lines.append(f"head.indexToLocFormat\t{head.get_index_to_loc_format()}")
            lines.append(f"head.glyphDataFormat\t{head.get_glyph_data_format()}")

        maxp = ttf.get_maximum_profile()
        if maxp is None:
            lines.append("maxp\tabsent")
        else:
            lines.append("maxp\tpresent")
            lines.append(f"maxp.version\t{_java_float_str(maxp.get_version())}")
            lines.append(f"maxp.numGlyphs\t{maxp.get_num_glyphs()}")
            lines.append(f"maxp.maxPoints\t{maxp.get_max_points()}")
            lines.append(f"maxp.maxContours\t{maxp.get_max_contours()}")
            lines.append(
                f"maxp.maxCompositePoints\t{maxp.get_max_composite_points()}"
            )
            lines.append(
                f"maxp.maxCompositeContours\t{maxp.get_max_composite_contours()}"
            )
            lines.append(f"maxp.maxZones\t{maxp.get_max_zones()}")
            lines.append(f"maxp.maxTwilightPoints\t{maxp.get_max_twilight_points()}")
            lines.append(f"maxp.maxStorage\t{maxp.get_max_storage()}")
            lines.append(f"maxp.maxFunctionDefs\t{maxp.get_max_function_defs()}")
            lines.append(
                f"maxp.maxInstructionDefs\t{maxp.get_max_instruction_defs()}"
            )
            lines.append(f"maxp.maxStackElements\t{maxp.get_max_stack_elements()}")
            lines.append(
                f"maxp.maxSizeOfInstructions\t{maxp.get_max_size_of_instructions()}"
            )
            lines.append(
                f"maxp.maxComponentElements\t{maxp.get_max_component_elements()}"
            )
            lines.append(
                f"maxp.maxComponentDepth\t{maxp.get_max_component_depth()}"
            )

        return "\n".join(lines) + "\n"
    finally:
        ttf.close()


def _assert_parity(font_path: Path) -> None:
    assert font_path.is_file(), f"missing fixture: {font_path}"
    java = run_probe_text("HeadMaxpProbe", str(font_path)).splitlines()
    py = _py_head_maxp(font_path).splitlines()

    assert len(java) == len(py), (
        f"line-count mismatch: java={len(java)} py={len(py)}\n"
        f"first java: {java[:3]}\nfirst py:   {py[:3]}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, "head/maxp parity broken:\n" + "\n".join(diffs[:40])


@requires_oracle
@pytest.mark.parametrize(
    "font_path",
    [_LIBERATION, _DEJAVU_MONO],
    ids=["liberation_sans", "dejavu_sans_mono"],
)
def test_head_maxp_matches_pdfbox(font_path: Path) -> None:
    """Every ``head`` and ``maxp`` accessor — including the float-typed
    version/fontRevision fields and the ``LONGDATETIME`` created/modified
    instants — must match Apache PDFBox 3.0.7 byte-for-byte.
    """
    _assert_parity(font_path)
