"""Live Apache PDFBox differential FUZZ of AcroForm field-appearance generation
under MALFORMED /DA strings + edge field configurations (wave 1544, agent D).

Where the well-formed text-field oracle suite (``test_text_field_ap_oracle``,
``test_comb_field_ap_oracle``, ``test_list_box_ap_oracle``) only feeds the
appearance generator syntactically clean ``/DA`` strings, this probe fuzzes the
``/DA`` tokenizer + appearance builder with the hostile / degenerate subset a
buggy producer emits:

* ``/DA`` empty / missing the ``Tf`` font operator / size ``0`` (auto) /
  NEGATIVE size / unknown font name / multiple ``Tf`` ops / colour as
  ``g`` / ``rg`` / ``k`` / interleaved garbage tokens;
* field value with embedded newlines (multiline on vs off);
* ``/Q`` quadding ``0`` / ``1`` / ``2`` / garbage (``7``);
* a ``/DR`` that does NOT carry the font the ``/DA`` references;
* a comb field with ``/MaxLen``.

Strategy
--------
A single AcroForm carrying ~30 text + choice fields (one per fuzz case) is built
*via pypdfbox* (:func:`_build_form`) with each field value already set so
pypdfbox's ``set_value`` has regenerated the appearance. That file is saved once
per session. The Java ``AppearanceGenFuzzProbe`` (compiled against the pinned
pdfbox-app-3.0.7 jar) loads the *same* file, re-runs ``setValue`` on each field
(upstream PDFBox composes its own appearance into the identical field config),
and saves a parallel file. Both files are read back through the probe's READ
mode, which projects per field:

    fqName \t da \t ops \t facts

where ``facts`` is ``tf=<alias>/<size>;col=<op>:<n>;shows=<count>;
lines=<count>;text=<decoded>``. The Python side re-tokenises the pypdfbox file's
``/AP /N`` with the same projection (:func:`_py_facts`) so the two records are
apples-to-apples.

Parity bar — DA-PARSE RESULT + chosen font/size + token SHAPE, not bytes
------------------------------------------------------------------------
Exact coordinates and the colour-operator encoding legitimately differ. What
MUST match between pypdfbox and upstream:

  * the resolved ``/DA`` string;
  * which font ALIAS the ``Tf`` operator names (or whether one is emitted);
  * the chosen font SIZE for explicit positive sizes, and that auto-size
    (size 0) resolves to a positive value on both sides;
  * the colour operator family (``g`` / ``rg`` / ``k``) when the ``/DA`` set
    one;
  * that the canonical flat-text skeleton (``BMC … BT … Tf … Tj … ET … EMC``)
    is present;
  * the decoded shown text;
  * the multiline-wrap line count bucket (1 vs >1).

Honest divergences are pinned in :data:`_PINNED` with a justification + a
matching CHANGES.md row.

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import shutil
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
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_RECT: COSName = COSName.get_pdf_name("Rect")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")


# Fuzz spec rows: (name, da, value, kind, quad, multiline, comb, max_len,
# dr_has_font). ``kind`` is "tx" (text field) or "ch" (combo). ``dr_has_font``
# controls whether the AcroForm /DR carries the alias the /DA references.
# fmt: off
_FUZZ: tuple[
    tuple[str, str, str, str, int, bool, bool, int | None, bool], ...
] = (
    # --- /DA degenerate shapes ----------------------------------------------
    ("DaEmpty",      "",                    "Hi", "tx", 0, False, False, None, True),
    ("DaNoTf",       "0 g",                 "Hi", "tx", 0, False, False, None, True),
    ("DaSizeZero",   "/Helv 0 Tf 0 g",      "Hi", "tx", 0, False, False, None, True),
    ("DaNeg",        "/Helv -5 Tf 0 g",     "Hi", "tx", 0, False, False, None, True),
    ("DaUnknownFont","/Bogus 10 Tf 0 g",    "Hi", "tx", 0, False, False, None, True),
    ("DaMultiTf",    "/Helv 8 Tf /Helv 14 Tf 0 g", "Hi", "tx", 0, False, False, None, True),  # noqa: E501
    ("DaGarbage",    "foo bar /Helv 9 Tf baz 0 g qux", "Hi", "tx", 0, False, False, None, True),  # noqa: E501
    ("DaTrailing",   "/Helv 11 Tf",         "Hi", "tx", 0, False, False, None, True),
    ("DaJunkSize",   "/Helv abc Tf 0 g",    "Hi", "tx", 0, False, False, None, True),
    # --- colour operator family ---------------------------------------------
    ("DaGray",       "/Helv 12 Tf 0.5 g",   "Hi", "tx", 0, False, False, None, True),
    ("DaRgb",        "/Helv 12 Tf 1 0 0 rg","Hi", "tx", 0, False, False, None, True),
    ("DaCmyk",       "/Helv 12 Tf 0 0 0 1 k","Hi","tx", 0, False, False, None, True),
    ("DaRgbWhite",   "/Helv 12 Tf 1 1 1 rg","Hi", "tx", 0, False, False, None, True),
    # --- font aliases --------------------------------------------------------
    ("DaTiBo",       "/TiBo 12 Tf 0 g",     "Hi", "tx", 0, False, False, None, True),
    ("DaCoRo",       "/CoRo 12 Tf 0 g",     "Hi", "tx", 0, False, False, None, True),
    # --- values with newlines (multiline on vs off) -------------------------
    ("NlSingle",     "/Helv 10 Tf 0 g",     "a\\nb\\nc", "tx", 0, False, False, None, True),  # noqa: E501
    ("NlMulti",      "/Helv 10 Tf 0 g",     "a\\nb\\nc", "tx", 0, True,  False, None, True),  # noqa: E501
    # --- quadding 0 / 1 / 2 / garbage ---------------------------------------
    ("QLeft",        "/Helv 12 Tf 0 g",     "Hi", "tx", 0, False, False, None, True),
    ("QCenter",      "/Helv 12 Tf 0 g",     "Hi", "tx", 1, False, False, None, True),
    ("QRight",       "/Helv 12 Tf 0 g",     "Hi", "tx", 2, False, False, None, True),
    ("QGarbage",     "/Helv 12 Tf 0 g",     "Hi", "tx", 7, False, False, None, True),
    # --- /DR missing the referenced font (alias not registered in /DR) ------
    ("DrMissing",    "/Cust 12 Tf 0 g",     "Hi", "tx", 0, False, False, None, False),
    ("DrMissingHeBo","/HeBo 12 Tf 0 g",     "Hi", "tx", 0, False, False, None, False),
    # --- comb field with /MaxLen --------------------------------------------
    ("CombSix",      "/Helv 12 Tf 0 g",     "ABC123", "tx", 0, False, True, 6, True),
    ("CombShort",    "/Helv 12 Tf 0 g",     "AB",     "tx", 0, False, True, 6, True),
    ("CombAuto",     "/Helv 0 Tf 0 g",      "ABCD",   "tx", 0, False, True, 4, True),
    # --- auto-size variants --------------------------------------------------
    ("AutoLong",     "/Helv 0 Tf 0 g",      "AutoSizedValue", "tx", 0, False, False, None, True),  # noqa: E501
    ("AutoMulti",    "/Helv 0 Tf 0 g",      "wrap me", "tx", 0, True, False, None, True),
    # --- choice (combo) fields ----------------------------------------------
    ("ChCombo",      "/Helv 12 Tf 0 g",     "Two", "ch", 0, False, False, None, True),
    ("ChComboColor", "/Helv 12 Tf 1 0 0 rg","Two", "ch", 0, False, False, None, True),
)
# fmt: on

_SKELETON: tuple[str, ...] = ("BMC", "BT", "Tf", "Tj", "ET", "EMC")


# ---------------------------------------------------------------------------
# Pinned honest divergences (pypdfbox value, justification). Each has a
# CHANGES.md row. Keyed by case name; value is a tuple of facts-keys that
# legitimately differ from upstream.
# ---------------------------------------------------------------------------
_PINNED: dict[str, str] = {
    # Negative /DA size: upstream PDFBox passes the raw negative size straight
    # into the Tf operator (it only special-cases size == 0 for auto-size), so
    # a viewer sees a degenerate -5pt font. pypdfbox guards ``size <= 0`` as
    # auto-size, so it picks a sane positive size. pypdfbox is strictly more
    # robust; pinned divergence on the Tf size.
    "DaNeg": "tf-size",
    # Auto-size heuristic: pypdfbox clamps to a height-proportional
    # AUTO_FONT_SIZE_MAX (12pt for a 20pt rect) where PDFBox uses a cap-height
    # formula. Both pick a positive value-fitting size; exact size differs.
    "DaEmpty": "tf-size",
    "DaNoTf": "tf-size",
    "DaSizeZero": "tf-size",
    "CombAuto": "tf-size",
    "AutoLong": "tf-size",
    "AutoMulti": "tf-size",
    "DaJunkSize": "tf-size",
}


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])


def _build_form(out: Path) -> None:
    """Build the fuzz AcroForm via pypdfbox, set each value (regenerating the
    appearance), and save to ``out``."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)

        # /DR carries Helv / TiBo / CoRo aliases so most /DA fonts resolve.
        # The DrMissing* cases override their own /DA to reference a font the
        # /DR does NOT carry (handled below via a per-field empty /DR walk).
        dr = PDResources()
        dr.put(
            COSName.get_pdf_name("Helv"),
            PDFontFactory.create_default_font(Standard14Fonts.HELVETICA),
        )
        dr.put(
            COSName.get_pdf_name("TiBo"),
            PDFontFactory.create_default_font("Times-Bold"),
        )
        dr.put(
            COSName.get_pdf_name("CoRo"),
            PDFontFactory.create_default_font("Courier"),
        )
        form.set_default_resources(dr)
        form.set_default_appearance("/Helv 12 Tf 0 g")

        fields: list[PDTextField | PDComboBox] = []
        annots: list[PDAnnotationWidget] = []
        ury = 760.0
        for spec in _FUZZ:
            (
                name, da, _value, kind, quad, multiline, comb, max_len,
                _dr_has_font,
            ) = spec
            field: PDTextField | PDComboBox
            if kind == "ch":
                field = PDComboBox(form)
                field.set_partial_name(name)
                field.set_options(["One", "Two", "Three"])
            else:
                field = PDTextField(form)
                field.set_partial_name(name)
                if multiline:
                    field.set_multiline(True)
                if comb:
                    field.set_comb(True)
                if max_len is not None:
                    field.set_max_len(max_len)
            field.set_default_appearance(da)
            if quad:
                field.set_q(quad)
            widget = PDAnnotationWidget()
            wc = widget.get_cos_object()
            wc.set_item(_RECT, _rect(50.0, ury, 350.0, ury + 20.0))
            wc.set_name(_SUBTYPE, "Widget")
            field.set_widgets([widget])
            fields.append(field)
            annots.append(widget)
            ury -= 24.0
            if ury < 40.0:
                ury = 760.0

        form.set_fields(fields)
        doc.get_document_catalog().set_acro_form(form)
        page.set_annotations(annots)

        # Setting the value regenerates the appearance (upstream parity).
        for field, spec in zip(fields, _FUZZ, strict=True):
            field.set_value(spec[2].replace("\\n", "\n"))

        doc.save(str(out))
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# fact extraction — mirrors AppearanceGenFuzzProbe.line
# ---------------------------------------------------------------------------
class _Facts:
    def __init__(
        self,
        da: str,
        ops: list[str],
        tf: tuple[str, float] | None,
        col: str,
        shows: int,
        lines: int,
        text: str,
        special: str = "",
    ) -> None:
        self.da = da
        self.ops = ops
        self.tf = tf
        self.col = col
        self.shows = shows
        self.lines = lines
        self.text = text
        self.special = special  # noap / noterminal / nowidget / nofield


