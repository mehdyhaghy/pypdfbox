"""Live PDFBox differential parity for the **full-save object-number
assignment order** on a freshly-created (in-memory) document.

ISO 32000-1 leaves indirect-object numbering free — any one-to-one mapping
of objects to ``(num, gen)`` keys is conforming. But PDFBox's ``COSWriter``
assigns numbers by a deterministic walk seeded from the trailer's ``/Root``,
then ``/Info``, then ``/Encrypt`` (``COSWriter.doWriteBody`` enqueues /Root
first and drains the breadth-first queue before moving on). For a document
built with ``new PDDocument()`` plus N blank pages and saved **uncompressed**
(classic xref table — the same shape pypdfbox's full save always emits), this
produces a fixed numbering:

    1 = /Catalog
    2 = /Pages   (the single page-tree root node)
    3 .. N+2 = the N /Page leaves, in add order

A port that walked the graph in a different order (e.g. depth-first, or
pages-before-catalog) would assign the *same* objects *different* numbers.
That is technically still valid PDF, but it breaks byte-level diffability
against PDFBox output and is exactly the kind of silent traversal divergence
the parity goal forbids. This module pins the order.

The companion ``SaveObjectOrderProbe`` drives Apache PDFBox 3.0.7 to perform
the equivalent ``new PDDocument()`` + ``addPage`` + uncompressed ``save`` and
emits, per reloaded indirect object, ``<objNum> <gen>: <role>`` where the role
is derived from ``/Type`` / structural identity (NOT from the number), so the
two sides are compared on the *binding of role to number*, not on a value we
hand-translated.

NOTE on compression: PDFBox's *default* full save of a fresh document packs
the page objects into an ``/ObjStm`` behind a ``/XRef`` stream; pypdfbox's
full save is always uncompressed (documented divergence — see CHANGES.md
"full save ignores CompressParameters"). To compare the numbering surface on
equal footing the probe passes ``CompressParameters.NO_COMPRESSION`` so both
sides emit a classic uncompressed table.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.cos import COSDictionary, COSName, COSObject
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.common import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]

_PAGE_COUNTS = [1, 2, 3, 5]


# ----------------------------------------------------------------- helpers


def _role(
    base: object,
    catalog: COSDictionary,
    pages_node: COSDictionary | None,
) -> str:
    """Mirror ``SaveObjectOrderProbe.role`` — derive a numbering-independent
    structural tag for a reloaded indirect object."""
    if isinstance(base, COSObject):
        base = base.get_object()
    if not isinstance(base, COSDictionary):
        return "other"
    if base is catalog:
        return "catalog"
    if pages_node is not None and base is pages_node:
        return "pages"
    type_base = base.get_dictionary_object(COSName.TYPE)
    type_name = (
        type_base.get_name()
        if type_base is not None and hasattr(type_base, "get_name")
        else None
    )
    if type_name == "Catalog":
        return "catalog"
    if type_name == "Pages":
        return "pages"
    if type_name == "Page":
        return "page"
    if type_name == "Font":
        return "font"
    if base.contains_key(COSName.MEDIA_BOX) and base.contains_key(COSName.PARENT):
        return "page"
    return "other"


def _pypdfbox_object_order(num_pages: int) -> tuple[int, list[tuple[int, str]]]:
    """Build a fresh ``PDDocument`` with ``num_pages`` blank LETTER pages,
    full-save it, reload, and return ``(count, [(objNum, role), ...])`` sorted
    by object number — the pypdfbox analogue of the probe's output."""
    doc = PDDocument()
    for _ in range(num_pages):
        doc.add_page(PDPage(PDRectangle.LETTER))
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()

    cos = Loader.load_pdf(buf.getvalue())
    pd = PDDocument(cos)
    try:
        catalog = pd.get_document_catalog().get_cos_object()
        pages_base = catalog.get_dictionary_object(COSName.PAGES)
        pages_node = pages_base if isinstance(pages_base, COSDictionary) else None

        xref = cos.get_xref_table()
        rows: list[tuple[int, str]] = []
        for key in sorted(
            xref.keys(), key=lambda k: (k.object_number, k.generation_number)
        ):
            try:
                obj = cos.get_object_from_pool(key).get_object()
            except Exception:
                obj = None
            rows.append((key.object_number, _role(obj, catalog, pages_node)))
        return len(xref), rows
    finally:
        pd.close()


def _parse_probe(out: str) -> tuple[int, list[tuple[int, str]]]:
    """Parse ``SaveObjectOrderProbe`` output into ``(count, [(num, role)])``."""
    count = 0
    rows: list[tuple[int, str]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("count="):
            count = int(line[len("count=") :])
            continue
        head, _, role = line.partition(":")
        num = int(head.split()[0])
        rows.append((num, role.strip()))
    return count, rows


# ----------------------------------------------------------- the parity tests


@requires_oracle
@pytest.mark.parametrize("num_pages", _PAGE_COUNTS)
def test_fresh_save_object_numbering_matches_pdfbox(num_pages: int) -> None:
    """The role-to-object-number binding pypdfbox assigns on a fresh
    uncompressed full save must match Apache PDFBox 3.0.7 exactly."""
    java_count, java_rows = _parse_probe(
        run_probe_text("SaveObjectOrderProbe", str(num_pages))
    )
    py_count, py_rows = _pypdfbox_object_order(num_pages)

    assert py_count == java_count, (
        f"object count diverged: PDFBox={java_count}, pypdfbox={py_count} "
        f"(num_pages={num_pages})"
    )
    assert py_rows == java_rows, (
        f"object-numbering order diverged for num_pages={num_pages}:\n"
        f"  PDFBox  : {java_rows}\n"
        f"  pypdfbox: {py_rows}"
    )


@requires_oracle
@pytest.mark.parametrize("num_pages", _PAGE_COUNTS)
def test_fresh_save_assigns_catalog_first(num_pages: int) -> None:
    """Independent of the oracle's exact tags, the breadth-first walk from
    ``/Root`` means object 1 is always the catalog and object 2 the page-tree
    root — the structural invariant the numbering contract rests on."""
    _, py_rows = _pypdfbox_object_order(num_pages)
    by_num = dict(py_rows)
    assert by_num[1] == "catalog"
    assert by_num[2] == "pages"
    # The N page leaves occupy the contiguous block 3 .. N+2.
    page_nums = sorted(n for n, role in py_rows if role == "page")
    assert page_nums == list(range(3, 3 + num_pages))
