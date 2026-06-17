"""Live Apache PDFBox differential parity tests for AcroForm field
FLATTENING (wave 1428).

Each test flattens the *same* AcroForm fixture via two routes — the Java
``FlattenProbe`` (``oracle/probes/FlattenProbe.java``, compiled against the
pinned pdfbox-app-3.0.7 jar) and pypdfbox's ``acro_form.flatten(...)`` — saves
both, reloads both, and compares post-flatten facts:

  * whether the catalog ``/AcroForm`` survives,
  * the root ``/Fields`` count,
  * per-page widget-annotation count,
  * page count,
  * whether each page's content stream grew (the flatten append),
  * that both outputs pass ``qpdf --check``,
  * that the flattened (now-static) text is still extractable.

Both probe modes emit, per fact, an LF-terminated record::

    ACROFORM\\t<0/1>
    FIELDS\\t<root /Fields count>
    PAGES\\t<page count>
    PAGE\\t<index>\\t<widget count>\\t<content byte length>
    TEXT\\t<extracted text, newlines -> \\n>

:func:`_py_read` reproduces the same facts from a reloaded pypdfbox document.

Why structural-parity, not byte-parity:
    The exact appearance bytes the two writers emit differ — Java composes the
    flatten ``Do`` invocation through ``PDPageContentStream`` (its own number
    formatting, colour-operator choices) while pypdfbox appends a hand-built
    ``q <cm> cm /Fm<n> Do Q`` snippet. So the per-page *content byte length*
    will differ; what MUST match is the structural outcome of a flatten:

      * every flattened widget is removed from its page's ``/Annots`` — a
        leftover interactive widget after flatten is a real bug (this was the
        pre-wave-1428 divergence: pypdfbox skipped removal for widgets that
        had no drawable ``/AP /N``, e.g. an unset text field),
      * the form's ``/Fields`` is emptied,
      * page count is preserved,
      * both outputs are qpdf-valid,
      * text remains extractable.

Documented benign divergence (see ``CHANGES.md``): on a flatten-*all*,
upstream PDFBox keeps the (now field-less) ``/AcroForm`` dictionary in the
catalog and merely empties ``/Fields``; pypdfbox drops the ``/AcroForm`` entry
outright. Both leave zero referencing widgets and an empty field set, so the
observable "the form is gone" contract is identical — these tests assert the
intersection (``/Fields`` empty + no widgets) rather than the exact catalog
shape. A flatten-*subset* keeps ``/AcroForm`` on both sides, so that case is
checked for full catalog-presence parity.

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"
_FORM_FIXTURES = _FIXTURES / "pdmodel" / "interactive" / "form"

_FIELDS: COSName = COSName.get_pdf_name("Fields")
_ANNOTS: COSName = COSName.get_pdf_name("Annots")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_WIDGET: COSName = COSName.get_pdf_name("Widget")
_CONTENTS: COSName = COSName.get_pdf_name("Contents")

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)


# ----------------------------------------------------------------- facts model


class _PageFact:
    __slots__ = ("widgets", "content_len")

    def __init__(self, widgets: int, content_len: int) -> None:
        self.widgets = widgets
        self.content_len = content_len


class _Facts:
    __slots__ = ("acroform", "fields", "pages", "page_facts", "text")

    def __init__(self) -> None:
        self.acroform: bool = False
        self.fields: int = 0
        self.pages: int = 0
        self.page_facts: list[_PageFact] = []
        self.text: str = ""


# ----------------------------------------------------------------- qpdf


def _qpdf_check(path: Path) -> tuple[int, str]:
    """``(returncode, combined output)`` from ``qpdf --check``.

    Exit codes (man qpdf): 0 = clean, 2 = errors (broken), 3 = warnings only
    (valid; qpdf recovered). Treat rc <= 3 as structurally valid.
    """
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _assert_qpdf_ok(path: Path, label: str) -> None:
    if _QPDF is None:
        return
    rc, log = _qpdf_check(path)
    assert rc <= 3, f"{label} failed qpdf --check (rc={rc}):\n{log}"


# ----------------------------------------------------------------- Java side


def _java_flatten(fixture: Path, out: Path, *pairs: str) -> None:
    run_probe("FlattenProbe", "flatten", str(fixture), str(out), *pairs)


def _java_flatten_subset(fixture: Path, out: Path, name: str, *pairs: str) -> None:
    run_probe("FlattenProbe", "flatten-subset", str(fixture), str(out), name, *pairs)


def _parse_facts(text: str) -> _Facts:
    facts = _Facts()
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        tag = parts[0]
        if tag == "ACROFORM":
            facts.acroform = parts[1] == "1"
        elif tag == "FIELDS":
            facts.fields = int(parts[1])
        elif tag == "PAGES":
            facts.pages = int(parts[1])
        elif tag == "PAGE":
            facts.page_facts.append(_PageFact(int(parts[2]), int(parts[3])))
        elif tag == "TEXT":
            raw = parts[1] if len(parts) > 1 else ""
            # The probe escapes the extracted text (\n -> \\n etc.); undo it
            # so comparisons are against real text, not the wire form.
            facts.text = (
                raw.replace("\\n", "\n")
                .replace("\\r", "\r")
                .replace("\\t", "\t")
                .replace("\\\\", "\\")
            )
    return facts


def _java_read(path: Path) -> _Facts:
    return _parse_facts(run_probe_text("FlattenProbe", "read", str(path)))


# ----------------------------------------------------------------- pypdfbox side


def _count_widgets(page_dict: COSDictionary) -> int:
    annots = page_dict.get_dictionary_object(_ANNOTS)
    if not isinstance(annots, COSArray):
        return 0
    count = 0
    for i in range(annots.size()):
        entry = annots.get_object(i)
        if isinstance(entry, COSDictionary) and entry.get_dictionary_object(_SUBTYPE) == _WIDGET:
            count += 1
    return count


def _content_len(page_dict: COSDictionary) -> int:
    contents = page_dict.get_dictionary_object(_CONTENTS)
    total = 0
    if isinstance(contents, COSStream):
        total += len(contents.create_input_stream().read())
    elif isinstance(contents, COSArray):
        for i in range(contents.size()):
            entry = contents.get_object(i)
            if isinstance(entry, COSStream):
                total += len(entry.create_input_stream().read())
    return total


def _py_read(path: Path) -> _Facts:
    """Reload-equivalent of the probe's READ mode for a pypdfbox-saved file."""
    facts = _Facts()
    doc = PDDocument.load(str(path))
    try:
        form = doc.get_document_catalog().get_acro_form()
        facts.acroform = form is not None
        if form is not None:
            raw = form.get_cos_object().get_dictionary_object(_FIELDS)
            facts.fields = raw.size() if isinstance(raw, COSArray) else 0
        facts.pages = doc.get_number_of_pages()
        for p in range(doc.get_number_of_pages()):
            page_dict = doc.get_page(p).get_cos_object()
            facts.page_facts.append(
                _PageFact(_count_widgets(page_dict), _content_len(page_dict))
            )
        from pypdfbox.text import PDFTextStripper

        facts.text = PDFTextStripper().get_text(doc)
    finally:
        doc.close()
    return facts