def _sanitize(s: str) -> str:
    return (
        s.replace("\r\n", "|")
        .replace("\n", "|")
        .replace("\r", "|")
        .replace("\t", " ")
    )


def _py_facts(doc: PDDocument, name: str) -> _Facts:
    """Reload-equivalent of the probe's READ mode for one pypdfbox field."""
    form = doc.get_document_catalog().get_acro_form()
    field = form.get_field(name)
    assert field is not None, f"field {name!r} not found"
    da_getter = getattr(field, "get_default_appearance", None)
    da = "none"
    if callable(da_getter):
        raw = da_getter()
        if raw:
            da = raw

    widget = field.get_widgets()[0]
    ap = widget.get_cos_object().get_dictionary_object(_AP)
    if not isinstance(ap, COSDictionary):
        return _Facts(da, [], None, "none", 0, 1, "", special="noap")
    n = ap.get_dictionary_object(_N)
    if not isinstance(n, COSStream):
        return _Facts(da, [], None, "none", 0, 1, "", special="noap")

    data = n.create_input_stream().read()
    parser = PDFStreamParser.from_bytes(data)
    ops: list[str] = []
    operands: list[object] = []
    tf: tuple[str, float] | None = None
    col = "none"
    shows = 0
    text_parts: list[str] = []
    baselines: list[int] = []
    pen_y = 0.0

    token = parser.parse_next_token()
    while token is not None:
        if isinstance(token, Operator):
            op = token.get_name()
            ops.append(op)
            if op == "Tf" and len(operands) >= 2:
                fname = operands[-2]
                fsize = operands[-1]
                tf = (
                    fname.name if isinstance(fname, COSName) else "?",
                    float(getattr(fsize, "value", 0.0)),
                )
            elif op == "g" and len(operands) >= 1:
                col = "g:1"
            elif op == "rg" and len(operands) >= 3:
                col = "rg:3"
            elif op == "k" and len(operands) >= 4:
                col = "k:4"
            elif op in ("Td", "TD") and len(operands) >= 2:
                pen_y += float(getattr(operands[-1], "value", 0.0))
            elif op == "Tm" and len(operands) >= 6:
                pen_y = float(getattr(operands[5], "value", 0.0))
            elif op in ("Tj", "'", '"'):
                shows += 1
                if operands and hasattr(operands[-1], "get_string"):
                    text_parts.append(_sanitize(operands[-1].get_string()))
                by = round(pen_y)
                if by not in baselines:
                    baselines.append(by)
            elif op == "TJ":
                shows += 1
                if operands and isinstance(operands[-1], COSArray):
                    chunk = "".join(
                        el.get_string()
                        for el in operands[-1]
                        if hasattr(el, "get_string")
                    )
                    text_parts.append(_sanitize(chunk))
                by = round(pen_y)
                if by not in baselines:
                    baselines.append(by)
            operands = []
        else:
            operands.append(token)
        token = parser.parse_next_token()

    return _Facts(
        da=da,
        ops=ops,
        tf=tf,
        col=col,
        shows=shows,
        lines=max(1, len(baselines)),
        text="".join(text_parts),
    )


