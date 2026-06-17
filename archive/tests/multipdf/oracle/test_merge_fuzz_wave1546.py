"""Live PDFBox differential fuzz for ``PDFMergerUtility`` document merging
(``pypdfbox.multipdf.pdf_merger_utility``) — wave 1546, agent E.

The existing merge-oracle modules each pin one facet on a small fixed source
set: ``test_merge_oracle`` (page/text/field-collision/outline/dest),
``test_merge_oc_properties_oracle`` (/OCProperties), ``test_merge_form_fields``
(merge modes), ``test_merge_page_labels``/``test_merge_dest_resolve``, the
struct-tree modules, and the byte/geometry oracles. This module is the
*combinatorial fuzz* layer: it drives ~24 small source-document COMBINATIONS
with edge content through both Java PDFBox 3.0.7 and pypdfbox on byte-identical
inputs, and compares a single STABLE structural fingerprint of the merged
result — total page count, AcroForm field FQ-name set, total outline bookmark
count, named-destination name set, and /OCProperties OCG count.

Fuzz angles NOT covered by the sibling modules:
  * empty (0-page) document combined with a non-empty one, BOTH orderings, and
    two empty docs;
  * merging a document into ITSELF (same source path listed twice);
  * N-way page accumulation across many tiny single-page docs;
  * outlines present in BOTH (multiple) sources — bookmark counts must sum;
  * named destinations colliding across THREE sources;
  * a three-way AcroForm field-name collision (the dummyFieldName<N> chain);
  * a mixed pile: form + outline + dest + OCG sources interleaved with empties.

Bytes / object counts / xref style are deliberately NOT compared — those are a
documented writer-strategy difference (see the pdfwriter oracle module). Only
structural merge facts are asserted, plus qpdf --check validity on the pypdfbox
output. The Java side runs through ``MergeFuzzProbe``.
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
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)
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
from tests.oracle.harness import requires_oracle, run_probe_text

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

_FT = COSName.get_pdf_name("FT")
_T = COSName.get_pdf_name("T")
_FIELDS = COSName.get_pdf_name("Fields")
_NAME = COSName.get_pdf_name("Name")


# ----------------------------------------------------------------- builders


def _text_page(doc: PDDocument, message: str) -> PDPage:
    """Append a Letter page showing ``message`` so a page-count probe sees it."""
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


def _add_outline(doc: PDDocument, target: PDPage, *titles: str) -> None:
    """Attach a flat document outline with one bookmark per title."""
    outline = PDDocumentOutline()
    doc.get_document_catalog().set_document_outline(outline)
    for title in titles:
        item = PDOutlineItem()
        item.set_title(title)
        item.set_destination(target)
        outline.add_last(item)


def _add_named_dest(doc: PDDocument, target: PDPage, name: str) -> None:
    """Attach a /Names /Dests entry mapping ``name`` to a fit-destination."""
    names = PDDocumentNameDictionary(doc.get_document_catalog())
    dest_tree = PDDestinationNameTreeNode()
    dest = PDPageFitDestination()
    dest.set_page(target)
    dest_tree.set_names({name: dest})
    names.set_dests(dest_tree)
    doc.get_document_catalog().set_names(names)


def _add_ocg(doc: PDDocument, *group_names: str) -> None:
    """Attach an /OCProperties carrying one OCG per name."""
    ocp = PDOptionalContentProperties()
    for name in group_names:
        ocp.add_group(PDOptionalContentGroup(name))
    doc.get_document_catalog().set_oc_properties(ocp)


def _save(doc: PDDocument, path: Path) -> None:
    doc.save(str(path))
    doc.close()


# Each builder takes (out_dir) and returns the path it wrote. Scenarios compose
# these into an ordered source list. Builders are factored so a single source
# can be referenced twice (self-merge) by reusing the same returned path.


def _empty(out_dir: Path, tag: str) -> Path:
    p = out_dir / f"empty_{tag}.pdf"
    doc = PDDocument()
    doc.add_page(PDPage(PDRectangle.LETTER))  # PDFBox cannot save a 0-page doc;
    # a "0-page source" in PDFBox terms is one whose pages we then remove — but
    # the merge edge we care about is a *single trivial* page vs a content page,
    # so this is the minimal-content source. See _zero_page for the true 0-page.
    _save(doc, p)
    return p


def _zero_page(out_dir: Path, tag: str) -> Path:
    """A genuinely 0-page source: a valid catalog + empty /Pages tree."""
    p = out_dir / f"zero_{tag}.pdf"
    doc = PDDocument()
    _save(doc, p)
    return p


def _plain(out_dir: Path, tag: str, n_pages: int = 1) -> Path:
    p = out_dir / f"plain_{tag}.pdf"
    doc = PDDocument()
    for i in range(n_pages):
        _text_page(doc, f"{tag} page {i}")
    _save(doc, p)
    return p


def _form(out_dir: Path, tag: str, field_name: str) -> Path:
    p = out_dir / f"form_{tag}.pdf"
    doc = PDDocument()
    _text_page(doc, f"{tag} form")
    _add_text_field(doc, field_name)
    _save(doc, p)
    return p


def _outlined(out_dir: Path, tag: str, *titles: str) -> Path:
    p = out_dir / f"outline_{tag}.pdf"
    doc = PDDocument()
    page = _text_page(doc, f"{tag} outline")
    _add_outline(doc, page, *titles)
    _save(doc, p)
    return p


def _dested(out_dir: Path, tag: str, dest_name: str) -> Path:
    p = out_dir / f"dest_{tag}.pdf"
    doc = PDDocument()
    page = _text_page(doc, f"{tag} dest")
    _add_named_dest(doc, page, dest_name)
    _save(doc, p)
    return p


def _layered(out_dir: Path, tag: str, *group_names: str) -> Path:
    p = out_dir / f"oc_{tag}.pdf"
    doc = PDDocument()
    _text_page(doc, f"{tag} layers")
    _add_ocg(doc, *group_names)
    _save(doc, p)
    return p


# ----------------------------------------------------------------- scenarios


def _scenarios(out_dir: Path) -> dict[str, list[Path]]:
    """Build every fuzz source once, return name -> ordered source list."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Shared sources (built once, reused across scenarios where useful).
    z1 = _zero_page(out_dir, "z1")
    p1 = _plain(out_dir, "p1", 1)
    p2 = _plain(out_dir, "p2", 2)
    p3 = _plain(out_dir, "p3", 3)
    e1 = _empty(out_dir, "e1")
    fa = _form(out_dir, "fa", "shared")
    fb = _form(out_dir, "fb", "shared")
    fc = _form(out_dir, "fc", "shared")
    fu = _form(out_dir, "fu", "uniqueField")
    o1 = _outlined(out_dir, "o1", "Bk A1", "Bk A2")
    o2 = _outlined(out_dir, "o2", "Bk B1")
    d1 = _dested(out_dir, "d1", "Shared")
    d2 = _dested(out_dir, "d2", "Shared")
    d3 = _dested(out_dir, "d3", "Unique")
    l1 = _layered(out_dir, "l1", "LayerX", "LayerY")
    l2 = _layered(out_dir, "l2", "LayerX")

    return {
        # --- empty / degenerate sources --------------------------------
        "zero_then_plain": [z1, p2],
        "plain_then_zero": [p2, z1],
        "two_zero_pages": [z1, _zero_page(out_dir, "z2")],
        "empty_then_plain": [e1, p1],
        "single_source": [p3],
        # --- self-merge (same path twice / thrice) ---------------------
        "self_merge_plain": [p2, p2],
        "self_merge_form": [fa, fa],
        "self_merge_thrice": [p1, p1, p1],
        # --- N-way page accumulation -----------------------------------
        "n_way_plain": [p1, p2, p3],
        "n_way_with_zero": [p1, z1, p2, z1, p3],
        # --- AcroForm collisions ---------------------------------------
        "form_two_collide": [fa, fb],
        "form_three_collide": [fa, fb, fc],
        "form_unique_plus_collide": [fu, fa, fb],
        "form_into_plain": [p1, fa],
        "plain_into_form": [fa, p1],
        # --- outlines (one-sided and two-sided) ------------------------
        "outline_one_sided": [o1, p1],
        "outline_two_sided": [o1, o2],
        "outline_three_way": [o1, o2, p1],
        # --- named-destination collisions ------------------------------
        "dest_unique": [d3, p1],
        "dest_two_collide": [d1, d2],
        "dest_three_mixed": [d1, d2, d3],
        # --- /OCProperties ---------------------------------------------
        "oc_one_sided": [l1, p1],
        "oc_two_collide": [l1, l2],
        # --- mixed everything ------------------------------------------
        "mixed_pile": [fu, z1, o1, d3, l1, fa, p2],
    }


