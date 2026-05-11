"""Default AcroForm fixup driver.

Mirrors ``org.apache.pdfbox.pdmodel.fixup.AcroFormDefaultFixup`` (Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/AcroFormDefaultFixup.java``).

Runs the defaults processor first; then, when ``/NeedAppearances`` is set
and the form has no fields, rebuilds them from orphan widget annotations
and regenerates appearance streams (PDFBOX-4985).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_fixup import AbstractFixup
from .processor.acro_form_defaults_processor import AcroFormDefaultsProcessor
from .processor.acro_form_generate_appearances_processor import (
    AcroFormGenerateAppearancesProcessor,
)
from .processor.acro_form_orphan_widgets_processor import (
    AcroFormOrphanWidgetsProcessor,
)

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


class AcroFormDefaultFixup(AbstractFixup):
    """Run the canonical AcroForm fixup chain.

    Mirrors the upstream constructor + ``apply`` (Java lines 27-58).
    """

    def __init__(self, document: PDDocument) -> None:
        super().__init__(document)

    def apply(self) -> None:
        """Mirrors ``apply`` (Java line 33)."""
        AcroFormDefaultsProcessor(self.document).process()

        # ``get_acro_form()`` applies this very fixup chain — pass
        # ``fixup=None`` to break the recursion (matches the upstream
        # ``getAcroForm(null)`` call).
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

        # PDFBOX-4985: rebuild visual appearances when none exist.
        need_appearances = getattr(acro_form, "get_need_appearances", None)
        if need_appearances is None or not need_appearances():
            return
        fields_method = getattr(acro_form, "get_fields", None)
        fields = fields_method() if fields_method else None
        if not fields:
            AcroFormOrphanWidgetsProcessor(self.document).process()
        AcroFormGenerateAppearancesProcessor(self.document).process()


__all__ = ["AcroFormDefaultFixup"]
