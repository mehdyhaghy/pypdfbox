"""Live Apache PDFBox differential parity tests for the AcroForm field-flag
+ metadata accessor surface (wave 1444).

Earlier form oracle waves covered flatten (1428), choice/radio (1432),
text-field appearance (1433) and the field hierarchy (1437). This wave is the
**field-flag + metadata** matrix: the ``/Ff`` bit accessors on
:class:`PDTextField` (``is_multiline`` / ``is_password`` / ``is_comb`` /
``is_do_not_scroll`` / ``is_do_not_spell_check`` / ``is_file_select``) and on
the :class:`PDField` base (``is_read_only`` / ``is_required`` /
``is_no_export``), plus ``get_max_len`` (``/MaxLen``),
``get_alternate_field_name`` (``/TU``), ``get_mapping_name`` (``/TM``) and
``get_q`` (``/Q``).

The exact ``/Ff`` bit -> predicate mapping is the high-value invariant:
``Multiline`` is bit 13 (``1 << 12``), ``Password`` bit 14 (``1 << 13``),
``FileSelect`` bit 21 (``1 << 20``), ``DoNotSpellCheck`` bit 23 (``1 << 22``),
``DoNotScroll`` bit 24 (``1 << 23``), ``Comb`` bit 25 (``1 << 24``) on a text
field, and ``ReadOnly`` bit 1, ``Required`` bit 2, ``NoExport`` bit 3 on the
base field. Get one bit wrong and a predicate silently flips.

A flat AcroForm with five top-level text fields is built once via pypdfbox and
saved to ``tmp_path``; **both** implementations reload the **same** bytes, so
the build itself is part of the differential surface. Each field carries its
``/Ff`` / ``/MaxLen`` / ``/TU`` / ``/TM`` / ``/Q`` locally (no inheritance) so
the comparison is apples-to-apples regardless of the (separately-tested)
local-vs-inheritable read semantics:

  * ``multiScroll`` — multiline + doNotScroll,
  * ``combField``   — comb + ``/MaxLen 8``,
  * ``pwField``     — password,
  * ``lockReq``     — read-only + required,
  * ``meta``        — ``/TU`` tooltip + ``/TM`` mapping name + ``/Q 2``.

The Java side is :file:`oracle/probes/FieldFlagsProbe.java`, compiled against
the pinned pdfbox-app-3.0.7 jar; it emits the raw ``/Ff`` int plus every
predicate and metadata accessor per field. :func:`_py_facts` reproduces the
identical facts from the reloaded pypdfbox document.

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "FieldFlagsProbe"

# The fields the probe inspects (also the order rows are emitted in).
_NAMES: tuple[str, ...] = (
    "multiScroll",
    "combField",
    "pwField",
    "lockReq",
    "meta",
)


# --------------------------------------------------------------------------- #
# Fixture build — five flat top-level text fields exercising the flag matrix.
# --------------------------------------------------------------------------- #
def _build_flags_form(path: Path) -> None:
    """Build + save the flat flag-matrix AcroForm. Saved once; both
    implementations reload the same bytes."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)

        fields: list[PDTextField] = []

        def _mk(name: str, y: float) -> PDTextField:
            f = PDTextField(form)
            f.set_partial_name(name)
            widget = f.get_widgets()[0]
            widget.set_rectangle(PDRectangle(50, y, 200, 20))
            widget.set_page(page)
            page.get_annotations().append(widget)
            fields.append(f)
            return f

        # multiline + doNotScroll
        multi = _mk("multiScroll", 700)
        multi.set_multiline(True)
        multi.set_do_not_scroll(True)

        # comb + /MaxLen 8
        comb = _mk("combField", 670)
        comb.set_comb(True)
        comb.set_max_len(8)

        # password
        pw = _mk("pwField", 640)
        pw.set_password(True)

        # read-only + required (base /Ff bits)
        lock = _mk("lockReq", 610)
        lock.set_read_only(True)
        lock.set_required(True)

        # /TU tooltip + /TM mapping name + /Q 2 (right-justified)
        meta = _mk("meta", 580)
        meta.set_alternate_field_name("Enter your full legal name")
        meta.set_mapping_name("legal_name")
        meta.set_q(PDTextField.QUADDING_RIGHT)

        form.set_fields(fields)
        doc.save(str(path))
    finally:
        # try/finally so a Windows file lock is released before the reload.
        doc.close()


