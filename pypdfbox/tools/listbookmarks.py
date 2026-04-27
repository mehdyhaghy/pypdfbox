"""
``pypdfbox listbookmarks INFILE [-password PWD] [-format tree|flat]`` —
print every entry in a PDF's outline (bookmarks) tree.

Ports upstream ``org.apache.pdfbox.examples.pdmodel.PrintBookmarks``
(PDFBox 3.0 examples module). Upstream is a plain ``main(args)`` example
rather than a PicoCLI tool; we wrap the same recursive ``printBookmark``
walk in pypdfbox's standard argparse subcommand surface so it slots into
the ``pypdfbox`` dispatcher next to ``info`` / ``extracttext`` / etc.

Output formats:

* ``tree`` (default) — indent each level by four spaces, mirroring
  upstream's ``indentation + "    "`` recursion. Each item line shows
  destination metadata (page number for explicit destinations, action /
  destination class names otherwise) followed by the title on its own
  line.
* ``flat`` — one entry per line, no indentation; each line is
  ``"<title> -> page <N>"`` or ``"<title>"`` when no destination page
  resolves. Useful for piping into ``grep`` / line-oriented tooling.

Exit codes follow the rest of the suite:
  0  success
  1  wrong password
  4  IO error (raised as ``OSError`` and caught by ``cli.run_cli``)
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import IO

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.encryption import PDInvalidPasswordException
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
    PDPageDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_document_outline import (
    PDDocumentOutline,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_node import (
    PDOutlineNode,
)

_FORMAT_TREE = "tree"
_FORMAT_FLAT = "flat"
_INDENT = "    "  # upstream printBookmark uses 4 spaces per level
_NO_BOOKMARKS = "This document does not contain any bookmarks"


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "listbookmarks",
        help="print the outline (bookmarks) tree of a PDF",
        description="Print every entry in a PDF's outline (bookmarks) tree. "
        "Mirrors the upstream PrintBookmarks example, walking /First / "
        "/Next chains recursively from the document outline root.",
    )
    p.add_argument("input", help="path to the input PDF")
    p.add_argument(
        "-password", "--password", dest="password", default="", metavar="PASSWORD",
        help="password for the PDF (defaults to empty string)",
    )
    p.add_argument(
        "-format", "--format", dest="format", default=_FORMAT_TREE,
        choices=(_FORMAT_TREE, _FORMAT_FLAT),
        help="output format: 'tree' (indented, default) or 'flat' (one entry per line)",
    )
    p.set_defaults(func=run)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _resolve_page_number(
    document: PDDocument, dest: object,
) -> int | None:
    """Return the 1-based destination page index, or ``None`` when the
    destination doesn't resolve to a concrete page within this document.

    Mirrors upstream's ``pd.retrievePageNumber() + 1`` plus the named-
    destination branch. Named-destination resolution requires a
    ``/Names`` / ``/Dests`` walk that pypdfbox does not yet expose on
    ``PDDocumentCatalog`` (no ``find_named_destination_page`` yet); when
    we encounter one, return ``None`` rather than guess.
    """
    if isinstance(dest, PDPageDestination):
        idx = dest.retrieve_page_number(document)
        if idx >= 0:
            return idx + 1
        return None
    if isinstance(dest, PDNamedDestination):
        # Catalog-level named-destination resolution is not yet ported;
        # the outline-item ``find_destination_page`` fallback in
        # ``_describe_item`` handles the explicit-array case.
        return None
    return None


def _destination_class_name(dest: object) -> str:
    """Return the upstream-equivalent ``getClass().getSimpleName()`` for
    diagnostic ``Destination class:`` / ``Action class:`` lines."""
    return type(dest).__name__


def _describe_item(
    document: PDDocument, item: PDOutlineItem,
) -> tuple[int | None, list[str]]:
    """Return ``(page_number, info_lines)`` for one outline item.

    ``page_number`` is the first concrete 1-based page we resolve from
    the item's ``/Dest`` or its ``/A`` GoTo action (preferring ``/Dest``,
    matching upstream's ordering). ``info_lines`` are the ``Destination
    page:`` / ``Destination class:`` / ``Action class:`` diagnostic
    lines upstream emits before the title.
    """
    info: list[str] = []
    page_number: int | None = None

    dest = item.get_destination()
    if isinstance(dest, PDPageDestination):
        resolved = _resolve_page_number(document, dest)
        if resolved is not None:
            info.append(f"Destination page: {resolved}")
            page_number = resolved
    elif isinstance(dest, PDNamedDestination):
        resolved = _resolve_page_number(document, dest)
        if resolved is not None:
            info.append(f"Destination page: {resolved}")
            page_number = resolved
    elif dest is not None:
        info.append(f"Destination class: {_destination_class_name(dest)}")

    action = item.get_action()
    if isinstance(action, PDActionGoTo):
        action_dest = action.get_destination()
        if isinstance(action_dest, PDPageDestination):
            resolved = _resolve_page_number(document, action_dest)
            if resolved is not None:
                info.append(f"Destination page: {resolved}")
                if page_number is None:
                    page_number = resolved
        elif isinstance(action_dest, PDNamedDestination):
            resolved = _resolve_page_number(document, action_dest)
            if resolved is not None:
                info.append(f"Destination page: {resolved}")
                if page_number is None:
                    page_number = resolved
        elif action_dest is not None:
            info.append(
                f"Destination class: {_destination_class_name(action_dest)}"
            )
    elif action is not None:
        info.append(f"Action class: {_destination_class_name(action)}")

    if page_number is None:
        # Fall back to the outline-item's own resolver (handles direct
        # page-dict references that ``retrieve_page_number`` covers but
        # upstream's "hard way" branches don't reach via /Names).
        page = item.find_destination_page(document)
        if page is not None:
            pages = document.get_pages()
            for index, candidate in enumerate(pages):
                if candidate.get_cos_object() is page:
                    page_number = index + 1
                    break

    return page_number, info


def _print_tree(
    document: PDDocument,
    bookmark: PDOutlineNode,
    indentation: str,
    output: IO[str],
) -> None:
    """Recursively print ``bookmark``'s children indented by
    ``indentation``. Mirrors upstream ``PrintBookmarks#printBookmark``."""
    current = bookmark.get_first_child()
    while current is not None:
        _, info = _describe_item(document, current)
        for line in info:
            output.write(f"{indentation}{line}\n")
        title = current.get_title() or ""
        output.write(f"{indentation}{title}\n")
        _print_tree(document, current, indentation + _INDENT, output)
        current = current.get_next_sibling()