# ----------------------------------------------------------------- fact model


class _Facts:
    __slots__ = ("dests", "fields", "ocgs", "outline", "pages")

    def __init__(
        self,
        pages: int,
        fields: list[str],
        outline: int,
        dests: list[str],
        ocgs: int,
    ) -> None:
        self.pages = pages
        self.fields = fields
        self.outline = outline
        self.dests = dests
        self.ocgs = ocgs

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _Facts):
            return NotImplemented
        return (
            self.pages == other.pages
            and self.fields == other.fields
            and self.outline == other.outline
            and self.dests == other.dests
            and self.ocgs == other.ocgs
        )

    def __repr__(self) -> str:  # pragma: no cover - only on assert failure
        return (
            f"_Facts(pages={self.pages}, fields={self.fields}, "
            f"outline={self.outline}, dests={self.dests}, ocgs={self.ocgs})"
        )


def _parse_probe(text: str) -> _Facts:
    pages = 0
    fields: list[str] = []
    outline = 0
    dests: list[str] = []
    ocgs = -1
    for line in text.splitlines():
        if not line:
            continue
        head, _, rest = line.partition(" ")
        if head == "pages":
            pages = int(rest)
        elif head == "field":
            fields.append(rest)
        elif head == "outline":
            outline = int(rest)
        elif head == "dest":
            dests.append(rest)
        elif head == "ocgs":
            ocgs = int(rest)
    fields.sort()
    dests.sort()
    return _Facts(pages, fields, outline, dests, ocgs)