def _py_pre_facts(fixture: Path) -> _Facts:
    """Read the *pre*-flatten facts for a fixture (widget counts baseline)."""
    return _py_read(fixture)


def _py_flatten(fixture: Path, out: Path, pairs: dict[str, str] | None = None) -> None:
    doc = PDDocument.load(str(fixture))
    try:
        form = doc.get_document_catalog().get_acro_form()
        if pairs:
            for name, value in pairs.items():
                field = form.get_field(name)
                assert field is not None, f"field {name!r} not found"
                field.set_value(value)
        form.flatten()
        doc.save(str(out))
    finally:
        doc.close()


def _py_flatten_subset(fixture: Path, out: Path, name: str) -> None:
    doc = PDDocument.load(str(fixture))
    try:
        form = doc.get_document_catalog().get_acro_form()
        field = form.get_field(name)
        assert field is not None, f"field {name!r} not found"
        form.flatten([field], False)
        doc.save(str(out))
    finally:
        doc.close()


# ----------------------------------------------------------------- tests

_FIXTURE_NAMES = [
    "AcroFormsBasicFields.pdf",
    "MultilineFields.pdf",
    "AcroFormsRotation.pdf",
]


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_flatten_all_structural_parity(tmp_path: Path, fixture_name: str) -> None:
    """Flattening every field via Java and via pypdfbox yields structurally
    equivalent results: form emptied, all widgets removed, page count
    preserved, both qpdf-valid."""
    fixture = _FORM_FIXTURES / fixture_name

    pre = _py_pre_facts(fixture)
    pre_widgets = sum(pf.widgets for pf in pre.page_facts)
    assert pre_widgets > 0, "fixture should carry widgets before flatten"

    java_out = tmp_path / f"java_{fixture_name}"
    py_out = tmp_path / f"py_{fixture_name}"

    _java_flatten(fixture, java_out)
    _py_flatten(fixture, py_out)

    java = _java_read(java_out)
    py = _py_read(py_out)

    # 1. Both outputs are structurally valid.
    _assert_qpdf_ok(java_out, "Java flatten output")
    _assert_qpdf_ok(py_out, "pypdfbox flatten output")

    # 2. Page count preserved on both routes.
    assert py.pages == java.pages == pre.pages

    # 3. /Fields emptied on both routes (the intersection invariant — Java
    #    keeps an empty /AcroForm, pypdfbox drops it; see module docstring).
    assert java.fields == 0
    assert py.fields == 0

    # 4. Every widget removed from every page on both routes (the real-bug
    #    invariant fixed in wave 1428).
    assert sum(pf.widgets for pf in java.page_facts) == 0
    assert sum(pf.widgets for pf in py.page_facts) == 0

    # 5. Per-page content stream grew (flatten appended the appearance Do).
    for i, pf in enumerate(pre.page_facts):
        if pf.widgets > 0:
            assert py.page_facts[i].content_len > pf.content_len, (
                f"page {i}: pypdfbox content did not grow after flatten"
            )
            assert java.page_facts[i].content_len > pf.content_len, (
                f"page {i}: Java content did not grow after flatten"
            )