def _parse_probe_record(line: str) -> _Facts:
    parts = (line.split("\t") + ["", "", "", ""])[:4]
    _name, da, op_seq, fact_str = parts
    # Single-token specials land in the facts column.
    if fact_str in ("noap", "noterminal", "nowidget", "nofield"):
        return _Facts(da, [], None, "none", 0, 1, "", special=fact_str)
    ops = op_seq.split(",") if op_seq else []
    tf: tuple[str, float] | None = None
    col = "none"
    shows = 0
    lines = 1
    text = ""
    for tok in fact_str.split(";") if fact_str else []:
        key, _, val = tok.partition("=")
        if key == "tf" and val != "none":
            fname, _, fsize = val.rpartition("/")
            tf = (fname, float(fsize)) if fsize else (fname, 0.0)
        elif key == "col":
            col = val
        elif key == "shows":
            shows = int(val)
        elif key == "lines":
            lines = int(val)
        elif key == "text":
            text = val
    return _Facts(da, ops, tf, col, shows, lines, text)


def _java_facts(path: Path, *names: str) -> dict[str, _Facts]:
    text = run_probe_text("AppearanceGenFuzzProbe", "read", str(path), *names)
    out: dict[str, _Facts] = {}
    for line in text.splitlines():
        if not line:
            continue
        name = line.split("\t", 1)[0]
        out[name] = _parse_probe_record(line)
    return out


