"""Live PDFBox differential parity for PDFontDescriptor /Flags bit-predicates
and numeric-metric accessors.

Companion to ``test_font_descriptor_oracle.py`` (wave 1412, descriptor metrics
read off real embedded fonts). This wave (1468) isolates the *bit-decode* surface
of :class:`PDFontDescriptor` — the ``is_fixed_pitch`` / ``is_serif`` /
``is_symbolic`` / ``is_script`` / ``is_non_symbolic`` / ``is_italic`` /
``is_all_cap`` / ``is_small_cap`` / ``is_force_bold`` predicates (PDF 32000-1
§9.8.2 Table 121, bits 1/2/3/4/6/7/17/18/19) — plus the full numeric metric
block (``get_italic_angle`` / ``get_ascent`` / ``get_descent`` /
``get_cap_height`` / ``get_x_height`` / ``get_stem_v`` / ``get_stem_h`` /
``get_missing_width`` / ``get_leading`` / ``get_average_width`` /
``get_max_width`` / ``get_font_weight``) and each accessor's default branch.

The descriptor is built directly from a synthetic :class:`COSDictionary` with a
chosen ``/Flags`` integer, so a divergence pins to the predicate / metric logic
rather than to font-program parsing. The oracle output is produced by
``oracle/probes/FontDescFlagsProbe.java``; the Python side reconstructs the
identical line format so a divergence shows up as a single differing line.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from tests.oracle.harness import requires_oracle, run_probe_text

# Flag integers exercising each individual bit plus combinations:
#   bit 1  FixedPitch  = 1
#   bit 2  Serif       = 2
#   bit 3  Symbolic    = 4
#   bit 4  Script      = 8
#   bit 6  NonSymbolic = 32
#   bit 7  Italic      = 64
#   bit 17 AllCap      = 65536
#   bit 18 SmallCap    = 131072
#   bit 19 ForceBold   = 262144
_FLAG_VALUES = [
    0,  # no bits — every predicate False
    1,  # FixedPitch only
    2,  # Serif only
    4,  # Symbolic only
    8,  # Script only
    32,  # NonSymbolic only
    64,  # Italic only
    65536,  # AllCap only
    131072,  # SmallCap only
    262144,  # ForceBold only
    2 + 64,  # Serif + Italic (typical Times-Italic)
    4 + 8,  # Symbolic + Script
    65536 + 131072 + 262144,  # all three high bits
    1 + 2 + 4 + 8 + 32 + 64 + 65536 + 131072 + 262144,  # every named bit
    0x7FFFFFFF,  # every bit in signed-int range — reserved bits must not leak
    16,  # bit 5 (reserved) only — every named predicate stays False
]


def _fmt(v: float) -> str:
    """Match the Java probe's ``String.format("%.4f", ...)`` with -0.0 collapse."""
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _py_block(flags: int, with_metrics: bool) -> str:
    """Reconstruct the FontDescFlagsProbe output from pypdfbox."""
    dict_ = COSDictionary()
    dict_.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("FontDescriptor"))
    dict_.set_name(COSName.get_pdf_name("FontName"), "ProbeFont")
    dict_.set_int(COSName.get_pdf_name("Flags"), flags)
    if with_metrics:
        dict_.set_float(COSName.get_pdf_name("ItalicAngle"), -12.5)
        dict_.set_float(COSName.get_pdf_name("Ascent"), 718.0)
        dict_.set_float(COSName.get_pdf_name("Descent"), -207.0)
        dict_.set_float(COSName.get_pdf_name("CapHeight"), 662.0)
        dict_.set_float(COSName.get_pdf_name("XHeight"), 450.0)
        dict_.set_float(COSName.get_pdf_name("StemV"), 84.0)
        dict_.set_float(COSName.get_pdf_name("StemH"), 73.0)
        dict_.set_float(COSName.get_pdf_name("MissingWidth"), 250.0)
        dict_.set_float(COSName.get_pdf_name("Leading"), 33.0)
        dict_.set_float(COSName.get_pdf_name("AvgWidth"), 441.0)
        dict_.set_float(COSName.get_pdf_name("MaxWidth"), 1000.0)
        dict_.set_float(COSName.get_pdf_name("FontWeight"), 400.0)

    fd = PDFontDescriptor(dict_)

    pred = (
        "PRED"
        f"\tfixedPitch={int(fd.is_fixed_pitch())}"
        f"\tserif={int(fd.is_serif())}"
        f"\tsymbolic={int(fd.is_symbolic())}"
        f"\tscript={int(fd.is_script())}"
        f"\tnonSymbolic={int(fd.is_non_symbolic())}"
        f"\titalic={int(fd.is_italic())}"
        f"\tallCap={int(fd.is_all_cap())}"
        f"\tsmallCap={int(fd.is_small_cap())}"
        f"\tforceBold={int(fd.is_force_bold())}"
    )
    metric = (
        "METRIC"
        f"\titalicAngle={_fmt(fd.get_italic_angle())}"
        f"\tascent={_fmt(fd.get_ascent())}"
        f"\tdescent={_fmt(fd.get_descent())}"
        f"\tcapHeight={_fmt(fd.get_cap_height())}"
        f"\txHeight={_fmt(fd.get_x_height())}"
        f"\tstemV={_fmt(fd.get_stem_v())}"
        f"\tstemH={_fmt(fd.get_stem_h())}"
        f"\tmissingWidth={_fmt(fd.get_missing_width())}"
        f"\tleading={_fmt(fd.get_leading())}"
        f"\tavgWidth={_fmt(fd.get_average_width())}"
        f"\tmaxWidth={_fmt(fd.get_max_width())}"
        f"\tfontWeight={_fmt(fd.get_font_weight())}"
    )
    return f"FLAGS\t{fd.get_flags()}\n{pred}\n{metric}\n"


@requires_oracle
@pytest.mark.parametrize("flags", _FLAG_VALUES)
@pytest.mark.parametrize("with_metrics", [True, False], ids=["metrics", "defaults"])
def test_font_desc_flags_match_pdfbox(flags: int, with_metrics: bool) -> None:
    """Every /Flags bit-predicate and numeric metric (incl. each accessor's
    default branch) must match Apache PDFBox 3.0.7 exactly for a descriptor
    built directly from a synthetic COSDictionary.
    """
    java = run_probe_text(
        "FontDescFlagsProbe", str(flags), "1" if with_metrics else "0"
    )
    py = _py_block(flags, with_metrics)
    jl = java.splitlines()
    pl = py.splitlines()
    diffs = [
        f"  java={j!r} py={p!r}"
        for j, p in zip(jl, pl, strict=True)
        if j != p
    ]
    assert jl == pl, (
        f"flags={flags} with_metrics={with_metrics} divergence:\n" + "\n".join(diffs)
    )
