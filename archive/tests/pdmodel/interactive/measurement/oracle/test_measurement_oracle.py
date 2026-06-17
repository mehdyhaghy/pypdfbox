"""Live PDFBox differential parity for the measurement package
(``pypdfbox.pdmodel.interactive.measurement``).

Before this module the whole measurement package — ``PDNumberFormatDictionary``,
``PDMeasureDictionary`` / ``PDRectlinearMeasureDictionary``, and
``PDViewportDictionary`` — had NO live-oracle coverage at all, only
value-based hand-written tests. These three differential tests pin the exact
behaviours that the hand-written expectations could have silently mistranslated
from upstream:

* every typed getter's literal DEFAULT on an empty dictionary (``getFloat`` →
  ``-1.0``, ``getInt`` → ``-1``, the string defaults ``,`` / ``.`` / `` `` /
  ``S`` / ``D``);
* the COS wire form a full setter pass produces (which ``/Key`` names land,
  including the constructor-stamped ``/Type`` and ``/Subtype``);
* the null-clears-key contract;
* the subtle ``PDViewportDictionary.getMeasure()`` dispatch question — upstream
  returns the BASE ``PDMeasureDictionary`` even when the embedded measure
  carries ``/Subtype RL`` (it does NOT auto-promote to the rectlinear subclass),
  and pypdfbox must match.

Java side: ``NumberFormatDictionaryProbe`` / ``RectlinearMeasureProbe`` /
``ViewportMeasureDispatchProbe``. Each emits canonical ``key=value`` lines; the
Python side reconstructs the identical report and asserts line-for-line.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
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


def _nz(value: object) -> str:
    return "NULL" if value is None else str(value)


def _float(value: float) -> str:
    # Java prints "-1.0" / "2.5" / "0.75"; Python's str(float) agrees for these.
    return str(value)


@requires_oracle
def test_number_format_dictionary_matches_pdfbox() -> None:
    java = run_probe_text("NumberFormatDictionaryProbe").splitlines()

    nf = PDNumberFormatDictionary()
    lines: list[str] = [
        f"empty.type={nf.get_type()}",
        f"empty.units={_nz(nf.get_units())}",
        f"empty.conversionFactor={_float(nf.get_conversion_factor())}",
        f"empty.fractionalDisplay={_nz(nf.get_fractional_display())}",
        f"empty.denominator={nf.get_denominator()}",
        f"empty.fd={str(nf.is_fd()).lower()}",
        f"empty.thousandsSeparator={_nz(nf.get_thousands_separator())}",
        f"empty.decimalSeparator={_nz(nf.get_decimal_separator())}",
        f"empty.labelPrefixString={_nz(nf.get_label_prefix_string())}",
        f"empty.labelSuffixString={_nz(nf.get_label_suffix_string())}",
        f"empty.labelPositionToValue={_nz(nf.get_label_position_to_value())}",
    ]

    s = PDNumberFormatDictionary()
    s.set_units("metres")
    s.set_conversion_factor(2.5)
    s.set_fractional_display(PDNumberFormatDictionary.FRACTIONAL_DISPLAY_ROUND)
    s.set_denominator(16)
    s.set_fd(True)
    s.set_thousands_separator(".")
    s.set_decimal_separator(",")
    s.set_label_prefix_string("[")
    s.set_label_suffix_string("]")
    s.set_label_position_to_value(PDNumberFormatDictionary.LABEL_PREFIX_TO_VALUE)

    lines += [
        f"set.units={_nz(s.get_units())}",
        f"set.conversionFactor={_float(s.get_conversion_factor())}",
        f"set.fractionalDisplay={_nz(s.get_fractional_display())}",
        f"set.denominator={s.get_denominator()}",
        f"set.fd={str(s.is_fd()).lower()}",
        f"set.thousandsSeparator={_nz(s.get_thousands_separator())}",
        f"set.decimalSeparator={_nz(s.get_decimal_separator())}",
        f"set.labelPrefixString={_nz(s.get_label_prefix_string())}",
        f"set.labelSuffixString={_nz(s.get_label_suffix_string())}",
        f"set.labelPositionToValue={_nz(s.get_label_position_to_value())}",
    ]
    keys = sorted(k.get_name() for k in s.get_cos_object().key_set())
    lines.append("wire.keys=" + ",".join(keys))

    s.set_units(None)
    lines.append(
        "clear.units.present="
        + str(s.get_cos_object().contains_key(COSName.get_pdf_name("U"))).lower()
    )

    assert lines == java


@requires_oracle
def test_rectlinear_measure_matches_pdfbox() -> None:
    java = run_probe_text("RectlinearMeasureProbe").splitlines()

    def _arr(a: list | None) -> str:
        return "NULL" if a is None else f"len:{len(a)}"

    def _farr(a: list | None) -> str:
        if a is None:
            return "NULL"
        return "[" + ",".join(_float(float(x)) for x in a) + "]"

    m = PDRectlinearMeasureDictionary()
    lines: list[str] = [
        f"empty.type={m.get_type()}",
        f"empty.subtype={m.get_subtype()}",
        f"empty.scaleRatio={_nz(m.get_scale_ratio())}",
        f"empty.changeXs={_arr(m.get_change_xs())}",
        f"empty.changeYs={_arr(m.get_change_ys())}",
        f"empty.distances={_arr(m.get_distances())}",
        f"empty.areas={_arr(m.get_areas())}",
        f"empty.angles={_arr(m.get_angles())}",
        f"empty.lineSloaps={_arr(m.get_line_sloaps())}",
        f"empty.coordSystemOrigin={_farr(m.get_coord_system_origin())}",
        f"empty.cyx={_float(m.get_cyx())}",
        f"const.measure.type={PDMeasureDictionary.TYPE}",
    ]

    s = PDRectlinearMeasureDictionary()
    s.set_scale_ratio("1in = 1mi")
    nf = PDNumberFormatDictionary()
    nf.set_units("mi")
    s.set_distances([nf])
    s.set_coord_system_origin([1.5, -2.0])
    s.set_cyx(0.75)

    distances = s.get_distances()
    assert distances is not None
    lines += [
        f"set.scaleRatio={s.get_scale_ratio()}",
        f"set.distances={_arr(distances)}",
        f"set.distances0.units={_nz(distances[0].get_units())}",
        f"set.coordSystemOrigin={_farr(s.get_coord_system_origin())}",
        f"set.cyx={_float(s.get_cyx())}",
    ]
    keys = sorted(k.get_name() for k in s.get_cos_object().key_set())
    lines.append("wire.keys=" + ",".join(keys))

    assert lines == java


@requires_oracle
def test_viewport_measure_dispatch_matches_pdfbox() -> None:
    java = run_probe_text("ViewportMeasureDispatchProbe").splitlines()

    v = PDViewportDictionary()
    lines: list[str] = [
        f"empty.type={v.get_type()}",
        f"empty.bbox={'NULL' if v.get_bbox() is None else 'present'}",
        f"empty.name={_nz(v.get_name())}",
        f"empty.measure={'NULL' if v.get_measure() is None else 'present'}",
    ]

    v.set_name("Imperial")
    v.set_bbox(PDRectangle(0, 0, 100, 200))

    md = COSDictionary()
    md.set_name(COSName.TYPE, "Measure")
    md.set_name(COSName.get_pdf_name("Subtype"), "RL")
    v.get_cos_object().set_item(COSName.get_pdf_name("Measure"), md)

    got = v.get_measure()
    assert got is not None
    bbox = v.get_bbox()
    assert bbox is not None
    lines += [
        f"set.name={v.get_name()}",
        f"set.bbox.width={_float(bbox.get_width())}",
        f"set.measure.class={type(got).__name__}",
        f"set.measure.subtype={_nz(got.get_subtype())}",
    ]

    md2 = COSDictionary()
    md2.set_name(COSName.TYPE, "Measure")
    v.get_cos_object().set_item(COSName.get_pdf_name("Measure"), md2)
    got2 = v.get_measure()
    assert got2 is not None
    lines.append(f"nosub.measure.class={type(got2).__name__}")

    keys = sorted(k.get_name() for k in v.get_cos_object().key_set())
    lines.append("wire.keys=" + ",".join(keys))

    # pypdfbox class names mirror the upstream simple class names exactly
    # (PDMeasureDictionary / PDRectlinearMeasureDictionary / PDViewportDictionary),
    # so the differential report compares string-for-string.
    assert lines == java
