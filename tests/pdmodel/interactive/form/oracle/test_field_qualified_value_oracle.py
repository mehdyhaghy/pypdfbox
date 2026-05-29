"""Live Apache PDFBox differential parity tests for the AcroForm field
QUALIFIED-NAME + VALUE/DEFAULT surface (wave 1469).

Earlier form-oracle waves covered the field *listing* (FieldProbe, wave-1431
sorted fqName/type/value/dv), the field *hierarchy + AcroForm attributes*
(FieldTreeProbe, wave 1437: DA/Ff/terminal/CO/DR/Q), and the field *flags*
(FieldFlagsProbe). This wave isolates a distinct facet of ``PDField``: the
NAMING + VALUE-resolution surface, exercised through a genuine field *tree*:

  * a non-terminal parent field ``profile`` carrying ``/FT /Tx`` + ``/V`` +
    ``/DV`` (but no widget of its own),
  * two terminal text-field children ``profile.first`` / ``profile.last``
    that OMIT ``/FT``, ``/V`` and ``/DV`` and must INHERIT field type, value
    and default value from the parent (PDF 32000-1 §12.7.4 inheritable
    attributes — ``getValueAsString`` / ``getDefaultValue`` both walk the
    inheritable chain),
  * a top-level combo-box (choice) field ``country`` carrying its OWN ``/V``
    and ``/DV`` (so its typed ``getValueAsString`` renders as Java
    ``Arrays.toString`` ``"[...]"`` and ``getDefaultValue().toString()`` as a
    ``List.toString`` ``"[...]"``).

The form is built once via pypdfbox and saved to ``tmp_path``; *both*
implementations then load the **same** bytes, so the build itself is part of
the differential surface.

The Java side is :mod:`oracle/probes/FieldQualifiedValueProbe.java`, compiled
against the pinned pdfbox-app-3.0.7 jar and loaded with a *null* fixup
(``getAcroForm(null)``) so PDFBox reports the AcroForm exactly as parsed,
matching pypdfbox's no-fixup-on-load behaviour.

Per-field record (sorted by fully-qualified name)::

    <fqName>\t<partialName>\t<parentFqn>\t<fieldType>\t<valueAsString>\t<defaultValue>

The high-value invariants under test:
  * **fully-qualified name** construction — dotted ``parent.child`` path,
  * **partial name** — the local ``/T``,
  * **parent linkage** — ``getParent().getFullyQualifiedName()`` (``<root>``
    for a top-level field),
  * **inherited field type** — children inherit ``/FT`` from the non-terminal
    parent,
  * **value-as-string** — children INHERIT the parent's ``/V`` (text render);
    the combo renders its own list value as ``Arrays.toString``,
  * **default value** — children INHERIT the parent's ``/DV``; the combo
    renders its own list default as ``List.toString``.

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "FieldQualifiedValueProbe"

_FT: COSName = COSName.get_pdf_name("FT")
_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")
_FONT: COSName = COSName.get_pdf_name("Font")


# --------------------------------------------------------------------------- #
# Fixture build
# --------------------------------------------------------------------------- #
def _helvetica_font() -> COSDictionary:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Type"), "Font")
    d.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    d.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    d.set_name(COSName.get_pdf_name("Encoding"), "WinAnsiEncoding")
    return d


def _build_form(path: Path) -> None:
    """Build + save the nested AcroForm described in the module docstring.

    ``/V`` and ``/DV`` are written straight onto the COS dictionaries (no
    ``set_value`` call) so the build emits no widget appearances — the
    null-fixup Java load and the pypdfbox load see the same bytes."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)

        # /DR with a Helvetica font keeps the saved PDF self-consistent.
        dr = PDResources()
        font_dict = COSDictionary()
        font_dict.set_item(COSName.get_pdf_name("Helv"), _helvetica_font())
        dr.get_cos_object().set_item(_FONT, font_dict)
        form.set_default_resources(dr)
        form.set_default_appearance("/Helv 0 Tf 0 g")

        # Non-terminal parent: carries /FT + /V + /DV for children to inherit.
        parent = PDNonTerminalField(form)
        parent.set_partial_name("profile")
        parent.get_cos_object().set_name(_FT, "Tx")
        parent.get_cos_object().set_string(_V, "shared-value")
        parent.get_cos_object().set_string(_DV, "shared-default")

        # Two terminal children that OMIT /FT, /V, /DV so they must inherit.
        def _mk_child(name: str, y: float) -> PDTextField:
            child = PDTextField(form)
            # PDTextField's constructor seeds /FT /Tx; drop it so the child
            # genuinely inherits /FT from the parent.
            child.get_cos_object().remove_item(_FT)
            child.set_partial_name(name)
            child.set_default_appearance("/Helv 10 Tf 0 g")
            widget = child.get_widgets()[0]
            widget.set_rectangle(PDRectangle(50, y, 200, 20))
            widget.set_page(page)
            page.get_annotations().append(widget)
            return child

        first = _mk_child("first", 700)
        last = _mk_child("last", 670)
        parent.set_children([first, last])

        # Top-level combo-box with its OWN /V + /DV (list/string semantics).
        combo = PDComboBox(form)
        combo.set_partial_name("country")
        combo.set_default_appearance("/Helv 10 Tf 0 g")
        combo.set_options(["us", "ca", "mx"])
        # Write /V and /DV directly so no appearance is generated on build.
        combo.get_cos_object().set_string(_V, "ca")
        combo.get_cos_object().set_string(_DV, "us")
        combo_widget = combo.get_widgets()[0]
        combo_widget.set_rectangle(PDRectangle(50, 740, 200, 20))
        combo_widget.set_page(page)
        page.get_annotations().append(combo_widget)

        form.set_fields([parent, combo])

        doc.save(str(path))
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# Probe drivers
# --------------------------------------------------------------------------- #
class _Facts:
    """fqName -> (partial, parentFqn, fieldType, valueAsString, defaultValue)."""

    def __init__(self) -> None:
        self.fields: dict[str, tuple[str, str, str, str, str]] = {}


