"""Fluent visible-signature configuration.

Mirrors ``org.apache.pdfbox.pdmodel.interactive.digitalsignature.visible.PDVisibleSigProperties``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/visible/PDVisibleSigProperties.java``).
Setters return ``self`` for chaining, matching the upstream builder
shape (each setter is a no-set bare method-name, e.g. ``signerName``
instead of ``setSignerName``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from .pd_visible_sign_designer import PDVisibleSignDesigner


class PDVisibleSigProperties:
    """Fluent properties bag — used to drive the template build pipeline."""

    def __init__(self) -> None:
        self._signer_name: str | None = None
        self._signer_location: str | None = None
        self._signature_reason: str | None = None
        self._visual_sign_enabled: bool = False
        self._page: int = 0
        self._preferred_size: int = 0
        self._visible_signature: BinaryIO | None = None
        self._pd_visible_signature: PDVisibleSignDesigner | None = None

    def build_signature(self) -> None:
        """Drive the build pipeline. Mirrors ``buildSignature`` (Java line 44)."""
        # Lazy imports to avoid the visible-package import cycle (each
        # of the imported classes pulls this one in transitively).
        from .pd_visible_sig_builder import PDVisibleSigBuilder
        from .pdf_template_creator import PDFTemplateCreator

        builder = PDVisibleSigBuilder()
        creator = PDFTemplateCreator(builder)
        self.set_visible_signature(creator.build_pdf(self.get_pd_visible_signature()))

    def get_signer_name(self) -> str | None:
        return self._signer_name

    def signer_name(self, signer_name: str) -> PDVisibleSigProperties:
        self._signer_name = signer_name
        return self

    def get_signer_location(self) -> str | None:
        return self._signer_location

    def signer_location(self, signer_location: str) -> PDVisibleSigProperties:
        self._signer_location = signer_location
        return self

    def get_signature_reason(self) -> str | None:
        return self._signature_reason

    def signature_reason(self, signature_reason: str) -> PDVisibleSigProperties:
        self._signature_reason = signature_reason
        return self

    def get_page(self) -> int:
        return self._page

    def page(self, page: int) -> PDVisibleSigProperties:
        self._page = page
        return self

    def get_preferred_size(self) -> int:
        return self._preferred_size

    def preferred_size(self, preferred_size: int) -> PDVisibleSigProperties:
        self._preferred_size = preferred_size
        return self

    def is_visual_sign_enabled(self) -> bool:
        return self._visual_sign_enabled

    def visual_sign_enabled(
        self, visual_sign_enabled: bool
    ) -> PDVisibleSigProperties:
        self._visual_sign_enabled = visual_sign_enabled
        return self

    def get_pd_visible_signature(self) -> PDVisibleSignDesigner | None:
        return self._pd_visible_signature

    def set_pd_visible_signature(
        self, pd_visible_signature: PDVisibleSignDesigner
    ) -> PDVisibleSigProperties:
        self._pd_visible_signature = pd_visible_signature
        return self

    def get_visible_signature(self) -> BinaryIO | None:
        return self._visible_signature

    def set_visible_signature(self, visible_signature: BinaryIO | None) -> None:
        self._visible_signature = visible_signature


__all__ = ["PDVisibleSigProperties"]
