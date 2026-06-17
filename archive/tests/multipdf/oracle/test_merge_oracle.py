"""Live PDFBox differential parity for ``PDFMergerUtility`` document merging
(``pypdfbox.multipdf.pdf_merger_utility``).

The companion ``test_merge_split_oracle.py`` already pins page count + per-page
media-box geometry on a spread of on-disk fixtures. This module goes deeper into
the *merged interactive structure*: it builds small, fully-controlled source
PDFs through pypdfbox (so the inputs are byte-identical on both sides of the
comparison), merges the same ordered set through Java PDFBox and through
pypdfbox, and asserts the recoverable merged facts agree:

* **total page count** and **per-page extracted text, in order** — a merge that
  drops, duplicates, or reorders a page shows up immediately;
* **merged AcroForm field FQ-name set** — including PDFBox's legacy
  ``dummyFieldName<N>`` rename on a field-name collision (two sources both
  declaring ``sharedField``): the high-value case, since a mis-merge silently
  clobbers or drops a form field;
* **outline bookmark count** and **named-destination name set** — interactive
  navigation structure must survive the merge;
* both outputs pass ``qpdf --check`` (structurally valid).

The Java side runs through ``MergeFactsProbe`` (``PDFMergerUtility``
``.mergeDocuments`` then a reload-and-fingerprint). The pypdfbox side runs the
same merge through ``PDFMergerUtility.merge_documents`` and reads the same facts
back. Object count / xref style are deliberately NOT compared — that is a
documented writer-strategy difference (PDFBox object-stream packing vs pypdfbox
flat bodies; see the pdfwriter oracle module for the rationale).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination_name_tree_node import (  # noqa: E501
    PDDestinationNameTreeNode,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (  # noqa: E501
    PDPageFitDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_document_outline import (  # noqa: E501
    PDDocumentOutline,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (  # noqa: E501
    PDOutlineItem,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

_FT = COSName.get_pdf_name("FT")
_T = COSName.get_pdf_name("T")
_FIELDS = COSName.get_pdf_name("Fields")


# ----------------------------------------------------------------- builders


def _text_page(doc: PDDocument, message: str) -> PDPage:
    """Append a Letter page to ``doc`` showing ``message`` so PDFTextStripper
    recovers it. Uses the standard-14 Helvetica default font (no embedding)."""
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    font = PDFontFactory.create_default_font()
    cs = PDPageContentStream(doc, page)
    cs.begin_text()
    cs.set_font(font, 12)
    cs.new_line_at_offset(72, 700)
    cs.show_text(message)
    cs.end_text()
    cs.close()
    return page


def _add_text_field(doc: PDDocument, field_name: str) -> None:
    """Attach a minimal AcroForm with a single text field named ``field_name``."""
    form = PDAcroForm(doc)
    fields = COSArray()
    field = COSDictionary()
    field.set_item(_FT, COSName.get_pdf_name("Tx"))
    field.set_string(_T, field_name)
    fields.add(field)
    form.get_cos_object().set_item(_FIELDS, fields)
    doc.get_document_catalog().set_acro_form(form)


def _build_source_set(out_dir: Path) -> list[Path]:
    """Build the three controlled source PDFs and return their paths in order:

    * ``a.pdf`` — two plain text pages (page-order probe).
    * ``b.pdf`` — one text page + an AcroForm field ``sharedField``.
    * ``c.pdf`` — one text page + an outline bookmark + a named destination
      ``CharlieDest`` + a *second* AcroForm field also named ``sharedField``
      (forces the legacy collision rename).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    # (a) plain text, two pages.
    a = out_dir / "a.pdf"
    doc = PDDocument()
    _text_page(doc, "Alpha page one")
    _text_page(doc, "Alpha page two")
    doc.save(str(a))
    doc.close()
    paths.append(a)

    # (b) text + AcroForm field.
    b = out_dir / "b.pdf"
    doc = PDDocument()
    _text_page(doc, "Bravo with form")
    _add_text_field(doc, "sharedField")
    doc.save(str(b))
    doc.close()
    paths.append(b)

    # (c) text + outline + named dest + colliding AcroForm field.
    c = out_dir / "c.pdf"
    doc = PDDocument()
    page_c = _text_page(doc, "Charlie with outline")
    outline = PDDocumentOutline()
    doc.get_document_catalog().set_document_outline(outline)
    item = PDOutlineItem()
    item.set_title("Go to Charlie")
    item.set_destination(page_c)
    outline.add_last(item)
    names = PDDocumentNameDictionary(doc.get_document_catalog())
    dest_tree = PDDestinationNameTreeNode()
    dest = PDPageFitDestination()
    dest.set_page(page_c)
    dest_tree.set_names({"CharlieDest": dest})
    names.set_dests(dest_tree)
    doc.get_document_catalog().set_names(names)
    _add_text_field(doc, "sharedField")  # collides with b.pdf's field
    doc.save(str(c))
    doc.close()
    paths.append(c)

    return paths


# ------------------------------------------------------------- fact readers


