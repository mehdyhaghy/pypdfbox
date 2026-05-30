"""Live Apache PDFBox differential parity for the MULTI-SELECT VALUE +
EDITABLE COMBO surface (wave 1474).

Surface under test (``pypdfbox/pdmodel/interactive/form/``):

  * :class:`PDListBox` with the MultiSelect ``/Ff`` flag (bit 22) — ``/V`` an
    ARRAY of two selected export values, ``/I`` the (sorted) selected-index
    array, ``/TI`` the top index; read back through ``get_value`` (a list),
    ``get_selected_options_index``, ``get_top_index``, ``is_multi_select``.
  * :class:`PDComboBox` with the Edit ``/Ff`` flag (bit 19) — ``/V`` a free-
    typed value NOT present in ``/Opt``; read back through ``get_value``,
    ``is_edit``, ``is_multi_select``.

Where ``test_list_box_detail_oracle`` (wave 1446) isolates the list box and
``test_editable_combo_oracle`` (wave 1447) isolates the combo, this file drives
*both field types in one document* so the choice-field type dispatch
(``PDFieldFactory`` → ``PDListBox`` vs ``PDComboBox``) is part of the
differential, and asserts the value-surface facts that distinguish them: a
multi-select list box returns a multi-element ``/V`` list with a sorted ``/I``
and a resolved selected-export set, while an editable combo returns its custom
free text with an empty ``/I`` (the value is not in ``/Opt``, so ``inOpt=0``).

PDFBox 3.0.7 has NO ``getSelectedExportValues`` on ``PDChoice``; the selected
export set is *resolved* from ``/I`` against the ``/Opt`` export half — by both
the Java ``MultiSelectComboProbe`` and the pypdfbox extractor here.

Each test emits canonical, deterministic facts two ways — via the Java probe
(compiled against the pinned pdfbox-app-3.0.7 jar) and via pypdfbox's typed
field API — and asserts the two are identical. A plain READ (the get surface),
a multi-select ``/V`` + ``/I`` re-selection round trip, and an editable-combo
custom-value round trip are all checked.

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit). No upstream fixture carries this
combined two-field shape, so the fixture is built at runtime via pypdfbox, then
loaded by *both* implementations — the build itself is part of the surface.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_choice import PDChoice
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_PROBE = "MultiSelectComboProbe"


# --------------------------------------------------------------------------- #
# Java probe drivers
# --------------------------------------------------------------------------- #
def _java_read(path: Path, *names: str) -> dict[str, dict[str, str]]:
    """Run the probe in READ mode for ``names``; parse each field's record
    into ``{name: {k: v}}`` (each line is ``<name>\\t<k=v>\\t<k=v>...``)."""
    text = run_probe_text(_PROBE, "read", str(path), *names)
    out: dict[str, dict[str, str]] = {}
    for name in names:
        line = next(line for line in text.splitlines() if line.startswith(name + "\t"))
        parts = line.split("\t")
        facts: dict[str, str] = {}
        for col in parts[1:]:
            key, _, value = col.partition("=")
            facts[key] = value
        out[name] = facts
    return out


def _java_set(fixture: Path, out: Path, *ops: str) -> None:
    """Run the probe in SET mode (load, apply ops, save). Ops are
    ``name=<v|v|...>`` (setValue List) or ``name=<v>`` (setValue String)."""
    run_probe(_PROBE, "set", str(fixture), str(out), *ops)


# --------------------------------------------------------------------------- #
# pypdfbox fact extraction — mirrors MultiSelectComboProbe.facts
# --------------------------------------------------------------------------- #
def _esc(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("|", "\\u007c")
        .replace(":", "\\u003a")
    )


def _py_field_facts(field: PDChoice) -> dict[str, str]:
    is_combo = isinstance(field, PDComboBox)
    multi = field.is_multi_select()
    edit = is_combo and field.is_edit()
    top_index = field.get_top_index() if isinstance(field, PDListBox) else 0
    value = field.get_value()
    indices = field.get_selected_options_index()
    export = field.get_options_export_values()

    sel_export = [export[j] if 0 <= j < len(export) else "<oob>" for j in indices]

    in_opt = bool(value) and all(v in export for v in value)

    return {
        "kind": "combo" if is_combo else "listbox",
        "multi": "1" if multi else "0",
        "edit": "1" if edit else "0",
        "topIndex": str(top_index),
        "value": "|".join(_esc(v) for v in value),
        "indices": "|".join(str(i) for i in indices),
        "export": "|".join(_esc(v) for v in export),
        "selExport": "|".join(_esc(v) for v in sel_export),
        "inOpt": "1" if in_opt else "0",
    }


def _py_read(path: Path, *names: str) -> dict[str, dict[str, str]]:
    doc = PDDocument.load(str(path))
    try:
        form = doc.get_document_catalog().get_acro_form()
        out: dict[str, dict[str, str]] = {}
        for name in names:
            field = form.get_field(name)
            assert isinstance(field, PDChoice), f"field {name!r} is not a choice"
            out[name] = _py_field_facts(field)
        return out
    finally:
        doc.close()


def _py_set(fixture: Path, out: Path, *ops: str) -> None:
    """Apply the same ops pypdfbox-side as the Java probe's SET dispatch."""
    doc = PDDocument.load(str(fixture))
    try:
        form = doc.get_document_catalog().get_acro_form()
        for op in ops:
            eq = op.find("=")
            name = op[:eq]
            value = op[eq + 1 :]
            field = form.get_field(name)
            field.set_value(value.split("|") if "|" in value else value)
        doc.save(str(out))
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# pypdfbox fixture builder (no upstream fixture carries this combined shape)
# --------------------------------------------------------------------------- #
def _build_doc(path: Path) -> None:
    """One document carrying two choice fields:

    * ``MultiList`` — a MultiSelect :class:`PDListBox` with four export/display
      ``/Opt`` pairs, ``/TI`` top index 1, two values pre-selected out of /Opt
      order (``e3``, ``e1``) so ``/I`` comes back sorted ``0,2``.
    * ``EditCombo`` — an editable :class:`PDComboBox` with three ``/Opt``
      strings whose ``/V`` is a CUSTOM free-typed value not in ``/Opt``.
    """
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)

        lb = PDListBox(form)
        lb.set_partial_name("MultiList")
        lb.set_multi_select(True)
        lb.set_options(
            ["e1", "e2", "e3", "e4"],
            ["Display 1", "Display 2", "Display 3", "Display 4"],
        )
        lb_widget = lb.get_widgets()[0]
        lb_widget.set_rectangle(PDRectangle(50, 500, 200, 100))
        lb_widget.set_page(page)
        page.get_annotations().append(lb_widget)

        cb = PDComboBox(form)
        cb.set_partial_name("EditCombo")
        cb.set_edit(True)
        cb.set_options(["red", "green", "blue"])
        cb_widget = cb.get_widgets()[0]
        cb_widget.set_rectangle(PDRectangle(50, 400, 200, 20))
        cb_widget.set_page(page)
        page.get_annotations().append(cb_widget)

        form.set_fields([lb, cb])

        lb.set_top_index(1)
        # Out of /Opt order: /V keeps insertion order e3,e1; /I sorts to 0,2.
        lb.set_value(["e3", "e1"])
        # A free-typed value not present in /Opt (the editable-combo case).
        cb.set_value("custom-magenta")
        doc.save(str(path))
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
    return result.returncode in (0, 3)


