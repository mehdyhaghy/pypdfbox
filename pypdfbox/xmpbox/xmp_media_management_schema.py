from __future__ import annotations

from typing import TYPE_CHECKING

from .type.agent_name_type import AgentNameType
from .type.array_property import ArrayProperty
from .type.integer_type import IntegerType
from .type.rendition_class_type import RenditionClassType
from .type.resource_event_type import ResourceEventType
from .type.resource_ref_type import ResourceRefType
from .type.text_type import TextType
from .type.uri_type import URIType
from .type.url_type import URLType
from .type.version_type import VersionType
from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class XMPMediaManagementSchema(XMPSchema):
    """
    Representation of the XMP Media Management schema.

    Ported from ``org.apache.xmpbox.schema.XMPMediaManagementSchema`` (PDFBox
    3.0). The schema tracks document identity, version history, and rendition
    lineage for assets managed by an external DAM. Property local names match
    upstream constants verbatim.

    Simple (string-typed) accessors mirror upstream getter/setter triplets:
    ``set_xxx(str)``, ``set_xxx_property(typed)``, ``get_xxx_property()`` and
    ``get_xxx()``.

      * ``DocumentID`` (URI) — URN/UUID for the authored document identity.
      * ``InstanceID`` (URI) — UUID for *this revision*; rotates on save.
      * ``OriginalDocumentID`` (Text) — UUID before any save-as.
      * ``VersionID`` (Text) — version label.
      * ``RenditionClass`` (RenditionClass) — e.g. ``default``, ``proof``.
      * ``RenditionParams`` (Text) — rendition-specific parameters.
      * ``ManageTo`` (URI) — URI to the asset-management system.
      * ``ManageUI`` (URI) — URI to the management UI.
      * ``Manager`` (AgentName) — asset-management application name.
      * ``ManagerVariant`` (Text) — manager build/variant identifier.
      * ``LastURL`` (URL).
      * ``SaveID`` (Integer).

    Structured-type properties:

      * ``DerivedFrom`` — single :class:`ResourceRefType`.
      * ``ManagedFrom`` — single :class:`ResourceRefType`.
      * ``History`` — Seq of :class:`ResourceEventType`.
      * ``Versions`` — Seq of :class:`VersionType` snapshots.
      * ``Ingredients`` — Bag of strings (upstream is ``Bag<Text>``).

    Divergences from upstream:

      * ``Manifest`` (Bag of :class:`ResourceRefType`) and ``RenditionOf``
        (single :class:`ResourceRefType`) are pypdfbox extensions retained
        for callers that targeted earlier waves.
      * Typed ``get_history()`` / ``get_versions()`` return list-of-typed
        instead of upstream's ``List<String>``; upstream string-flavored
        accessors are exposed under
        :meth:`get_history_string_list` / :meth:`get_versions_string_list`.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/mm/"
    PREFERRED_PREFIX = "xmpMM"

    # Local-name constants — names match upstream ``public static final`` fields.
    DOCUMENT_ID = "DocumentID"
    DOCUMENTID = "DocumentID"
    INSTANCE_ID = "InstanceID"
    INSTANCEID = "InstanceID"
    ORIGINAL_DOCUMENT_ID = "OriginalDocumentID"
    ORIGINALDOCUMENTID = "OriginalDocumentID"
    VERSION_ID = "VersionID"
    VERSIONID = "VersionID"
    RENDITION_CLASS = "RenditionClass"
    RENDITIONCLASS = "RenditionClass"
    RENDITION_PARAMS = "RenditionParams"
    RENDITIONPARAMS = "RenditionParams"
    MANAGE_TO = "ManageTo"
    MANAGETO = "ManageTo"
    MANAGE_UI = "ManageUI"
    MANAGEUI = "ManageUI"
    MANAGER = "Manager"
    MANAGER_VARIANT = "ManagerVariant"
    MANAGERVARIANT = "ManagerVariant"
    DERIVED_FROM = "DerivedFrom"
    HISTORY = "History"
    VERSIONS = "Versions"
    MANIFEST = "Manifest"
    INGREDIENTS = "Ingredients"
    LAST_URL = "LastURL"
    SAVE_ID = "SaveID"
    RENDITION_OF = "RenditionOf"
    MANAGED_FROM = "ManagedFrom"

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

    # --- shared helpers ---------------------------------------------

    def _read_text(self, local_name: str) -> str | None:
        """
        Return the string value at ``local_name``, unwrapping a stored
        :class:`TextType` (or subclass) if any. Lets ``get_xxx()`` and
        ``get_xxx_property()`` interoperate after a typed-form
        ``set_xxx_property`` call.
        """
        v = self._properties.get(local_name)
        if isinstance(v, TextType):
            return v.get_string_value()
        return self.get_unqualified_text_property_value(local_name)

    def _get_simple_typed(
        self, local_name: str, type_cls: type
    ) -> object | None:
        """
        Return the property at ``local_name`` if it is already an instance of
        ``type_cls``, otherwise materialise one from the stored ``str`` (so
        ``getXxxProperty()`` works whether the schema was built typed or via
        the parser, which stores raw strings).
        """
        v = self._properties.get(local_name)
        if v is None:
            return None
        if isinstance(v, type_cls):
            return v
        if isinstance(v, str):
            try:
                return type_cls(
                    self._metadata, self._namespace, self._prefix, local_name, v
                )
            # TextType/URLType accept any str; this guard is parity scaffolding
            # for subclasses where the constructor can reject the value.
            except (TypeError, ValueError):  # pragma: no cover
                return None  # pragma: no cover
        return None

    # --- DocumentID --------------------------------------------------

    def get_document_id(self) -> str | None:
        return self._read_text(self.DOCUMENT_ID)

    def set_document_id(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.DOCUMENT_ID)
            return
        self.set_text_property_value(self.DOCUMENT_ID, value)

    def set_document_id_property(self, prop: URIType | None) -> None:
        """Mirror of upstream ``setDocumentIDProperty(URIType)``."""
        if prop is None:
            self.remove_property(self.DOCUMENT_ID)
            return
        self._properties[self.DOCUMENT_ID] = prop

    def get_document_id_property(self) -> TextType | None:
        """Mirror of upstream ``getDocumentIDProperty()`` — returns TextType."""
        return self._get_simple_typed(self.DOCUMENT_ID, TextType)  # type: ignore[return-value]

    # --- InstanceID --------------------------------------------------

    def get_instance_id(self) -> str | None:
        return self._read_text(self.INSTANCE_ID)

    def set_instance_id(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.INSTANCE_ID)
            return
        self.set_text_property_value(self.INSTANCE_ID, value)

    def set_instance_id_property(self, prop: URIType | None) -> None:
        """Mirror of upstream ``setInstanceIDProperty(URIType)``."""
        if prop is None:
            self.remove_property(self.INSTANCE_ID)
            return
        self._properties[self.INSTANCE_ID] = prop

    def get_instance_id_property(self) -> TextType | None:
        """Mirror of upstream ``getInstanceIDProperty()`` — returns TextType."""
        return self._get_simple_typed(self.INSTANCE_ID, TextType)  # type: ignore[return-value]

    # --- OriginalDocumentID -----------------------------------------

    def get_original_document_id(self) -> str | None:
        return self._read_text(self.ORIGINAL_DOCUMENT_ID)

    def set_original_document_id(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.ORIGINAL_DOCUMENT_ID)
            return
        self.set_text_property_value(self.ORIGINAL_DOCUMENT_ID, value)

    def set_original_document_id_property(self, prop: TextType | None) -> None:
        """Mirror of upstream ``setOriginalDocumentIDProperty(TextType)``."""
        if prop is None:
            self.remove_property(self.ORIGINAL_DOCUMENT_ID)
            return
        self._properties[self.ORIGINAL_DOCUMENT_ID] = prop

    def get_original_document_id_property(self) -> TextType | None:
        """Mirror of upstream ``getOriginalDocumentIDProperty()``."""
        return self._get_simple_typed(self.ORIGINAL_DOCUMENT_ID, TextType)  # type: ignore[return-value]

    # --- VersionID ---------------------------------------------------

    def get_version_id(self) -> str | None:
        return self._read_text(self.VERSION_ID)

    def set_version_id(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.VERSION_ID)
            return
        self.set_text_property_value(self.VERSION_ID, value)

    def set_version_id_property(self, prop: TextType | None) -> None:
        """Mirror of upstream ``setVersionIDProperty(TextType)``."""
        if prop is None:
            self.remove_property(self.VERSION_ID)
            return
        self._properties[self.VERSION_ID] = prop

    def get_version_id_property(self) -> TextType | None:
        """Mirror of upstream ``getVersionIDProperty()``."""
        return self._get_simple_typed(self.VERSION_ID, TextType)  # type: ignore[return-value]

    # --- RenditionClass ---------------------------------------------

    def get_rendition_class(self) -> str | None:
        return self._read_text(self.RENDITION_CLASS)

    def set_rendition_class(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.RENDITION_CLASS)
            return
        self.set_text_property_value(self.RENDITION_CLASS, value)

    def set_rendition_class_property(
        self, prop: RenditionClassType | None
    ) -> None:
        """Mirror of upstream ``setRenditionClassProperty(RenditionClassType)``."""
        if prop is None:
            self.remove_property(self.RENDITION_CLASS)
            return
        self._properties[self.RENDITION_CLASS] = prop

    def get_rendition_class_property(self) -> TextType | None:
        """Mirror of upstream ``getRenditionClassProperty()``."""
        return self._get_simple_typed(self.RENDITION_CLASS, TextType)  # type: ignore[return-value]

    # --- RenditionParams --------------------------------------------

    def get_rendition_params(self) -> str | None:
        return self._read_text(self.RENDITION_PARAMS)

    def set_rendition_params(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.RENDITION_PARAMS)
            return
        self.set_text_property_value(self.RENDITION_PARAMS, value)

    def set_rendition_params_property(self, prop: TextType | None) -> None:
        """Mirror of upstream ``setRenditionParamsProperty(TextType)``."""
        if prop is None:
            self.remove_property(self.RENDITION_PARAMS)
            return
        self._properties[self.RENDITION_PARAMS] = prop

    def get_rendition_params_property(self) -> TextType | None:
        """Mirror of upstream ``getRenditionParamsProperty()``."""
        return self._get_simple_typed(self.RENDITION_PARAMS, TextType)  # type: ignore[return-value]

    # --- ManageTo ----------------------------------------------------

    def get_manage_to(self) -> str | None:
        return self._read_text(self.MANAGE_TO)

    def set_manage_to(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.MANAGE_TO)
            return
        self.set_text_property_value(self.MANAGE_TO, value)

    def set_manage_to_property(self, prop: URIType | None) -> None:
        """Mirror of upstream ``setManageToProperty(URIType)``."""
        if prop is None:
            self.remove_property(self.MANAGE_TO)
            return
        self._properties[self.MANAGE_TO] = prop

    def get_manage_to_property(self) -> TextType | None:
        """Mirror of upstream ``getManageToProperty()``."""
        return self._get_simple_typed(self.MANAGE_TO, TextType)  # type: ignore[return-value]

    # --- ManageUI ----------------------------------------------------

    def get_manage_ui(self) -> str | None:
        return self._read_text(self.MANAGE_UI)

    def set_manage_ui(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.MANAGE_UI)
            return
        self.set_text_property_value(self.MANAGE_UI, value)

    def set_manage_ui_property(self, prop: URIType | None) -> None:
        """Mirror of upstream ``setManageUIProperty(URIType)``."""
        if prop is None:
            self.remove_property(self.MANAGE_UI)
            return
        self._properties[self.MANAGE_UI] = prop

    def get_manage_ui_property(self) -> TextType | None:
        """Mirror of upstream ``getManageUIProperty()``."""
        return self._get_simple_typed(self.MANAGE_UI, TextType)  # type: ignore[return-value]

    # --- Manager -----------------------------------------------------

    def get_manager(self) -> str | None:
        return self._read_text(self.MANAGER)

    def set_manager(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.MANAGER)
            return
        self.set_text_property_value(self.MANAGER, value)

    def set_manager_property(self, prop: AgentNameType | None) -> None:
        """Mirror of upstream ``setManagerProperty(AgentNameType)``."""
        if prop is None:
            self.remove_property(self.MANAGER)
            return
        self._properties[self.MANAGER] = prop

    def get_manager_property(self) -> TextType | None:
        """Mirror of upstream ``getManagerProperty()``."""
        return self._get_simple_typed(self.MANAGER, TextType)  # type: ignore[return-value]

    # --- ManagerVariant ---------------------------------------------

    def get_manager_variant(self) -> str | None:
        return self._read_text(self.MANAGER_VARIANT)

    def set_manager_variant(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.MANAGER_VARIANT)
            return
        self.set_text_property_value(self.MANAGER_VARIANT, value)

    def set_manager_variant_property(self, prop: TextType | None) -> None:
        """Mirror of upstream ``setManagerVariantProperty(TextType)``."""
        if prop is None:
            self.remove_property(self.MANAGER_VARIANT)
            return
        self._properties[self.MANAGER_VARIANT] = prop

    def get_manager_variant_property(self) -> TextType | None:
        """Mirror of upstream ``getManagerVariantProperty()``."""
        return self._get_simple_typed(self.MANAGER_VARIANT, TextType)  # type: ignore[return-value]

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

    def set_derived_from_property(self, ref: ResourceRefType | None) -> None:
        """Mirror upstream ``setDerivedFromProperty(ResourceRefType)``."""
        self.set_derived_from(ref)

    def get_derived_from_property(self) -> ResourceRefType | None:
        """Mirror upstream ``getDerivedFromProperty()``."""
        return self.get_derived_from()

    def get_resource_ref_property(self) -> ResourceRefType | None:
        """
        Mirror of upstream ``getResourceRefProperty()`` for ``DerivedFrom``.

        Upstream marks this method ``@Deprecated`` in favor of
        :meth:`get_derived_from_property`.
        """
        return self.get_derived_from()

    # --- History (Seq of ResourceEvent) -----------------------------

    def add_history(self, event: ResourceEventType | str) -> None:
        """
        Append ``event`` to the ``History`` Seq.

        Mirrors upstream ``addHistory(String)`` when given a string (stored as
        a Seq value via :meth:`add_unqualified_sequence_value`); typed
        :class:`ResourceEventType` callers are also supported (pypdfbox
        extension).
        """
        if isinstance(event, str):
            self.add_unqualified_sequence_value(self.HISTORY, event)
            return
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

        Diverges from upstream ``getHistory()`` (which is itself
        ``@Deprecated`` and returns ``List<String>``); use
        :meth:`get_history_string_list` for the upstream-flavored accessor.
        """
        v = self._properties.get(self.HISTORY)
        if v is None:
            return None
        if not isinstance(v, list):
            v = [v]
        return [item for item in v if isinstance(item, ResourceEventType)]

    def get_history_string_list(self) -> list[str] | None:
        """Mirror of upstream (deprecated) ``getHistory()``."""
        return self.get_unqualified_sequence_value_list(self.HISTORY)

    def get_history_property(self) -> ArrayProperty | None:
        """Mirror of upstream ``getHistoryProperty()``."""
        v = self._properties.get(self.HISTORY)
        if isinstance(v, ArrayProperty):
            return v
        return None

    # --- Versions (Seq of Version) ----------------------------------

    def add_version(self, version: VersionType) -> None:
        """Append ``version`` (typed) to the ``Versions`` Seq."""
        existing = self._properties.get(self.VERSIONS)
        if not isinstance(existing, list):
            existing = []
            self._properties[self.VERSIONS] = existing
        existing.append(version)

    def add_versions(self, value: str) -> None:
        """
        Append a string ``value`` to the ``Versions`` array. Mirrors upstream
        ``addVersions(String)`` which calls ``addQualifiedBagValue``.
        """
        self.add_qualified_bag_value(self.VERSIONS, value)

    def get_versions(self) -> list[VersionType] | None:
        """
        Return the ``Versions`` Seq as a list of :class:`VersionType`
        instances, or ``None`` when absent. Untyped entries are skipped.

        Diverges from upstream ``getVersions()`` (returns ``List<String>``);
        use :meth:`get_versions_string_list` for the upstream-flavored
        accessor.
        """
        v = self._properties.get(self.VERSIONS)
        if v is None:
            return None
        if not isinstance(v, list):
            v = [v]
        return [item for item in v if isinstance(item, VersionType)]

    def get_versions_string_list(self) -> list[str] | None:
        """Mirror of upstream ``getVersions()``."""
        return self.get_unqualified_bag_value_list(self.VERSIONS)

    def get_versions_property(self) -> ArrayProperty | None:
        """Mirror of upstream ``getVersionsProperty()``."""
        v = self._properties.get(self.VERSIONS)
        if isinstance(v, ArrayProperty):
            return v
        return None

    # --- Manifest (Bag of ResourceRef) — pypdfbox extension ---------

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

    # --- LastURL -----------------------------------------------------

    def get_last_url(self) -> str | None:
        """Mirror of upstream ``getLastURL()``."""
        return self._read_text(self.LAST_URL)

    def set_last_url(self, value: str | None) -> None:
        """Mirror of upstream ``setLastURL(String)``."""
        if value is None:
            self.remove_property(self.LAST_URL)
            return
        self.set_text_property_value(self.LAST_URL, value)

    def set_last_url_property(self, prop: URLType | None) -> None:
        """Mirror of upstream ``setLastURLProperty(URLType)``."""
        if prop is None:
            self.remove_property(self.LAST_URL)
            return
        self._properties[self.LAST_URL] = prop

    def get_last_url_property(self) -> URLType | None:
        """Mirror of upstream ``getLastURLProperty()``."""
        return self._get_simple_typed(self.LAST_URL, URLType)  # type: ignore[return-value]

    # --- SaveID (Integer) -------------------------------------------

    def get_save_id(self) -> int | None:
        """Mirror of upstream ``getSaveID()``."""
        v = self._properties.get(self.SAVE_ID)
        if isinstance(v, IntegerType):
            return v.get_value()
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v.strip())
            except ValueError:
                return None
        return None

    def set_save_id(self, value: int | str | None) -> None:
        """Mirror of upstream ``setSaveId(Integer)``."""
        if value is None:
            self.remove_property(self.SAVE_ID)
            return
        prop = IntegerType(
            self._metadata, self._namespace, self._prefix, self.SAVE_ID, value
        )
        self._properties[self.SAVE_ID] = prop

    def get_save_id_property(self) -> IntegerType | None:
        """Mirror of upstream ``getSaveIDProperty()``."""
        v = self._properties.get(self.SAVE_ID)
        if isinstance(v, IntegerType):
            return v
        if isinstance(v, bool):
            return None
        if isinstance(v, int | str):
            try:
                return IntegerType(
                    self._metadata, self._namespace, self._prefix, self.SAVE_ID, v
                )
            except ValueError:
                return None
        return None

    def set_save_id_property(self, value: IntegerType | None) -> None:
        """Mirror of upstream ``setSaveIDProperty(IntegerType)``."""
        if value is None:
            self.remove_property(self.SAVE_ID)
            return
        self._properties[self.SAVE_ID] = value

    # --- RenditionOf (single ResourceRef) — pypdfbox extension ------

    def get_rendition_of(self) -> ResourceRefType | None:
        v = self._properties.get(self.RENDITION_OF)
        if isinstance(v, ResourceRefType):
            return v
        return None

    def set_rendition_of(self, ref: ResourceRefType | None) -> None:
        if ref is None:
            self.remove_property(self.RENDITION_OF)
            return
        self.set_property(self.RENDITION_OF, ref)

    # --- ManagedFrom (single ResourceRef) ---------------------------

    def get_managed_from(self) -> ResourceRefType | None:
        """Mirror of upstream ``getManagedFromProperty()``."""
        v = self._properties.get(self.MANAGED_FROM)
        if isinstance(v, ResourceRefType):
            return v
        return None

    def get_managed_from_property(self) -> ResourceRefType | None:
        """Mirror of upstream ``getManagedFromProperty()``."""
        return self.get_managed_from()

    def set_managed_from(self, ref: ResourceRefType | None) -> None:
        """Mirror of upstream ``setManagedFromProperty(ResourceRefType)``."""
        if ref is None:
            self.remove_property(self.MANAGED_FROM)
            return
        self.set_property(self.MANAGED_FROM, ref)

    def set_managed_from_property(self, ref: ResourceRefType | None) -> None:
        """Mirror of upstream ``setManagedFromProperty(ResourceRefType)``."""
        self.set_managed_from(ref)

    # --- Ingredients (Bag of ResourceRef) ---------------------------

    def add_ingredient(self, ref: ResourceRefType) -> None:
        """Append ``ref`` (typed) to the ``Ingredients`` Bag (pypdfbox extension)."""
        existing = self._properties.get(self.INGREDIENTS)
        if not isinstance(existing, list):
            existing = []
            self._properties[self.INGREDIENTS] = existing
        existing.append(ref)

    def add_ingredients(self, value: str) -> None:
        """Mirror of upstream ``addIngredients(String)`` — appends a string."""
        self.add_qualified_bag_value(self.INGREDIENTS, value)

    def get_ingredients(self) -> list[ResourceRefType] | None:
        """
        Return ``Ingredients`` as a list of typed :class:`ResourceRefType`,
        or ``None`` when absent. Untyped (string) entries are skipped.

        Diverges from upstream ``getIngredients()`` (returns ``List<String>``);
        use :meth:`get_ingredients_string_list` for the upstream-flavored
        accessor.
        """
        v = self._properties.get(self.INGREDIENTS)
        if v is None:
            return None
        if not isinstance(v, list):
            v = [v]
        return [item for item in v if isinstance(item, ResourceRefType)]

    def get_ingredients_string_list(self) -> list[str] | None:
        """Mirror of upstream ``getIngredients()``."""
        return self.get_unqualified_bag_value_list(self.INGREDIENTS)

    def get_ingredients_property(self) -> ArrayProperty | None:
        """Mirror of upstream ``getIngredientsProperty()``."""
        v = self._properties.get(self.INGREDIENTS)
        if isinstance(v, ArrayProperty):
            return v
        return None
