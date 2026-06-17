"""Live Apache PDFBox differential parity tests for the AcroForm field
HIERARCHY + AcroForm-level attribute surface (wave 1437).

This wave targets the *hierarchical* form-field surface that earlier form
oracle waves did not cover — flatten (1428), choice/radio (1432), and
text-field appearances (1433) all operate on flat or single-field forms.
Here the subject is a genuine field *tree*:

  * a non-terminal parent field ``address`` carrying ``/FT /Tx`` + ``/DA`` +
    ``/Ff`` (multiline),
  * two terminal text-field children ``address.street`` / ``address.city``
    that OMIT ``/FT`` / ``/DA`` / ``/Ff`` and must INHERIT them from the
    parent (PDF 32000-1 §12.7.4 inheritable attributes),
  * a top-level terminal field ``fullName`` carrying its own ``/DA``,
  * AcroForm-level ``/NeedAppearances true``, ``/CO`` (calculation order),
  * ``/DR`` (default resources, one ``/Helv`` font), ``/Q`` (form-wide
    quadding), and form-level ``/DA``.

The form is built once via pypdfbox and saved to ``tmp_path``; *both*
implementations then load the **same** bytes, so the build itself is part of
the differential surface.

The Java side is the ``FieldTreeProbe`` (``oracle/probes/FieldTreeProbe.java``,
compiled against the pinned pdfbox-app-3.0.7 jar). It is loaded with a *null*
fixup (``getAcroForm(null)``) so PDFBox reports the AcroForm exactly as parsed
— without its ``AcroFormDefaultFixup`` (which would generate missing widget
appearances, clear ``/NeedAppearances``, and inject a ``ZaDb`` font into
``/DR``). pypdfbox performs no such fixup on load, so the null-fixup form is
the apples-to-apples reference for this surface.

Per-field FIELD records (sorted by fully-qualified name) carry::

    FIELD\t<fqName>\t<fieldType>\t<inheritedDA>\t<inheritedFf>\t<T|N>\t<widgetCount>

plus AcroForm-level lines (``NEEDAPPEARANCES``, ``CO``, ``DR``, ``Q``,
``FORMDA``) and ``LOOKUP`` lines for ``getField(fullyQualifiedName)``
resolution. :func:`_py_probe` reproduces the identical facts from the reloaded
pypdfbox document.

The high-value invariants under test:
  * **fully-qualified name** construction — dotted parent.child path,
  * **inheritance walk** — children inherit ``/FT`` / ``/DA`` / ``/Ff`` from
    the non-terminal parent when their own dictionaries omit them,
  * **terminal vs non-terminal** classification,
  * **field-by-FQN lookup** through the hierarchy (including a miss),
  * AcroForm ``/NeedAppearances`` / ``/CO`` (dotted FQNs!) / ``/DR`` font keys
    / ``/Q`` / form ``/DA``.

Wave-1437 fix pinned here: pypdfbox's ``get_calc_order`` previously wrapped
each ``/CO`` entry in a fresh parent-less field, so the returned fields' FQNs
were the bare partial names (``street``) instead of the dotted path
(``address.street``). It now mirrors upstream — matching each ``/CO`` entry
against the already-parented field tree — so the dotted FQNs match PDFBox.

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "FieldTreeProbe"

_FT: COSName = COSName.get_pdf_name("FT")
_DA: COSName = COSName.get_pdf_name("DA")
_FF: COSName = COSName.get_pdf_name("Ff")
_FONT: COSName = COSName.get_pdf_name("Font")

# The fully-qualified names we ask getField() / get_field() to resolve.
_LOOKUPS: tuple[str, ...] = (
    "address.street",
    "address.city",
    "address",
    "fullName",
    "nonexistent.field",
)


# --------------------------------------------------------------------------- #
# Fixture build — one non-terminal parent + two inheriting children + a
# top-level field, with the full AcroForm attribute set.
# --------------------------------------------------------------------------- #
def _helvetica_font() -> COSDictionary:
    """A minimal but VALID standard-14 Helvetica font dictionary.

    A valid font in ``/DR`` keeps PDFBox's (separately-tested) appearance
    fixup from NPE-ing on an empty font dict; this probe disables the fixup
    anyway, but a real font also keeps the saved PDF self-consistent for any
    downstream reader."""
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Type"), "Font")
    d.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    d.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    d.set_name(COSName.get_pdf_name("Encoding"), "WinAnsiEncoding")
    return d


def _build_hierarchy_form(path: Path) -> None:
    """Build + save the hierarchical AcroForm described in the module docstring.

    Saved once; both implementations reload the same bytes."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)

        # Non-terminal parent: carries /FT + /DA + /Ff for its children to
        # inherit; a non-terminal field has no widget of its own.
        parent = PDNonTerminalField(form)
        parent.set_partial_name("address")
        parent.get_cos_object().set_name(_FT, "Tx")
        parent.get_cos_object().set_string(_DA, "/Helv 12 Tf 0 g")
        parent.get_cos_object().set_int(_FF, PDTextField.FLAG_MULTILINE)

        # Two terminal children that OMIT /FT, /DA, /Ff so they must inherit.
        def _mk_child(name: str, y: float) -> PDTextField:
            child = PDTextField(form)
            # PDTextField's constructor seeds /FT /Tx; drop it so the child
            # genuinely inherits /FT from the parent.
            child.get_cos_object().remove_item(_FT)
            child.set_partial_name(name)
            widget = child.get_widgets()[0]
            widget.set_rectangle(PDRectangle(50, y, 200, 20))
            widget.set_page(page)
            page.get_annotations().append(widget)
            return child

        street = _mk_child("street", 700)
        city = _mk_child("city", 670)
        parent.set_children([street, city])

        # Top-level terminal field with its OWN /DA + no flags.
        top = PDTextField(form)
        top.set_partial_name("fullName")
        top.set_default_appearance("/Helv 10 Tf 0 0 1 rg")
        top_widget = top.get_widgets()[0]
        top_widget.set_rectangle(PDRectangle(50, 740, 200, 20))
        top_widget.set_page(page)
        page.get_annotations().append(top_widget)

        form.set_fields([parent, top])

        # AcroForm-level attributes.
        form.set_need_appearances(True)
        form.set_calc_order([street, city])

        dr = PDResources()
        font_dict = COSDictionary()
        font_dict.set_item(COSName.get_pdf_name("Helv"), _helvetica_font())
        dr.get_cos_object().set_item(_FONT, font_dict)
        form.set_default_resources(dr)
        form.set_default_appearance("/Helv 0 Tf 0 g")
        form.set_q(PDAcroForm.QUADDING_CENTERED)

        doc.save(str(path))
    finally:
        # try/finally so a Windows file lock is released before the reload.
        doc.close()


