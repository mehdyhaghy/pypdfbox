from __future__ import annotations

from typing import TYPE_CHECKING

from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


class PDSoundAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a sound annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDSoundAppearanceHandler``.

    Upstream PDFBox 3.0 implements all three ``generate*Appearance``
    methods as no-ops (their bodies are empty save for a single
    deferred-impl placeholder comment). We mirror that behaviour
    exactly so any caller that registers this handler observes the same
    "no appearance written" result as Java PDFBox. See
    ``PDSoundAppearanceHandler.java`` (lines 34, 40, 46).
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        # Upstream is an empty no-op (PDSoundAppearanceHandler.java:34).
        # Reproducing that behaviour verbatim — see class docstring.
        return None

    def generate_rollover_appearance(self) -> None:
        # Upstream is an empty no-op (PDSoundAppearanceHandler.java:40).
        return None

    def generate_down_appearance(self) -> None:
        # Upstream is an empty no-op (PDSoundAppearanceHandler.java:46).
        return None


__all__ = ["PDSoundAppearanceHandler"]
