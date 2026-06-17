"""Live Apache PDFBox differential parity tests for EDITABLE COMBO BOX
semantics (wave 1447).

Surface under test (``pypdfbox/pdmodel/interactive/form/``):

  * :class:`PDComboBox` — ``is_edit`` / ``set_edit`` (``/Ff`` Edit bit,
    ``1 << 18``), ``is_do_not_spell_check`` (``/Ff`` DoNotSpellCheck bit).
  * :class:`PDChoice` (via the combo box) — ``set_value(str)`` / ``get_value``
    (``/V``), ``get_options_export_values`` / ``get_options_display_values``
    (the ``/Opt`` export/display halves).

The high-value differential is the *editable combo box*: an editable combo may
have its value set to a **custom string NOT present in /Opt** (a free-typed
value). Upstream ``PDChoice.setValue(String)`` writes ``/V`` unconditionally and
clears ``/I`` — it performs **no** membership check against ``/Opt`` — so:

  * an EDITABLE combo stores a custom value verbatim and resolves it to itself
    (``inOpt=0``);
  * a value that IS an ``/Opt`` export entry resolves to its paired *display*
    label (``inOpt=1``), exactly as ``PDComboBox.constructAppearances`` does;
  * a NON-editable combo *also* accepts a custom string via ``setValue(String)``
    (the membership gate lives only in the ``setValue(List)`` overload). This
    last fact is the one pypdfbox previously diverged on — it raised
    ``ValueError`` for a non-editable combo set to a value outside ``/Opt`` —
    and is closed in wave 1447.

Each test emits canonical, deterministic *facts* about a combo-box field two
ways — via the Java ``EditableComboProbe`` (compiled against the pinned
pdfbox-app-3.0.7 jar) and via pypdfbox's typed field API — and asserts the two
are identical. A plain READ (the get surface) and a ``set_value`` round trip
(custom value + in-``/Opt`` value, editable + non-editable) are all checked.

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit). No upstream fixture carries this
editable export/display combo shape, so the fixtures are built at runtime via
pypdfbox, then loaded by *both* implementations — the build itself is therefore
part of the differential surface. ``/NeedAppearances`` is set on the form so the
facts under test are the pure ``/V`` + ``/Opt`` resolution (the probe reads no
appearance stream), not appearance-generator output.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_choice import PDChoice
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_PROBE = "EditableComboProbe"


# --------------------------------------------------------------------------- #
# Java probe drivers
# --------------------------------------------------------------------------- #
def _java_read(path: Path, name: str) -> dict[str, str]:
    """Run the probe in READ mode; parse the named field's record into a flat
    ``{k: v}`` facts dict (each line is ``<name>\\t<k=v>\\t<k=v>...``)."""
    text = run_probe_text(_PROBE, "read", str(path), name)
    line = next(line for line in text.splitlines() if line.startswith(name + "\t"))
    parts = line.split("\t")
    facts: dict[str, str] = {}
    for col in parts[1:]:
        key, _, value = col.partition("=")
        facts[key] = value
    return facts


def _java_set(fixture: Path, out: Path, *ops: str) -> None:
    """Run the probe in SET mode (load, apply ``name=value`` setValue ops,
    save)."""
    run_probe(_PROBE, "set", str(fixture), str(out), *ops)


# --------------------------------------------------------------------------- #
# pypdfbox fact extraction — mirrors EditableComboProbe.comboFacts
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


def _py_facts(doc: PDDocument, name: str) -> dict[str, str]:
    field = doc.get_document_catalog().get_acro_form().get_field(name)
    assert isinstance(field, PDComboBox), f"field {name!r} is not a combo box"

    edit = field.is_edit()
    spell = field.is_do_not_spell_check()
    value = field.get_value()
    export = field.get_options_export_values()
    display = field.get_options_display_values()

    if not value:
        resolved = ""
        in_opt = False
    else:
        first = value[0]
        index = export.index(first) if first in export else -1
        in_opt = index != -1
        separate = export != display
        resolved = (
            display[index] if in_opt and separate and index < len(display) else first
        )

    return {
        "edit": "1" if edit else "0",
        "spell": "1" if spell else "0",
        "value": "|".join(_esc(v) for v in value),
        "export": "|".join(_esc(v) for v in export),
        "display": "|".join(_esc(v) for v in display),
        "resolved": _esc(resolved),
        "inOpt": "1" if in_opt else "0",
    }


def _py_read(path: Path, name: str) -> dict[str, str]:
    doc = PDDocument.load(str(path))
    try:
        return _py_facts(doc, name)
    finally:
        doc.close()


def _py_set(fixture: Path, out: Path, *ops: str) -> None:
    """Apply the same ``name=value`` setValue ops pypdfbox-side as the Java
    probe's SET dispatch."""
    doc = PDDocument.load(str(fixture))
    try:
        form = doc.get_document_catalog().get_acro_form()
        for op in ops:
            eq = op.find("=")
            name = op[:eq]
            value = op[eq + 1 :]
            field = form.get_field(name)
            assert isinstance(field, PDComboBox)
            field.set_value(value)
        doc.save(str(out))
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# pypdfbox fixture builder (no upstream fixture carries this shape)
# --------------------------------------------------------------------------- #
def _build_combos(path: Path) -> None:
    """An AcroForm with two combo boxes sharing three export/display ``/Opt``
    pairs:

      * ``EditCombo`` — Edit flag set (editable), DoNotSpellCheck set.
      * ``PlainCombo`` — Edit flag clear (non-editable).

    No ``/V`` is pre-set; the SET round trips drive the value writes.
    """
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)
        form.set_need_appearances(True)
        doc.get_document_catalog().set_acro_form(form)

        def _mk(name: str, edit: bool, spell: bool) -> PDComboBox:
            cb = PDComboBox(form)
            cb.set_partial_name(name)
            cb.set_edit(edit)
            cb.set_do_not_spell_check(spell)
            cb.set_options(["e1", "e2", "e3"], ["Disp 1", "Disp 2", "Disp 3"])
            widget = cb.get_widgets()[0]
            widget.set_rectangle(PDRectangle(50, 500, 200, 20))
            widget.set_page(page)
            page.get_annotations().append(widget)
            return cb

        edit_combo = _mk("EditCombo", edit=True, spell=True)
        plain_combo = _mk("PlainCombo", edit=False, spell=False)
        form.set_fields([edit_combo, plain_combo])
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
# READ parity — flags + initial empty value
# --------------------------------------------------------------------------- #
@requires_oracle
def test_combo_flags_read_parity(tmp_path: Path) -> None:
    """The Edit and DoNotSpellCheck ``/Ff`` bits, the (empty) ``/V`` and the
    ``/Opt`` export/display halves pypdfbox reports equal what Apache PDFBox
    reports on the same fixture."""
    fixture = tmp_path / "combos.pdf"
    _build_combos(fixture)

    for name, edit, spell in (("EditCombo", "1", "1"), ("PlainCombo", "0", "0")):
        java = _java_read(fixture, name)
        py = _py_read(fixture, name)
        assert py == java
        assert py["edit"] == edit
        assert py["spell"] == spell
        assert py["value"] == ""
        assert py["export"] == "e1|e2|e3"
        assert py["display"] == "Disp 1|Disp 2|Disp 3"
    assert _qpdf_ok(fixture)