def _parse(text: str) -> _Facts:
    facts = _Facts()
    for line in text.splitlines():
        if not line:
            continue
        fqn, partial, parent_fqn, ftype, value, dv = line.split("\t")
        facts.fields[fqn] = (partial, parent_fqn, ftype, value, dv)
    return facts


def _java_facts(path: Path) -> _Facts:
    return _parse(run_probe_text(_PROBE, str(path)))


def _esc(value: str) -> str:
    """Mirror the probe's escaping so strings compare byte-for-byte."""
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _py_default_value(field: object) -> str:
    """Mirror the probe's defaultValue() typed dispatch.

    PDTextField -> getDefaultValue() (str). PDComboBox (PDChoice) ->
    getDefaultValue() (list[str]) rendered like Java List.toString. Other ->
    raw inheritable /DV present/none."""
    if isinstance(field, PDTextField):
        return _esc(field.get_default_value())
    if isinstance(field, PDComboBox):
        values = field.get_default_value()
        return _esc("[" + ", ".join(values) + "]")
    dv = field.get_inheritable_attribute(_DV)  # type: ignore[attr-defined]
    return "present" if dv is not None else "none"


def _py_facts(path: Path) -> _Facts:
    doc = PDDocument.load(str(path))
    try:
        form = doc.get_document_catalog().get_acro_form()
        facts = _Facts()
        for field in form.get_field_tree():
            fqn = field.get_fully_qualified_name() or "<empty>"
            partial = field.get_partial_name()
            partial = _esc(partial) if partial is not None else "<null>"
            parent = field.get_parent()
            if parent is None:
                parent_fqn = "<root>"
            else:
                parent_fqn = parent.get_fully_qualified_name() or "<empty>"
                parent_fqn = _esc(parent_fqn)
            ftype = field.get_field_type() or "?"
            value = _esc(field.get_value_as_string())
            dv = _py_default_value(field)
            facts.fields[fqn] = (partial, parent_fqn, ftype, value, dv)
        return facts
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
@requires_oracle
def test_qualified_names_match_pdfbox(tmp_path: Path) -> None:
    """Fully-qualified names, partial names and parent linkage match PDFBox."""
    pdf = tmp_path / "qualified_value.pdf"
    _build_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    assert set(py.fields) == set(java.fields)
    assert {"profile", "profile.first", "profile.last", "country"} == set(
        py.fields
    )
    for name in java.fields:
        # partial name + parent FQN columns.
        assert py.fields[name][:2] == java.fields[name][:2], name

    # Spell out the naming + linkage contract.
    assert py.fields["profile.first"][0] == "first"
    assert py.fields["profile.first"][1] == "profile"
    assert py.fields["profile"][1] == "<root>"
    assert py.fields["country"][0] == "country"
    assert py.fields["country"][1] == "<root>"


