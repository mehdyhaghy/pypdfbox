"""Wave 1403 branch round-out for ``print_bookmarks``.

Closes two partials in ``print_bookmark``:

* ``63->73`` — an item-level named destination that cannot be resolved
  (``find_named_destination_page`` returns None) skips the page print and
  falls through to the action handling.
The companion ``83->98`` arc (GoTo-action named destination that fails to
resolve) is **unreachable** in pypdfbox: ``PDActionGoTo.get_destination``
returns a plain ``str`` for named destinations rather than a
``PDNamedDestination``, so the action-level ``elif`` never fires. The source
guards that arm with ``# pragma: no cover`` and a parity note; the test below
documents the realised behaviour (the named str lands in the class-name
fallback).
"""

from __future__ import annotations

from pypdfbox.examples.pdmodel.print_bookmarks import PrintBookmarks
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_document_outline import (
    PDDocumentOutline,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)


def test_item_named_destination_unresolved_skips_page(capsys) -> None:
    """An item whose /Dest is a named destination with no matching /Names
    entry → ``find_named_destination_page`` returns None (63->73)."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))
        # NB: no /Names tree wired up, so the lookup cannot resolve.
        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)
        item = PDOutlineItem()
        item.set_title("Dangling Named")
        item.set_destination(PDNamedDestination("does-not-exist"))
        outline.add_last(item)
        PrintBookmarks().print_bookmark(doc, outline, "")
    finally:
        doc.close()
    out = capsys.readouterr().out
    # No "Destination page:" line was emitted for this item; the title is
    # still printed.
    assert "Dangling Named\n" in out
    assert "Destination page:" not in out


def test_goto_action_named_destination_lands_in_class_fallback(capsys) -> None:
    """A GoTo action with a named destination surfaces as a ``str`` from
    ``get_destination`` (not a ``PDNamedDestination``), so it lands in the
    class-name fallback rather than the (unreachable) named-destination arm.
    """
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))
        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)
        item = PDOutlineItem()
        item.set_title("Goto Named")
        action = PDActionGoTo()
        action.set_destination(PDNamedDestination("missing-target"))
        item.set_action(action)
        outline.add_last(item)
        PrintBookmarks().print_bookmark(doc, outline, "")
    finally:
        doc.close()
    out = capsys.readouterr().out
    assert "Goto Named\n" in out
    assert "Destination class: str\n" in out
