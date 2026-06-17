"""Live Apache PDFBox differential parity for TEXT-FIELD appearance-stream
BYTE-LEVEL token payload (``PDTextField.set_value`` → ``/AP /N`` regeneration).

Surface
-------
This complements the structural ``test_text_field_ap_oracle.py`` (wave 1433),
which pins the operator *skeleton* and the *decoded* shown string. Here we pin
the **exact encoded bytes** of the ``Tj`` literal — the payload emitted through
the ``/DA`` font's encoder — plus the resolved ``Tf`` size. A viewer renders
the literal *bytes* against the font's encoding, so the bytes — not just the
round-tripped Unicode — must match upstream for true appearance parity. A
decoded-only comparison would mask a divergence where both sides decode back to
the same string from different bytes.

Strategy (mirrors the sibling test): one AcroForm is built via pypdfbox with
each text field's value already set (so pypdfbox has regenerated the
appearance), saved once. The Java ``TextFieldApTokenProbe`` then re-runs
``setValue`` through upstream PDFBox on the identical field configuration and
saves a parallel file. Both files are read back through the probe's READ mode
and pypdfbox re-tokenises its own file with the same extraction.

Encodable boundary
------------------
The byte-parity values stay inside the font's encodable set — ASCII plus the
``(`` / ``)`` / ``\\`` glyphs that PDF literal-string escaping touches but that
the standard Helvetica encoding still maps to a single byte. A separate test
PINS the one *documented* divergence on this surface: a value carrying a
codepoint absent from the no-``/Encoding`` Standard-14 Helvetica's built-in
encoding (``é`` / eacute) makes upstream PDFBox 3.0.7 raise
``IllegalArgumentException`` from ``PDType1Font.encode`` (via ``getStringWidth``
in ``PlainTextFormatter``), whereas pypdfbox leniently substitutes — the
deferred encode-leniency boundary recorded in ``DEFERRED.md`` and ``CHANGES.md``
(wave 1408 / std-14 metrics). That asymmetry is asserted here as a regression
guard, not flagged as a bug.

Decorated ``@requires_oracle`` so it skips without Java + jar. Hand-written.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import (
    _classpath,
    _ensure_compiled,
    requires_oracle,
    run_probe,
    run_probe_text,
)

_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_RECT: COSName = COSName.get_pdf_name("Rect")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")

_PROBE = "TextFieldApTokenProbe"

# (name, da, value) — single-line, left-aligned, explicit 12pt /Helv. Values
# stay inside the no-/Encoding Helvetica's encodable set so PDFBox composes an
# appearance rather than raising (the é case is exercised separately).
_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("Ascii", "/Helv 12 Tf 0 g", "Hello World"),
    ("Parens", "/Helv 12 Tf 0 g", "Total (net): 100"),
    ("Backslash", "/Helv 12 Tf 0 g", r"a\b\c"),
)


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])


def _build_form(out: Path, fields: tuple[tuple[str, str, str], ...]) -> None:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)

        dr = PDResources()
        dr.put(
            COSName.get_pdf_name("Helv"),
            PDFontFactory.create_default_font(Standard14Fonts.HELVETICA),
        )
        form.set_default_resources(dr)
        form.set_default_appearance("/Helv 12 Tf 0 g")

        py_fields: list[PDTextField] = []
        annots: list[PDAnnotationWidget] = []
        ury = 700.0
        for name, da, _value in fields:
            field = PDTextField(form)
            field.set_partial_name(name)
            field.set_default_appearance(da)
            widget = PDAnnotationWidget()
            wc = widget.get_cos_object()
            wc.set_item(_RECT, _rect(50.0, ury, 350.0, ury + 20.0))
            wc.set_name(_SUBTYPE, "Widget")
            field.set_widgets([widget])
            py_fields.append(field)
            annots.append(widget)
            ury -= 40.0

        form.set_fields(py_fields)
        doc.get_document_catalog().set_acro_form(form)
        page.set_annotations(annots)

        for field, spec in zip(py_fields, fields, strict=True):
            field.set_value(spec[2])

        doc.save(str(out))
    finally:
        doc.close()


class _Tokens:
    def __init__(self, tf_size: float, tj_hex: str) -> None:
        self.tf_size = tf_size
        self.tj_hex = tj_hex


def _py_tokens(doc: PDDocument, name: str) -> _Tokens:
    form = doc.get_document_catalog().get_acro_form()
    field = form.get_field(name)
    assert field is not None, f"field {name!r} not found"
    widget = field.get_widgets()[0]
    ap = widget.get_cos_object().get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary), f"{name}: no /AP dict"
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream), f"{name}: /AP /N not a stream"

    data = n.create_input_stream().read()
    parser = PDFStreamParser.from_bytes(data)
    operands: list[object] = []
    tf_size = 0.0
    have_size = False
    tj_hex_parts: list[str] = []

    token = parser.parse_next_token()
    while token is not None:
        if isinstance(token, Operator):
            op = token.get_name()
            if op == "Tf" and len(operands) >= 2 and not have_size:
                tf_size = float(getattr(operands[-1], "value", 0.0))
                have_size = True
            elif op in ("Tj", "'", '"'):
                if operands and hasattr(operands[-1], "get_bytes"):
                    tj_hex_parts.append(operands[-1].get_bytes().hex())
            elif op == "TJ":
                if operands and isinstance(operands[-1], COSArray):
                    for el in operands[-1]:
                        if hasattr(el, "get_bytes"):
                            tj_hex_parts.append(el.get_bytes().hex())
            operands = []
        else:
            operands.append(token)
        token = parser.parse_next_token()

    return _Tokens(tf_size, "".join(tj_hex_parts))


def _parse_record(line: str) -> tuple[str, _Tokens]:
    parts = (line.split("\t") + ["", "0", "", "0"])[:4]
    name, tf_size, tj_hex, _td_y = parts
    return name, _Tokens(float(tf_size), tj_hex)


def _java_tokens(path: Path, *names: str) -> dict[str, _Tokens]:
    text = run_probe_text(_PROBE, "read", str(path), *names)
    out: dict[str, _Tokens] = {}
    for line in text.splitlines():
        if not line:
            continue
        name, tok = _parse_record(line)
        out[name] = tok
    return out


@pytest.fixture
def py_file(tmp_path: Path) -> Path:
    out = tmp_path / "py_token_fields.pdf"
    _build_form(out, _FIELDS)
    return out


@pytest.fixture
def java_file(tmp_path: Path, py_file: Path) -> Path:
    out = tmp_path / "java_token_fields.pdf"
    pairs = [f"{spec[0]}={spec[2]}" for spec in _FIELDS]
    run_probe(_PROBE, "set", str(py_file), str(out), *pairs)
    return out


@requires_oracle
@pytest.mark.parametrize("name", [spec[0] for spec in _FIELDS])
def test_tj_encoded_bytes_match_pdfbox(
    py_file: Path, java_file: Path, name: str
) -> None:
    """The exact encoded ``Tj`` byte payload + ``Tf`` size match PDFBox.

    The encoder maps each codepoint to a single-byte font code; the emitted
    hex (which is what a viewer renders against the font) must be
    byte-identical, not merely decode-equal.
    """
    java = _java_tokens(java_file, name)[name]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_tokens(doc, name)
    finally:
        doc.close()

    assert py.tf_size == java.tf_size == 12.0
    assert py.tj_hex == java.tj_hex, (
        f"{name}: Tj byte payload diverges\n"
        f"  pypdfbox: {py.tj_hex}\n  PDFBox:   {java.tj_hex}"
    )


@requires_oracle
def test_tj_payload_is_exact_ascii_bytes(py_file: Path) -> None:
    """Spell out the load-bearing byte expectations so a regression names the
    exact value that drifted (the Java side is pinned by the parity test)."""
    doc = PDDocument.load(str(py_file))
    try:
        assert _py_tokens(doc, "Ascii").tj_hex == b"Hello World".hex()
        assert _py_tokens(doc, "Parens").tj_hex == b"Total (net): 100".hex()
        assert _py_tokens(doc, "Backslash").tj_hex == rb"a\b\c".hex()
    finally:
        doc.close()


@requires_oracle
def test_accented_glyph_encodes_via_winansi_in_both_engines(tmp_path: Path) -> None:
    """``café`` (eacute) round-trips through the WinAnsi default font in
    BOTH engines — closed wave 1491.

    The form's ``/Helv`` default font is built by
    ``PDFontFactory.create_default_font``, which now mirrors the upstream
    *direct* ``PDType1Font(FontName)`` constructor and writes an explicit
    ``/Encoding /WinAnsiEncoding`` into the dict (PDType1Font.java line 120).
    WinAnsi maps ``é`` to byte 0xE9, so the appearance generator can encode
    it on both sides — ``café`` -> ``636166e9``.

    Before wave 1491 the font carried NO ``/Encoding`` and pypdfbox's
    ``read_encoding_from_font`` returned WinAnsi *only in memory*; the saved
    dict had no /Encoding, so on reload upstream PDFBox fell back to the
    AFM's AdobeStandardEncoding (no eacute byte) and ``PDType1Font.encode``
    raised ``IllegalArgumentException`` while pypdfbox leniently substituted.
    Writing the explicit /Encoding (as the direct constructor does) closes
    that asymmetry: the accented glyph is now genuinely encodable for both.
    """
    fields = (("Acc", "/Helv 12 Tf 0 g", "café"),)
    py_out = tmp_path / "py_acc.pdf"

    # pypdfbox: set_value composes an /AP /N with WinAnsi-encoded "café".
    _build_form(py_out, fields)
    doc = PDDocument.load(str(py_out))
    try:
        tok = _py_tokens(doc, "Acc")
        assert tok.tj_hex == "café".encode("cp1252").hex()  # 636166e9
    finally:
        doc.close()

    # PDFBox: re-running setValue now SUCCEEDS (WinAnsi has eacute), exits 0,
    # and composes the identical WinAnsi byte sequence.
    _ensure_compiled(_PROBE)
    java_out = tmp_path / "java_acc.pdf"
    result = subprocess.run(
        [
            "java", "-cp", _classpath(), _PROBE, "set",
            str(py_out), str(java_out), "Acc=café",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    java_tok = _java_tokens(java_out, "Acc")["Acc"]
    assert java_tok.tj_hex == "café".encode("cp1252").hex()