# --------------------------------------------------------------------------- #
# editable combo — custom value not in /Opt
# --------------------------------------------------------------------------- #
@requires_oracle
def test_editable_combo_custom_value_parity(tmp_path: Path) -> None:
    """An editable combo accepts a free-typed value NOT present in ``/Opt``,
    stores it verbatim in ``/V``, and resolves it to itself (``inOpt=0``) —
    identical under both implementations."""
    fixture = tmp_path / "combos.pdf"
    _build_combos(fixture)

    java_out = tmp_path / "java_custom.pdf"
    py_out = tmp_path / "py_custom.pdf"
    _java_set(fixture, java_out, "EditCombo=MyCustom")
    _py_set(fixture, py_out, "EditCombo=MyCustom")

    java = _java_read(java_out, "EditCombo")
    py = _py_read(py_out, "EditCombo")
    assert py == java
    assert py["value"] == "MyCustom"  # stored verbatim, even though not in /Opt
    assert py["resolved"] == "MyCustom"  # a custom value resolves to itself
    assert py["inOpt"] == "0"
    assert py["edit"] == "1"
    assert _qpdf_ok(py_out)


# --------------------------------------------------------------------------- #
# editable combo — value that IS an /Opt export entry
# --------------------------------------------------------------------------- #
@requires_oracle
def test_editable_combo_known_value_parity(tmp_path: Path) -> None:
    """When the value IS an ``/Opt`` export entry, both implementations store
    the export token in ``/V`` and resolve it to the paired *display* label
    (``inOpt=1``) — the export/display resolution that drives the combo's
    appearance."""
    fixture = tmp_path / "combos.pdf"
    _build_combos(fixture)

    java_out = tmp_path / "java_known.pdf"
    py_out = tmp_path / "py_known.pdf"
    _java_set(fixture, java_out, "EditCombo=e2")
    _py_set(fixture, py_out, "EditCombo=e2")

    java = _java_read(java_out, "EditCombo")
    py = _py_read(py_out, "EditCombo")
    assert py == java
    assert py["value"] == "e2"  # export value stored
    assert py["resolved"] == "Disp 2"  # resolves to the paired display label
    assert py["inOpt"] == "1"
    assert _qpdf_ok(py_out)


