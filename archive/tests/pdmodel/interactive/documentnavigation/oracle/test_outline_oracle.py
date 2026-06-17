"""Live PDFBox differential parity for the document outline (bookmarks) +
destination-resolution surface
(``pypdfbox.pdmodel.interactive.documentnavigation.outline`` +
``...documentnavigation.destination``).

Compares pypdfbox's depth-first outline walk against Apache PDFBox's, via the
``OutlineProbe`` Java oracle. Each outline item is reduced to one canonical
line so the two languages compare byte-for-byte without tripping over object
layout, float rendering, or locale.

Canonical line grammar (must match ``oracle/probes/OutlineProbe.java``)::

    <depth>\t<title>\t<pageIndex>

Where ``depth`` is 0-based nesting depth in a stable ``/First`` -> ``/Next``
pre-order walk; ``title`` is ``/Title`` with backslash/newline/CR/tab escaped
(``null`` when absent); and ``pageIndex`` is the 0-based page the item targets,
resolved from its ``/Dest`` or, failing that, its ``/A`` GoTo action's
destination (named destinations chased through the catalog), or ``-1`` when no
page target resolves.

This exercises the three resolution paths the task calls out:
  * **named destinations** — ``with_outline.pdf`` (string /Dest -> /Names/Dests);
  * **GoTo actions** — the ``PDFBOX-*`` fixtures whose items carry ``/A`` GoTo;
  * **nested items** — every fixture with depth > 0 in the dump.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[5]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"


def _escape(title: str | None) -> str:
    """Mirror ``OutlineProbe.escape`` exactly."""
    if title is None:
        return "null"
    return (
        title.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _resolve_page_index(doc: PDDocument, item) -> int:
    """Reproduce ``OutlineProbe.resolvePageIndex`` in pypdfbox terms.

    Resolve the item's ``/Dest`` (or its ``/A`` GoTo action's destination) to a
    :class:`PDPageDestination`, chasing named destinations through the catalog,
    then map it to a 0-based page index. Returns ``-1`` when no page target
    resolves.
    """
    dest = item.get_destination()
    if dest is None:
        action = item.get_action()
        if isinstance(action, PDActionGoTo):
            resolved = action.get_destination()
            # Our PDActionGoTo returns the bare string for the named form;
            # re-wrap so the named path below fires (see CHANGES.md).
            dest = PDNamedDestination(resolved) if isinstance(resolved, str) else resolved
    if dest is None:
        return -1
    if isinstance(dest, PDNamedDestination):
        dest = item._resolve_named_destination(doc, dest)
        if dest is None:
            return -1
    if not isinstance(dest, PDPageDestination):
        return -1
    # Local destination: a direct page-object reference.
    page = dest.get_page()
    if page is not None:
        idx = doc.get_pages().index_of(page)
        if idx >= 0:
            return idx
    # Remote destination: an explicit numeric page index.
    return dest.get_page_number()


def _dump_outline(doc: PDDocument) -> str:
    outline = doc.get_document_catalog().get_document_outline()
    lines: list[str] = []

    def walk(node, depth: int) -> None:
        for item in node.children():
            lines.append(
                f"{depth}\t{_escape(item.get_title())}\t{_resolve_page_index(doc, item)}"
            )
            walk(item, depth + 1)

    if outline is not None:
        walk(outline, 0)
    # OutlineProbe terminates every line with '\n' (including the last).
    return "".join(line + "\n" for line in lines)


def _has_outline(pdf: Path) -> bool:
    try:
        doc = PDDocument.load(str(pdf))
    except Exception:
        # Malformed / fuzz corpus fixtures that pypdfbox declines to load
        # are simply not outline fixtures.
        return False
    try:
        outline = doc.get_document_catalog().get_document_outline()
        if outline is None:
            return False
        return outline.get_first_child() is not None
    except Exception:
        return False
    finally:
        doc.close()


def _discover_outline_fixtures() -> list[Path]:
    """All fixture PDFs whose catalog carries a non-empty document outline."""
    pdfs = sorted(_FIXTURES.rglob("*.pdf"))
    return [p for p in pdfs if _has_outline(p)]


_OUTLINE_FIXTURES = _discover_outline_fixtures()
_FIXTURE_IDS = [str(p.relative_to(_FIXTURES)) for p in _OUTLINE_FIXTURES]


@requires_oracle
@pytest.mark.parametrize("fixture", _OUTLINE_FIXTURES, ids=_FIXTURE_IDS)
def test_outline_dump_matches_pdfbox(fixture: Path) -> None:
    """pypdfbox's depth-first outline + destination dump equals PDFBox's."""
    java = run_probe_text("OutlineProbe", str(fixture))
    doc = PDDocument.load(str(fixture))
    try:
        py = _dump_outline(doc)
    finally:
        doc.close()
    assert py == java


@requires_oracle
def test_with_outline_named_destinations() -> None:
    """``with_outline.pdf`` resolves string-named /Dest entries to pages."""
    fixture = _FIXTURES / "pdmodel" / "with_outline.pdf"
    java = run_probe_text("OutlineProbe", str(fixture))
    doc = PDDocument.load(str(fixture))
    try:
        py = _dump_outline(doc)
    finally:
        doc.close()
    assert py == java
    # Sanity: this fixture must actually exercise nested items + named dests.
    assert "\t0\n" in java  # at least one item resolves to page 0
    assert any(line.startswith("2\t") for line in java.splitlines())  # depth-2 nesting
