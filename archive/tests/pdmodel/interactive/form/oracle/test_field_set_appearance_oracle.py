"""Live Apache PDFBox differential parity tests for AcroForm field SETTING
+ appearance generation (wave 1413).

Each test sets the *same* field value via two routes — the Java
``FieldSetProbe`` (``oracle/probes/FieldSetProbe.java``, compiled against the
pinned pdfbox-app-3.0.7 jar) and pypdfbox's ``field.set_value(...)`` — saves
both, reloads both, and compares:

  * the stored field value (``getValueAsString`` / ``get_value_as_string``),
  * the presence of a normal appearance (``/AP /N``), and
  * the *operator-token skeleton* of the regenerated appearance content
    stream.

The probe emits, per field, a tab-separated record::

    <fqName>\\t<value>\\t<hasN>\\t<tokenCount>\\t<opSequence>

The pypdfbox side mirrors this exactly via :func:`_py_read_field`, which
walks the reloaded field's widgets and tokenises each ``/AP /N`` stream with
:class:`PDFStreamParser` — the same approach the Java probe takes with
``org.apache.pdfbox.pdfparser.PDFStreamParser``.

Why "skeleton" parity, not byte / token-exact parity:
    Both implementations emit the canonical flat-text frame
    ``BMC q <clip> W n BT … Tf … Td (text) Tj ET Q EMC`` (PDF 32000-1
    §12.7.3.3 / Adobe's ``AppearanceGeneratorHelper``). The exact colour
    operator differs — Java emits ``cs <name> sc`` (explicit DeviceGray
    colour space + ``sc``) where pypdfbox emits the equivalent ``0 g`` — and
    Java's auto line-wrap can split a multi-line value into a different
    number of ``Td (line) Tj`` pairs than pypdfbox's wrap heuristic. Those
    are documented legitimate appearance-formatting differences (see
    ``CHANGES.md``). What MUST match — and what regressed before wave 1413,
    when pypdfbox's ``set_value`` did not regenerate appearances at all — is
    that setting the value (a) stores the identical text and (b) produces a
    non-empty ``/AP /N`` whose content draws that text inside the
    ``BMC … BT … (text) Tj … ET … EMC`` frame.

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.form.pd_terminal_field import PDTerminalField
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"
_FORM_FIXTURES = _FIXTURES / "pdmodel" / "interactive" / "form"

_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_AS: COSName = COSName.get_pdf_name("AS")
_OFF: COSName = COSName.get_pdf_name("Off")

# The canonical flat-text appearance frame both implementations must emit
# (in this relative order, possibly with extra colour ops interleaved). This
# is the structural invariant that distinguishes "appearance regenerated with
# the set text" from "no appearance" / "garbage appearance".
_TEXT_SKELETON: tuple[str, ...] = ("BMC", "BT", "Tj", "ET", "EMC")


def _tokenize(stream: COSStream) -> tuple[int, list[str]]:
    """Return (token-count, operator-name-sequence) for a content stream.

    Mirrors ``FieldSetProbe.tokenize`` — counts every token and records the
    operator names in order.
    """
    data = stream.create_input_stream().read()
    parser = PDFStreamParser.from_bytes(data)
    count = 0
    ops: list[str] = []
    token = parser.parse_next_token()
    while token is not None:
        count += 1
        if isinstance(token, Operator):
            ops.append(token.get_name())
        token = parser.parse_next_token()
    return count, ops


def _pick_state_stream(
    n: COSDictionary, widget_cos: COSDictionary
) -> COSStream | None:
    """Pick the on-state appearance stream from a state subdictionary.

    Mirrors ``FieldSetProbe.pickState``: prefer the entry matching the
    widget's ``/AS``, else the first non-``/Off`` entry, else any entry.
    """
    asv = widget_cos.get_dictionary_object(_AS)
    if isinstance(asv, COSName):
        hit = n.get_dictionary_object(asv)
        if isinstance(hit, COSStream):
            return hit
    for key in n.key_set():
        if key != _OFF:
            entry = n.get_dictionary_object(key)
            if isinstance(entry, COSStream):
                return entry
    for key in n.key_set():
        entry = n.get_dictionary_object(key)
        if isinstance(entry, COSStream):
            return entry
    return None


def _py_read_field(doc: PDDocument, name: str) -> tuple[str, bool, int, list[str]]:
    """Reload-equivalent of the probe's READ mode for one field.

    Returns ``(value, has_normal_appearance, token_count, op_sequence)`` —
    the pypdfbox counterpart to the Java probe's per-field record.
    """
    form = doc.get_document_catalog().get_acro_form()
    field = form.get_field(name)
    assert field is not None, f"field {name!r} not found"
    value = field.get_value_as_string()
    has_n = False
    tok = 0
    ops: list[str] = []
    if isinstance(field, PDTerminalField):
        for widget in field.get_widgets():
            widget_cos = widget.get_cos_object()
            ap = widget_cos.get_dictionary_object(_AP)
            if not isinstance(ap, COSDictionary):
                continue
            n = ap.get_dictionary_object(_N)
            if n is None:
                continue
            has_n = True
            stream: COSStream | None = None
            if isinstance(n, COSStream):
                stream = n
            elif isinstance(n, COSDictionary):
                stream = _pick_state_stream(n, widget_cos)
            if stream is not None:
                count, stream_ops = _tokenize(stream)
                tok += count
                ops.extend(stream_ops)
    return value, has_n, tok, ops


def _java_set(fixture: Path, out: Path, *pairs: str) -> None:
    """Run the probe in SET mode (load fixture, set fields, save to out)."""
    run_probe("FieldSetProbe", "set", str(fixture), str(out), *pairs)


def _java_read(path: Path, *names: str) -> dict[str, tuple[str, bool, int, list[str]]]:
    """Run the probe in READ mode and parse its records into a dict by name."""
    text = run_probe_text("FieldSetProbe", "read", str(path), *names)
    out: dict[str, tuple[str, bool, int, list[str]]] = {}
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        name, value, has_n, count, op_seq = (parts + ["", "", "0", "0", ""])[:5]
        ops = op_seq.split(",") if op_seq else []
        out[name] = (value, has_n == "1", int(count), ops)
    return out


def _py_set(fixture: Path, out: Path, pairs: dict[str, str]) -> None:
    """Set each named field's value via pypdfbox and save to out."""
    doc = PDDocument.load(str(fixture))
    try:
        form = doc.get_document_catalog().get_acro_form()
        for name, value in pairs.items():
            field = form.get_field(name)
            assert field is not None, f"field {name!r} not found"
            field.set_value(value)
        doc.save(str(out))
    finally:
        # try/finally so a Windows file lock is always released before the
        # reload below reopens the same path.
        doc.close()


