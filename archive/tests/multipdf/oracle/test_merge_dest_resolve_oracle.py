"""Live PDFBox differential parity for ``PDFMergerUtility``'s named-destination
and outline page *re-resolution* after a merge.

``test_merge_oracle.py`` pins the *set of surviving* destination names and the
outline bookmark *count*. It does NOT verify that those destinations still point
at the correct page once the merge has concatenated the page trees and shifted
every source page to a higher index. This module fills that gap: it resolves
each merged named destination and each merged outline item back to a 0-based
page INDEX and compares against Apache PDFBox.

A merge that cloned a destination's inner ``/Pg`` reference without routing it
through the clone identity table would land the destination on the wrong page
(or on nothing). ``MergeDestResolveProbe`` runs PDFBox's
``PDFMergerUtility.mergeDocuments`` then resolves
``PDPageDestination.retrievePageNumber`` / page-identity scan; the pypdfbox side
runs the same merge and resolves through ``retrieve_page_number``. Both merged
outputs must also pass ``qpdf --check``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary
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
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from tests.oracle.harness import requires_oracle, run_probe_text

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)


# ----------------------------------------------------------------- builders


def _text_page(doc: PDDocument, message: str) -> PDPage:
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


def _nav_source(
    path: Path,
    *,
    lead_pages: int,
    dest_name: str,
    outline_title: str,
) -> None:
    """Build a PDF with ``lead_pages`` filler pages, then a target page that is
    both a named destination (``dest_name``) and an outline item
    (``outline_title``) — so the merged document must re-resolve both to the
    target page's NEW index."""
    doc = PDDocument()
    for i in range(lead_pages):
        _text_page(doc, f"filler {i}")
    target = _text_page(doc, f"target for {dest_name}")

    outline = PDDocumentOutline()
    doc.get_document_catalog().set_document_outline(outline)
    item = PDOutlineItem()
    item.set_title(outline_title)
    item.set_destination(target)
    outline.add_last(item)

    names = PDDocumentNameDictionary(doc.get_document_catalog())
    dest_tree = PDDestinationNameTreeNode()
    dest = PDPageFitDestination()
    dest.set_page(target)
    dest_tree.set_names({dest_name: dest})
    names.set_dests(dest_tree)
    doc.get_document_catalog().set_names(names)

    doc.save(str(path))
    doc.close()


# ------------------------------------------------------------- fact reader


def _py_merge(sources: list[Path], dest: Path) -> None:
    merger = PDFMergerUtility()
    for src in sources:
        merger.add_source(str(src))
    merger.set_destination_file_name(str(dest))
    merger.merge_documents()


def _read_dest_facts(path: Path) -> list[str]:
    doc = PDDocument.load(str(path))
    try:
        lines = [f"pages {doc.get_number_of_pages()}"]
        catalog = doc.get_document_catalog()

        names = catalog.get_names()
        dest_map: dict[str, PDPageFitDestination] = {}
        if names is not None:
            dests = names.get_dests()
            if dests is not None:
                got = dests.get_names()
                if got:
                    dest_map = got
        for key in sorted(dest_map.keys()):
            lines.append(f"dest {key} page={_resolve(doc, dest_map[key])}")

        outline = catalog.get_document_outline()
        if outline is not None:
            for item in outline.children():
                title = item.get_title() or ""
                idx = -1
                dest = item.get_destination()
                if dest is not None and hasattr(dest, "retrieve_page_number"):
                    idx = _resolve(doc, dest)
                lines.append(f"outline {title} page={idx}")
        return lines
    finally:
        doc.close()


def _resolve(doc: PDDocument, dest: object) -> int:
    """0-based merged page index for ``dest``, or ``-1``."""
    if dest is None:
        return -1
    retrieve = getattr(dest, "retrieve_page_number", None)
    if callable(retrieve):
        try:
            idx = retrieve(doc)
            if isinstance(idx, int) and idx >= 0:
                return idx
        except Exception:  # noqa: BLE001
            pass
    get_page = getattr(dest, "get_page", None)
    if callable(get_page):
        target = get_page()
        if isinstance(target, COSDictionary):
            for i, page in enumerate(doc.get_pages()):
                if page.get_cos_object() is target:
                    return i
    return -1


def _qpdf_check(path: Path) -> int:
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode


# ------------------------------------------------------------------- tests


@requires_oracle
@_requires_qpdf
def test_merge_dest_resolves_to_shifted_page(tmp_path: Path) -> None:
    """Two nav sources merged in order: the second source's destination must
    re-resolve to its shifted index (= len(first) + its local index), and so
    must each outline item."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    # a: 2 filler + target at local idx 2 (dest -> page 2)
    _nav_source(a, lead_pages=2, dest_name="AlphaDest", outline_title="To Alpha")
    # b: 1 filler + target at local idx 1 -> merged idx 3 + 1 = 4
    _nav_source(b, lead_pages=1, dest_name="BravoDest", outline_title="To Bravo")

    java_out = tmp_path / "java.pdf"
    py_out = tmp_path / "py.pdf"
    java = run_probe_text("MergeDestResolveProbe", str(java_out), str(a), str(b))
    _py_merge([a, b], py_out)
    py = "\n".join(_read_dest_facts(py_out)) + "\n"

    assert py == java
    assert _qpdf_check(py_out) <= 3
    # Sanity: AlphaDest stays at 2, BravoDest shifts to 4 (3 a-pages + b idx 1).
    assert "dest AlphaDest page=2" in py
    assert "dest BravoDest page=4" in py


@requires_oracle
@_requires_qpdf
def test_merge_dest_three_sources(tmp_path: Path) -> None:
    """Three nav sources: every destination and outline item must re-resolve to
    the correct cumulative index across all three concatenated page trees."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    c = tmp_path / "c.pdf"
    _nav_source(a, lead_pages=1, dest_name="OneDest", outline_title="One")
    _nav_source(b, lead_pages=0, dest_name="TwoDest", outline_title="Two")
    _nav_source(c, lead_pages=2, dest_name="ThreeDest", outline_title="Three")

    java_out = tmp_path / "java.pdf"
    py_out = tmp_path / "py.pdf"
    java = run_probe_text(
        "MergeDestResolveProbe", str(java_out), str(a), str(b), str(c)
    )
    _py_merge([a, b, c], py_out)
    py = "\n".join(_read_dest_facts(py_out)) + "\n"

    assert py == java
    assert _qpdf_check(py_out) <= 3