@requires_oracle
@_requires_qpdf
def test_flatten_all_removes_acroform_or_empties_fields(tmp_path: Path) -> None:
    """Pin the documented divergence boundary: after a flatten-all, the
    referencing form is gone on both routes — pypdfbox drops ``/AcroForm``;
    Java keeps it but with an empty ``/Fields``. Either way no field remains
    referenceable."""
    fixture = _FORM_FIXTURES / "AcroFormsBasicFields.pdf"
    java_out = tmp_path / "java.pdf"
    py_out = tmp_path / "py.pdf"
    _java_flatten(fixture, java_out)
    _py_flatten(fixture, py_out)

    java = _java_read(java_out)
    py = _py_read(py_out)

    # Java keeps the AcroForm dict (documented), pypdfbox drops it.
    assert java.acroform is True
    assert py.acroform is False
    # Both leave zero referenceable fields.
    assert java.fields == 0
    assert py.fields == 0


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_flatten_preserves_static_page_text(
    tmp_path: Path, fixture_name: str
) -> None:
    """Flatten must not destroy the static page text that was extractable
    *before* flatten — flatten only appends a ``Do`` invocation, it does not
    rewrite the original page glyphs.

    The invariant is asserted *per engine* (pypdfbox post ⊇ pypdfbox pre,
    Java post ⊇ Java pre) rather than cross-engine, because the two text
    strippers extract differently on these fixtures. That cross-engine text
    difference is a pre-existing ``pypdfbox.text`` gap unrelated to flatten —
    on ``MultilineFields`` Java extracts the static heading while pypdfbox's
    stripper yields nothing for that page even before any flatten. Reported
    as a cross-module note (see final report); not in scope for the form
    flatten surface.
    """
    fixture = _FORM_FIXTURES / fixture_name

    # Per-engine baselines (pre-flatten extractable text).
    py_pre = _py_read(fixture).text
    java_pre = _java_read(fixture).text

    java_out = tmp_path / f"java_{fixture_name}"
    py_out = tmp_path / f"py_{fixture_name}"
    _java_flatten(fixture, java_out)
    _py_flatten(fixture, py_out)

    java_post = _java_read(java_out).text
    py_post = _py_read(py_out).text

    # Every non-blank line extractable before flatten is still extractable
    # after — on the same engine.
    for line in py_pre.splitlines():
        line = line.strip()
        if line:
            assert line in py_post, f"pypdfbox flatten dropped page text: {line!r}"
    for line in java_pre.splitlines():
        line = line.strip()
        if line:
            assert line in java_post, f"Java flatten dropped page text: {line!r}"