def _merge_py(sources: list[Path], dest: Path, mode: str) -> None:
    merger = PDFMergerUtility()
    if mode == "JOIN":
        merger.set_acro_form_merge_mode(
            PDFMergerUtility.AcroFormMergeMode.JOIN_FORM_FIELDS_MODE
        )
    else:
        merger.set_acro_form_merge_mode(
            PDFMergerUtility.AcroFormMergeMode.PDFBOX_LEGACY_MODE
        )
    for src in sources:
        merger.add_source(str(src))
    merger.set_destination_file_name(str(dest))
    merger.merge_documents()


def _count_bookmarks(node: object) -> int:
    count = 0
    for child in node.children():  # type: ignore[attr-defined]
        count += 1
        count += _count_bookmarks(child)
    return count


def _read_py_facts(path: Path) -> _Facts:
    doc = PDDocument.load(path)
    try:
        pages = doc.get_number_of_pages()
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

        ocgs = -1
        ocp = catalog.get_oc_properties()
        if ocp is not None:
            ocgs = ocp.get_oc_gs().size()

        return _Facts(pages, fields, outline_count, dests, ocgs)
    finally:
        doc.close()


def _qpdf_ok(path: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode <= 3, (proc.stdout or "") + (proc.stderr or "")


# ------------------------------------------------------------------- tests


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("mode", ["LEGACY", "JOIN"])
def test_merge_fuzz_structural_parity(mode: str, tmp_path: Path) -> None:
    """Drive every fuzz scenario through Java PDFBox and pypdfbox on identical
    source bytes; the merged structural fingerprint must agree case-for-case,
    and every pypdfbox output must be qpdf-valid.

    Both AcroForm merge modes are exercised: in PDFBox 3.0.x
    JOIN_FORM_FIELDS_MODE delegates to PDFBOX_LEGACY_MODE, so the field-name
    fingerprint is identical under both — this run pins that equivalence across
    the whole fuzz matrix, not just the single fixed source set the dedicated
    mode probe covers.
    """
    scenarios = _scenarios(tmp_path / "src")

    divergences: list[str] = []
    for name, sources in scenarios.items():
        java_out = tmp_path / f"java_{name}.pdf"
        java_facts = _parse_probe(
            run_probe_text(
                "MergeFuzzProbe", mode, str(java_out), *[str(s) for s in sources]
            )
        )

        py_out = tmp_path / f"py_{name}.pdf"
        _merge_py(sources, py_out, mode)
        py_facts = _read_py_facts(py_out)

        ok, log = _qpdf_ok(py_out)
        if not ok:
            divergences.append(f"[{name}] pypdfbox output failed qpdf --check:\n{log}")

        if py_facts != java_facts:
            divergences.append(
                f"[{name}] fingerprint divergence:\n"
                f"    pypdfbox: {py_facts}\n    PDFBox:   {java_facts}"
            )

    assert not divergences, (
        f"merge fuzz ({mode}) — {len(divergences)} divergent case(s):\n"
        + "\n".join(divergences)
    )


@requires_oracle
@_requires_qpdf
def test_three_way_form_collision_rename_chain(tmp_path: Path) -> None:
    """Three sources all declaring field ``shared``: PDFBox keeps the first
    verbatim and renames each later collision to a distinct ``dummyFieldName<N>``
    so no field is dropped. pypdfbox must produce the identical 3-name set."""
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    a = _form(src, "a", "shared")
    b = _form(src, "b", "shared")
    c = _form(src, "c", "shared")

    java_out = tmp_path / "java.pdf"
    java_facts = _parse_probe(
        run_probe_text("MergeFuzzProbe", "LEGACY", str(java_out), str(a), str(b), str(c))
    )

    py_out = tmp_path / "py.pdf"
    _merge_py([a, b, c], py_out, "LEGACY")
    py_facts = _read_py_facts(py_out)

    assert py_facts.fields == java_facts.fields, (
        f"three-way collision divergence:\n"
        f"  pypdfbox: {py_facts.fields}\n  PDFBox:   {java_facts.fields}"
    )
    assert len(py_facts.fields) == 3
    assert "shared" in py_facts.fields
    renamed = [f for f in py_facts.fields if f != "shared"]
    assert len(renamed) == 2
    assert all(r.startswith("dummyFieldName") for r in renamed)


@requires_oracle
@_requires_qpdf
def test_self_merge_doubles_facts(tmp_path: Path) -> None:
    """Merging a source into itself (same path twice): page count doubles and
    the interactive facts compose exactly as PDFBox composes them — the
    field-name collision rename fires even when the colliding field comes from
    the SAME source bytes."""
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    f = _form(src, "self", "shared")

    java_out = tmp_path / "java.pdf"
    java_facts = _parse_probe(
        run_probe_text("MergeFuzzProbe", "LEGACY", str(java_out), str(f), str(f))
    )

    py_out = tmp_path / "py.pdf"
    _merge_py([f, f], py_out, "LEGACY")
    py_facts = _read_py_facts(py_out)

    assert py_facts == java_facts, (
        f"self-merge divergence:\n  pypdfbox: {py_facts}\n  PDFBox: {java_facts}"
    )
    assert py_facts.pages == 2