# --------------------------------------------------------------------------- #
# READ parity — both field types in one document
# --------------------------------------------------------------------------- #
@requires_oracle
def test_multi_select_and_editable_combo_read_parity(tmp_path: Path) -> None:
    """Every fact pypdfbox reports for the multi-select list box AND the
    editable combo equals what Apache PDFBox reports on the same fixture: the
    field-type discriminator, ``isMultiSelect`` / ``isEdit``, ``/TI`` top
    index, ``/V`` (a multi-element list for the list box, the custom free text
    for the combo), ``/I`` (sorted, empty for the combo), and the selected
    export set resolved from ``/I``."""
    fixture = tmp_path / "doc.pdf"
    _build_doc(fixture)

    java = _java_read(fixture, "MultiList", "EditCombo")
    py = _py_read(fixture, "MultiList", "EditCombo")
    assert py == java

    # High-value invariants, asserted directly so a regression names itself.
    ml = py["MultiList"]
    assert ml["kind"] == "listbox"
    assert ml["multi"] == "1"
    assert ml["edit"] == "0"  # Edit flag is combo-only
    assert ml["topIndex"] == "1"
    assert ml["value"] == "e3|e1"  # /V keeps insertion order
    assert ml["indices"] == "0|2"  # /I sorted ascending despite /V order
    assert ml["selExport"] == "e1|e3"  # resolved from sorted /I
    assert ml["inOpt"] == "1"  # both values are real /Opt members

    ec = py["EditCombo"]
    assert ec["kind"] == "combo"
    assert ec["multi"] == "0"
    assert ec["edit"] == "1"
    assert ec["topIndex"] == "0"
    assert ec["value"] == "custom-magenta"  # free-typed value verbatim
    assert ec["indices"] == ""  # not in /Opt -> no /I
    assert ec["inOpt"] == "0"  # custom value is not an /Opt member

    assert _qpdf_ok(fixture)


