"""Live Apache PDFBox differential parity tests for the AcroForm RADIO-BUTTON
GROUP surface that the ChoiceButtonProbe oracle does not cover (wave 1470).

Surface under test (:class:`pypdfbox.pdmodel.interactive.form.PDRadioButton`):

  * a parent radio field with THREE widget kids, each carrying its own
    ``/AP /N`` on-state, plus an ``/Opt`` export-values array — i.e. the
    PDFBOX-3656-shaped "export values" radio group built from scratch;
  * ``get_value`` / ``set_value(str)`` selecting which kid is "on"
    (``/V`` + each widget's ``/AS``);
  * ``get_on_values`` (union of the kids' on-state names);
  * ``get_export_values`` (the ``/Opt`` array);
  * ``get_selected_export_values`` (the export value(s) whose on-state
    matches ``/V``) — NOT exercised by the existing oracle;
  * ``is_radios_in_unison`` (the ``RadiosInUnison`` ``/Ff`` bit);
  * ``get_selected_index`` and per-widget ``/AS``;
  * ``set_value_by_index`` — the upstream ``setValue(int)`` overload that
    stores the integer-string index as ``/V`` and re-reads through ``/Opt``.

Each test emits canonical, deterministic facts about the field two ways — via
the Java ``RadioGroupProbe`` (``oracle/probes/RadioGroupProbe.java``, compiled
against the pinned pdfbox-app-3.0.7 jar) and via pypdfbox's typed field API —
and asserts they are identical. The fixture (a 3-option export-values radio
group) is built at runtime via pypdfbox, then loaded by *both* implementations,
so the build itself is part of the differential surface (no upstream fixture
ships a freshly-built export-values radio group).

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_entry import (
    PDAppearanceEntry,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_AS: COSName = COSName.get_pdf_name("AS")
_OFF: COSName = COSName.get_pdf_name("Off")
_PROBE = "RadioGroupProbe"

_OPTIONS = ["Red", "Green", "Blue"]
_FIELD = "Color"


# --------------------------------------------------------------------------- #
# Fixture builder — a 3-option export-values radio group, built via pypdfbox
# --------------------------------------------------------------------------- #
def _build_radio_group(path: Path, *, in_unison: bool = False) -> None:
    """Build a radio field named ``Color`` with three widget kids.

    Each widget carries its own ``/AP /N`` with an ``Off`` entry and a single
    on-state keyed by the matching option name, and the parent field carries an
    ``/Opt`` export-values array of the same option names. ``Green`` is
    pre-selected.
    """
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)

        radio = PDRadioButton(form)
        radio.set_partial_name(_FIELD)
        if in_unison:
            radio.set_radios_in_unison(True)
        radio.set_export_values(_OPTIONS)

        widgets = []
        for idx, opt in enumerate(_OPTIONS):
            widget = PDAnnotationWidget()
            ap_n = COSDictionary()
            ap_n.set_item(_OFF, PDAppearanceStream(doc).get_cos_object())
            ap_n.set_item(
                COSName.get_pdf_name(opt), PDAppearanceStream(doc).get_cos_object()
            )
            appearance = PDAppearanceDictionary()
            appearance.set_normal_appearance(PDAppearanceEntry(ap_n))
            widget.set_appearance(appearance)
            widget.set_appearance_state("Off")
            widget.set_rectangle(PDRectangle(50, 500 - idx * 40, 20, 20))
            widget.set_page(page)
            page.get_annotations().append(widget)
            widgets.append(widget)
        radio.set_widgets(widgets)

        form.set_fields([radio])
        radio.set_value("Green")
        doc.save(str(path))
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# Java probe drivers
# --------------------------------------------------------------------------- #
def _java_read(path: Path, name: str) -> dict[str, str]:
    text = run_probe_text(_PROBE, "read", str(path), name)
    line = next(line for line in text.splitlines() if line)
    parts = line.split("\t")
    facts: dict[str, str] = {"kind": parts[1] if len(parts) > 1 else "<missing>"}
    for col in parts[2:]:
        key, _, value = col.partition("=")
        facts[key] = value
    return facts


def _java_set(fixture: Path, out: Path, name: str, value: str) -> None:
    run_probe(_PROBE, "set", str(fixture), str(out), name, value)


def _java_set_index(fixture: Path, out: Path, name: str, idx: int) -> None:
    run_probe(_PROBE, "setindex", str(fixture), str(out), name, str(idx))


# --------------------------------------------------------------------------- #
# pypdfbox fact extraction — mirrors RadioGroupProbe.radioFacts
# --------------------------------------------------------------------------- #
def _widget_as(field: PDRadioButton) -> list[str]:
    out: list[str] = []
    for widget in field.get_widgets():
        value = widget.get_cos_object().get_dictionary_object(_AS)
        out.append(value.name if isinstance(value, COSName) else "Off")
    return out


def _widget_on(field: PDRadioButton) -> list[str]:
    out: list[str] = []
    for widget in field.get_widgets():
        on = field.get_on_value_for_widget(widget)
        out.append(on if on else "<none>")
    return out


def _py_facts(field: PDRadioButton) -> dict[str, str]:
    return {
        "kind": "radio",
        "onValues": "|".join(sorted(field.get_on_values())),
        "value": field.get_value(),
        "exportValues": "|".join(field.get_export_values()),
        "selectedExport": "|".join(field.get_selected_export_values()),
        "selectedIndex": str(field.get_selected_index()),
        "radiosInUnison": "1" if field.is_radios_in_unison() else "0",
        "widgetAS": "|".join(_widget_as(field)),
        "widgetOn": "|".join(_widget_on(field)),
    }


def _py_read(path: Path, name: str) -> dict[str, str]:
    doc = PDDocument.load(str(path))
    try:
        field = doc.get_document_catalog().get_acro_form().get_field(name)
        assert isinstance(field, PDRadioButton), f"{name!r} is not a radio button"
        return _py_facts(field)
    finally:
        doc.close()


def _py_set(fixture: Path, out: Path, name: str, value: str) -> None:
    doc = PDDocument.load(str(fixture))
    try:
        field = doc.get_document_catalog().get_acro_form().get_field(name)
        assert isinstance(field, PDRadioButton)
        field.set_value(value)
        doc.save(str(out))
    finally:
        doc.close()


def _py_set_index(fixture: Path, out: Path, name: str, idx: int) -> None:
    doc = PDDocument.load(str(fixture))
    try:
        field = doc.get_document_catalog().get_acro_form().get_field(name)
        assert isinstance(field, PDRadioButton)
        field.set_value_by_index(idx)
        doc.save(str(out))
    finally:
        doc.close()


def _qpdf_ok(path: Path) -> bool:
    import shutil
    import subprocess

    if shutil.which("qpdf") is None:
        return True
    result = subprocess.run(
        ["qpdf", "--check", str(path)],
        capture_output=True,
        text=True,
    )
    return result.returncode in (0, 3)


# --------------------------------------------------------------------------- #
# READ parity — the value GET surface
# --------------------------------------------------------------------------- #
@requires_oracle
def test_built_radio_group_read_parity(tmp_path: Path) -> None:
    """A freshly-built 3-option export-values radio group reads back identical
    facts under both implementations: on-values, the pre-selected value
    (``Green``), the ``/Opt`` export values, the selected export value(s),
    selected index, RadiosInUnison flag, and per-widget ``/AS`` + on-state."""
    fixture = tmp_path / "radio.pdf"
    _build_radio_group(fixture)

    java = _java_read(fixture, _FIELD)
    py = _py_read(fixture, _FIELD)
    assert py == java
    assert py["value"] == "Green"
    assert py["exportValues"] == "Red|Green|Blue"
    assert py["selectedExport"] == "Green"
    assert py["selectedIndex"] == "1"
    assert py["radiosInUnison"] == "0"
    assert py["widgetAS"] == "Off|Green|Off"
    assert _qpdf_ok(fixture)


@requires_oracle
def test_radios_in_unison_flag_parity(tmp_path: Path) -> None:
    """The ``RadiosInUnison`` ``/Ff`` bit set at build time reads back as ``1``
    under both implementations."""
    fixture = tmp_path / "radio_unison.pdf"
    _build_radio_group(fixture, in_unison=True)

    java = _java_read(fixture, _FIELD)
    py = _py_read(fixture, _FIELD)
    assert py == java
    assert py["radiosInUnison"] == "1"
    assert _qpdf_ok(fixture)


# --------------------------------------------------------------------------- #
# SET-then-READ — selecting a different export value
# --------------------------------------------------------------------------- #
@requires_oracle
@pytest.mark.parametrize("value", ["Red", "Blue"])
def test_radio_set_export_value_then_read_parity(tmp_path: Path, value: str) -> None:
    """Selecting a radio export value via ``set_value`` flips exactly the
    matching widget on and re-reads to identical facts (value, selected export,
    selected index, per-widget ``/AS``) under both implementations."""
    fixture = tmp_path / "radio.pdf"
    _build_radio_group(fixture)

    java_out = tmp_path / f"java_{value}.pdf"
    py_out = tmp_path / f"py_{value}.pdf"
    _java_set(fixture, java_out, _FIELD, value)
    _py_set(fixture, py_out, _FIELD, value)

    java = _java_read(java_out, _FIELD)
    py = _py_read(py_out, _FIELD)
    assert py == java
    assert py["value"] == value
    assert py["selectedExport"] == value
    assert py["selectedIndex"] == str(_OPTIONS.index(value))
    states = py["widgetAS"].split("|")
    assert states.count(value) == 1
    assert all(s in (value, "Off") for s in states)
    assert _qpdf_ok(py_out)


@requires_oracle
def test_radio_set_off_then_read_parity(tmp_path: Path) -> None:
    """Setting the group to ``Off`` deselects every widget and empties the
    selected-export list identically under both implementations."""
    fixture = tmp_path / "radio.pdf"
    _build_radio_group(fixture)

    java_out = tmp_path / "java_off.pdf"
    py_out = tmp_path / "py_off.pdf"
    _java_set(fixture, java_out, _FIELD, "Off")
    _py_set(fixture, py_out, _FIELD, "Off")

    java = _java_read(java_out, _FIELD)
    py = _py_read(py_out, _FIELD)
    assert py == java
    assert py["value"] == "Off"
    assert py["selectedExport"] == ""
    assert py["selectedIndex"] == "-1"
    assert _qpdf_ok(py_out)


# --------------------------------------------------------------------------- #
# SET-by-INDEX — the upstream setValue(int) overload
# --------------------------------------------------------------------------- #
@requires_oracle
@pytest.mark.parametrize("idx", [0, 2])
def test_radio_set_by_index_then_read_parity(tmp_path: Path, idx: int) -> None:
    """``set_value_by_index`` (upstream ``setValue(int)``) stores the index as
    ``/V`` and re-reads identically under both implementations.

    Subtle upstream contract pinned here: the int overload calls
    ``updateByValue(String.valueOf(index))`` (PDButton.java line 188), so
    ``/V`` is the integer-string ``"idx"``. ``getValue()`` translates that
    back through ``/Opt`` to the export value, and ``getSelectedExportValues``
    therefore reports the export value. BUT the widget ``/AP /N`` here is keyed
    by export *names* (``Red``/``Green``/``Blue``), not numeric indices, so no
    widget matches ``"idx"`` — every ``/AS`` stays ``Off`` and ``selectedIndex``
    (which walks the widget ``/AS`` states) is ``-1``. pypdfbox reproduces this
    exactly."""
    fixture = tmp_path / "radio.pdf"
    _build_radio_group(fixture)

    java_out = tmp_path / f"java_idx{idx}.pdf"
    py_out = tmp_path / f"py_idx{idx}.pdf"
    _java_set_index(fixture, java_out, _FIELD, idx)
    _py_set_index(fixture, py_out, _FIELD, idx)

    java = _java_read(java_out, _FIELD)
    py = _py_read(py_out, _FIELD)
    assert py == java
    # /V translates back through /Opt to the export value.
    assert py["value"] == _OPTIONS[idx]
    assert py["selectedExport"] == _OPTIONS[idx]
    # Widget /AS unchanged (keyed by name, not index) -> no selected widget.
    assert py["widgetAS"] == "Off|Off|Off"
    assert py["selectedIndex"] == "-1"
    assert _qpdf_ok(py_out)