def _assert_skeleton(ops: list[str]) -> None:
    """Assert ``ops`` contains the canonical text-appearance skeleton in
    order (extra ops between the anchors are allowed)."""
    it = iter(ops)
    for anchor in _TEXT_SKELETON:
        assert anchor in it, f"missing {anchor!r} in appearance op sequence {ops}"


@requires_oracle
@pytest.mark.parametrize(
    ("fixture_name", "field", "value"),
    [
        ("AcroFormsBasicFields.pdf", "TextField", "Hello World"),
        ("AcroFormsBasicFields.pdf", "TextField", "0123456789"),
        ("MultilineFields.pdf", "AlignLeft", "Single short line"),
        ("MultilineFields.pdf", "AlignRight", "Right aligned text"),
    ],
)
def test_text_field_set_value_appearance_parity(
    tmp_path: Path, fixture_name: str, field: str, value: str
) -> None:
    """Setting a text-field value via Java and via pypdfbox yields the same
    stored value and a structurally-equivalent regenerated ``/AP /N``."""
    fixture = _FORM_FIXTURES / fixture_name

    java_out = tmp_path / f"java_{field}.pdf"
    py_out = tmp_path / f"py_{field}.pdf"

    _java_set(fixture, java_out, f"{field}={value}")
    _py_set(fixture, py_out, {field: value})

    # Java reference record (reload via the probe's own READ mode).
    java = _java_read(java_out, field)[field]
    java_value, java_has_n, _java_tok, java_ops = java

    # pypdfbox record (reload + tokenise the same way).
    doc = PDDocument.load(str(py_out))
    try:
        py_value, py_has_n, py_tok, py_ops = _py_read_field(doc, field)
    finally:
        doc.close()

    # 1. Identical stored value.
    assert py_value == java_value == value

    # 2. Both produce a normal appearance.
    assert java_has_n is True
    assert py_has_n is True

    # 3. pypdfbox's appearance is non-empty and draws text.
    assert py_tok > 0
    assert "Tj" in py_ops

    # 4. Structural skeleton parity — both carry the canonical
    #    BMC … BT … Tj … ET … EMC flat-text frame.
    _assert_skeleton(java_ops)
    _assert_skeleton(py_ops)


