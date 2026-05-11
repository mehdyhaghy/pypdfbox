"""Rebuild widget appearance streams when /NeedAppearances is true.

Mirrors ``org.apache.pdfbox.pdmodel.fixup.processor.AcroFormGenerateAppearancesProcessor``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/processor/AcroFormGenerateAppearancesProcessor.java``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .abstract_processor import AbstractProcessor

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument

_log = logging.getLogger(__name__)


class AcroFormGenerateAppearancesProcessor(AbstractProcessor):
    """Regenerate appearance streams. Mirrors upstream class shape."""

    def __init__(self, document: PDDocument) -> None:
        super().__init__(document)

    def process(self) -> None:
        """Mirrors ``process`` (Java line 37)."""
        catalog = self.document.get_document_catalog()
        get_acro_form = getattr(catalog, "get_acro_form", None)
        if get_acro_form is None:
            return
        try:
            acro_form = get_acro_form(None)
        except TypeError:
            acro_form = get_acro_form()
        if acro_form is None:
            return
        try:
            _log.debug(
                "trying to generate appearance streams for fields as NeedAppearances is true()"
            )
            refresh = getattr(acro_form, "refresh_appearances", None)
            if refresh is not None:
                refresh()
            set_need = getattr(acro_form, "set_need_appearances", None)
            if set_need is not None:
                set_need(False)
        except (OSError, ValueError) as exc:
            _log.debug(
                "couldn't generate appearance stream for some fields - check output"
            )
            _log.debug(str(exc))


__all__ = ["AcroFormGenerateAppearancesProcessor"]