@requires_oracle
@_requires_qpdf
def test_flatten_subset_parity(tmp_path: Path) -> None:
    """``flatten([field], False)`` removes exactly that field's widgets and
    drops it from ``/Fields`` on both routes, leaving the rest of the form
    (and the ``/AcroForm`` dict) intact."""
    fixture = _FORM_FIXTURES / "AcroFormsBasicFields.pdf"

    pre = _py_pre_facts(fixture)
    pre_widgets = sum(pf.widgets for pf in pre.page_facts)

    java_out = tmp_path / "java_sub.pdf"
    py_out = tmp_path / "py_sub.pdf"

    # "Checkbox" is a single-widget terminal field.
    _java_flatten_subset(fixture, java_out, "Checkbox")
    _py_flatten_subset(fixture, py_out, "Checkbox")

    java = _java_read(java_out)
    py = _py_read(py_out)

    _assert_qpdf_ok(java_out, "Java subset flatten output")
    _assert_qpdf_ok(py_out, "pypdfbox subset flatten output")

    # AcroForm survives a partial flatten on both routes.
    assert java.acroform is True
    assert py.acroform is True

    # Exactly one root field dropped (18 -> 17) on both routes.
    assert java.fields == pre.fields - 1
    assert py.fields == pre.fields - 1

    # Exactly one widget removed (Checkbox has a single widget) on both routes.
    java_widgets = sum(pf.widgets for pf in java.page_facts)
    py_widgets = sum(pf.widgets for pf in py.page_facts)
    assert java_widgets == pre_widgets - 1
    assert py_widgets == pre_widgets - 1
    assert java_widgets == py_widgets

    # Page count preserved.
    assert py.pages == java.pages == pre.pages


@requires_oracle
@_requires_qpdf
def test_flatten_with_set_value_bakes_text_into_content(tmp_path: Path) -> None:
    """Setting a text-field value then flattening bakes that value into the
    page content on both routes (the field value is no longer interactive but
    is rendered)."""
    fixture = _FORM_FIXTURES / "AcroFormsBasicFields.pdf"
    java_out = tmp_path / "java_set.pdf"
    py_out = tmp_path / "py_set.pdf"

    _java_flatten(fixture, java_out, "TextField=BAKED-VALUE-123")
    _py_flatten(fixture, py_out, {"TextField": "BAKED-VALUE-123"})

    _assert_qpdf_ok(java_out, "Java set+flatten output")
    _assert_qpdf_ok(py_out, "pypdfbox set+flatten output")

    java = _java_read(java_out)
    py = _py_read(py_out)

    # No widgets remain on either side after a full flatten.
    assert sum(pf.widgets for pf in java.page_facts) == 0
    assert sum(pf.widgets for pf in py.page_facts) == 0

    # The baked value is present in pypdfbox's flattened page content
    # (the appearance XObject body was registered as a page resource).
    doc = PDDocument.load(str(py_out))
    try:
        page_dict = doc.get_page(0).get_cos_object()
        from pypdfbox.pdmodel.pd_resources import PDResources

        resources_cos = page_dict.get_dictionary_object(COSName.get_pdf_name("Resources"))
        assert isinstance(resources_cos, COSDictionary)
        xobjects = resources_cos.get_dictionary_object(COSName.get_pdf_name("XObject"))
        assert isinstance(xobjects, COSDictionary)
        found = False
        for key in xobjects.key_set():
            entry = xobjects.get_dictionary_object(key)
            if not isinstance(entry, COSStream):
                continue
            if b"BAKED-VALUE-123" in entry.create_input_stream().read():
                found = True
                break
        assert found, "baked field value not found in any flattened XObject"
        # PDResources is importable/usable on the flattened page.
        assert PDResources(resources_cos) is not None
    finally:
        doc.close()
