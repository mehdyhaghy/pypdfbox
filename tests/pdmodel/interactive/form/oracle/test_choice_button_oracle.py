"""Live Apache PDFBox differential parity tests for CHOICE + BUTTON form-field
get/set semantics (wave 1432).

Surface under test (``pypdfbox/pdmodel/interactive/form/``):

  * :class:`PDChoice` / :class:`PDComboBox` / :class:`PDListBox` —
    ``get_options_export_values`` / ``get_options_display_values``,
    ``get_value`` / ``set_value`` (str + list overloads),
    ``get_selected_options_indices``, ``is_multi_select``.
  * :class:`PDRadioButton` — ``get_value`` / ``set_value`` (selecting an
    on-state across the widget group), ``get_on_values``,
    ``get_export_values``, ``get_selected_index``, per-widget ``/AS``.
  * :class:`PDCheckBox` — ``get_on_value``, ``check`` / ``un_check`` /
    ``is_checked``, ``get_value``, per-widget ``/AS``.

Each test emits canonical, deterministic *facts* about a field two ways — via
the Java ``ChoiceButtonProbe`` (``oracle/probes/ChoiceButtonProbe.java``,
compiled against the pinned pdfbox-app-3.0.7 jar) and via pypdfbox's typed
field API — and asserts the two are identical. Both a plain READ (the value
get surface) and a SET-then-READ round trip (the value set surface) are
checked, per field type.

The high-value invariants:
  * radio on-state selection — which widget ``/AS`` becomes the on-appearance
    after ``set_value`` (PDFBox flips exactly the matching widget on);
  * combo/list export-vs-display handling — ``get_value`` returns the export
    value, ``get_options_display_values`` the parallel display half;
  * multi-select list ``/V`` + ``/I`` (sorted ascending);
  * checkbox on-value + ``is_checked`` (checked iff ``/V`` == on-value).

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit). The multi-select list-box and
the separate-export/display combo fixtures are built at runtime via pypdfbox
(no upstream fixture carries a multi-select list box), then loaded by *both*
implementations — the build itself is therefore part of the differential
surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_choice import PDChoice
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"
_FORM_FIXTURES = _FIXTURES / "pdmodel" / "interactive" / "form"
_BASIC = _FORM_FIXTURES / "AcroFormsBasicFields.pdf"

_AS: COSName = COSName.get_pdf_name("AS")

_PROBE = "ChoiceButtonProbe"


# --------------------------------------------------------------------------- #
# Java probe drivers
# --------------------------------------------------------------------------- #
def _java_read(path: Path, *names: str) -> dict[str, dict[str, str]]:
    """Run the probe in READ mode; parse its records into ``{name: facts}``.

    Each line is ``<name>\\t<kind>\\t<k=v>\\t<k=v>...``. The returned dict maps
    the field name to a flat facts dict that always carries ``kind``.
    """
    text = run_probe_text(_PROBE, "read", str(path), *names)
    out: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        name = parts[0]
        facts: dict[str, str] = {"kind": parts[1] if len(parts) > 1 else "<missing>"}
        for col in parts[2:]:
            key, _, value = col.partition("=")
            facts[key] = value
        out[name] = facts
    return out


def _java_set(fixture: Path, out: Path, *ops: str) -> None:
    """Run the probe in SET mode (load, apply ``name=value`` ops, save)."""
    run_probe(_PROBE, "set", str(fixture), str(out), *ops)


# --------------------------------------------------------------------------- #
# pypdfbox fact extraction — mirrors ChoiceButtonProbe's per-kind helpers
# --------------------------------------------------------------------------- #
def _widget_as(field: object) -> list[str]:
    out: list[str] = []
    for widget in field.get_widgets():  # type: ignore[attr-defined]
        value = widget.get_cos_object().get_dictionary_object(_AS)
        out.append(value.name if isinstance(value, COSName) else "<none>")
    return out


def _py_choice_facts(field: PDChoice) -> dict[str, str]:
    multi = isinstance(field, PDListBox) and field.is_multi_select()
    return {
        "kind": "choice",
        "export": "|".join(field.get_options_export_values()),
        "display": "|".join(field.get_options_display_values()),
        "value": "|".join(field.get_value()),
        "indices": "|".join(str(i) for i in field.get_selected_options_indices()),
        "multi": "1" if multi else "0",
        "combo": "1" if isinstance(field, PDComboBox) else "0",
        "valueAsString": field.get_value_as_string(),
    }


def _py_radio_facts(field: PDRadioButton) -> dict[str, str]:
    return {
        "kind": "radio",
        "onValues": "|".join(sorted(field.get_on_values())),
        "value": field.get_value(),
        "exportValues": "|".join(field.get_export_values()),
        "selectedIndex": str(field.get_selected_index()),
        "widgetAS": "|".join(_widget_as(field)),
    }


def _py_checkbox_facts(field: PDCheckBox) -> dict[str, str]:
    return {
        "kind": "checkbox",
        "onValue": field.get_on_value(),
        "value": field.get_value(),
        "checked": "1" if field.is_checked() else "0",
        "widgetAS": "|".join(_widget_as(field)),
    }


def _py_facts(doc: PDDocument, name: str) -> dict[str, str]:
    field = doc.get_document_catalog().get_acro_form().get_field(name)
    assert field is not None, f"field {name!r} not found"
    if isinstance(field, PDChoice):
        return _py_choice_facts(field)
    if isinstance(field, PDRadioButton):
        return _py_radio_facts(field)
    if isinstance(field, PDCheckBox):
        return _py_checkbox_facts(field)
    raise AssertionError(f"unexpected field type for {name!r}: {type(field).__name__}")


def _py_read(path: Path, name: str) -> dict[str, str]:
    doc = PDDocument.load(str(path))
    try:
        return _py_facts(doc, name)
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# pypdfbox fixture builders (no upstream fixture carries these shapes)
# --------------------------------------------------------------------------- #
def _build_multi_select_list(path: Path) -> None:
    """A multi-select :class:`PDListBox` with four single-string options and
    two values pre-selected (``Beta``, ``Delta``)."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)
        lb = PDListBox(form)
        lb.set_partial_name("MultiList")
        lb.set_multi_select(True)
        lb.set_options(["Alpha", "Beta", "Gamma", "Delta"])
        widget = lb.get_widgets()[0]
        widget.set_rectangle(PDRectangle(50, 500, 200, 100))
        widget.set_page(page)
        page.get_annotations().append(widget)
        form.set_fields([lb])
        lb.set_value(["Beta", "Delta"])
        doc.save(str(path))
    finally:
        doc.close()


