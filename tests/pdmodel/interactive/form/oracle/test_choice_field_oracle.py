"""Live Apache PDFBox differential parity for AcroForm CHOICE fields built
from scratch — :class:`PDListBox` (multi-select, ``[export, display]`` ``/Opt``
pairs) and :class:`PDComboBox` (flat-string ``/Opt``).

The sibling ``test_list_box_detail_oracle.py`` / ``test_multi_select_combo_oracle.py``
pin the *read + re-select* surface against a hand-built fixture loaded from disk.
This module pins the **build-from-scratch** path: a fresh ``PDListBox`` /
``PDComboBox`` constructed via the no-COS constructor, ``setOptions`` (both the
``List`` and the ``(export, display)`` overload), ``setValue`` (``String`` and
``List``), then a save → reload round trip. It checks the exact observables
PDFBox emits through the ``ChoiceFieldProbe``:

* ``getOptions`` / ``getOptionsExportValues`` (export half) and
  ``getOptionsDisplayValues`` (display half) of the ``[export, display]`` pairs;
* ``getValue`` preserves the caller's insertion order in ``/V`` …
* … while ``getSelectedOptionsIndex`` (``/I``) comes back **sorted ascending**
  (PDF 32000-1 §12.7.4.4) regardless of ``/V`` order;
* ``getValueAsString`` renders the Java ``Arrays.toString`` form (``"[a, b]"``);
* a single-value ``setValue(String)`` on the combo clears ``/I``;
* every observable survives the save → reload round trip unchanged;
* ``setValue(List)`` with a value NOT in ``/Opt`` on a non-editable combo
  raises (Java ``IllegalArgumentException`` → pypdfbox ``ValueError``).

Both sides drive the identical construction sequence — the Java
``ChoiceFieldProbe`` and the pypdfbox builder here — and the parsed observables
must agree exactly.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "ChoiceFieldProbe"


# ----------------------------------------------------------------- fact readers


def _parse_probe(text: str) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in text.splitlines():
        if not line:
            continue
        key, _, rest = line.partition(" ")
        facts[key] = rest
    return facts


def _list_repr(values: list[str] | list[int]) -> str:
    """Render a list the way the Java probe does (``Arrays.toString``-ish):
    ``[a, b, c]`` (empty -> ``[]``)."""
    return "[" + ", ".join(str(v) for v in values) + "]"


def _build_py_facts(out: Path) -> dict[str, str]:
    """Drive the identical construction sequence pypdfbox-side and emit the same
    fact keys as ``ChoiceFieldProbe``. ``regenerate_appearance=False`` mirrors
    the probe's ``/NeedAppearances true`` gate (no widgets attached, so no
    appearance stream is produced either way)."""
    facts: dict[str, str] = {}

    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)

        lb = PDListBox(form)
        lb.set_partial_name("lb")
        lb.set_multi_select(True)
        exports = ["e0", "e1", "e2", "e3"]
        displays = ["Display Zero", "Display One", "Display Two", "Display Three"]
        lb.set_options(exports, displays)

        facts["lb_options"] = _list_repr(lb.get_options())
        facts["lb_export"] = _list_repr(lb.get_options_export_values())
        facts["lb_display"] = _list_repr(lb.get_options_display_values())

        lb.set_value(["e2", "e0"], regenerate_appearance=False)
        facts["lb_value"] = _list_repr(lb.get_value())
        facts["lb_value_str"] = lb.get_value_as_string()
        facts["lb_index"] = _list_repr(lb.get_selected_options_indices())

        cb = PDComboBox(form)
        cb.set_partial_name("cb")
        cb.set_options(["Alpha", "Beta", "Gamma"])
        facts["cb_options"] = _list_repr(cb.get_options())

        cb.set_value("Beta", regenerate_appearance=False)
        facts["cb_value"] = _list_repr(cb.get_value())
        facts["cb_value_str"] = cb.get_value_as_string()
        facts["cb_index"] = _list_repr(cb.get_selected_options_indices())

        from pypdfbox.cos import COSArray, COSName

        fields = COSArray()
        fields.add(lb.get_cos_object())
        fields.add(cb.get_cos_object())
        form.get_cos_object().set_item(COSName.get_pdf_name("Fields"), fields)

        doc.save(str(out))
    finally:
        doc.close()

    # ----- reload and re-emit the persisted view -----
    doc = PDDocument.load(out)
    try:
        form = doc.get_document_catalog().get_acro_form()
        lb = form.get_field("lb")
        cb = form.get_field("cb")

        facts["rt_lb_options"] = _list_repr(lb.get_options())
        facts["rt_lb_display"] = _list_repr(lb.get_options_display_values())
        facts["rt_lb_value"] = _list_repr(lb.get_value())
        facts["rt_lb_index"] = _list_repr(lb.get_selected_options_indices())
        facts["rt_cb_value"] = _list_repr(cb.get_value())
        facts["rt_cb_index"] = _list_repr(cb.get_selected_options_indices())

        try:
            cb.set_value(["NotAnOption"], regenerate_appearance=False)
            facts["cb_bad_set"] = "ok"
        except ValueError:
            facts["cb_bad_set"] = "IllegalArgumentException"
    finally:
        doc.close()

    return facts


# ------------------------------------------------------------------- tests


@requires_oracle
def test_choice_field_build_matches_pdfbox(tmp_path: Path) -> None:
    """The full build-from-scratch observable set agrees with PDFBox exactly."""
    java_facts = _parse_probe(run_probe_text(_PROBE, str(tmp_path / "java.pdf")))
    py_facts = _build_py_facts(tmp_path / "py.pdf")

    assert py_facts == java_facts, (
        f"choice-field build divergence:\n"
        f"  pypdfbox: {py_facts}\n  PDFBox:   {java_facts}"
    )


@requires_oracle
def test_choice_field_key_invariants(tmp_path: Path) -> None:
    """Spell out the load-bearing invariants the probe pins, so a regression
    names the exact rule it broke."""
    facts = _parse_probe(run_probe_text(_PROBE, str(tmp_path / "java.pdf")))

    # [export, display] pairs split into the two halves correctly.
    assert facts["lb_options"] == "[e0, e1, e2, e3]"
    assert facts["lb_export"] == "[e0, e1, e2, e3]"
    assert facts["lb_display"] == "[Display Zero, Display One, Display Two, Display Three]"

    # /V keeps caller insertion order; /I comes back sorted ascending.
    assert facts["lb_value"] == "[e2, e0]"
    assert facts["lb_index"] == "[0, 2]"
    assert facts["lb_value_str"] == "[e2, e0]"

    # single-value combo: /V set, /I cleared.
    assert facts["cb_value"] == "[Beta]"
    assert facts["cb_index"] == "[]"

    # survives round trip.
    assert facts["rt_lb_value"] == "[e2, e0]"
    assert facts["rt_lb_index"] == "[0, 2]"
    assert facts["rt_lb_display"] == "[Display Zero, Display One, Display Two, Display Three]"

    # setValue(List) membership gate on a non-editable combo throws.
    assert facts["cb_bad_set"] == "IllegalArgumentException"
