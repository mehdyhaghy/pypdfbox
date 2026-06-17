"""Live PDFBox differential fuzz parity for ``PDFontDescriptor`` over
malformed descriptor dictionaries (wave 1529, agent A).

Companion to ``test_font_desc_flags_oracle.py`` (wave 1468, well-formed
``/Flags`` int + a full ``COSFloat`` metric block) and
``test_font_descriptor_oracle.py`` (wave 1412, descriptors read off real
embedded fonts). Neither of those fuzzes the *COS type* of the descriptor
entries. This wave builds deliberately MALFORMED font descriptor dictionaries
in memory and pins every accessor's leniency against Apache PDFBox 3.0.7:

* ``/Flags`` missing / as ``COSFloat`` (incl. truncating-toward-zero) / as
  ``COSString`` / as ``COSBoolean`` / a huge int past the signed-32 range
  (wraps) / negative (all bits, reserved bits must not leak into the named
  predicates) — exercising Java int bit-extraction semantics;
* ``/FontBBox`` missing / short (2, 3 entries) / over-long (5) / non-numeric
  entries (coerced to 0) / a non-array shape (resolves to ``None``);
* numeric metrics missing (default 0 branch), stored as non-numeric shapes
  (returns default), and stored as ``COSInteger`` (read as float);
* PDFBOX-429 negative ``/CapHeight`` & ``/XHeight`` (read back as absolute);
* ``/FontName`` missing / as ``COSString`` (lenient ``getNameAsString``) / as
  ``COSInteger`` (rejected → ``None``);
* ``/FontStretch`` as a ``COSString``; ``/FontWeight`` non-numeric;
* ``/CharSet`` absent / as ``COSString`` / as ``COSName`` (rejected → ``None``);
* ``/FontFile`` ``/FontFile2`` ``/FontFile3`` presence as a stream vs a
  non-stream shape.

The oracle output is produced by ``oracle/probes/FontDescriptorFuzzProbe.java``;
the Python side reconstructs the identical line format so a divergence shows up
as a single differing ``CASE`` line. As of wave 1529 every case matches
byte-for-byte — no production divergence was found on this surface.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from tests.oracle.harness import requires_oracle, run_probe_text

# Case order must match FontDescriptorFuzzProbe.main() exactly.
_CASE_ORDER = [
    "flags_missing",
    "flags_float",
    "flags_float_trunc",
    "flags_string",
    "flags_bool",
    "flags_huge",
    "flags_neg",
    "flags_bit17_18_19",
    "bbox_missing",
    "bbox_short2",
    "bbox_short3",
    "bbox_long5",
    "bbox_nonnum",
    "bbox_nonarray",
    "metrics_missing",
    "metrics_nonnum",
    "metrics_int",
    "capheight_negative",
    "name_missing",
    "name_string",
    "name_int",
    "stretch_string",
    "weight_nonnum",
    "charset_absent",
    "charset_string",
    "charset_name",
    "fontfile_stream",
    "fontfile_nonstream",
    "all_three_fontfiles",
]


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _base() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_n("Type"), _n("FontDescriptor"))
    return d


def _build_cases() -> dict[str, COSDictionary]:
    out: dict[str, COSDictionary] = {}

    d = _base()
    d.set_name(_n("FontName"), "Probe")
    out["flags_missing"] = d

    d = _base()
    d.set_item(_n("Flags"), COSFloat(64.0))
    out["flags_float"] = d

    d = _base()
    d.set_item(_n("Flags"), COSFloat(65.9))
    out["flags_float_trunc"] = d

    d = _base()
    d.set_item(_n("Flags"), COSString("64"))
    out["flags_string"] = d

    d = _base()
    d.set_item(_n("Flags"), COSBoolean.TRUE)
    out["flags_bool"] = d

    d = _base()
    d.set_item(_n("Flags"), COSInteger.get(0x100000040))
    out["flags_huge"] = d

    d = _base()
    d.set_int(_n("Flags"), -1)
    out["flags_neg"] = d

    d = _base()
    d.set_int(_n("Flags"), (1 << 16) | (1 << 17) | (1 << 18))
    out["flags_bit17_18_19"] = d

    d = _base()
    d.set_name(_n("FontName"), "Probe")
    out["bbox_missing"] = d

    a = COSArray()
    a.add(COSFloat(0))
    a.add(COSFloat(-200))
    d = _base()
    d.set_item(_n("FontBBox"), a)
    out["bbox_short2"] = d

    a = COSArray()
    a.add(COSFloat(0))
    a.add(COSFloat(-200))
    a.add(COSFloat(1000))
    d = _base()
    d.set_item(_n("FontBBox"), a)
    out["bbox_short3"] = d

    a = COSArray()
    for v in (0, -200, 1000, 900, 123):
        a.add(COSFloat(v))
    d = _base()
    d.set_item(_n("FontBBox"), a)
    out["bbox_long5"] = d

    a = COSArray()
    a.add(COSString("x"))
    a.add(COSFloat(-200))
    a.add(_n("y"))
    a.add(COSFloat(900))
    d = _base()
    d.set_item(_n("FontBBox"), a)
    out["bbox_nonnum"] = d

    d = _base()
    d.set_int(_n("FontBBox"), 42)
    out["bbox_nonarray"] = d

    d = _base()
    d.set_name(_n("FontName"), "Probe")
    out["metrics_missing"] = d

    d = _base()
    d.set_item(_n("Ascent"), COSString("700"))
    d.set_item(_n("Descent"), _n("low"))
    d.set_item(_n("CapHeight"), COSString("z"))
    d.set_item(_n("StemV"), COSBoolean.FALSE)
    out["metrics_nonnum"] = d

    d = _base()
    d.set_int(_n("Ascent"), 718)
    d.set_int(_n("Descent"), -207)
    d.set_int(_n("CapHeight"), 662)
    d.set_int(_n("StemV"), 84)
    d.set_int(_n("FontWeight"), 700)
    out["metrics_int"] = d

    d = _base()
    d.set_float(_n("CapHeight"), -662)
    d.set_float(_n("XHeight"), -450)
    out["capheight_negative"] = d

    d = _base()
    out["name_missing"] = d

    d = _base()
    d.set_item(_n("FontName"), COSString("StringName"))
    out["name_string"] = d

    d = _base()
    d.set_int(_n("FontName"), 7)
    out["name_int"] = d

    d = _base()
    d.set_item(_n("FontStretch"), COSString("Condensed"))
    d.set_string(_n("FontFamily"), "Probe Family")
    out["stretch_string"] = d

    d = _base()
    d.set_item(_n("FontWeight"), COSString("bold"))
    out["weight_nonnum"] = d

    d = _base()
    out["charset_absent"] = d

    d = _base()
    d.set_item(_n("CharSet"), COSString("/a/b/c"))
    out["charset_string"] = d

    d = _base()
    d.set_item(_n("CharSet"), _n("abc"))
    out["charset_name"] = d

    d = _base()
    d.set_item(_n("FontFile"), COSStream())
    out["fontfile_stream"] = d

    d = _base()
    d.set_item(_n("FontFile"), COSDictionary())
    out["fontfile_nonstream"] = d

    d = _base()
    d.set_item(_n("FontFile"), COSStream())
    d.set_item(_n("FontFile2"), COSStream())
    d.set_item(_n("FontFile3"), COSStream())
    out["all_three_fontfiles"] = d

    return out


def _fmt(v: float) -> str:
    """Match the Java probe's ``String.format("%.4f", ...)`` with -0.0 collapse."""
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _s(value: str | None) -> str:
    return "null" if value is None else value


