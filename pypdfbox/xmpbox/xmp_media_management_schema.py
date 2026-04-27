from __future__ import annotations

from typing import TYPE_CHECKING

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class XMPMediaManagementSchema(XMPSchema):
    """
    Representation of the XMP Media Management schema.

    Ported (subset, read+write path) from
    ``org.apache.xmpbox.schema.XMPMediaManagementSchema`` (PDFBox 3.0). The
    schema tracks document identity, version history, and rendition lineage
    for assets managed by an external DAM. Property local names match upstream
    constants verbatim.

    Cluster #1 ships text-typed accessors for the simple (string) properties:

      * ``DocumentID`` — URN/UUID for the authored document identity.
      * ``InstanceID`` — UUID for *this revision*; rotates on every save.
      * ``OriginalDocumentID`` — UUID for the document before any save-as.
      * ``VersionID`` — version label.
      * ``RenditionClass`` — e.g. ``default``, ``proof``,
        ``thumbnail:format=jpeg``.
      * ``RenditionParams`` — rendition-specific parameters.
      * ``ManageTo`` — URI to the asset-management system.
      * ``ManageUI`` — URI to the management UI.
      * ``Manager`` — asset-management application name.
      * ``ManagerVariant`` — manager build/variant identifier.

    Deferred until the typed ``ResourceRef`` wrapper lands (see cluster #1
    plan): ``DerivedFrom`` (single ``ResourceRef`` struct) and
    ``Ingredients`` (``Bag`` of ``ResourceRef``). Callers needing raw access
    to those properties before the wrapper ships can use the generic
    :meth:`XMPSchema.get_property` accessor.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/mm/"
    PREFERRED_PREFIX = "xmpMM"

    # Local-name constants — names match upstream ``public static final`` fields.
    DOCUMENT_ID = "DocumentID"
    INSTANCE_ID = "InstanceID"
    ORIGINAL_DOCUMENT_ID = "OriginalDocumentID"
    VERSION_ID = "VersionID"
    RENDITION_CLASS = "RenditionClass"
    RENDITION_PARAMS = "RenditionParams"
    MANAGE_TO = "ManageTo"
    MANAGE_UI = "ManageUI"
    MANAGER = "Manager"
    MANAGER_VARIANT = "ManagerVariant"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)

    # --- DocumentID --------------------------------------------------

    def get_document_id(self) -> str | None:
        return self.get_unqualified_text_property_value(self.DOCUMENT_ID)

    def set_document_id(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.DOCUMENT_ID)
            return
        self.set_text_property_value(self.DOCUMENT_ID, value)

    # --- InstanceID --------------------------------------------------

    def get_instance_id(self) -> str | None:
        return self.get_unqualified_text_property_value(self.INSTANCE_ID)

    def set_instance_id(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.INSTANCE_ID)
            return
        self.set_text_property_value(self.INSTANCE_ID, value)

    # --- OriginalDocumentID -----------------------------------------

    def get_original_document_id(self) -> str | None:
        return self.get_unqualified_text_property_value(self.ORIGINAL_DOCUMENT_ID)

    def set_original_document_id(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.ORIGINAL_DOCUMENT_ID)
            return
        self.set_text_property_value(self.ORIGINAL_DOCUMENT_ID, value)

    # --- VersionID ---------------------------------------------------

    def get_version_id(self) -> str | None:
        return self.get_unqualified_text_property_value(self.VERSION_ID)

    def set_version_id(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.VERSION_ID)
            return
        self.set_text_property_value(self.VERSION_ID, value)

    # --- RenditionClass ---------------------------------------------

    def get_rendition_class(self) -> str | None:
        return self.get_unqualified_text_property_value(self.RENDITION_CLASS)

    def set_rendition_class(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.RENDITION_CLASS)
            return
        self.set_text_property_value(self.RENDITION_CLASS, value)

    # --- RenditionParams --------------------------------------------

    def get_rendition_params(self) -> str | None:
        return self.get_unqualified_text_property_value(self.RENDITION_PARAMS)

    def set_rendition_params(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.RENDITION_PARAMS)
            return
        self.set_text_property_value(self.RENDITION_PARAMS, value)

    # --- ManageTo ----------------------------------------------------

    def get_manage_to(self) -> str | None:
        return self.get_unqualified_text_property_value(self.MANAGE_TO)

    def set_manage_to(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.MANAGE_TO)
            return
        self.set_text_property_value(self.MANAGE_TO, value)

    # --- ManageUI ----------------------------------------------------

    def get_manage_ui(self) -> str | None:
        return self.get_unqualified_text_property_value(self.MANAGE_UI)

    def set_manage_ui(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.MANAGE_UI)
            return
        self.set_text_property_value(self.MANAGE_UI, value)

    # --- Manager -----------------------------------------------------

    def get_manager(self) -> str | None:
        return self.get_unqualified_text_property_value(self.MANAGER)

    def set_manager(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.MANAGER)
            return
        self.set_text_property_value(self.MANAGER, value)

    # --- ManagerVariant ---------------------------------------------

    def get_manager_variant(self) -> str | None:
        return self.get_unqualified_text_property_value(self.MANAGER_VARIANT)

    def set_manager_variant(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.MANAGER_VARIANT)
            return
        self.set_text_property_value(self.MANAGER_VARIANT, value)
