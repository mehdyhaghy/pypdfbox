"""Differential-fuzz parity for the measurement annotation dictionaries.

Wave 1555. Complements ``test_measurement_oracle.py`` (default/round-trip
pins) by hammering MALFORMED / edge-case COS shapes through every accessor of
``PDMeasureDictionary`` / ``PDRectlinearMeasureDictionary`` /
``PDViewportDictionary`` / ``PDNumberFormatDictionary`` and asserting the
projected result (and exception class) matches live Apache PDFBox 3.0.7
line-for-line.

Java side: ``MeasureDictFuzzProbe`` emits canonical ``key=value`` lines; the
Python side reconstructs the identical report and asserts equality.

Surfaces fuzzed (~50 cases):
  * /Subtype as name "RL"/"GEO", string "RL", integer, absent → get_subtype;
  * /X /Y /D /A /T /S as good array / empty / mixed-member / bare dict / int /
    absent → list size, NULL, or exception class;
  * /R scale ratio as string / name / int;
  * /O coord origin as float-array / int / absent;
  * /CYX as int / float / string / absent;
  * number-format /C negative/zero/string/absent, /D int/float/string/absent,
    /F valid/unknown-name/string/absent + setter validation, /U name/string/int,
    /O label-position setter validation + unknown name;
  * viewport /BBox arity 0/2/4, /Name name/string/int, /Measure non-dict /
    RL-subtype dispatch / absent.

Honest divergence pinned: when a /D-family array contains a non-dictionary
member, upstream's unchecked ``(COSDictionary) array.getObject(i)`` cast throws
``ClassCastException``; pypdfbox raises ``TypeError`` (Python's structural
equivalent). The probe prints the simple class name, so the Python projection
maps the equivalent failure to the same ``"ClassCastException"`` token — the
behaviour (raise rather than silently drop the bad member) is identical and was
fixed in this wave (was previously a silent skip).
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (
    PDMeasureDictionary,
)
from pypdfbox.pdmodel.interactive.measurement.pd_number_format_dictionary import (
    PDNumberFormatDictionary,
)
from pypdfbox.pdmodel.interactive.measurement.pd_rectlinear_measure_dictionary import (
    PDRectlinearMeasureDictionary,
)
from pypdfbox.pdmodel.interactive.measurement.pd_viewport_dictionary import (
    PDViewportDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_U = COSName.get_pdf_name("U")
_C = COSName.get_pdf_name("C")
_D = COSName.get_pdf_name("D")
_F = COSName.get_pdf_name("F")
_O = COSName.get_pdf_name("O")
_R = COSName.get_pdf_name("R")
_X = COSName.get_pdf_name("X")
_Y = COSName.get_pdf_name("Y")
_A = COSName.get_pdf_name("A")
_T = COSName.get_pdf_name("T")
_S = COSName.get_pdf_name("S")
_CYX = COSName.get_pdf_name("CYX")
_BBOX = COSName.get_pdf_name("BBox")
_NAME = COSName.get_pdf_name("Name")
_MEASURE = COSName.get_pdf_name("Measure")
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]
_TYPE = COSName.TYPE  # type: ignore[attr-defined]


def _nz(value: object) -> str:
    return "NULL" if value is None else str(value)


def _sz(items: list[object] | None) -> str:
    return "NULL" if items is None else f"len:{len(items)}"


def _sz_try(getter) -> str:  # noqa: ANN001
    """Project a list-getter, mapping a raised exception to its oracle token.

    Java prints the JVM ``ClassCastException`` simple name; pypdfbox raises a
    ``TypeError`` from the same unchecked-cast site, which we normalize to the
    same string so the line matches the oracle.
    """
    try:
        return _sz(getter())
    except TypeError:
        return "ClassCastException"


def _farr(values: list[float] | None) -> str:
    if values is None:
        return "NULL"
    return "[" + ",".join(str(v) for v in values) + "]"


def _nf_dict(units: str | None) -> COSDictionary:
    d = COSDictionary()
    d.set_name(_TYPE, "NumberFormat")
    if units is not None:
        d.set_string(_U, units)
    return d


def _build_report() -> list[str]:
    lines: list[str] = []

    # ---- /Subtype shapes ------------------------------------------------
    d1 = COSDictionary()
    d1.set_name(_SUBTYPE, "RL")
    lines.append(f"subtype.name_rl={PDMeasureDictionary(d1).get_subtype()}")
    d2 = COSDictionary()
    d2.set_name(_SUBTYPE, "GEO")
    lines.append(f"subtype.name_geo={PDMeasureDictionary(d2).get_subtype()}")
    d3 = COSDictionary()
    d3.set_item(_SUBTYPE, COSString("RL"))
    lines.append(f"subtype.string_rl={PDMeasureDictionary(d3).get_subtype()}")
    d4 = COSDictionary()
    d4.set_item(_SUBTYPE, COSInteger.get(7))
    lines.append(f"subtype.int={PDMeasureDictionary(d4).get_subtype()}")
    lines.append(f"subtype.absent={PDMeasureDictionary(COSDictionary()).get_subtype()}")

    # ---- rectlinear array getters over malformed /D ---------------------
    rl = PDRectlinearMeasureDictionary()
    rld = rl.get_cos_object()

    good = COSArray()
    good.add(_nf_dict("mi"))
    good.add(_nf_dict("km"))
    rld.set_item(_D, good)
    lines.append(f"d.good={_sz_try(rl.get_distances)}")

    rld.set_item(_D, COSArray())
    lines.append(f"d.empty={_sz_try(rl.get_distances)}")

    mixed = COSArray()
    mixed.add(COSInteger.get(3))
    mixed.add(_nf_dict("ft"))
    mixed.add(COSString("x"))
    rld.set_item(_D, mixed)
    lines.append(f"d.mixed={_sz_try(rl.get_distances)}")

    rld.set_item(_D, _nf_dict("yd"))
    lines.append(f"d.dict={_sz_try(rl.get_distances)}")

    rld.set_item(_D, COSInteger.get(5))
    lines.append(f"d.int={_sz_try(rl.get_distances)}")

    rld.remove_item(_D)
    lines.append(f"d.absent={_sz_try(rl.get_distances)}")

    rld.set_item(_X, COSArray())
    lines.append(f"x.empty={_sz_try(rl.get_change_xs)}")
    rld.set_item(_Y, _nf_dict("a"))
    lines.append(f"y.dict={_sz_try(rl.get_change_ys)}")
    rld.set_item(_A, COSInteger.get(1))
    lines.append(f"a.int={_sz_try(rl.get_areas)}")
    rld.set_item(_T, good)
    lines.append(f"t.good={_sz_try(rl.get_angles)}")
    lines.append(f"s.absent={_sz_try(rl.get_line_sloaps)}")

    # ---- /R scale ratio shapes -----------------------------------------
    r2 = PDRectlinearMeasureDictionary()
    r2.get_cos_object().set_item(_R, COSString("1in = 1mi"))
    lines.append(f"r.string={_nz(r2.get_scale_ratio())}")
    r2.get_cos_object().set_name(_R, "ratio")
    lines.append(f"r.name={_nz(r2.get_scale_ratio())}")
    r2.get_cos_object().set_item(_R, COSInteger.get(2))
    lines.append(f"r.int={_nz(r2.get_scale_ratio())}")

    # ---- /O coord origin shapes ----------------------------------------
    r3 = PDRectlinearMeasureDictionary()
    o4 = COSArray()
    o4.add(COSFloat(1.5))
    o4.add(COSInteger.get(2))
    r3.get_cos_object().set_item(_O, o4)
    lines.append(f"o.floatarr={_farr(r3.get_coord_system_origin())}")
    r3.get_cos_object().set_item(_O, COSInteger.get(9))
    lines.append(f"o.int={_farr(r3.get_coord_system_origin())}")
    r3.get_cos_object().remove_item(_O)
    lines.append(f"o.absent={_farr(r3.get_coord_system_origin())}")

    # ---- /CYX shapes ----------------------------------------------------
    r4 = PDRectlinearMeasureDictionary()
    r4.get_cos_object().set_item(_CYX, COSInteger.get(3))
    lines.append(f"cyx.int={r4.get_cyx()}")
    r4.get_cos_object().set_item(_CYX, COSFloat(0.5))
    lines.append(f"cyx.float={r4.get_cyx()}")
    r4.get_cos_object().set_item(_CYX, COSString("nan"))
    lines.append(f"cyx.string={r4.get_cyx()}")
    r4.get_cos_object().remove_item(_CYX)
    lines.append(f"cyx.absent={r4.get_cyx()}")

    # ---- number format /C conversion edge values -----------------------
    nf = PDNumberFormatDictionary()
    nf.set_conversion_factor(-2.5)
    lines.append(f"c.negative={nf.get_conversion_factor()}")
    nf.set_conversion_factor(0.0)
    lines.append(f"c.zero={nf.get_conversion_factor()}")
    nf.get_cos_object().set_item(_C, COSString("notnum"))
    lines.append(f"c.string={nf.get_conversion_factor()}")
    nf.get_cos_object().remove_item(_C)
    lines.append(f"c.absent={nf.get_conversion_factor()}")

    # ---- number format /D precision shapes -----------------------------
    nf2 = PDNumberFormatDictionary()
    nf2.get_cos_object().set_item(_D, COSInteger.get(16))
    lines.append(f"nfd.int={nf2.get_denominator()}")
    nf2.get_cos_object().set_item(_D, COSFloat(4.7))
    lines.append(f"nfd.float={nf2.get_denominator()}")
    nf2.get_cos_object().set_item(_D, COSString("z"))
    lines.append(f"nfd.string={nf2.get_denominator()}")
    nf2.get_cos_object().remove_item(_D)
    lines.append(f"nfd.absent={nf2.get_denominator()}")

    # ---- number format /F format style shapes --------------------------
    nf3 = PDNumberFormatDictionary()
    nf3.set_fractional_display("R")
    lines.append(f"f.valid={_nz(nf3.get_fractional_display())}")
    nf3.get_cos_object().set_name(_F, "Q")
    lines.append(f"f.unknown_name={_nz(nf3.get_fractional_display())}")
    nf3.get_cos_object().set_item(_F, COSString("F"))
    lines.append(f"f.string={_nz(nf3.get_fractional_display())}")
    nf3.get_cos_object().remove_item(_F)
    lines.append(f"f.absent={_nz(nf3.get_fractional_display())}")
    try:
        nf3.set_fractional_display("Q")
        f_err = "NO_THROW"
    except ValueError:
        # pypdfbox raises ValueError; upstream throws IllegalArgumentException.
        f_err = "IllegalArgumentException"
    lines.append(f"f.setter_bad={f_err}")

    # ---- number format /U units shapes ---------------------------------
    nf4 = PDNumberFormatDictionary()
    nf4.get_cos_object().set_string(_U, "metres")
    lines.append(f"u.string={_nz(nf4.get_units())}")
    nf4.get_cos_object().set_name(_U, "metres")
    lines.append(f"u.name={_nz(nf4.get_units())}")
    nf4.get_cos_object().set_item(_U, COSInteger.get(1))
    lines.append(f"u.int={_nz(nf4.get_units())}")

    # ---- number format /O label position -------------------------------
    nf5 = PDNumberFormatDictionary()
    try:
        nf5.set_label_position_to_value("Z")
        o_err = "NO_THROW"
    except ValueError:
        o_err = "IllegalArgumentException"
    lines.append(f"o.setter_bad={o_err}")
    nf5.get_cos_object().set_name(_O, "Z")
    lines.append(f"o.unknown_name={_nz(nf5.get_label_position_to_value())}")

    # ---- viewport /BBox arity ------------------------------------------
    v = PDViewportDictionary()
    v.get_cos_object().set_item(_BBOX, COSArray())
    lines.append(f"bbox.empty={'NULL' if v.get_bbox() is None else 'present'}")
    two = COSArray()
    two.add(COSInteger.get(0))
    two.add(COSInteger.get(0))
    v.get_cos_object().set_item(_BBOX, two)
    try:
        bbox2 = "NULL" if v.get_bbox() is None else f"w:{v.get_bbox().get_width()}"
    except (TypeError, IndexError, ValueError) as e:
        bbox2 = type(e).__name__
    lines.append(f"bbox.two={bbox2}")
    v.set_bbox(PDRectangle(0, 0, 100, 200))
    lines.append(f"bbox.four=w:{v.get_bbox().get_width()}")

    # ---- viewport /Name shapes -----------------------------------------
    v2 = PDViewportDictionary()
    v2.get_cos_object().set_name(_NAME, "Imperial")
    lines.append(f"name.name={_nz(v2.get_name())}")
    v2.get_cos_object().set_item(_NAME, COSString("Metric"))
    lines.append(f"name.string={_nz(v2.get_name())}")
    v2.get_cos_object().set_item(_NAME, COSInteger.get(4))
    lines.append(f"name.int={_nz(v2.get_name())}")

    # ---- viewport /Measure dispatch ------------------------------------
    v3 = PDViewportDictionary()
    v3.get_cos_object().set_item(_MEASURE, COSInteger.get(1))
    lines.append(f"measure.int={'NULL' if v3.get_measure() is None else 'present'}")
    md = COSDictionary()
    md.set_name(_SUBTYPE, "RL")
    v3.get_cos_object().set_item(_MEASURE, md)
    got = v3.get_measure()
    lines.append(f"measure.rl.class={'NULL' if got is None else type(got).__name__}")
    lines.append(f"measure.rl.subtype={'NULL' if got is None else got.get_subtype()}")
    lines.append(
        f"measure.absent="
        f"{'NULL' if PDViewportDictionary().get_measure() is None else 'present'}"
    )

    return lines


@requires_oracle
def test_measure_dict_fuzz_matches_pdfbox() -> None:
    java = run_probe_text("MeasureDictFuzzProbe").splitlines()
    py = _build_report()
    assert py == java


def test_measure_dict_fuzz_pinned_values() -> None:
    """Self-contained pin of the PDFBox-3.0.7 expected report.

    Keeps the divergence pins green even on a machine without the live oracle
    (the only place the ``d.mixed`` ClassCastException-parity fix is asserted
    without needing the JVM).
    """
    expected = [
        "subtype.name_rl=RL",
        "subtype.name_geo=GEO",
        "subtype.string_rl=RL",
        "subtype.int=RL",
        "subtype.absent=RL",
        "d.good=len:2",
        "d.empty=len:0",
        "d.mixed=ClassCastException",
        "d.dict=NULL",
        "d.int=NULL",
        "d.absent=NULL",
        "x.empty=len:0",
        "y.dict=NULL",
        "a.int=NULL",
        "t.good=len:2",
        "s.absent=NULL",
        "r.string=1in = 1mi",
        "r.name=NULL",
        "r.int=NULL",
        "o.floatarr=[1.5,2.0]",
        "o.int=NULL",
        "o.absent=NULL",
        "cyx.int=3.0",
        "cyx.float=0.5",
        "cyx.string=-1.0",
        "cyx.absent=-1.0",
        "c.negative=-2.5",
        "c.zero=0.0",
        "c.string=-1.0",
        "c.absent=-1.0",
        "nfd.int=16",
        "nfd.float=4",
        "nfd.string=-1",
        "nfd.absent=-1",
        "f.valid=R",
        "f.unknown_name=D",
        "f.string=F",
        "f.absent=D",
        "f.setter_bad=IllegalArgumentException",
        "u.string=metres",
        "u.name=NULL",
        "u.int=NULL",
        "o.setter_bad=IllegalArgumentException",
        "o.unknown_name=S",
        "bbox.empty=present",
        "bbox.two=w:0.0",
        "bbox.four=w:100.0",
        "name.name=Imperial",
        "name.string=Metric",
        "name.int=NULL",
        "measure.int=NULL",
        "measure.rl.class=PDMeasureDictionary",
        "measure.rl.subtype=RL",
        "measure.absent=NULL",
    ]
    assert _build_report() == expected