def _py_line(name: str, dict_: COSDictionary) -> str:
    """Reconstruct one FontDescriptorFuzzProbe CASE line from pypdfbox."""
    fd = PDFontDescriptor(dict_)
    sb = f"CASE\t{name}\tflags={fd.get_flags()}"
    pred = "".join(
        str(int(x))
        for x in (
            fd.is_fixed_pitch(),
            fd.is_serif(),
            fd.is_symbolic(),
            fd.is_script(),
            fd.is_non_symbolic(),
            fd.is_italic(),
            fd.is_all_cap(),
            fd.is_small_cap(),
            fd.is_force_bold(),
        )
    )
    sb += f"\tpred={pred}"

    bbox = fd.get_font_bounding_box()
    if bbox is None:
        sb += "\tbbox=null"
    else:
        sb += (
            f"\tbbox={_fmt(bbox.get_lower_left_x())},"
            f"{_fmt(bbox.get_lower_left_y())},"
            f"{_fmt(bbox.get_upper_right_x())},"
            f"{_fmt(bbox.get_upper_right_y())}"
        )

    mets = (
        fd.get_italic_angle(),
        fd.get_ascent(),
        fd.get_descent(),
        fd.get_cap_height(),
        fd.get_x_height(),
        fd.get_stem_v(),
        fd.get_stem_h(),
        fd.get_missing_width(),
        fd.get_leading(),
        fd.get_average_width(),
        fd.get_max_width(),
        fd.get_font_weight(),
    )
    sb += "\tmetrics=" + ",".join(_fmt(m) for m in mets)

    sb += f"\tname={_s(fd.get_font_name())}"
    sb += f"\tfamily={_s(fd.get_font_family())}"
    sb += f"\tstretch={_s(fd.get_font_stretch())}"
    sb += f"\tcharset={_s(fd.get_char_set())}"
    sb += f"\tff={int(fd.get_font_file() is not None)}"
    sb += f"\tff2={int(fd.get_font_file2() is not None)}"
    sb += f"\tff3={int(fd.get_font_file3() is not None)}"
    return sb


@requires_oracle
def test_font_descriptor_fuzz_matches_pdfbox() -> None:
    """Every malformed font descriptor case must project byte-for-byte the same
    flag predicates, bbox, numeric metrics, names, /CharSet and font-program
    presence as Apache PDFBox 3.0.7.
    """
    java_lines = run_probe_text("FontDescriptorFuzzProbe").splitlines()
    cases = _build_cases()
    py_lines = [_py_line(name, cases[name]) for name in _CASE_ORDER]

    diffs = [
        f"  java={j!r}\n   py ={p!r}"
        for j, p in zip(java_lines, py_lines, strict=True)
        if j != p
    ]
    assert java_lines == py_lines, "FontDescriptor fuzz divergence:\n" + "\n".join(diffs)
