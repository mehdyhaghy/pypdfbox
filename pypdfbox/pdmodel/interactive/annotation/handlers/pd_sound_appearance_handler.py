from __future__ import annotations

from typing import TYPE_CHECKING

from .pd_abstract_appearance_handler import PDAbstractAppearanceHandler

if TYPE_CHECKING:
    from ....pd_document import PDDocument
    from ..pd_annotation import PDAnnotation


class PDSoundAppearanceHandler(PDAbstractAppearanceHandler):
    """Generate the appearance stream for a sound annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.PDSoundAppearanceHandler``.

    Upstream is a complete no-op — ``generate*Appearance`` methods carry
    ``// TODO to be implemented`` comments. The lite port preserves the
    signatures so callers (and the ``set_custom_appearance_handler``
    plumbing) continue to type-check.
    """

    def __init__(
        self,
        annotation: PDAnnotation,
        document: PDDocument | None = None,
    ) -> None:
        super().__init__(annotation, document)

    def generate_normal_appearance(self) -> None:
        # TODO to be implemented (PDSoundAppearanceHandler.java:34)
        return None

    def generate_rollover_appearance(self) -> None:
        # TODO to be implemented (PDSoundAppearanceHandler.java:40)
        return None

    def generate_down_appearance(self) -> None:
        # TODO to be implemented (PDSoundAppearanceHandler.java:46)
        return None


__all__ = ["PDSoundAppearanceHandler"]