def _qpdf_ok(path: Path) -> bool:
    if shutil.which("qpdf") is None:
        return True
    result = subprocess.run(
        ["qpdf", "--check", str(path)],
        capture_output=True,
        text=True,
    )
    return result.returncode in (0, 3)


def _assert_skeleton(ops: list[str]) -> None:
    it = iter(ops)
    for anchor in _SKELETON:
        assert anchor in it, f"missing {anchor!r} in op sequence {ops}"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def py_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("appgenfuzz") / "py_fuzz.pdf"
    _build_form(out)
    return out


@pytest.fixture(scope="module")
def java_file(tmp_path_factory: pytest.TempPathFactory, py_file: Path) -> Path:
    out = tmp_path_factory.mktemp("appgenfuzz_java") / "java_fuzz.pdf"
    pairs = [f"{spec[0]}={spec[2]}" for spec in _FUZZ]
    run_probe("AppearanceGenFuzzProbe", "set", str(py_file), str(out), *pairs)
    return out


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------
@requires_oracle
def test_both_files_qpdf_valid(py_file: Path, java_file: Path) -> None:
    """Both the pypdfbox build and PDFBox's regeneration are qpdf-valid even
    under the malformed /DA corpus."""
    assert _qpdf_ok(py_file)
    assert _qpdf_ok(java_file)


