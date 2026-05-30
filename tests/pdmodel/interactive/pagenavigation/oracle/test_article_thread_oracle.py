"""Live PDFBox differential parity for ARTICLE THREADS / BEADS.

Builds a multi-page PDF wiring two article threads through the catalog
``/Threads`` array. Each thread carries an ``/I`` info dict (with ``/Title``)
and a ``/F`` first bead; each bead forms a circular doubly-linked list via
``/N`` next / ``/V`` prev, referencing a page (``/P``) and a rectangle
(``/R``). The test re-reads the PDF and compares pypdfbox's traversal —
``PDDocumentCatalog.get_threads()`` → per-thread ``get_thread_info().get_title()``
+ ``get_first_bead()`` → ``/N`` walk emitting page index + rect per bead — byte
for byte against Apache PDFBox 3.0.7 via the ``ArticleThreadProbe`` Java oracle.

Threads built:

* **thread 0** ("Intro") — 3 beads spanning pages 0 → 1 → 2 (circular).
* **thread 1** ("Sidebar") — 2 beads spanning pages 1 → 2 (circular).

The circular ``/N`` walk is identity-guarded against the first bead's COS
object so the loop terminates on both sides.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _rect(llx: int, lly: int, urx: int, ury: int) -> COSArray:
    arr = COSArray()
    for v in (llx, lly, urx, ury):
        arr.add(_i(v))
    return arr


def _make_bead(page: COSDictionary, rect: COSArray) -> COSDictionary:
    bead = COSDictionary()
    bead.set_item(_name("Type"), _name("Bead"))
    bead.set_item(_name("P"), page)
    bead.set_item(_name("R"), rect)
    return bead


def _link_chain(beads: list[COSDictionary], thread: COSDictionary) -> None:
    """Wire a circular doubly-linked list and the /T on the first bead."""
    n = len(beads)
    for idx, bead in enumerate(beads):
        bead.set_item(_name("N"), beads[(idx + 1) % n])
        bead.set_item(_name("V"), beads[(idx - 1) % n])
    beads[0].set_item(_name("T"), thread)


def _build_pdf(path: str) -> None:
    doc = PDDocument()
    try:
        pages = [PDPage() for _ in range(3)]
        for page in pages:
            doc.add_page(page)
        pc = [page.get_cos_object() for page in pages]
        catalog = doc.get_document_catalog().get_cos_object()

        # ---- thread 0: "Intro", 3 beads across pages 0,1,2 ----
        thread0 = COSDictionary()
        thread0.set_item(_name("Type"), _name("Thread"))
        info0 = COSDictionary()
        info0.set_item(_name("Title"), COSString("Intro"))
        thread0.set_item(_name("I"), info0)
        beads0 = [
            _make_bead(pc[0], _rect(10, 20, 110, 120)),
            _make_bead(pc[1], _rect(30, 40, 130, 140)),
            _make_bead(pc[2], _rect(50, 60, 150, 160)),
        ]
        _link_chain(beads0, thread0)
        thread0.set_item(_name("F"), beads0[0])

        # ---- thread 1: "Sidebar", 2 beads across pages 1,2 ----
        thread1 = COSDictionary()
        thread1.set_item(_name("Type"), _name("Thread"))
        info1 = COSDictionary()
        info1.set_item(_name("Title"), COSString("Sidebar"))
        thread1.set_item(_name("I"), info1)
        beads1 = [
            _make_bead(pc[1], _rect(200, 210, 300, 310)),
            _make_bead(pc[2], _rect(220, 230, 320, 330)),
        ]
        _link_chain(beads1, thread1)
        thread1.set_item(_name("F"), beads1[0])

        threads = COSArray()
        threads.add(thread0)
        threads.add(thread1)
        catalog.set_item(_name("Threads"), threads)

        doc.save(path)
    finally:
        doc.close()


def _num(value: float) -> str:
    f = float(value)
    return str(int(f)) if f == int(f) else str(f)


def _rect_str(bead) -> str:
    r = bead.get_rectangle()
    if r is None:
        return "none"
    return (
        f"{_num(r.get_lower_left_x())},{_num(r.get_lower_left_y())},"
        f"{_num(r.get_upper_right_x())},{_num(r.get_upper_right_y())}"
    )


def _dump(doc: PDDocument) -> str:
    catalog = doc.get_document_catalog()
    pages = doc.get_pages()
    lines: list[str] = []
    for ti, thread in enumerate(catalog.get_threads()):
        lines.append(f"THREAD {ti}")
        info = thread.get_thread_info()
        title = None if info is None else info.get_title()
        lines.append(f"TITLE {'none' if title is None else title}")
        first = thread.get_first_bead()
        if first is not None:
            first_cos = first.get_cos_object()
            bead = first
            while True:
                page = bead.get_page()
                page_index = -1 if page is None else pages.index_of(page)
                lines.append(f"BEAD {page_index} {_rect_str(bead)}")
                nxt = bead.get_next_bead()
                if nxt is None or nxt.get_cos_object() is first_cos:
                    break
                bead = nxt
        lines.append("ENDTHREAD")
    return "".join(line + "\n" for line in lines)


@pytest.fixture(scope="module")
def article_thread_pdf() -> Path:
    fd, path = tempfile.mkstemp(suffix="_article_thread.pdf")
    os.close(fd)
    _build_pdf(path)
    try:
        yield Path(path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


@requires_oracle
def test_article_threads_traverse_like_pdfbox(article_thread_pdf: Path) -> None:
    """pypdfbox walks every article thread — title, first bead, circular ``/N``
    bead chain, each bead's page index + rectangle — to the SAME fingerprint
    as Apache PDFBox 3.0.7."""
    java = run_probe_text("ArticleThreadProbe", "read", str(article_thread_pdf))
    doc = PDDocument.load(str(article_thread_pdf))
    try:
        py = _dump(doc)
    finally:
        doc.close()
    assert py == java
    # Sanity: the battery must actually cover both threads + all beads.
    assert "THREAD 0\n" in java
    assert "THREAD 1\n" in java
    assert "TITLE Intro\n" in java
    assert "TITLE Sidebar\n" in java
    # thread 0 has 3 beads, thread 1 has 2 — 5 BEAD lines total.
    assert java.count("BEAD ") == 5


@requires_oracle
def test_article_thread_bead_pages_distinct(article_thread_pdf: Path) -> None:
    """Each bead resolves to its own page index — proving the ``/P`` page
    references survive the round trip and the ``/N`` walk visits the chain in
    order (thread 0: pages 0,1,2; thread 1: pages 1,2)."""
    doc = PDDocument.load(str(article_thread_pdf))
    try:
        catalog = doc.get_document_catalog()
        pages = doc.get_pages()
        threads = catalog.get_threads()
        assert len(threads) == 2

        def chain_pages(thread) -> list[int]:
            first = thread.get_first_bead()
            first_cos = first.get_cos_object()
            out: list[int] = []
            bead = first
            while True:
                out.append(pages.index_of(bead.get_page()))
                nxt = bead.get_next_bead()
                if nxt is None or nxt.get_cos_object() is first_cos:
                    break
                bead = nxt
            return out

        assert chain_pages(threads[0]) == [0, 1, 2]
        assert chain_pages(threads[1]) == [1, 2]
    finally:
        doc.close()
