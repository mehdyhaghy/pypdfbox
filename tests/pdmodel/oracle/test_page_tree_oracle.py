"""Live PDFBox differential parity for page-tree traversal + mutation.

This complements ``test_page_geometry_oracle`` (which pins the resolved
geometry of every page) by pinning the **structure** of the page tree: the
total ``getNumberOfPages`` count, the document-order ``/Kids`` traversal, the
agreement between iteration order and ``indexOf`` per page, the inherited
``/MediaBox``, and the inherited ``/Font`` resource count. These are the
fields that diverge when traversal of an unbalanced / nested ``/Kids`` tree
(``page_tree_multiple_levels``) or inheritable-attribute resolution is wrong.

Every field is **exact-match** — there is no slack. The Java side is
``oracle/probes/PageTreeProbe.java``; the Python side rebuilds the identical
canonical report through :class:`PDPageTree` so the comparison is string-for
-string.

A second tier exercises mutation parity: remove a page index via both
libraries (``removePage``), save, reload, and assert the resulting count +
traversal are identical; then insert a fresh A4 page after a page via both
(``addPage`` when the index is last, else ``insertAfter``) and re-check. This
catches ``/Count`` desync and ``/Kids`` splice divergences that only surface
after a save/reload round-trip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# Fixtures spanning: a nested/unbalanced /Kids tree with an inheritable
# MediaBox + Resources on the intermediate node (page_tree_multiple_levels),
# a flat two-page writer doc, a multi-page doc with per-page font variation,
# and a single fractional-MediaBox page.
_CASES = [
    ("pdmodel/page_tree_multiple_levels.pdf", "nested_kids"),
    ("pdfwriter/unencrypted.pdf", "flat_two_page"),
    ("multipdf/PDFBOX-5811-362972.pdf", "multi_page_fonts"),
    ("text/BidiSample.pdf", "single_fractional"),
]


def _fmt(value: float) -> str:
    """Canonical float rendering matching ``PageTreeProbe.fmt``: integral
    values print without a trailing ``.0``; non-integral values print with up
    to 4 decimals, trailing zeros stripped."""
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _box(rect: PDRectangle) -> str:
    return (
        f"{_fmt(rect.lower_left_x)} {_fmt(rect.lower_left_y)} "
        f"{_fmt(rect.upper_right_x)} {_fmt(rect.upper_right_y)}"
    )


def _traversal(doc: PDDocument) -> str:
    """Rebuild the canonical traversal report ``PageTreeProbe`` emits.

    Mirrors the probe field-for-field: count via ``get_number_of_pages``,
    then per-page the document-order index ``i``, the ``index_of`` lookup
    (proving iteration order and index agree), the inherited ``/MediaBox``,
    and the resolved ``/Font`` resource count.
    """
    lines: list[str] = []
    count = doc.get_number_of_pages()
    lines.append(f"count {count}")
    tree = doc.get_pages()
    for i, page in enumerate(tree):
        idx = tree.index_of(page)
        media = page.get_media_box()
        res = page.get_resources()
        fonts = len(res.get_font_names()) if res is not None else 0
        lines.append(f"page {i} idx {idx} media {_box(media)} fonts {fonts}")
    return "\n".join(lines) + "\n"


@requires_oracle
@pytest.mark.parametrize(("rel_path", "label"), _CASES, ids=[c[1] for c in _CASES])
def test_page_tree_traversal_matches_pdfbox(rel_path: str, label: str) -> None:
    fixture = _FIXTURES / rel_path
    java = run_probe_text("PageTreeProbe", str(fixture))
    doc = PDDocument.load(fixture)
    try:
        py = _traversal(doc)
    finally:
        doc.close()
    assert py == java, (
        f"{label}: page-tree traversal diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


@requires_oracle
@pytest.mark.parametrize(
    ("rel_path", "label", "remove_index"),
    [
        ("pdmodel/page_tree_multiple_levels.pdf", "nested_kids", 1),
        ("multipdf/PDFBOX-5811-362972.pdf", "multi_page_fonts", 0),
        ("multipdf/PDFBOX-5811-362972.pdf", "multi_page_fonts_last", 3),
    ],
    ids=["nested_kids", "multi_page_fonts", "multi_page_fonts_last"],
)
def test_remove_page_round_trip_matches_pdfbox(
    rel_path: str, label: str, remove_index: int, tmp_path: Path
) -> None:
    fixture = _FIXTURES / rel_path
    out_dir = tmp_path / "java"
    out_dir.mkdir()
    java = run_probe_text(
        "PageTreeProbe", str(fixture), "remove", str(remove_index), str(out_dir / "out.pdf")
    )

    py_out = tmp_path / "py.pdf"
    doc = PDDocument.load(fixture)
    try:
        doc.remove_page(remove_index)
        doc.save(py_out)
    finally:
        doc.close()
    reloaded = PDDocument.load(py_out)
    try:
        py = _traversal(reloaded)
    finally:
        reloaded.close()

    assert py == java, (
        f"{label}: post-remove({remove_index}) tree diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


@requires_oracle
@pytest.mark.parametrize(
    ("rel_path", "label", "insert_after"),
    [
        ("pdmodel/page_tree_multiple_levels.pdf", "nested_kids_mid", 0),
        ("pdfwriter/unencrypted.pdf", "flat_two_page_last", 1),
    ],
    ids=["nested_kids_mid", "flat_two_page_last"],
)
def test_insert_page_round_trip_matches_pdfbox(
    rel_path: str, label: str, insert_after: int, tmp_path: Path
) -> None:
    fixture = _FIXTURES / rel_path
    out_dir = tmp_path / "java"
    out_dir.mkdir()
    java = run_probe_text(
        "PageTreeProbe", str(fixture), "insert", str(insert_after), str(out_dir / "out.pdf")
    )

    py_out = tmp_path / "py.pdf"
    doc = PDDocument.load(fixture)
    try:
        fresh = PDPage(PDRectangle.A4)
        tree = doc.get_pages()
        # Mirror the probe exactly: addPage when the target is the last
        # index (or beyond), else insertAfter the page at that index.
        if insert_after >= tree.get_count() - 1:
            doc.add_page(fresh)
        else:
            tree.insert_after(fresh, doc.get_page(insert_after))
        doc.save(py_out)
    finally:
        doc.close()
    reloaded = PDDocument.load(py_out)
    try:
        py = _traversal(reloaded)
    finally:
        reloaded.close()

    assert py == java, (
        f"{label}: post-insert(after {insert_after}) tree diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
