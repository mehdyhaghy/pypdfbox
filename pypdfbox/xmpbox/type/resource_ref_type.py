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
        # Mirror upstream @PropertyType annotations: renditionClass uses
        # RenditionClassType, fromPart/toPart use PartType (all subclass
        # TextType so existing string accessors keep working).
        RENDITION_CLASS: "RenditionClass",
        FROM_PART: "Part",
        TO_PART: "Part",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)
        self.add_namespace(self.get_namespace() or "", self.get_prefered_prefix())

    # --- documentID --------------------------------------------------

    def get_document_id(self) -> str | None:
        return self.get_property_value_as_string(self.DOCUMENT_ID)

    def set_document_id(self, value: str) -> None:
        self.add_simple_property(self.DOCUMENT_ID, value)

    # --- filePath ----------------------------------------------------

    def get_file_path(self) -> str | None:
        return self.get_property_value_as_string(self.FILE_PATH)

    def set_file_path(self, value: str) -> None:
        self.add_simple_property(self.FILE_PATH, value)

    # --- instanceID --------------------------------------------------

    def get_instance_id(self) -> str | None:
        return self.get_property_value_as_string(self.INSTANCE_ID)

    def set_instance_id(self, value: str) -> None:
        self.add_simple_property(self.INSTANCE_ID, value)

    # --- lastModifyDate ----------------------------------------------

    def get_last_modify_date(self) -> datetime | None:
        return self.get_date_property_as_calendar(self.LAST_MODIFY_DATE)

    def set_last_modify_date(self, value: datetime) -> None:
        self.add_simple_property(self.LAST_MODIFY_DATE, value)

    # --- manageUI ----------------------------------------------------

    def get_manage_ui(self) -> str | None:
        return self.get_property_value_as_string(self.MANAGE_UI)

    def set_manage_ui(self, value: str) -> None:
        self.add_simple_property(self.MANAGE_UI, value)

    # --- manageTo ----------------------------------------------------

    def get_manage_to(self) -> str | None:
        return self.get_property_value_as_string(self.MANAGE_TO)

    def set_manage_to(self, value: str) -> None:
        self.add_simple_property(self.MANAGE_TO, value)

    # --- manager -----------------------------------------------------

    def get_manager(self) -> str | None:
        return self.get_property_value_as_string(self.MANAGER)

    def set_manager(self, value: str) -> None:
        self.add_simple_property(self.MANAGER, value)

    # --- managerVariant ---------------------------------------------

    def get_manager_variant(self) -> str | None:
        return self.get_property_value_as_string(self.MANAGER_VARIANT)

    def set_manager_variant(self, value: str) -> None:
        self.add_simple_property(self.MANAGER_VARIANT, value)

    # --- partMapping -------------------------------------------------

    def get_part_mapping(self) -> str | None:
        return self.get_property_value_as_string(self.PART_MAPPING)

    def set_part_mapping(self, value: str) -> None:
        self.add_simple_property(self.PART_MAPPING, value)

    # --- renditionParams --------------------------------------------

    def get_rendition_params(self) -> str | None:
        return self.get_property_value_as_string(self.RENDITION_PARAMS)

    def set_rendition_params(self, value: str) -> None:
        self.add_simple_property(self.RENDITION_PARAMS, value)

    # --- versionID ---------------------------------------------------

    def get_version_id(self) -> str | None:
        return self.get_property_value_as_string(self.VERSION_ID)

    def set_version_id(self, value: str) -> None:
        self.add_simple_property(self.VERSION_ID, value)

    # --- maskMarkers -------------------------------------------------

    def get_mask_markers(self) -> str | None:
        return self.get_property_value_as_string(self.MASK_MARKERS)

    def set_mask_markers(self, value: str) -> None:
        self.add_simple_property(self.MASK_MARKERS, value)

    # --- renditionClass ----------------------------------------------

    def get_rendition_class(self) -> str | None:
        return self.get_property_value_as_string(self.RENDITION_CLASS)

    def set_rendition_class(self, value: str) -> None:
        self.add_simple_property(self.RENDITION_CLASS, value)

    # --- fromPart / toPart -------------------------------------------

    def get_from_part(self) -> str | None:
        return self.get_property_value_as_string(self.FROM_PART)

    def set_from_part(self, value: str) -> None:
        self.add_simple_property(self.FROM_PART, value)

    def get_to_part(self) -> str | None:
        return self.get_property_value_as_string(self.TO_PART)

    def set_to_part(self, value: str) -> None:
        self.add_simple_property(self.TO_PART, value)

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

    def get_alternate_paths_property(self) -> ArrayProperty | None:
        prop = self.get_first_equivalent_property(self.ALTERNATE_PATHS, ArrayProperty)
        if isinstance(prop, ArrayProperty):
            return prop
        return None

    def get_alternate_paths(self) -> list[str] | None:
        seq = self.get_alternate_paths_property()
        if seq is None:
            return None
        return seq.get_elements_as_string()
