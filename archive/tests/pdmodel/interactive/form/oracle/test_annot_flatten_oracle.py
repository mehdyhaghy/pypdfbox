"""Live Apache PDFBox differential parity for NON-FORM annotation behaviour
under an AcroForm FLATTEN (wave 1440).

Surface under test: ``PDAcroForm.flatten`` in
``pypdfbox/pdmodel/interactive/form/pd_acro_form.py`` — specifically, what a
form-field flatten does to annotations that are **not** form widgets (a
Highlight markup, a FreeText note).

The high-value contract (established empirically against PDFBox 3.0.7, see the
``AnnotFlattenProbe`` finding below):

    ``acroForm.flatten()`` is **form-field only**. It removes the field's
    Widget annotation from the page and empties ``/Fields``; it does NOT touch
    non-form annotations. A Highlight and a FreeText annotation — each with its
    own ``/AP`` — SURVIVE the flatten intact, still referenced from the page's
    ``/Annots`` and still rendering from their appearance streams.

PDFBox's measured behaviour on the combined fixture (1 Widget + 1 Highlight +
1 FreeText on one page):

    pre-flatten : ACROFORM=1 FIELDS=1  /Annots=3 (Widget, Highlight, FreeText)
    post-flatten: ACROFORM=1 FIELDS=0  /Annots=2 (Highlight, FreeText)

i.e. exactly the one Widget is removed; the two non-form annotations remain.

How the test works
------------------
1. A combined PDF is built ONCE via pypdfbox (``_build_combined``): a page with
   an AcroForm ``/Tx`` text field (value set, so its ``/AP /N`` is generated and
   the value is baked on flatten) plus a Highlight (``/QuadPoints`` + ``/C`` +
   generated ``/AP``) and a FreeText (``/Contents`` + ``/DA`` + generated
   ``/AP``). This single file is the shared INPUT for both engines.
2. The Java ``AnnotFlattenProbe flatten`` calls ``acroForm.flatten()`` and saves;
   pypdfbox's ``acro_form.flatten()`` does the same. Both outputs are read back
   via the probe's ``read`` mode (Java) / a COS walk (pypdfbox).
3. Asserted post-flatten parity:
     * which annotation subtypes survive — the Highlight + FreeText must remain,
       only the Widget is removed, on BOTH engines;
     * the AcroForm-removal boundary (Java keeps an empty ``/AcroForm``; pypdfbox
       drops it — documented wave-1428 divergence; both leave zero fields);
     * the rendered page matches within the render-oracle gate
       (``MAD < 6`` / ``MAXDIFF < 60``) — the form field's value is now baked
       into page content and the non-form annotations still render from ``/AP``.

Decorated ``@requires_oracle`` so it skips without Java + jar. Hand-written
(not ported from upstream JUnit — upstream has no combined form+markup flatten
fixture).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationFreeText,
    PDAnnotationHighlight,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDTextField
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "AnnotFlattenProbe"

_FIELDS: COSName = COSName.get_pdf_name("Fields")
_ANNOTS: COSName = COSName.get_pdf_name("Annots")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")

_GRID = 16
# Standard render-oracle gate (same as the text-markup render oracle). A correct
# result scores MAD ~0 (measured 0.05 / maxdiff 4 in development).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)


# --------------------------------------------------------------- build fixture


def _build_combined(path: Path) -> None:
    """Build a page carrying ONE AcroForm text field (value set) plus TWO
    non-form annotations (a Highlight with /AP, a FreeText with /AP), saved
    once. This is the shared input both engines flatten."""
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 300.0, 400.0))
        doc.add_page(page)
        catalog = doc.get_document_catalog()
        form = PDAcroForm(doc)
        form.set_default_appearance("/Helv 12 Tf 0 0 0 rg")
        catalog.set_acro_form(form)

        # --- AcroForm /Tx text field as a merged widget ---
        field = PDTextField(form)
        field.set_partial_name("TextField")
        fd = field.get_cos_object()
        fd.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
        fd.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
        rect = COSArray()
        for v in (50.0, 340.0, 250.0, 370.0):
            rect.add(COSFloat(v))
        fd.set_item(COSName.get_pdf_name("Rect"), rect)
        fd.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
        field.set_default_appearance("/Helv 12 Tf 0 0 0 rg")
        field.set_value("HELLO-FORM")  # generates /AP /N + bakes on flatten
        form.set_fields([field])

        # --- non-form annotation: Highlight ---
        highlight = PDAnnotationHighlight()
        highlight.set_rectangle(PDRectangle(50, 295, 250, 320))
        highlight.set_quad_points([50, 315, 250, 315, 50, 300, 250, 300])
        highlight.set_color([1.0, 1.0, 0.0])
        highlight.construct_appearances(doc)

        # --- non-form annotation: FreeText ---
        free_text = PDAnnotationFreeText()
        free_text.set_rectangle(PDRectangle(50, 230, 250, 280))
        free_text.set_contents("Free text note")
        free_text.set_default_appearance("/Helv 10 Tf 0 0 1 rg")
        free_text.construct_appearances(doc)

        # The text field's widget is a PDField COS dict (not a PDAnnotation
        # object), so /Annots is assembled directly rather than via
        # PDPage.set_annotations (which only accepts PDAnnotation instances).
        annots = COSArray()
        annots.add(field.get_cos_object())
        annots.add(highlight.get_cos_object())
        annots.add(free_text.get_cos_object())
        page.get_cos_object().set_item(_ANNOTS, annots)

        doc.save(str(path))
    finally:
        doc.close()


# --------------------------------------------------------------- facts model


class _Facts:
    __slots__ = ("acroform", "fields", "pages", "subtypes")

    def __init__(self) -> None:
        self.acroform: bool = False
        self.fields: int = 0
        self.pages: int = 0
        # page index -> {subtype name: count}
        self.subtypes: dict[int, dict[str, int]] = {}

    def page_subtypes(self, page: int) -> dict[str, int]:
        return self.subtypes.get(page, {})


# --------------------------------------------------------------- qpdf


def _qpdf_ok(path: Path) -> bool:
    if _QPDF is None:
        return True
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    # 0 = clean, 3 = warnings only (valid), 2 = errors.
    return proc.returncode in (0, 3)


# --------------------------------------------------------------- Java side


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
            facts.subtypes.setdefault(int(parts[1]), {})
        elif tag == "SUB":
            facts.subtypes.setdefault(int(parts[1]), {})[parts[2]] = int(parts[3])
    return facts


def _java_flatten(src: Path, out: Path) -> None:
    run_probe_text(_PROBE, "flatten", str(src), str(out))


def _java_read(path: Path) -> _Facts:
    return _parse_facts(run_probe_text(_PROBE, "read", str(path)))


# --------------------------------------------------------------- pypdfbox side


def _py_flatten(src: Path, out: Path) -> None:
    doc = PDDocument.load(str(src))
    try:
        form = doc.get_document_catalog().get_acro_form()
        assert form is not None, "fixture should carry an AcroForm"
        form.flatten()
        doc.save(str(out))
    finally:
        doc.close()


def _py_read(path: Path) -> _Facts:
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
            tally: dict[str, int] = {}
            annots = page_dict.get_dictionary_object(_ANNOTS)
            if isinstance(annots, COSArray):
                for i in range(annots.size()):
                    entry = annots.get_object(i)
                    sub = "?"
                    if isinstance(entry, COSDictionary):
                        st = entry.get_dictionary_object(_SUBTYPE)
                        if isinstance(st, COSName):
                            sub = st.name
                    tally[sub] = tally.get(sub, 0) + 1
            facts.subtypes[p] = tally
    finally:
        doc.close()
    return facts


# --------------------------------------------------------------- render grid


def _grid_from_image(img: Image.Image) -> list[int]:
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            total[idx] += pixels[x, y]
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255 for i in range(_GRID * _GRID)
    ]


def _render_grid_java(path: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text(_PROBE, "render", str(path), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _render_grid_py(path: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(path) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


# --------------------------------------------------------------- tests


@requires_oracle
@_requires_qpdf
def test_non_form_annotations_survive_form_flatten(tmp_path: Path) -> None:
    """The HIGH-VALUE contract: ``acroForm.flatten()`` is form-field-only. On
    both PDFBox and pypdfbox, flattening removes exactly the Widget while the
    Highlight and FreeText non-form annotations survive on the page."""
    fixture = tmp_path / "combined.pdf"
    _build_combined(fixture)
    assert _qpdf_ok(fixture), "combined fixture failed qpdf --check"

    # Pre-flatten baseline (from the freshly-built input).
    pre = _py_read(fixture)
    assert pre.acroform is True
    assert pre.fields == 1
    assert pre.page_subtypes(0) == {"Widget": 1, "Highlight": 1, "FreeText": 1}

    java_out = tmp_path / "java_flat.pdf"
    py_out = tmp_path / "py_flat.pdf"
    _java_flatten(fixture, java_out)
    _py_flatten(fixture, py_out)

    assert _qpdf_ok(java_out), "Java flatten output failed qpdf --check"
    assert _qpdf_ok(py_out), "pypdfbox flatten output failed qpdf --check"

    java = _java_read(java_out)
    py = _py_read(py_out)

    # Page count preserved on both routes.
    assert java.pages == py.pages == pre.pages == 1

    # The Widget is gone; the two non-form annotations survive — on BOTH
    # engines, with identical multiplicity.
    expected_surviving = {"Highlight": 1, "FreeText": 1}
    assert java.page_subtypes(0) == expected_surviving, (
        f"PDFBox flatten changed non-form annotations: {java.page_subtypes(0)}"
    )
    assert py.page_subtypes(0) == expected_surviving, (
        f"pypdfbox flatten changed non-form annotations: {py.page_subtypes(0)}"
    )
    # Cross-engine: the surviving annotation sets are identical.
    assert java.page_subtypes(0) == py.page_subtypes(0)

    # The Widget specifically was removed on both routes.
    assert "Widget" not in java.page_subtypes(0)
    assert "Widget" not in py.page_subtypes(0)


@requires_oracle
@_requires_qpdf
def test_flatten_empties_fields_acroform_boundary(tmp_path: Path) -> None:
    """Pin the documented divergence boundary: after a flatten-all the form is
    no longer referenceable on either route — PDFBox keeps an empty
    ``/AcroForm`` (FIELDS=0), pypdfbox drops ``/AcroForm`` outright (wave 1428).
    Either way zero fields remain."""
    fixture = tmp_path / "combined.pdf"
    _build_combined(fixture)

    java_out = tmp_path / "java_flat.pdf"
    py_out = tmp_path / "py_flat.pdf"
    _java_flatten(fixture, java_out)
    _py_flatten(fixture, py_out)

    java = _java_read(java_out)
    py = _py_read(py_out)

    # PDFBox keeps the AcroForm dict with an empty /Fields (documented).
    assert java.acroform is True
    assert java.fields == 0
    # pypdfbox drops the AcroForm entry (documented wave-1428 divergence).
    assert py.acroform is False
    assert py.fields == 0


@requires_oracle
@_requires_qpdf
def test_flattened_page_renders_match_pdfbox(tmp_path: Path) -> None:
    """The visible result of the form flatten matches across engines: the form
    field's value is now baked into page content and the surviving non-form
    annotations still render from their ``/AP``. Compared at the standard
    render-oracle gate (MAD < 6 / MAXDIFF < 60)."""
    fixture = tmp_path / "combined.pdf"
    _build_combined(fixture)

    java_out = tmp_path / "java_flat.pdf"
    py_out = tmp_path / "py_flat.pdf"
    _java_flatten(fixture, java_out)
    _py_flatten(fixture, py_out)

    (jw, jh), java_grid = _render_grid_java(java_out)
    (pw, ph), py_grid = _render_grid_py(py_out)

    # Exact pixel dimensions — a mismatch is a real bug, not anti-aliasing.
    assert (pw, ph) == (jw, jh), (
        f"rendered dimensions diverge: pypdfbox={pw}x{ph} java={jw}x{jh}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"post-flatten render mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — a baked field or surviving annotation diverges "
        "from PDFBox, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"post-flatten render worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@_requires_qpdf
def test_surviving_annotations_keep_appearance_streams(tmp_path: Path) -> None:
    """A surviving non-form annotation keeps its ``/AP`` after the flatten —
    the flatten must not strip the markup/free-text appearance streams (that is
    what lets them still render). Asserted on the pypdfbox output; the
    cross-engine render gate confirms the visible equivalence."""
    fixture = tmp_path / "combined.pdf"
    _build_combined(fixture)
    py_out = tmp_path / "py_flat.pdf"
    _py_flatten(fixture, py_out)

    doc = PDDocument.load(str(py_out))
    try:
        page_dict = doc.get_page(0).get_cos_object()
        annots = page_dict.get_dictionary_object(_ANNOTS)
        assert isinstance(annots, COSArray)
        seen: dict[str, bool] = {}
        for i in range(annots.size()):
            entry = annots.get_object(i)
            assert isinstance(entry, COSDictionary)
            st = entry.get_dictionary_object(_SUBTYPE)
            assert isinstance(st, COSName)
            ap = entry.get_dictionary_object(COSName.get_pdf_name("AP"))
            assert isinstance(ap, COSDictionary), f"{st.name} lost its /AP on flatten"
            normal = ap.get_dictionary_object(COSName.get_pdf_name("N"))
            assert isinstance(normal, COSStream), f"{st.name} lost its /AP /N stream"
            seen[st.name] = True
        assert seen == {"Highlight": True, "FreeText": True}
    finally:
        doc.close()
