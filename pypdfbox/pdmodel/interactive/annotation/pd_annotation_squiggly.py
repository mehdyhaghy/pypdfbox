from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary

from .pd_annotation_text_markup import PDAnnotationTextMarkup

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument

    from .handlers.pd_appearance_handler import PDAppearanceHandler


class PDAnnotationSquiggly(PDAnnotationTextMarkup):
    """``/Subtype /Squiggly`` text markup annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquiggly``.
    """

    SUB_TYPE: str = "Squiggly"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        self._custom_appearance_handler: PDAppearanceHandler | None = None
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- appearance construction ----------

    def set_custom_appearance_handler(
        self, appearance_handler: PDAppearanceHandler | None
    ) -> None:
        """Set the custom appearance handler used by
        :meth:`construct_appearances`.

        Mirrors upstream ``setCustomAppearanceHandler``. Pass ``None`` to
        clear the custom handler and restore the default construction path.
        """
        self._custom_appearance_handler = appearance_handler

    def get_custom_appearance_handler(self) -> PDAppearanceHandler | None:
        """Return the custom appearance handler previously set via
        :meth:`set_custom_appearance_handler`, or ``None`` when the default
        construction path is in use. No upstream getter exists (the field is
        package-private in Java); this is the Pythonic accessor used by
        tests and downstream code that needs to inspect the wired handler.
        """
        return self._custom_appearance_handler

    def construct_appearances(self, document: PDDocument | None = None) -> None:
        """Generate squiggly annotation appearances.

        Mirrors upstream ``constructAppearances()`` and
        ``constructAppearances(PDDocument)`` (``PDAnnotationSquiggly.java``
        lines 66-82). A custom handler, when configured, is invoked exactly
        as upstream does; otherwise the built-in
        :class:`PDSquigglyAppearanceHandler` generates the ``/AP`` streams.
        The lite handler draws the zig-zag directly rather than via a tiling
        pattern (documented divergence — see ``CHANGES.md``).
        """
        if self._custom_appearance_handler is not None:
            self._custom_appearance_handler.generate_appearance_streams()
            return None
        from .handlers.pd_squiggly_appearance_handler import (
            PDSquigglyAppearanceHandler,
        )

        PDSquigglyAppearanceHandler(self, document).generate_appearance_streams()
        return None


__all__ = ["PDAnnotationSquiggly"]
