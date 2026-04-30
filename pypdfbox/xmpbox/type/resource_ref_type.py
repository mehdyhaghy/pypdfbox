from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .array_property import ArrayProperty, Cardinality
from .text_type import TextType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class ResourceRefType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.ResourceRefType``. Represents the
    ``stRef:ResourceRef`` structure used by XMP Media Management to identify a
    referenced resource (``documentID``, ``instanceID``, rendition class, ...).
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/sType/ResourceRef#"
    PREFERRED_PREFIX = "stRef"

    DOCUMENT_ID = "documentID"
    FILE_PATH = "filePath"
    INSTANCE_ID = "instanceID"
    LAST_MODIFY_DATE = "lastModifyDate"
    MANAGE_TO = "manageTo"
    MANAGE_UI = "manageUI"
    MANAGER = "manager"
    MANAGER_VARIANT = "managerVariant"
    PART_MAPPING = "partMapping"
    RENDITION_PARAMS = "renditionParams"
    VERSION_ID = "versionID"
    MASK_MARKERS = "maskMarkers"
    RENDITION_CLASS = "renditionClass"
    FROM_PART = "fromPart"
    TO_PART = "toPart"
    ALTERNATE_PATHS = "alternatePaths"

    _FIELD_TYPES = {
        DOCUMENT_ID: "URI",
        FILE_PATH: "URI",
        INSTANCE_ID: "URI",
        LAST_MODIFY_DATE: "Date",
        MANAGE_TO: "URI",
        MANAGE_UI: "URI",
        MANAGER: "AgentName",
        MANAGER_VARIANT: "Text",
        PART_MAPPING: "Text",
        RENDITION_PARAMS: "Text",
        VERSION_ID: "Text",
        MASK_MARKERS: "Choice",
        RENDITION_CLASS: "Text",
        FROM_PART: "Text",
        TO_PART: "Text",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)
        self.add_namespace(self.get_namespace() or "", self.get_prefered_prefix())

    # --- documentID --------------------------------------------------

    def get_document_id(self) -> str | None:
        return self.get_property_value_as_string(self.DOCUMENT_ID)

    def getDocumentID(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_document_id()

    def set_document_id(self, value: str) -> None:
        self.add_simple_property(self.DOCUMENT_ID, value)

    def setDocumentID(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_document_id(value)

    # --- filePath ----------------------------------------------------

    def get_file_path(self) -> str | None:
        return self.get_property_value_as_string(self.FILE_PATH)

    def getFilePath(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_file_path()

    def set_file_path(self, value: str) -> None:
        self.add_simple_property(self.FILE_PATH, value)

    def setFilePath(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_file_path(value)

    # --- instanceID --------------------------------------------------

    def get_instance_id(self) -> str | None:
        return self.get_property_value_as_string(self.INSTANCE_ID)

    def getInstanceID(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_instance_id()

    def set_instance_id(self, value: str) -> None:
        self.add_simple_property(self.INSTANCE_ID, value)

    def setInstanceID(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_instance_id(value)

    # --- lastModifyDate ----------------------------------------------

    def get_last_modify_date(self) -> datetime | None:
        return self.get_date_property_as_calendar(self.LAST_MODIFY_DATE)

    def getLastModifyDate(self) -> datetime | None:  # noqa: N802 - upstream Java name
        return self.get_last_modify_date()

    def set_last_modify_date(self, value: datetime) -> None:
        self.add_simple_property(self.LAST_MODIFY_DATE, value)

    def setLastModifyDate(self, value: datetime) -> None:  # noqa: N802
        self.set_last_modify_date(value)

    # --- manageUI ----------------------------------------------------

    def get_manage_ui(self) -> str | None:
        return self.get_property_value_as_string(self.MANAGE_UI)

    def getManageUI(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_manage_ui()

    def set_manage_ui(self, value: str) -> None:
        self.add_simple_property(self.MANAGE_UI, value)

    def setManageUI(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_manage_ui(value)

    # --- manageTo ----------------------------------------------------

    def get_manage_to(self) -> str | None:
        return self.get_property_value_as_string(self.MANAGE_TO)

    def getManageTo(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_manage_to()

    def set_manage_to(self, value: str) -> None:
        self.add_simple_property(self.MANAGE_TO, value)

    def setManageTo(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_manage_to(value)

    # --- manager -----------------------------------------------------

    def get_manager(self) -> str | None:
        return self.get_property_value_as_string(self.MANAGER)

    def getManager(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_manager()

    def set_manager(self, value: str) -> None:
        self.add_simple_property(self.MANAGER, value)

    def setManager(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_manager(value)

    # --- managerVariant ---------------------------------------------

    def get_manager_variant(self) -> str | None:
        return self.get_property_value_as_string(self.MANAGER_VARIANT)

    def getManagerVariant(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_manager_variant()

    def set_manager_variant(self, value: str) -> None:
        self.add_simple_property(self.MANAGER_VARIANT, value)

    def setManagerVariant(self, value: str) -> None:  # noqa: N802
        self.set_manager_variant(value)

    # --- partMapping -------------------------------------------------

    def get_part_mapping(self) -> str | None:
        return self.get_property_value_as_string(self.PART_MAPPING)

    def getPartMapping(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_part_mapping()

    def set_part_mapping(self, value: str) -> None:
        self.add_simple_property(self.PART_MAPPING, value)

    def setPartMapping(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_part_mapping(value)

    # --- renditionParams --------------------------------------------

    def get_rendition_params(self) -> str | None:
        return self.get_property_value_as_string(self.RENDITION_PARAMS)

    def getRenditionParams(self) -> str | None:  # noqa: N802
        return self.get_rendition_params()

    def set_rendition_params(self, value: str) -> None:
        self.add_simple_property(self.RENDITION_PARAMS, value)

    def setRenditionParams(self, value: str) -> None:  # noqa: N802
        self.set_rendition_params(value)

    # --- versionID ---------------------------------------------------

    def get_version_id(self) -> str | None:
        return self.get_property_value_as_string(self.VERSION_ID)

    def getVersionID(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_version_id()

    def set_version_id(self, value: str) -> None:
        self.add_simple_property(self.VERSION_ID, value)

    def setVersionID(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_version_id(value)

    # --- maskMarkers -------------------------------------------------

    def get_mask_markers(self) -> str | None:
        return self.get_property_value_as_string(self.MASK_MARKERS)

    def getMaskMarkers(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_mask_markers()

    def set_mask_markers(self, value: str) -> None:
        self.add_simple_property(self.MASK_MARKERS, value)

    def setMaskMarkers(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_mask_markers(value)

    # --- renditionClass ----------------------------------------------

    def get_rendition_class(self) -> str | None:
        return self.get_property_value_as_string(self.RENDITION_CLASS)

    def getRenditionClass(self) -> str | None:  # noqa: N802
        return self.get_rendition_class()

    def set_rendition_class(self, value: str) -> None:
        self.add_simple_property(self.RENDITION_CLASS, value)

    def setRenditionClass(self, value: str) -> None:  # noqa: N802
        self.set_rendition_class(value)

    # --- fromPart / toPart -------------------------------------------

    def get_from_part(self) -> str | None:
        return self.get_property_value_as_string(self.FROM_PART)

    def getFromPart(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_from_part()

    def set_from_part(self, value: str) -> None:
        self.add_simple_property(self.FROM_PART, value)

    def setFromPart(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_from_part(value)

    def get_to_part(self) -> str | None:
        return self.get_property_value_as_string(self.TO_PART)

    def getToPart(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_to_part()

    def set_to_part(self, value: str) -> None:
        self.add_simple_property(self.TO_PART, value)

    def setToPart(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_to_part(value)

    # --- alternatePaths ----------------------------------------------

    def add_alternate_path(self, value: str) -> None:
        seq = self.get_first_equivalent_property(self.ALTERNATE_PATHS, ArrayProperty)
        if not isinstance(seq, ArrayProperty):
            seq = ArrayProperty(
                self._metadata,
                None,
                self.get_prefered_prefix(),
                self.ALTERNATE_PATHS,
                Cardinality.Seq,
            )
            self.add_property(seq)
        seq.add_property(TextType(self._metadata, None, "rdf", "li", value))

    def addAlternatePath(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.add_alternate_path(value)

    def get_alternate_paths_property(self) -> ArrayProperty | None:
        prop = self.get_first_equivalent_property(self.ALTERNATE_PATHS, ArrayProperty)
        if isinstance(prop, ArrayProperty):
            return prop
        return None

    def getAlternatePathsProperty(self) -> ArrayProperty | None:  # noqa: N802
        return self.get_alternate_paths_property()

    def get_alternate_paths(self) -> list[str] | None:
        seq = self.get_alternate_paths_property()
        if seq is None:
            return None
        return seq.get_elements_as_string()

    def getAlternatePaths(self) -> list[str] | None:  # noqa: N802 - upstream Java name
        return self.get_alternate_paths()