def _build_export_display_combo(path: Path) -> None:
    """A :class:`PDComboBox` whose options carry SEPARATE export + display
    halves (``e1`` -> ``Display One`` etc.), value ``e2`` pre-selected."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)
        cb = PDComboBox(form)
        cb.set_partial_name("ExpCombo")
        cb.set_options(
            ["e1", "e2", "e3"],
            ["Display One", "Display Two", "Display Three"],
        )
        widget = cb.get_widgets()[0]
        widget.set_rectangle(PDRectangle(50, 500, 200, 30))
        widget.set_page(page)
        page.get_annotations().append(widget)
        form.set_fields([cb])
        cb.set_value("e2")
        doc.save(str(path))
    finally:
        doc.close()


def _py_set(fixture: Path, out: Path, name: str, value: str) -> None:
    """Apply a typed set on one field via pypdfbox, mirroring the probe's SET
    dispatch (choice with ``|`` -> list overload; ``__check__`` / ``__uncheck__``
    -> checkbox check/un_check)."""
    doc = PDDocument.load(str(fixture))
    try:
        field = doc.get_document_catalog().get_acro_form().get_field(name)
        assert field is not None, f"field {name!r} not found"
        if isinstance(field, PDChoice):
            field.set_value(value.split("|") if "|" in value else value)
        elif isinstance(field, PDCheckBox) and value == "__check__":
            field.check()
        elif isinstance(field, PDCheckBox) and value == "__uncheck__":
            field.un_check()
        else:
            field.set_value(value)
        doc.save(str(out))
    finally:
        doc.close()


def _qpdf_ok(path: Path) -> bool:
    """``qpdf --check`` passes (warnings tolerated, hard errors not)."""
    import shutil
    import subprocess

    if shutil.which("qpdf") is None:
        return True
    result = subprocess.run(
        ["qpdf", "--check", str(path)],
        capture_output=True,
        text=True,
    )
    # qpdf exit codes: 0 = clean, 3 = warnings only, 2 = errors.
    return result.returncode in (0, 3)


# --------------------------------------------------------------------------- #
# READ parity — the value GET surface
# --------------------------------------------------------------------------- #
@requires_oracle
@pytest.mark.parametrize(
    "name",
    [
        "ComboBox",
        "ComboBox-DefaultValue",
        "ListBox",
        "ListBox-DefaultValue",
        "Checkbox",
        "Checkbox-DefaultValue",
        "CheckboxGroup",
        "CheckboxGroupChecked",
        "RadioButtonGroup",
        "RadioButtonGroup-DefaultValue",
    ],
)
def test_field_get_facts_match_pdfbox(name: str) -> None:
    """Every canonical fact pypdfbox reports for a choice/radio/checkbox field
    equals what Apache PDFBox reports on the same fixture — the value-get
    surface (options export/display, value(s), selected indices, multi-select,
    on-values, checkbox on-value + isChecked, per-widget /AS)."""
    java = _java_read(_BASIC, name)[name]
    py = _py_read(_BASIC, name)
    assert py == java


# --------------------------------------------------------------------------- #
# Choice (combo) SET-then-READ
# --------------------------------------------------------------------------- #
@requires_oracle
@pytest.mark.parametrize("value", ["Opt02", "Opt03"])
def test_combo_set_then_read_parity(tmp_path: Path, value: str) -> None:
    """Setting a combo value via Java vs pypdfbox stores the identical export
    value, clears ``/I`` the same way, and re-reads to identical facts."""
    java_out = tmp_path / f"java_combo_{value}.pdf"
    py_out = tmp_path / f"py_combo_{value}.pdf"
    _java_set(_BASIC, java_out, f"ComboBox-DefaultValue={value}")
    _py_set(_BASIC, py_out, "ComboBox-DefaultValue", value)

    java = _java_read(java_out, "ComboBox-DefaultValue")["ComboBox-DefaultValue"]
    py = _py_read(py_out, "ComboBox-DefaultValue")
    assert py == java
    assert py["value"] == value
    assert _qpdf_ok(py_out)


# --------------------------------------------------------------------------- #
# Choice — separate export vs display values (built via pypdfbox)
# --------------------------------------------------------------------------- #
@requires_oracle
def test_export_display_combo_read_parity(tmp_path: Path) -> None:
    """A combo whose options carry separate export + display halves reads back
    identically under both implementations: ``get_value`` is the export value,
    ``get_options_display_values`` the parallel display half."""
    fixture = tmp_path / "expcombo.pdf"
    _build_export_display_combo(fixture)

    java = _java_read(fixture, "ExpCombo")["ExpCombo"]
    py = _py_read(fixture, "ExpCombo")
    assert py == java
    assert py["export"] == "e1|e2|e3"
    assert py["display"] == "Display One|Display Two|Display Three"
    assert py["value"] == "e2"
    assert _qpdf_ok(fixture)


@requires_oracle
def test_export_display_combo_set_then_read_parity(tmp_path: Path) -> None:
    """Setting the export value ``e3`` on the export/display combo round-trips
    to identical facts under both implementations (value is the export token,
    not the display label)."""
    fixture = tmp_path / "expcombo.pdf"
    _build_export_display_combo(fixture)

    java_out = tmp_path / "java_expcombo.pdf"
    py_out = tmp_path / "py_expcombo.pdf"
    _java_set(fixture, java_out, "ExpCombo=e3")
    _py_set(fixture, py_out, "ExpCombo", "e3")

    java = _java_read(java_out, "ExpCombo")["ExpCombo"]
    py = _py_read(py_out, "ExpCombo")
    assert py == java
    assert py["value"] == "e3"
    assert _qpdf_ok(py_out)


# --------------------------------------------------------------------------- #
# Choice — multi-select list box (built via pypdfbox)
# --------------------------------------------------------------------------- #
@requires_oracle
def test_multi_select_list_read_parity(tmp_path: Path) -> None:
    """A multi-select list box reads back identical facts under both
    implementations: both values present in ``/V`` and ``/I`` sorted
    ascending."""
    fixture = tmp_path / "multilist.pdf"
    _build_multi_select_list(fixture)

    java = _java_read(fixture, "MultiList")["MultiList"]
    py = _py_read(fixture, "MultiList")
    assert py == java
    assert py["multi"] == "1"
    assert py["value"] == "Beta|Delta"
    assert py["indices"] == "1|3"
    assert _qpdf_ok(fixture)


@requires_oracle
def test_multi_select_list_set_then_read_parity(tmp_path: Path) -> None:
    """Re-selecting two different options on the multi-select list round-trips
    to identical ``/V`` + ascending-sorted ``/I`` under both implementations."""
    fixture = tmp_path / "multilist.pdf"
    _build_multi_select_list(fixture)

    java_out = tmp_path / "java_multilist.pdf"
    py_out = tmp_path / "py_multilist.pdf"
    # Note the deliberately out-of-order pair: /I must come back sorted (0,2).
    _java_set(fixture, java_out, "MultiList=Gamma|Alpha")
    _py_set(fixture, py_out, "MultiList", "Gamma|Alpha")

    java = _java_read(java_out, "MultiList")["MultiList"]
    py = _py_read(py_out, "MultiList")
    assert py == java
    # PDF 32000-1 §12.7.4.4: /I sorted ascending regardless of /V order.
    assert py["indices"] == "0|2"
    assert _qpdf_ok(py_out)


# --------------------------------------------------------------------------- #
# Radio button SET-then-READ
# --------------------------------------------------------------------------- #
@requires_oracle
@pytest.mark.parametrize("value", ["RadioButton01", "RadioButton02"])
def test_radio_set_then_read_parity(tmp_path: Path, value: str) -> None:
    """Selecting a radio on-value flips exactly the matching widget's ``/AS``
    on (others ``/Off``) and sets ``/V`` identically under both
    implementations — the high-value on-state selection invariant."""
    java_out = tmp_path / f"java_radio_{value}.pdf"
    py_out = tmp_path / f"py_radio_{value}.pdf"
    _java_set(_BASIC, java_out, f"RadioButtonGroup={value}")
    _py_set(_BASIC, py_out, "RadioButtonGroup", value)

    java = _java_read(java_out, "RadioButtonGroup")["RadioButtonGroup"]
    py = _py_read(py_out, "RadioButtonGroup")
    assert py == java
    assert py["value"] == value
    # Exactly one widget /AS is the chosen on-value; the rest are Off.
    states = py["widgetAS"].split("|")
    assert states.count(value) == 1
    assert all(s in (value, "Off") for s in states)
    assert _qpdf_ok(py_out)


@requires_oracle
def test_radio_set_off_parity(tmp_path: Path) -> None:
    """Setting a radio group to ``Off`` deselects all widgets identically."""
    java_out = tmp_path / "java_radio_off.pdf"
    py_out = tmp_path / "py_radio_off.pdf"
    _java_set(_BASIC, java_out, "RadioButtonGroup-DefaultValue=Off")
    _py_set(_BASIC, py_out, "RadioButtonGroup-DefaultValue", "Off")

    java = _java_read(java_out, "RadioButtonGroup-DefaultValue")[
        "RadioButtonGroup-DefaultValue"
    ]
    py = _py_read(py_out, "RadioButtonGroup-DefaultValue")
    assert py == java
    assert py["value"] == "Off"
    assert py["selectedIndex"] == "-1"
    assert _qpdf_ok(py_out)


# --------------------------------------------------------------------------- #
# Checkbox SET-then-READ
# --------------------------------------------------------------------------- #
@requires_oracle
def test_checkbox_check_then_read_parity(tmp_path: Path) -> None:
    """``check()`` stores the widget on-value as ``/V``, flips ``/AS`` on, and
    re-reads ``isChecked`` true — identical to PDFBox's ``check()``."""
    java_out = tmp_path / "java_cb_check.pdf"
    py_out = tmp_path / "py_cb_check.pdf"
    _java_set(_BASIC, java_out, "Checkbox=__check__")
    _py_set(_BASIC, py_out, "Checkbox", "__check__")

    java = _java_read(java_out, "Checkbox")["Checkbox"]
    py = _py_read(py_out, "Checkbox")
    assert py == java
    assert py["checked"] == "1"
    assert py["value"] == py["onValue"]
    assert _qpdf_ok(py_out)