# --------------------------------------------------------------------------- #
# multi-select /V + /I re-selection round trip
# --------------------------------------------------------------------------- #
@requires_oracle
def test_multi_select_reselect_then_read_parity(tmp_path: Path) -> None:
    """Re-selecting two list-box options out of /Opt order round-trips to
    identical ``/V`` (insertion order) and ``/I`` (sorted ascending) under both
    implementations, and the resolved selected-export set follows the sorted
    indices."""
    fixture = tmp_path / "doc.pdf"
    _build_doc(fixture)

    java_out = tmp_path / "java_ml.pdf"
    py_out = tmp_path / "py_ml.pdf"
    # e4 then e2 -> /V = e4|e2, /I sorts to 1,3 -> selExport e2|e4.
    _java_set(fixture, java_out, "MultiList=e4|e2")
    _py_set(fixture, py_out, "MultiList=e4|e2")

    java = _java_read(java_out, "MultiList")
    py = _py_read(py_out, "MultiList")
    assert py == java
    assert py["MultiList"]["value"] == "e4|e2"
    assert py["MultiList"]["indices"] == "1|3"
    assert py["MultiList"]["selExport"] == "e2|e4"
    assert _qpdf_ok(py_out)


# --------------------------------------------------------------------------- #
# editable-combo custom-value round trip
# --------------------------------------------------------------------------- #
@requires_oracle
def test_editable_combo_custom_value_then_read_parity(tmp_path: Path) -> None:
    """Writing a fresh custom (not-in-/Opt) value to the editable combo via
    ``set_value(str)`` round-trips verbatim with ``/I`` cleared under both
    implementations — upstream ``PDChoice.setValue(String)`` performs no /Opt
    membership check and ends with ``setSelectedOptionsIndex(null)``."""
    fixture = tmp_path / "doc.pdf"
    _build_doc(fixture)

    java_out = tmp_path / "java_ec.pdf"
    py_out = tmp_path / "py_ec.pdf"
    _java_set(fixture, java_out, "EditCombo=freshly-typed")
    _py_set(fixture, py_out, "EditCombo=freshly-typed")

    java = _java_read(java_out, "EditCombo")
    py = _py_read(py_out, "EditCombo")
    assert py == java
    assert py["EditCombo"]["value"] == "freshly-typed"
    assert py["EditCombo"]["indices"] == ""
    assert py["EditCombo"]["inOpt"] == "0"
    assert py["EditCombo"]["edit"] == "1"
    assert _qpdf_ok(py_out)
