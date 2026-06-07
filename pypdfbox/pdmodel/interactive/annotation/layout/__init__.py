"""Annotation-layout text classes.

Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.layout`` — the
text-layout helpers the FreeText appearance handler uses to wrap
``/Contents`` into the annotation rectangle.

Upstream ships this package as a near-duplicate of
``org.apache.pdfbox.pdmodel.interactive.form``: ``AppearanceStyle``,
``PlainTextFormatter`` (with its ``Builder`` / ``TextAlign``) and the
``PlainText.Line`` / ``PlainText.Word`` inner classes are functionally
identical (only Java visibility differs), so the port re-exports them from
:mod:`pypdfbox.pdmodel.interactive.form` rather than duplicating the bytes.
Only :class:`PlainText` (and its :class:`Paragraph`) genuinely differs — the
layout variant has no PDFBOX-5049/6082 force-split and a distinct
empty-paragraph constructor — so it lives in :mod:`.plain_text`.
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.form.appearance_style import AppearanceStyle
from pypdfbox.pdmodel.interactive.form.plain_text_formatter import (
    PlainTextFormatter,
)
from pypdfbox.pdmodel.interactive.form.text_align import TextAlign

from .plain_text import Paragraph, PlainText

__all__ = [
    "AppearanceStyle",
    "Paragraph",
    "PlainText",
    "PlainTextFormatter",
    "TextAlign",
]