# --------------------------------------------------------------------------- #
# non-editable combo — also accepts a custom value (no /Opt membership gate)
# --------------------------------------------------------------------------- #
@requires_oracle
def test_non_editable_combo_custom_value_parity(tmp_path: Path) -> None:
    """A NON-editable combo also accepts a custom value via
    ``set_value(str)`` — upstream ``PDChoice.setValue(String)`` writes ``/V``
    unconditionally, with no membership check against ``/Opt``. pypdfbox must
    NOT reject it (the previous ``ValueError`` was a divergence, closed in wave
    1447)."""
    fixture = tmp_path / "combos.pdf"
    _build_combos(fixture)

    java_out = tmp_path / "java_plain.pdf"
    py_out = tmp_path / "py_plain.pdf"
    _java_set(fixture, java_out, "PlainCombo=NotInOpt")
    # The high-value assertion: pypdfbox accepts the custom value rather than
    # raising, matching PDFBox.
    _py_set(fixture, py_out, "PlainCombo=NotInOpt")

    java = _java_read(java_out, "PlainCombo")
    py = _py_read(py_out, "PlainCombo")
    assert py == java
    assert py["value"] == "NotInOpt"
    assert py["resolved"] == "NotInOpt"
    assert py["inOpt"] == "0"
    assert py["edit"] == "0"
    assert _qpdf_ok(py_out)


# --------------------------------------------------------------------------- #
# pypdfbox-direct: set_value(str) never raises for a value outside /Opt
# --------------------------------------------------------------------------- #
@requires_oracle
def test_set_value_string_no_membership_gate(tmp_path: Path) -> None:
    """Direct API check (no save round trip): ``PDChoice.set_value(str)`` must
    not raise for a value outside ``/Opt`` on either an editable or a
    non-editable combo, and must clear any pre-existing ``/I``."""
    fixture = tmp_path / "combos.pdf"
    _build_combos(fixture)

    doc = PDDocument.load(str(fixture))
    try:
        form = doc.get_document_catalog().get_acro_form()
        edit_combo = form.get_field("EditCombo")
        plain_combo = form.get_field("PlainCombo")
        assert isinstance(edit_combo, PDComboBox)
        assert isinstance(plain_combo, PDComboBox)

        edit_combo.set_value("FreeText")
        assert edit_combo.get_value() == ["FreeText"]
        # /I is cleared on the single-value path (mirrors upstream).
        assert isinstance(edit_combo, PDChoice)
        assert edit_combo.get_selected_options_index() == []

        # Non-editable must behave identically — no rejection.
        plain_combo.set_value("AlsoFree")
        assert plain_combo.get_value() == ["AlsoFree"]
    finally:
        doc.close()
