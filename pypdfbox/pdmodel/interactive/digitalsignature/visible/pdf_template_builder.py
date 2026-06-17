"""Abstract builder protocol for the visible-signature form XObject.

Mirrors ``org.apache.pdfbox.pdmodel.interactive.digitalsignature.visible.PDFTemplateBuilder``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/visible/PDFTemplateBuilder.java``).
The Java upstream is an interface — we use Python ABC semantics so
concrete builders raise on unimplemented hooks rather than silently
no-op.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .pd_visible_sign_designer import PDVisibleSignDesigner
    from .pdf_template_structure import PDFTemplateStructure


class PDFTemplateBuilder(ABC):
    """Builder protocol for assembling the visible-signature template.

    Method names mirror the upstream camelCase → snake_case mapping
    documented in the project's conventions. Each method is a step in the build
    pipeline driven by :class:`PDFTemplateCreator.build_pdf`.
    """

    @abstractmethod
    def create_affine_transform(self, affine_transform: Any) -> None:
        """Mirrors ``createAffineTransform`` (Java line 46)."""

    @abstractmethod
    def create_page(self, properties: PDVisibleSignDesigner) -> None:
        """Mirrors ``createPage`` (Java line 53)."""

    @abstractmethod
    def create_template(self, page: Any) -> None:
        """Mirrors ``createTemplate`` (Java line 61)."""

    @abstractmethod
    def create_acro_form(self, template: Any) -> None:
        """Mirrors ``createAcroForm`` (Java line 68)."""

    @abstractmethod
    def create_signature_field(self, acro_form: Any) -> None:
        """Mirrors ``createSignatureField`` (Java line 76)."""

    @abstractmethod
    def create_signature(
        self,
        pd_signature_field: Any,
        page: Any,
        signer_name: str,
    ) -> None:
        """Mirrors ``createSignature`` (Java line 88)."""

    @abstractmethod
    def create_acro_form_dictionary(
        self, acro_form: Any, signature_field: Any
    ) -> None:
        """Mirrors ``createAcroFormDictionary`` (Java line 98)."""

    @abstractmethod
    def create_signature_rectangle(
        self, signature_field: Any, properties: PDVisibleSignDesigner
    ) -> None:
        """Mirrors ``createSignatureRectangle`` (Java line 108)."""

    @abstractmethod
    def create_proc_set_array(self) -> None:
        """Mirrors ``createProcSetArray`` (Java line 114)."""

    @abstractmethod
    def create_signature_image(self, template: Any, image: Any) -> None:
        """Mirrors ``createSignatureImage`` (Java line 123)."""

    @abstractmethod
    def create_formatter_rectangle(self, params: list[int]) -> None:
        """Mirrors ``createFormatterRectangle`` (Java line 132)."""

    @abstractmethod
    def create_holder_form_stream(self, template: Any) -> None:
        """Mirrors ``createHolderFormStream`` (Java line 139)."""

    @abstractmethod
    def create_holder_form_resources(self) -> None:
        """Mirrors ``createHolderFormResources`` (Java line 144)."""

    @abstractmethod
    def create_holder_form(
        self,
        holder_form_resources: Any,
        holder_form_stream: Any,
        bbox: Any,
    ) -> None:
        """Mirrors ``createHolderForm`` (Java line 153)."""

    @abstractmethod
    def create_appearance_dictionary(
        self, holder_form: Any, signature_field: Any
    ) -> None:
        """Mirrors ``createAppearanceDictionary`` (Java line 163)."""

    @abstractmethod
    def create_inner_form_stream(self, template: Any) -> None:
        """Mirrors ``createInnerFormStream`` (Java line 171)."""

    @abstractmethod
    def create_inner_form_resource(self) -> None:
        """Mirrors ``createInnerFormResource`` (Java line 176)."""

    @abstractmethod
    def create_inner_form(
        self,
        inner_form_resources: Any,
        inner_form_stream: Any,
        bbox: Any,
    ) -> None:
        """Mirrors ``createInnerForm`` (Java line 185)."""

    @abstractmethod
    def insert_inner_form_to_holder_resources(
        self, inner_form: Any, holder_form_resources: Any
    ) -> None:
        """Mirrors ``insertInnerFormToHolderResources`` (Java line 193)."""

    @abstractmethod
    def create_image_form_stream(self, template: Any) -> None:
        """Mirrors ``createImageFormStream`` (Java line 201)."""

    @abstractmethod
    def create_image_form_resources(self) -> None:
        """Mirrors ``createImageFormResources`` (Java line 206)."""

    @abstractmethod
    def create_image_form(
        self,
        image_form_resources: Any,
        inner_form_resource: Any,
        image_form_stream: Any,
        bbox: Any,
        affine_transform: Any,
        img: Any,
    ) -> None:
        """Mirrors ``createImageForm`` (Java line 219)."""

    @abstractmethod
    def create_background_layer_form(
        self, inner_form_resource: Any, bbox: Any
    ) -> None:
        """Mirrors ``createBackgroundLayerForm`` (Java line 230)."""

    @abstractmethod
    def inject_proc_set_array(
        self,
        inner_form: Any,
        page: Any,
        inner_form_resources: Any,
        image_form_resources: Any,
        holder_form_resources: Any,
        proc_set: Any,
    ) -> None:
        """Mirrors ``injectProcSetArray`` (Java line 243)."""

    @abstractmethod
    def inject_appearance_streams(
        self,
        holder_form_stream: Any,
        inner_form_stream: Any,
        image_form_stream: Any,
        image_form_name: Any,
        image_name: Any,
        inner_form_name: Any,
        properties: PDVisibleSignDesigner,
    ) -> None:
        """Mirrors ``injectAppearanceStreams`` (Java line 259)."""

    @abstractmethod
    def create_visual_signature(self, template: Any) -> None:
        """Mirrors ``createVisualSignature`` (Java line 268)."""

    @abstractmethod
    def create_widget_dictionary(
        self, signature_field: Any, holder_form_resources: Any
    ) -> None:
        """Mirrors ``createWidgetDictionary`` (Java line 277)."""

    @abstractmethod
    def get_structure(self) -> PDFTemplateStructure:
        """Mirrors ``getStructure`` (Java line 285)."""

    @abstractmethod
    def close_template(self, template: Any) -> None:
        """Mirrors ``closeTemplate`` (Java line 294)."""


__all__ = ["PDFTemplateBuilder"]
