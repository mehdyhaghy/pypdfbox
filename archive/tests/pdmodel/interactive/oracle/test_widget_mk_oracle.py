"""Live PDFBox differential parity for the widget ``/MK``
appearance-characteristics READ surface
(:class:`pypdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary`).

``WidgetApProbe`` (wave 1434) only reads ``/BG`` / ``/BC`` (on an RGB-only,
pypdfbox-built fixture) plus ``/CA`` normal caption and ``/R`` rotation. This
module pins the parts it does NOT cover:

* ``/RC`` rollover caption + ``/AC`` alternate caption;
* the colour ARITY DISPATCH in ``get_border_colour()`` / ``get_background()``:
  a 1-, 3- or 4-element array maps to DeviceGray / DeviceRGB / DeviceCMYK and
  round-trips its components, while a 2-element (or empty) array maps to
  ``None`` — exactly upstream's private ``getColor(COSName)`` arity switch.

The fixture is BUILT by Apache PDFBox (the authoritative writer) so the
differential is purely pypdfbox's READ path against the bytes upstream wrote.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSNumber, COSString
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_T = COSName.get_pdf_name("T")


# --------------------------------------------------------------------------- #
# canonical float rendering — mirrors WidgetMkProbe.canonFloat (Java)
# --------------------------------------------------------------------------- #
def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _color_array(color: object) -> str:
    """Space-joined canonical-float components of a PDColor's COSArray, or
    ``none`` when the colour is absent (matches WidgetMkProbe.colorArray)."""
    if color is None:
        return "none"
    arr = color.to_cos_array()  # type: ignore[attr-defined]
    comps: list[str] = []
    for i in range(arr.size()):
        elem = arr.get_object(i)
        if isinstance(elem, COSNumber):
            comps.append(_canon_float(elem.float_value()))
    return " ".join(comps) if comps else "none"


def _caption(value: str | None) -> str:
    return "none" if value is None else f"[{value}]"


def _widget_name(widget: object) -> str:
    t = widget.get_cos_object().get_dictionary_object(_T)  # type: ignore[attr-defined]
    if isinstance(t, COSString):
        return t.get_string()
    return "-" if t is None else str(t)


def _py_report(path: object) -> str:
    """Build the same per-widget /MK report WidgetMkProbe READ-mode emits."""
    lines: list[str] = []
    doc = PDDocument.load(path)
    try:
        for page in doc.get_pages():
            for annot in page.get_annotations():
                if annot.get_subtype() != "Widget":
                    continue
                lines.append(f"WIDGET {_widget_name(annot)}")
                mk = annot.get_appearance_characteristics()
                if mk is None:
                    lines.append("BC none")
                    lines.append("BG none")
                    lines.append("CA none")
                    lines.append("RC none")
                    lines.append("AC none")
                    lines.append("R 0")
                else:
                    lines.append(f"BC {_color_array(mk.get_border_colour())}")
                    lines.append(f"BG {_color_array(mk.get_background())}")
                    lines.append(f"CA {_caption(mk.get_normal_caption())}")
                    lines.append(f"RC {_caption(mk.get_rollover_caption())}")
                    lines.append(f"AC {_caption(mk.get_alternate_caption())}")
                    lines.append(f"R {mk.get_rotation()}")
                lines.append("END")
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


@requires_oracle
def test_widget_mk_matches_pdfbox(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fixture = tmp_path / "mk_fixture.pdf"
    # Build with upstream PDFBox so the bytes under test are upstream-authored.
    run_probe("WidgetMkProbe", "build", str(fixture))
    java = run_probe_text("WidgetMkProbe", "read", str(fixture))
    py = _py_report(fixture)
    assert py == java


@requires_oracle
def test_widget_mk_fixture_actually_carries_widgets(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Guard: the built fixture must enumerate widgets so the parity test
    cannot pass vacuously on an empty report."""
    fixture = tmp_path / "mk_fixture.pdf"
    run_probe("WidgetMkProbe", "build", str(fixture))
    report = _py_report(fixture)
    assert report.count("WIDGET ") == 5
    # The arity-2 /BC and empty arrays must resolve to "none" (the bug-prone
    # cases): two widgets with BC none beyond the CMYK one, etc.
    assert "BC 0.25\n" in report  # gray arity-1 round-trips
    assert "BG 0.1 0.2 0.3 0.4\n" in report  # cmyk arity-4 round-trips


@requires_oracle
def test_widget_mk_arity_two_is_none(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Pin the arity-dispatch edge: a 2-element /BC array must read as None
    (DeviceGray=1 / RGB=3 / CMYK=4 only; everything else is null)."""
    fixture = tmp_path / "mk_fixture.pdf"
    run_probe("WidgetMkProbe", "build", str(fixture))
    doc = PDDocument.load(fixture)
    try:
        for page in doc.get_pages():
            for annot in page.get_annotations():
                if _widget_name(annot) == "btnTwo":
                    mk = annot.get_appearance_characteristics()
                    assert mk is not None
                    assert mk.get_border_colour() is None
                    # raw array is still reachable via the escape hatch
                    raw = mk.get_border_colour_array()
                    assert raw is not None
                    assert raw.size() == 2
                    return
        pytest.fail("btnTwo widget not found")
    finally:
        doc.close()