@requires_oracle
def test_set_value_text_appears_in_appearance_stream(tmp_path: Path) -> None:
    """The literal set text is present in pypdfbox's regenerated appearance
    content (the ``( … ) Tj`` show-text operand), matching the fact that
    Java's appearance shows the same text."""
    fixture = _FORM_FIXTURES / "AcroFormsBasicFields.pdf"
    py_out = tmp_path / "py_text.pdf"
    _py_set(fixture, py_out, {"TextField": "PARITY-CHECK-XYZ"})

    doc = PDDocument.load(str(py_out))
    try:
        form = doc.get_document_catalog().get_acro_form()
        field = form.get_field("TextField")
        widget_cos = field.get_widgets()[0].get_cos_object()
        ap = widget_cos.get_dictionary_object(_AP)
        n = ap.get_dictionary_object(_N)
        body = n.create_input_stream().read()
    finally:
        doc.close()
    assert b"PARITY-CHECK-XYZ" in body


@requires_oracle
def test_combo_box_set_value_parity(tmp_path: Path) -> None:
    """A choice (combo) field stores the same value via both routes; the
    ``getValueAsString`` rendering (Java ``Arrays.toString`` ``[Opt02]``)
    matches pypdfbox exactly."""
    fixture = _FORM_FIXTURES / "AcroFormsBasicFields.pdf"
    java_out = tmp_path / "java_combo.pdf"
    py_out = tmp_path / "py_combo.pdf"

    _java_set(fixture, java_out, "ComboBox=Opt02")
    _py_set(fixture, py_out, {"ComboBox": "Opt02"})

    java = _java_read(java_out, "ComboBox")["ComboBox"]
    java_value, java_has_n, _java_tok, _java_ops = java

    doc = PDDocument.load(str(py_out))
    try:
        py_value, py_has_n, _py_tok, _py_ops = _py_read_field(doc, "ComboBox")
    finally:
        doc.close()

    assert py_value == java_value == "[Opt02]"
    # Both regenerate an appearance for the selected option.
    assert java_has_n is True
    assert py_has_n is True


@requires_oracle
def test_set_value_default_matches_java_regeneration_contract(
    tmp_path: Path,
) -> None:
    """Pin the wave-1413 fix: pypdfbox's *default* ``set_value`` (no explicit
    ``regenerate_appearance``) regenerates the appearance just like Java's
    ``setValue`` → ``applyChange()`` — i.e. ``/AP /N`` is present after a
    bare set, on a fixture whose AcroForm has no ``/NeedAppearances``.
    """
    fixture = _FORM_FIXTURES / "AcroFormsBasicFields.pdf"

    # The fixture's AcroForm carries no /NeedAppearances, so Java's
    # setValue → applyChange() regenerates the appearance; pypdfbox's
    # default set_value must do the same.
    java_out = tmp_path / "java_default.pdf"
    py_out = tmp_path / "py_default.pdf"
    _java_set(fixture, java_out, "TextField=defaulted")
    _py_set(fixture, py_out, {"TextField": "defaulted"})

    java = _java_read(java_out, "TextField")["TextField"]
    doc = PDDocument.load(str(py_out))
    try:
        py = _py_read_field(doc, "TextField")
    finally:
        doc.close()

    # Java has a normal appearance after a bare setValue → pypdfbox must too.
    assert java[1] is True
    assert py[1] is True