# --------------------------------------------------------------------------- #
# Probe drivers — parse the canonical lines into per-field fact dicts.
# --------------------------------------------------------------------------- #
def _parse(text: str) -> dict[str, dict[str, str]]:
    facts: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        name = parts[0]
        if len(parts) == 2 and parts[1] == "<missing>":
            facts[name] = {"<missing>": "1"}
            continue
        row: dict[str, str] = {}
        for col in parts[1:]:
            key, _, value = col.partition("=")
            row[key] = value
        facts[name] = row
    return facts


def _java_facts(path: Path) -> dict[str, dict[str, str]]:
    return _parse(run_probe_text(_PROBE, str(path), *_NAMES))


def _esc(value: str | None) -> str:
    """Mirror the probe's escaping / ``none`` sentinel for /TU and /TM."""
    if value is None:
        return "none"
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _b(value: bool) -> str:
    return "1" if value else "0"


def _py_facts(path: Path) -> dict[str, dict[str, str]]:
    """Reproduce the probe's facts from a reloaded pypdfbox document.

    Mirrors :file:`FieldFlagsProbe.java`: the raw ``/Ff`` int via
    ``get_field_flags``; the text-field predicates and base-field predicates
    via the typed ``is_*`` accessors; ``get_max_len`` / ``get_q`` /
    ``get_alternate_field_name`` / ``get_mapping_name`` as the metadata
    accessors."""
    doc = PDDocument.load(str(path))
    try:
        form = doc.get_document_catalog().get_acro_form()
        facts: dict[str, dict[str, str]] = {}
        for name in _NAMES:
            field = form.get_field(name)
            if field is None:
                facts[name] = {"<missing>": "1"}
                continue
            row: dict[str, str] = {"ff": str(field.get_field_flags())}
            if isinstance(field, PDTextField):
                row["multiline"] = _b(field.is_multiline())
                row["password"] = _b(field.is_password())
                row["comb"] = _b(field.is_comb())
                row["doNotScroll"] = _b(field.is_do_not_scroll())
                row["doNotSpellCheck"] = _b(field.is_do_not_spell_check())
                row["fileSelect"] = _b(field.is_file_select())
                row["maxLen"] = str(field.get_max_len())
                row["q"] = str(field.get_q())
            else:
                row["multiline"] = "0"
                row["password"] = "0"
                row["comb"] = "0"
                row["doNotScroll"] = "0"
                row["doNotSpellCheck"] = "0"
                row["fileSelect"] = "0"
                row["maxLen"] = "-1"
                row["q"] = "0"
            row["readOnly"] = _b(field.is_read_only())
            row["required"] = _b(field.is_required())
            row["noExport"] = _b(field.is_no_export())
            row["tu"] = _esc(field.get_alternate_field_name())
            row["tm"] = _esc(field.get_mapping_name())
            facts[name] = row
        return facts
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
@requires_oracle
def test_all_fields_present_and_raw_ff_matches_pdfbox(tmp_path: Path) -> None:
    """Every named field is found by both implementations and the raw /Ff
    integer matches PDFBox."""
    pdf = tmp_path / "flags.pdf"
    _build_flags_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    assert set(py) == set(java) == set(_NAMES)
    for name in _NAMES:
        assert "<missing>" not in py[name], f"{name} missing in pypdfbox"
        assert "<missing>" not in java[name], f"{name} missing in PDFBox"
        assert py[name]["ff"] == java[name]["ff"], f"raw /Ff mismatch for {name}"


