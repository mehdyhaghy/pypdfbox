from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .date_type import DateType
from .resource_event_type import ResourceEventType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class VersionType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.VersionType``. Represents the
    ``stVer:Version`` structure used by XMP Media Management's
    ``xmpMM:Versions`` Seq — one row per saved version of the document
    (``comments`` / ``event`` / ``modifier`` / ``modifyDate`` / ``version``).

    The ``event`` field nests a :class:`ResourceEventType` describing the
    save action (action / instanceID / when / softwareAgent / parameters /
    changed); upstream models it as a single inline structured property.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/sType/Version#"
    PREFERRED_PREFIX = "stVer"

    COMMENTS = "comments"
    EVENT = "event"
    MODIFIER = "modifier"
    MODIFY_DATE = "modifyDate"
    VERSION = "version"

    _FIELD_TYPES = {
        COMMENTS: "Text",
        # EVENT is a structured ResourceEventType — handled via add_property
        MODIFIER: "ProperName",
        MODIFY_DATE: "Date",
        VERSION: "Text",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)
        self.add_namespace(self.get_namespace() or "", self.get_prefered_prefix())

    # --- comments ----------------------------------------------------

    def get_comments(self) -> str | None:
        return self.get_property_value_as_string(self.COMMENTS)

    def getComments(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_comments()

    def set_comments(self, value: str) -> None:
        self.add_simple_property(self.COMMENTS, value)

    def setComments(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_comments(value)

    # --- event (nested ResourceEventType) ----------------------------

    def get_event(self) -> ResourceEventType | None:
        prop = self.get_first_equivalent_property(self.EVENT, ResourceEventType)
        if isinstance(prop, ResourceEventType):
            return prop
        return None

    def getEvent(self) -> ResourceEventType | None:  # noqa: N802 - upstream Java name
        return self.get_event()

    def set_event(self, value: ResourceEventType) -> None:
        # Mirror upstream: addProperty(value) — caller must have set the
        # property name to "event" beforehand (or we set it here to match
        # upstream's expectation that the field-name slot is occupied).
        value.set_property_name(self.EVENT)
        self.add_property(value)

    def setEvent(self, value: ResourceEventType) -> None:  # noqa: N802 - upstream Java name
        self.set_event(value)

    def get_event_property(self) -> ResourceEventType | None:
        """Return the nested ``ResourceEventType`` carrier or ``None``."""
        prop = self.get_first_equivalent_property(self.EVENT, ResourceEventType)
        return prop if isinstance(prop, ResourceEventType) else None

    # --- modifyDate --------------------------------------------------

    def get_modify_date(self) -> datetime | None:
        return self.get_date_property_as_calendar(self.MODIFY_DATE)

    def get_modify_date_property(self) -> DateType | None:
        """Return the underlying ``DateType`` carrier for ``modifyDate``."""
        prop = self.get_first_equivalent_property(self.MODIFY_DATE, DateType)
        return prop if isinstance(prop, DateType) else None

    def getModifyDate(self) -> datetime | None:  # noqa: N802 - upstream Java name
        return self.get_modify_date()

    def set_modify_date(self, value: datetime) -> None:
        self.add_simple_property(self.MODIFY_DATE, value)

    def setModifyDate(self, value: datetime) -> None:  # noqa: N802 - upstream Java name
        self.set_modify_date(value)

    # --- version -----------------------------------------------------

    def get_version(self) -> str | None:
        return self.get_property_value_as_string(self.VERSION)

    def getVersion(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_version()

    def set_version(self, value: str) -> None:
        self.add_simple_property(self.VERSION, value)

    def setVersion(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_version(value)

    # --- modifier ----------------------------------------------------

    def get_modifier(self) -> str | None:
        return self.get_property_value_as_string(self.MODIFIER)

    def getModifier(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_modifier()

    def set_modifier(self, value: str) -> None:
        self.add_simple_property(self.MODIFIER, value)

    def setModifier(self, value: str) -> None:  # noqa: N802 - upstream Java name
        self.set_modifier(value)
