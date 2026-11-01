"""AcroForm-fixup processors — port of ``org.apache.pdfbox.pdmodel.fixup.processor``."""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .abstract_processor import AbstractProcessor
    from .acro_form_defaults_processor import AcroFormDefaultsProcessor
    from .acro_form_generate_appearances_processor import AcroFormGenerateAppearancesProcessor
    from .acro_form_orphan_widgets_processor import AcroFormOrphanWidgetsProcessor
    from .pd_document_processor import PDDocumentProcessor

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AbstractProcessor": ".abstract_processor",
        "AcroFormDefaultsProcessor": ".acro_form_defaults_processor",
        "AcroFormGenerateAppearancesProcessor": ".acro_form_generate_appearances_processor",
        "AcroFormOrphanWidgetsProcessor": ".acro_form_orphan_widgets_processor",
        "PDDocumentProcessor": ".pd_document_processor",
    },
)

__all__ = [
    "AbstractProcessor",
    "AcroFormDefaultsProcessor",
    "AcroFormGenerateAppearancesProcessor",
    "AcroFormOrphanWidgetsProcessor",
    "PDDocumentProcessor",
]
