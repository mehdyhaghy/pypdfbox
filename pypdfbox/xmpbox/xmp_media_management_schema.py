from __future__ import annotations

from typing import TYPE_CHECKING

from .type.resource_event_type import ResourceEventType
from .type.resource_ref_type import ResourceRefType
from .type.version_type import VersionType
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

    Wave 40 round-out adds typed accessors for the structured-type
    properties:

      * ``DerivedFrom`` — single :class:`ResourceRefType` struct.
      * ``History`` — ordered ``Seq`` of :class:`ResourceEventType` (one
        per save / publish / convert action).
      * ``Versions`` — ordered ``Seq`` of :class:`VersionType` snapshots
        recording version labels, modifiers, comments, and save events.
      * ``Manifest`` — unordered ``Bag`` of :class:`ResourceRefType`
        recording the source ingredients of the asset.
      * ``Ingredients`` — alias for ``Manifest`` in older XMP spec drafts;
        retained as a separate Bag of ``ResourceRefType`` for spec parity.

    The cluster-#1 raw-property pass-through (`get_property` /
    `set_property`) continues to work for callers that haven't migrated to
    typed accessors.
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
    DERIVED_FROM = "DerivedFrom"
    HISTORY = "History"
    VERSIONS = "Versions"
    MANIFEST = "Manifest"
    INGREDIENTS = "Ingredients"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)
        # Pre-register the structured-type sub-namespaces so callers serialising
        # DerivedFrom / History / Manifest get the right xmlns declarations on
        # the surrounding rdf:Description element.
        self.add_namespace(ResourceRefType.PREFERRED_PREFIX, ResourceRefType.NAMESPACE)
        self.add_namespace(
            ResourceEventType.PREFERRED_PREFIX, ResourceEventType.NAMESPACE
        )
        self.add_namespace(VersionType.PREFERRED_PREFIX, VersionType.NAMESPACE)

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

    # --- DerivedFrom (single ResourceRef) ---------------------------

    def get_derived_from(self) -> ResourceRefType | None:
        """
        Return the ``DerivedFrom`` property as a typed
        :class:`ResourceRefType`, or ``None`` if absent or stored in another
        shape. Callers wanting raw access can fall back to
        :meth:`get_property`.
        """
        v = self._properties.get(self.DERIVED_FROM)
        if isinstance(v, ResourceRefType):
            return v
        return None

    def set_derived_from(self, ref: ResourceRefType | None) -> None:
        if ref is None:
            self.remove_property(self.DERIVED_FROM)
            return
        self.set_property(self.DERIVED_FROM, ref)

    # --- History (Seq of ResourceEvent) -----------------------------

    def add_history(self, event: ResourceEventType) -> None:
        """Append ``event`` to the ``History`` Seq."""
        existing = self._properties.get(self.HISTORY)
        if not isinstance(existing, list):
            existing = []
            self._properties[self.HISTORY] = existing
        existing.append(event)

    def get_history(self) -> list[ResourceEventType] | None:
        """
        Return the ``History`` Seq as a list of :class:`ResourceEventType`
        instances, or ``None`` when absent. Untyped (string / dict) entries
        are skipped.
        """
        v = self._properties.get(self.HISTORY)
        if v is None:
            return None
        if not isinstance(v, list):
            v = [v]
        return [item for item in v if isinstance(item, ResourceEventType)]

    # --- Versions (Seq of Version) ----------------------------------

    def add_version(self, version: VersionType) -> None:
        """Append ``version`` to the ``Versions`` Seq."""
        existing = self._properties.get(self.VERSIONS)
        if not isinstance(existing, list):
            existing = []
            self._properties[self.VERSIONS] = existing
        existing.append(version)

    def get_versions(self) -> list[VersionType] | None:
        """
        Return the ``Versions`` Seq as a list of :class:`VersionType`
        instances, or ``None`` when absent. Untyped entries are skipped.
        """
        v = self._properties.get(self.VERSIONS)
        if v is None:
            return None
        if not isinstance(v, list):
            v = [v]
        return [item for item in v if isinstance(item, VersionType)]

    # --- Manifest (Bag of ResourceRef) ------------------------------

    def add_manifest(self, ref: ResourceRefType) -> None:
        """Append ``ref`` to the ``Manifest`` Bag."""
        existing = self._properties.get(self.MANIFEST)
        if not isinstance(existing, list):
            existing = []
            self._properties[self.MANIFEST] = existing
        existing.append(ref)

    def get_manifest(self) -> list[ResourceRefType] | None:
        v = self._properties.get(self.MANIFEST)
        if v is None:
            return None
        if not isinstance(v, list):
            v = [v]
        return [item for item in v if isinstance(item, ResourceRefType)]

    # --- Ingredients (Bag of ResourceRef) ---------------------------

    def add_ingredient(self, ref: ResourceRefType) -> None:
        """Append ``ref`` to the ``Ingredients`` Bag."""
        existing = self._properties.get(self.INGREDIENTS)
        if not isinstance(existing, list):
            existing = []
            self._properties[self.INGREDIENTS] = existing
        existing.append(ref)

    def get_ingredients(self) -> list[ResourceRefType] | None:
        v = self._properties.get(self.INGREDIENTS)
        if v is None:
            return None
        if not isinstance(v, list):
            v = [v]
        return [item for item in v if isinstance(item, ResourceRefType)]