# --------------------------------------------------------------------------- #
# Probe drivers
# --------------------------------------------------------------------------- #
class _Facts:
    """Parsed probe output: per-field FIELD records + AcroForm-level facts."""

    def __init__(self) -> None:
        # fqName -> (fieldType, inheritedDA, inheritedFf, terminalFlag, widgets)
        self.fields: dict[str, tuple[str, str, int, str, int]] = {}
        self.need_appearances: str = "false"
        self.calc_order: list[str] = []
        self.dr_fonts: list[str] = []
        self.q: int = 0
        self.form_da: str = ""
        self.lookups: dict[str, str] = {}


def _parse(text: str) -> _Facts:
    facts = _Facts()
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        kind = parts[0]
        if kind == "FIELD":
            name, ftype, da, ff, terminal, widgets = parts[1:7]
            facts.fields[name] = (ftype, da, int(ff), terminal, int(widgets))
        elif kind == "NEEDAPPEARANCES":
            facts.need_appearances = parts[1]
        elif kind == "CO":
            facts.calc_order = parts[1].split(",") if parts[1] else []
        elif kind == "DR":
            facts.dr_fonts = parts[1].split(",") if parts[1] else []
        elif kind == "Q":
            facts.q = int(parts[1])
        elif kind == "FORMDA":
            facts.form_da = parts[1]
        elif kind == "LOOKUP":
            facts.lookups[parts[1]] = parts[2]
    return facts


def _java_facts(path: Path) -> _Facts:
    text = run_probe_text(_PROBE, str(path), *_LOOKUPS)
    return _parse(text)


def _esc(value: str) -> str:
    """Mirror the probe's escaping so DA strings compare byte-for-byte."""
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _py_facts(path: Path) -> _Facts:
    """Reproduce the probe's facts from a reloaded pypdfbox document.

    Mirrors ``FieldTreeProbe`` exactly: the inherited ``/DA`` walk uses
    ``get_inheritable_attribute`` (self -> parent -> AcroForm) just like the
    probe's ``inheritedDA``; ``/Ff`` uses the typed ``get_field_flags`` (which
    walks self -> parent for terminals and reads the local value for
    non-terminals — the same as PDFBox's ``getFieldFlags``)."""
    doc = PDDocument.load(str(path))
    try:
        # Mirror the probe's getAcroForm(null): no default fixup (wave 1484
        # made the no-arg form apply AcroFormDefaultFixup like upstream).
        form = doc.get_document_catalog().get_acro_form(None)
        facts = _Facts()

        for field in form.get_field_tree():
            name = field.get_fully_qualified_name() or "<empty>"
            ftype = field.get_field_type() or "?"
            item = field.get_inheritable_attribute(_DA)
            da = _esc(item.get_string()) if isinstance(item, COSString) else "none"
            ff = field.get_field_flags()
            terminal = "T" if field.is_terminal() else "N"
            widgets = len(field.get_widgets())
            facts.fields[name] = (ftype, da, ff, terminal, widgets)

        facts.need_appearances = "true" if form.get_need_appearances() else "false"
        facts.calc_order = [
            f.get_fully_qualified_name() for f in form.get_calc_order()
        ]

        dr = form.get_default_resources()
        if dr is not None:
            fonts = dr.get_cos_object().get_dictionary_object(_FONT)
            if isinstance(fonts, COSDictionary):
                facts.dr_fonts = sorted(k.name for k in fonts.key_set())

        facts.q = form.get_q()
        form_da = form.get_default_appearance()
        facts.form_da = _esc(form_da) if form_da else ""

        for name in _LOOKUPS:
            resolved = form.get_field(name)
            facts.lookups[name] = (
                resolved.get_fully_qualified_name() if resolved is not None else "<null>"
            )
        return facts
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
@requires_oracle
def test_fully_qualified_names_match_pdfbox(tmp_path: Path) -> None:
    """The dotted fully-qualified names of every tree field match PDFBox."""
    pdf = tmp_path / "hierarchy.pdf"
    _build_hierarchy_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    assert set(py.fields) == set(java.fields)
    # The expected dotted paths must be present (guards against a regression
    # where a child's FQN collapses to its bare partial name).
    assert {"address", "address.street", "address.city", "fullName"} == set(
        py.fields
    )


