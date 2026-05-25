"""Wave 1403 branch round-out for :class:`FieldRemover`.

Closes the ``99->113`` partial: a successfully-removed field that carries
*no* widget annotations leaves ``widget_set`` empty, so the page-walk guard
(``if widget_set:``) takes its false branch while removal still proceeds to
the save step.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from pypdfbox.examples.interactive.form.field_remover import FieldRemover
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_document import PDDocument


def _build_widgetless_group_form(path: Path) -> None:
    """A non-terminal (group) field has no widget annotations of its own."""
    doc = PDDocument()
    try:
        acro_form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(acro_form)
        parent = PDNonTerminalField(acro_form)
        parent.set_partial_name("Group")
        child = PDTextField(acro_form)
        child.set_partial_name("Child")
        parent.set_children([child])
        acro_form.set_fields([parent])
        doc.save(str(path))
    finally:
        doc.close()


def test_remove_widgetless_field_skips_page_walk(tmp_path: Path) -> None:
    """Removing a widget-free field drives ``99->113``: ``widget_set`` is
    empty so the page annotation walk is skipped, yet ``removed`` is True so
    the document is still saved."""
    src = tmp_path / "group.pdf"
    _build_widgetless_group_form(src)

    # Confirm the field genuinely has no widgets before removal.
    with PDDocument.load(str(src)) as probe:
        field = probe.get_document_catalog().get_acro_form().get_field("Group")
        assert field.get_widgets() == []

    dst = tmp_path / "group_removed.pdf"
    assert FieldRemover().remove(str(src), str(dst), "Group") is True
    assert dst.exists()
    with PDDocument.load(str(dst)) as out:
        acro_form = out.get_document_catalog().get_acro_form()
        assert acro_form is None or acro_form.get_field("Group") is None


def test_remove_widgetless_field_via_tempfile_roundtrip() -> None:
    """Same path exercised through an explicit temp-file round-trip so the
    branch is covered even when ``tmp_path`` semantics differ across
    platforms (handles are closed before any unlink)."""
    fd_src, src = tempfile.mkstemp(suffix=".pdf")
    os.close(fd_src)
    fd_dst, dst = tempfile.mkstemp(suffix=".pdf")
    os.close(fd_dst)
    try:
        _build_widgetless_group_form(Path(src))
        assert FieldRemover().remove(src, dst, "Group") is True
    finally:
        for p in (src, dst):
            with contextlib.suppress(OSError):
                os.unlink(p)