@requires_oracle
def test_inherited_field_type_matches_pdfbox(tmp_path: Path) -> None:
    """Children inherit /FT from the non-terminal parent; combo is /Ch."""
    pdf = tmp_path / "qualified_value.pdf"
    _build_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    for name in java.fields:
        assert py.fields[name][2] == java.fields[name][2], f"/FT for {name}"

    assert py.fields["profile"][2] == "Tx"
    assert py.fields["profile.first"][2] == "Tx"
    assert py.fields["profile.last"][2] == "Tx"
    assert py.fields["country"][2] == "Ch"


@requires_oracle
def test_value_as_string_matches_pdfbox(tmp_path: Path) -> None:
    """getValueAsString matches PDFBox: children INHERIT the parent's /V text;
    the combo renders its own value as Java Arrays.toString."""
    pdf = tmp_path / "qualified_value.pdf"
    _build_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    for name in java.fields:
        assert py.fields[name][3] == java.fields[name][3], f"/V for {name}"

    # The non-terminal parent's getValueAsString is its raw COS value's
    # toString() (upstream PDNonTerminalField.getValueAsString) — i.e. the
    # COSString wrapper render, NOT the decoded text.
    assert py.fields["profile"][3] == "COSString{shared-value}"
    # Text children inherit the parent's /V and decode it (PDTextField path).
    assert py.fields["profile.first"][3] == "shared-value"
    assert py.fields["profile.last"][3] == "shared-value"
    # Choice getValueAsString -> Arrays.toString of the single selected value.
    assert py.fields["country"][3] == "[ca]"


@requires_oracle
def test_default_value_matches_pdfbox(tmp_path: Path) -> None:
    """getDefaultValue matches PDFBox: children INHERIT the parent's /DV; the
    combo renders its own list default as List.toString."""
    pdf = tmp_path / "qualified_value.pdf"
    _build_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    for name in java.fields:
        assert py.fields[name][4] == java.fields[name][4], f"/DV for {name}"

    # Text children inherit the parent's /DV text.
    assert py.fields["profile.first"][4] == "shared-default"
    assert py.fields["profile.last"][4] == "shared-default"
    # The non-terminal parent is not a PDTextField/PDChoice -> raw /DV present.
    assert py.fields["profile"][4] == "present"
    # Choice getDefaultValue -> List.toString of its own single default.
    assert py.fields["country"][4] == "[us]"


@requires_oracle
def test_full_record_matches_pdfbox(tmp_path: Path) -> None:
    """The whole per-field record matches PDFBox byte-for-byte (regression
    pin across naming + type + value + default in one assertion)."""
    pdf = tmp_path / "qualified_value.pdf"
    _build_form(pdf)

    assert _py_facts(pdf).fields == _java_facts(pdf).fields