@requires_oracle
def test_checkbox_uncheck_then_read_parity(tmp_path: Path) -> None:
    """``un_check()`` stores ``Off``, flips ``/AS`` off, ``isChecked`` false —
    identical to PDFBox's ``unCheck()``."""
    java_out = tmp_path / "java_cb_uncheck.pdf"
    py_out = tmp_path / "py_cb_uncheck.pdf"
    _java_set(_BASIC, java_out, "Checkbox-DefaultValue=__uncheck__")
    _py_set(_BASIC, py_out, "Checkbox-DefaultValue", "__uncheck__")

    java = _java_read(java_out, "Checkbox-DefaultValue")["Checkbox-DefaultValue"]
    py = _py_read(py_out, "Checkbox-DefaultValue")
    assert py == java
    assert py["checked"] == "0"
    assert py["value"] == "Off"
    assert _qpdf_ok(py_out)


@requires_oracle
def test_checkbox_group_set_then_read_parity(tmp_path: Path) -> None:
    """Setting a multi-widget checkbox group to its on-value flips exactly the
    matching widget(s) ``/AS`` on and stores the on-value as ``/V`` identically
    under both implementations."""
    java_out = tmp_path / "java_cbg.pdf"
    py_out = tmp_path / "py_cbg.pdf"
    _java_set(_BASIC, java_out, "CheckboxGroup=Option1")
    _py_set(_BASIC, py_out, "CheckboxGroup", "Option1")

    java = _java_read(java_out, "CheckboxGroup")["CheckboxGroup"]
    py = _py_read(py_out, "CheckboxGroup")
    assert py == java
    assert py["value"] == "Option1"
    assert py["checked"] == "1"
    assert _qpdf_ok(py_out)