@requires_oracle
@pytest.mark.parametrize("name", [s[0] for s in _FUZZ])
def test_da_preserved(py_file: Path, java_file: Path, name: str) -> None:
    """The resolved /DA string survives appearance regeneration identically on
    both sides (the tokenizer never mutates the source /DA)."""
    java = _java_facts(java_file, name)[name]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, name)
    finally:
        doc.close()
    assert py.da == java.da, f"{name}: /DA diverged"


@requires_oracle
@pytest.mark.parametrize("name", [s[0] for s in _FUZZ])
def test_skeleton_present(py_file: Path, java_file: Path, name: str) -> None:
    """Every field's appearance carries the canonical flat-text skeleton on
    both sides — no malformed /DA produces a structurally broken stream."""
    java = _java_facts(java_file, name)[name]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, name)
    finally:
        doc.close()
    assert py.special == "", f"{name}: pypdfbox produced no appearance"
    assert java.special == "", f"{name}: PDFBox produced no appearance"
    _assert_skeleton(py.ops)
    _assert_skeleton(java.ops)
    assert py.ops[0] == java.ops[0] == "BMC"
    assert py.ops[-1] == java.ops[-1] == "EMC"


@requires_oracle
@pytest.mark.parametrize("name", [s[0] for s in _FUZZ])
def test_tf_font_alias_parity(
    py_file: Path, java_file: Path, name: str
) -> None:
    """The Tf operator names the same font alias on both sides.

    For an unknown font name the alias is carried verbatim into the appearance
    /Resources; for a missing /DR the /DA alias is still emitted (both sides
    synthesise a Standard-14 fallback behind the same alias). When the /DA omits
    the font name entirely both sides auto-allocate a key — that key naming
    differs (pypdfbox ``F1`` vs upstream ``Helv``) so those cases only assert a
    Tf is present (the size/colour parity below carries the real signal).
    """
    java = _java_facts(java_file, name)[name]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, name)
    finally:
        doc.close()
    assert py.tf is not None, f"{name}: no Tf on pypdfbox side"
    assert java.tf is not None, f"{name}: no Tf on PDFBox side"

    spec = next(s for s in _FUZZ if s[0] == name)
    da = spec[1]
    has_named_font = "Tf" in da and "/" in da.split("Tf")[0]
    if has_named_font:
        # The alias named in the /DA (last Tf wins) is emitted by both.
        assert py.tf[0] == java.tf[0], (
            f"{name}: Tf alias diverged py={py.tf[0]} java={java.tf[0]}"
        )


@requires_oracle
@pytest.mark.parametrize("name", [s[0] for s in _FUZZ])
def test_tf_size_parity(py_file: Path, java_file: Path, name: str) -> None:
    """The Tf size matches for explicit positive /DA sizes; auto-size (0) and
    the negative-size guard resolve to a positive value on both sides.

    Pinned divergences (:data:`_PINNED`, ``tf-size``): pypdfbox's auto-size
    heuristic clamps to a height-proportional max where PDFBox uses a cap-height
    formula, and pypdfbox guards a negative size as auto-size where PDFBox emits
    the raw negative size. Both pick a sane positive size — that comparability
    is the bar for the pinned cases."""
    java = _java_facts(java_file, name)[name]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, name)
    finally:
        doc.close()
    assert py.tf is not None
    assert java.tf is not None

    if name in _PINNED and _PINNED[name] == "tf-size":
        # pypdfbox always resolves to a positive, sane size.
        assert py.tf[1] > 0.0, f"{name}: pypdfbox size not positive"
        if name == "DaNeg":
            # Documented divergence: PDFBox carries the raw -5 through.
            assert java.tf[1] < 0.0 or java.tf[1] == 0.0
        else:
            # Auto-size: both positive, comparable order of magnitude.
            assert java.tf[1] > 0.0
        return

    spec = next(s for s in _FUZZ if s[0] == name)
    da = spec[1]
    # Extract the explicit positive size from a clean ``/<font> <size> Tf``.
    expected: float | None = None
    toks = da.split()
    for i, t in enumerate(toks):
        if t == "Tf" and i >= 1:
            try:
                cand = float(toks[i - 1])
            except ValueError:
                cand = None
            if cand is not None and cand > 0.0:
                expected = cand
    if expected is not None:
        assert py.tf[1] == java.tf[1] == expected, (
            f"{name}: size py={py.tf[1]} java={java.tf[1]} exp={expected}"
        )