def _print_flat(
    document: PDDocument,
    bookmark: PDOutlineNode,
    output: IO[str],
) -> None:
    """One entry per line, no indentation. ``"<title> -> page <N>"`` when
    a destination resolves; bare ``"<title>"`` otherwise."""
    current = bookmark.get_first_child()
    while current is not None:
        page_number, _ = _describe_item(document, current)
        title = current.get_title() or ""
        if page_number is not None:
            output.write(f"{title} -> page {page_number}\n")
        else:
            output.write(f"{title}\n")
        _print_flat(document, current, output)
        current = current.get_next_sibling()


def list_bookmarks(
    document: PDDocument,
    output: IO[str],
    *,
    format: str = _FORMAT_TREE,
) -> None:
    """Walk ``document``'s outline tree and write entries to ``output``.

    Equivalent to upstream ``PrintBookmarks#main`` minus the file-loading
    plumbing — supply an already-loaded :class:`PDDocument`.
    """
    outline = document.get_document_catalog().get_document_outline()
    if not isinstance(outline, PDDocumentOutline):
        output.write(f"{_NO_BOOKMARKS}\n")
        return
    if format == _FORMAT_FLAT:
        _print_flat(document, outline, output)
    else:
        _print_tree(document, outline, "", output)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"listbookmarks: {src}: not a file", flush=True)
        return 4

    try:
        doc = PDDocument.load(src, password=args.password or "")
    except PDInvalidPasswordException as exc:
        print(f"listbookmarks: {exc}", flush=True)
        return 1

    try:
        import sys
        list_bookmarks(doc, sys.stdout, format=args.format)
    finally:
        doc.close()
    return 0