def _qpdf_check(path: Path) -> tuple[int, str]:
    """``(returncode, combined output)`` from ``qpdf --check``. rc <= 3 is
    structurally valid (3 = warnings only — PDFBox's xref-stream output draws a
    benign rc-3)."""
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


class _MergeFacts:
    """The recoverable merged facts compared across the Java/pypdfbox boundary."""

    __slots__ = ("dests", "fields", "outline", "page_text", "pages")

    def __init__(
        self,
        pages: int,
        page_text: list[str],
        fields: list[str],
        outline: int,
        dests: list[str],
    ) -> None:
        self.pages = pages
        self.page_text = page_text
        self.fields = fields
        self.outline = outline
        self.dests = dests

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _MergeFacts):
            return NotImplemented
        return (
            self.pages == other.pages
            and self.page_text == other.page_text
            and self.fields == other.fields
            and self.outline == other.outline
            and self.dests == other.dests
        )

    def __repr__(self) -> str:  # pragma: no cover - only on assert failure
        return (
            f"_MergeFacts(pages={self.pages}, page_text={self.page_text}, "
            f"fields={self.fields}, outline={self.outline}, dests={self.dests})"
        )


def _parse_probe(text: str) -> _MergeFacts:
    """Parse ``MergeFactsProbe`` stdout into a :class:`_MergeFacts`."""
    pages = 0
    page_text: list[str] = []
    fields: list[str] = []
    outline = 0
    dests: list[str] = []
    for line in text.splitlines():
        if not line:
            continue
        head, _, rest = line.partition(" ")
        if head == "pages":
            pages = int(rest)
        elif head == "page":
            # "page <i> <escapedText>" — split off the index, keep the rest.
            _idx, _, body = rest.partition(" ")
            page_text.append(_unescape(body))
        elif head == "fields":
            pass  # count is implied by the field lines
        elif head == "field":
            fields.append(rest)
        elif head == "outline":
            outline = int(rest)
        elif head == "dests":
            pass
        elif head == "dest":
            dests.append(rest)
    fields.sort()
    dests.sort()
    return _MergeFacts(pages, page_text, fields, outline, dests)


def _unescape(s: str) -> str:
    return (
        s.replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace("\\n", "\n")
        .replace("\\\\", "\\")
    )


def _merge_py(sources: list[Path], dest: Path) -> None:
    merger = PDFMergerUtility()
    for src in sources:
        merger.add_source(str(src))
    merger.set_destination_file_name(str(dest))
    merger.merge_documents()


def _read_py_facts(path: Path) -> _MergeFacts:
    """Reload a pypdfbox-merged document and read the same facts the probe emits.

    Closes the document in ``finally`` so the file handle is released before any
    reopen/overwrite (Windows file-lock safety)."""
    doc = PDDocument.load(path)
    try:
        n = doc.get_number_of_pages()
        stripper = PDFTextStripper()
        page_text: list[str] = []
        for i in range(n):
            stripper.set_start_page(i + 1)
            stripper.set_end_page(i + 1)
            page_text.append(stripper.get_text(doc).strip())

        catalog = doc.get_document_catalog()

        fields: list[str] = []
        form = catalog.get_acro_form()
        if form is not None:
            for field in form.get_field_tree():
                fqn = field.get_fully_qualified_name()
                fields.append("<null>" if fqn is None else fqn)
        fields.sort()

        outline_count = 0
        outline = catalog.get_document_outline()
        if outline is not None:
            outline_count = _count_bookmarks(outline)

        dests: list[str] = []
        names = catalog.get_names()
        if names is not None:
            dest_tree = names.get_dests()
            if dest_tree is not None:
                mapping = dest_tree.get_names()
                if mapping:
                    dests.extend(mapping.keys())
        dests.sort()

        return _MergeFacts(n, page_text, fields, outline_count, dests)
    finally:
        doc.close()


def _count_bookmarks(node: object) -> int:
    """Recursively count every bookmark reachable from ``node.children()``."""
    count = 0
    for child in node.children():  # type: ignore[attr-defined]
        count += 1
        count += _count_bookmarks(child)
    return count


# ------------------------------------------------------------------- tests


