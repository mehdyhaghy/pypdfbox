"""AcroForm-fixup processors — port of ``org.apache.pdfbox.pdmodel.fixup.processor``."""

from __future__ import annotations

from .abstract_processor import AbstractProcessor
from .acro_form_defaults_processor import AcroFormDefaultsProcessor
from .acro_form_generate_appearances_processor import (
    AcroFormGenerateAppearancesProcessor,
)
from .acro_form_orphan_widgets_processor import AcroFormOrphanWidgetsProcessor
from .pd_document_processor import PDDocumentProcessor

__all__ = [
    "AbstractProcessor",
    "AcroFormDefaultsProcessor",
    "AcroFormGenerateAppearancesProcessor",
    "AcroFormOrphanWidgetsProcessor",
    "PDDocumentProcessor",
]