@requires_oracle
def test_inherited_field_type_da_ff_match_pdfbox(tmp_path: Path) -> None:
    """Children inherit /FT, /DA and /Ff from the non-terminal parent — the
    resolved values match PDFBox per field."""
    pdf = tmp_path / "hierarchy.pdf"
    _build_hierarchy_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    for name in java.fields:
        java_type, java_da, java_ff, _jt, _jw = java.fields[name]
        py_type, py_da, py_ff, _pt, _pw = py.fields[name]
        assert py_type == java_type, f"/FT mismatch for {name}"
        assert py_da == java_da, f"/DA mismatch for {name}"
        assert py_ff == java_ff, f"/Ff mismatch for {name}"

    # Spell out the inheritance contract explicitly: the children inherited
    # the parent's Tx / DA / multiline-Ff; the top-level field kept its own.
    assert py.fields["address.street"][:3] == ("Tx", "/Helv 12 Tf 0 g", 4096)
    assert py.fields["address.city"][:3] == ("Tx", "/Helv 12 Tf 0 g", 4096)
    assert py.fields["fullName"][:3] == ("Tx", "/Helv 10 Tf 0 0 1 rg", 0)
    # The non-terminal parent reports its own Tx / DA / Ff.
    assert py.fields["address"][:3] == ("Tx", "/Helv 12 Tf 0 g", 4096)


@requires_oracle
def test_terminal_classification_and_widget_count_match_pdfbox(
    tmp_path: Path,
) -> None:
    """Terminal vs non-terminal classification and per-field widget counts
    match PDFBox."""
    pdf = tmp_path / "hierarchy.pdf"
    _build_hierarchy_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    for name in java.fields:
        _jt, _jda, _jff, java_terminal, java_widgets = java.fields[name]
        _pt, _pda, _pff, py_terminal, py_widgets = py.fields[name]
        assert py_terminal == java_terminal, f"terminal flag mismatch for {name}"
        assert py_widgets == java_widgets, f"widget count mismatch for {name}"

    # The non-terminal parent has no widget; each terminal has exactly one.
    assert py.fields["address"][3] == "N"
    assert py.fields["address"][4] == 0
    assert py.fields["address.street"][3] == "T"
    assert py.fields["address.street"][4] == 1


@requires_oracle
def test_get_field_by_fqn_matches_pdfbox(tmp_path: Path) -> None:
    """getField(fullyQualifiedName) resolves the same field (or miss) through
    the hierarchy as PDFBox."""
    pdf = tmp_path / "hierarchy.pdf"
    _build_hierarchy_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    assert py.lookups == java.lookups
    # Each existing dotted/top-level name resolves to itself; the miss is null.
    assert py.lookups["address.street"] == "address.street"
    assert py.lookups["address"] == "address"
    assert py.lookups["nonexistent.field"] == "<null>"


@requires_oracle
def test_acroform_attributes_match_pdfbox(tmp_path: Path) -> None:
    """AcroForm-level /NeedAppearances, /CO (with dotted FQNs!), /DR font
    keys, /Q and form /DA all match PDFBox."""
    pdf = tmp_path / "hierarchy.pdf"
    _build_hierarchy_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    assert py.need_appearances == java.need_appearances == "true"
    # /CO entries carry the DOTTED fully-qualified names — the wave-1437 fix.
    assert py.calc_order == java.calc_order == ["address.street", "address.city"]
    assert py.dr_fonts == java.dr_fonts == ["Helv"]
    assert py.q == java.q == PDAcroForm.QUADDING_CENTERED
    assert py.form_da == java.form_da == "/Helv 0 Tf 0 g"