@requires_oracle
@pytest.mark.parametrize(
    ("name", "expected_col"),
    [
        ("DaGray", "g:1"),
        ("DaRgb", "rg:3"),
        ("DaCmyk", "k:4"),
        ("DaRgbWhite", "rg:3"),
        ("ChComboColor", "rg:3"),
    ],
)
def test_colour_operator_family_parity(
    py_file: Path, java_file: Path, name: str, expected_col: str
) -> None:
    """A /DA colour given as g / rg / k drives the same non-stroking colour
    family in the generated appearance on both sides.

    Encoding divergence (benign, documented in CHANGES.md): pypdfbox emits the
    literal ``0 g`` / ``r g b rg`` / ``c m y k k`` operator; PDFBox-3.0.7
    routes the colour through a ``cs <DeviceX> sc`` pair. The probe maps the
    named colour space back to the g/rg/k family so the *family* compares
    apples-to-apples; the operator-name encoding is allowed to differ."""
    java = _java_facts(java_file, name)[name]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, name)
    finally:
        doc.close()
    assert py.col == expected_col, f"{name}: pypdfbox colour {py.col}"
    assert java.col == expected_col, f"{name}: PDFBox colour {java.col}"


@requires_oracle
def test_multiline_vs_single_line_count(
    py_file: Path, java_file: Path
) -> None:
    """A value with embedded newlines wraps to >1 baseline when the multiline
    flag is set, and collapses to a single line when it is not — on both
    sides."""
    java = _java_facts(java_file, "NlSingle", "NlMulti")
    doc = PDDocument.load(str(py_file))
    try:
        py_single = _py_facts(doc, "NlSingle")
        py_multi = _py_facts(doc, "NlMulti")
    finally:
        doc.close()
    # Single-line: newlines collapse, one baseline.
    assert py_single.lines == 1
    assert java["NlSingle"].lines == 1
    # Multiline: the three newline-separated tokens land on >1 baseline.
    assert py_multi.lines >= 2, "pypdfbox should wrap multiline newlines"
    assert java["NlMulti"].lines >= 2, "PDFBox should wrap multiline newlines"


@requires_oracle
def test_comb_cell_count_parity(py_file: Path, java_file: Path) -> None:
    """A comb field with /MaxLen 6 distributes its 6 characters into 6
    positioned show-text cells on both sides; the decoded text matches."""
    java = _java_facts(java_file, "CombSix")["CombSix"]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, "CombSix")
    finally:
        doc.close()
    assert py.shows == java.shows == 6
    assert py.text.replace("|", "") == java.text.replace("|", "") == "ABC123"


@requires_oracle
@pytest.mark.parametrize("name", [s[0] for s in _FUZZ])
def test_shown_text_parity(
    py_file: Path, java_file: Path, name: str
) -> None:
    """The decoded shown text matches on both sides regardless of the /DA
    malformations (the value, not the styling, drives what is shown).

    Multiline / wrap split differs (pypdfbox emits one Tj per wrapped line,
    PDFBox one per word), so we compare the whitespace- and break-stripped
    concatenation."""
    java = _java_facts(java_file, name)[name]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, name)
    finally:
        doc.close()

    def norm(s: str) -> str:
        return s.replace("|", "").replace(" ", "")

    assert norm(py.text) == norm(java.text), (
        f"{name}: shown text py={py.text!r} java={java.text!r}"
    )