@requires_oracle
def test_ff_bit_predicates_match_pdfbox(tmp_path: Path) -> None:
    """Every /Ff bit predicate (text-field + base-field) matches PDFBox per
    field — the bit -> predicate mapping matrix."""
    pdf = tmp_path / "flags.pdf"
    _build_flags_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    predicates = (
        "multiline",
        "password",
        "comb",
        "doNotScroll",
        "doNotSpellCheck",
        "fileSelect",
        "readOnly",
        "required",
        "noExport",
    )
    for name in _NAMES:
        for pred in predicates:
            assert py[name][pred] == java[name][pred], (
                f"{pred} predicate mismatch for {name}: "
                f"py={py[name][pred]} java={java[name][pred]}"
            )


@requires_oracle
def test_ff_bit_predicates_spelled_out(tmp_path: Path) -> None:
    """The exact expected predicate truth-table — guards against a regression
    where two predicates read the same (wrong) bit and still happen to agree
    with PDFBox because PDFBox is wrong the same way (it isn't)."""
    pdf = tmp_path / "flags.pdf"
    _build_flags_form(pdf)

    py = _py_facts(pdf)

    # multiline + doNotScroll only.
    assert (py["multiScroll"]["multiline"], py["multiScroll"]["doNotScroll"]) == (
        "1",
        "1",
    )
    assert py["multiScroll"]["password"] == "0"
    assert py["multiScroll"]["comb"] == "0"
    # comb only (plus MaxLen).
    assert py["combField"]["comb"] == "1"
    assert py["combField"]["multiline"] == "0"
    # password only.
    assert py["pwField"]["password"] == "1"
    assert py["pwField"]["multiline"] == "0"
    # read-only + required (base bits) — none of the text flags.
    assert (py["lockReq"]["readOnly"], py["lockReq"]["required"]) == ("1", "1")
    assert py["lockReq"]["noExport"] == "0"
    assert py["lockReq"]["multiline"] == "0"
    # meta has no /Ff bits set.
    assert py["meta"]["ff"] == "0"


@requires_oracle
def test_max_len_matches_pdfbox(tmp_path: Path) -> None:
    """/MaxLen (get_max_len) matches PDFBox — set on the comb field, absent
    (-> -1) elsewhere."""
    pdf = tmp_path / "flags.pdf"
    _build_flags_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    for name in _NAMES:
        assert py[name]["maxLen"] == java[name]["maxLen"], (
            f"/MaxLen mismatch for {name}"
        )
    assert py["combField"]["maxLen"] == "8"
    assert py["multiScroll"]["maxLen"] == "-1"


@requires_oracle
def test_tu_tm_q_match_pdfbox(tmp_path: Path) -> None:
    """/TU (alternate field name / tooltip), /TM (mapping name) and /Q
    (quadding) all match PDFBox."""
    pdf = tmp_path / "flags.pdf"
    _build_flags_form(pdf)

    java = _java_facts(pdf)
    py = _py_facts(pdf)

    for name in _NAMES:
        assert py[name]["tu"] == java[name]["tu"], f"/TU mismatch for {name}"
        assert py[name]["tm"] == java[name]["tm"], f"/TM mismatch for {name}"
        assert py[name]["q"] == java[name]["q"], f"/Q mismatch for {name}"

    # Spell out the meta field's metadata explicitly.
    assert py["meta"]["tu"] == "Enter your full legal name"
    assert py["meta"]["tm"] == "legal_name"
    assert py["meta"]["q"] == str(PDTextField.QUADDING_RIGHT) == "2"
    # The others carry no /TU / /TM and default /Q 0.
    assert py["multiScroll"]["tu"] == "none"
    assert py["multiScroll"]["tm"] == "none"
    assert py["multiScroll"]["q"] == "0"