@requires_oracle
@_requires_qpdf
def test_merge_facts_match_pdfbox(tmp_path: Path) -> None:
    """Merge the controlled three-PDF source set through Java PDFBox and through
    pypdfbox; every recoverable merged fact must agree, and both outputs must be
    qpdf-valid.

    Source set:
      a.pdf = 2 plain text pages
      b.pdf = text + AcroForm 'sharedField'
      c.pdf = text + outline + named dest 'CharlieDest' + AcroForm 'sharedField'

    High-value invariants exercised here:
      * page-order text (4 pages, fixed order),
      * AcroForm field-name collision → legacy dummyFieldName<N> rename,
      * outline + named destination survive the merge.
    """
    sources = _build_source_set(tmp_path / "src")

    java_out = tmp_path / "java_merged.pdf"
    java_text = run_probe_text(
        "MergeFactsProbe", str(java_out), *[str(s) for s in sources]
    )
    java_facts = _parse_probe(java_text)

    py_out = tmp_path / "py_merged.pdf"
    _merge_py(sources, py_out)
    py_facts = _read_py_facts(py_out)

    # Structural validity on both sides.
    java_rc, java_log = _qpdf_check(java_out)
    py_rc, py_log = _qpdf_check(py_out)
    assert java_rc <= 3, f"Java merge failed qpdf --check (rc={java_rc}):\n{java_log}"
    assert py_rc <= 3, f"pypdfbox merge failed qpdf --check (rc={py_rc}):\n{py_log}"

    # Page count + per-page text, in order.
    assert py_facts.pages == java_facts.pages == 4, (
        f"merged page count: pypdfbox {py_facts.pages} vs PDFBox {java_facts.pages}"
    )
    assert py_facts.page_text == java_facts.page_text, (
        f"page-order text divergence:\n"
        f"  pypdfbox: {py_facts.page_text}\n  PDFBox:   {java_facts.page_text}"
    )

    # AcroForm field set — including the collision rename.
    assert py_facts.fields == java_facts.fields, (
        f"merged AcroForm field divergence:\n"
        f"  pypdfbox: {py_facts.fields}\n  PDFBox:   {java_facts.fields}"
    )

    # Outline bookmark count + named-destination set.
    assert py_facts.outline == java_facts.outline, (
        f"outline count divergence: pypdfbox {py_facts.outline} "
        f"vs PDFBox {java_facts.outline}"
    )
    assert py_facts.dests == java_facts.dests, (
        f"named-destination divergence:\n"
        f"  pypdfbox: {py_facts.dests}\n  PDFBox:   {java_facts.dests}"
    )

    # Whole-record equality (catches anything the targeted asserts miss).
    assert py_facts == java_facts


@requires_oracle
@_requires_qpdf
def test_merge_acroform_collision_dedup_matches_pdfbox(tmp_path: Path) -> None:
    """Two sources both declaring AcroForm field ``sharedField``: PDFBox's
    legacy merge keeps the first verbatim and renames the second to
    ``dummyFieldName<N>``. pypdfbox must produce the identical name set so a
    colliding field is neither dropped nor clobbered.
    """
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)

    a = src / "a.pdf"
    doc = PDDocument()
    _text_page(doc, "page A")
    _add_text_field(doc, "sharedField")
    doc.save(str(a))
    doc.close()

    b = src / "b.pdf"
    doc = PDDocument()
    _text_page(doc, "page B")
    _add_text_field(doc, "sharedField")
    doc.save(str(b))
    doc.close()

    sources = [a, b]

    java_out = tmp_path / "java.pdf"
    java_facts = _parse_probe(
        run_probe_text("MergeFactsProbe", str(java_out), str(a), str(b))
    )

    py_out = tmp_path / "py.pdf"
    _merge_py(sources, py_out)
    py_facts = _read_py_facts(py_out)

    # Exactly two fields, both sides: one kept verbatim, one renamed.
    assert java_facts.fields == py_facts.fields, (
        f"collision field-set divergence:\n"
        f"  pypdfbox: {py_facts.fields}\n  PDFBox:   {java_facts.fields}"
    )
    assert "sharedField" in py_facts.fields
    assert len(py_facts.fields) == 2
    # The non-verbatim field follows PDFBox's dummyFieldName<N> convention.
    renamed = [f for f in py_facts.fields if f != "sharedField"]
    assert len(renamed) == 1
    assert renamed[0].startswith("dummyFieldName")

    py_rc, py_log = _qpdf_check(py_out)
    assert py_rc <= 3, f"pypdfbox collision merge failed qpdf (rc={py_rc}):\n{py_log}"


@requires_oracle
@_requires_qpdf
def test_merge_page_order_preserved_matches_pdfbox(tmp_path: Path) -> None:
    """Page order is load-bearing: merging in a fixed source order must yield
    the concatenated page text in that exact order on both sides. Uses a
    distinctive marker per page so a reorder/drop is unambiguous.
    """
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)

    markers = ["ZULU", "YANKEE", "XRAY", "WHISKEY"]
    sources: list[Path] = []
    for i, marker in enumerate(markers):
        p = src / f"p{i}.pdf"
        doc = PDDocument()
        _text_page(doc, marker)
        doc.save(str(p))
        doc.close()
        sources.append(p)

    java_out = tmp_path / "java.pdf"
    java_facts = _parse_probe(
        run_probe_text("MergeFactsProbe", str(java_out), *[str(s) for s in sources])
    )

    py_out = tmp_path / "py.pdf"
    _merge_py(sources, py_out)
    py_facts = _read_py_facts(py_out)

    assert py_facts.page_text == markers, (
        f"pypdfbox page order wrong: {py_facts.page_text} (expected {markers})"
    )
    assert py_facts.page_text == java_facts.page_text
    assert py_facts.pages == java_facts.pages == len(markers)
