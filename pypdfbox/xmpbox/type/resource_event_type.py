from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class ResourceEventType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.ResourceEventType``. Represents the
    ``stEvt:ResourceEvent`` structure used by XMP Media Management to record
    actions taken on a resource (``action`` / ``when`` / ``softwareAgent`` /
    ``instanceID`` / ``parameters`` / ``changed``).
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/sType/ResourceEvent#"
    PREFERRED_PREFIX = "stEvt"

    ACTION = "action"
    CHANGED = "changed"
    INSTANCE_ID = "instanceID"
    PARAMETERS = "parameters"
    SOFTWARE_AGENT = "softwareAgent"
    WHEN = "when"

    _FIELD_TYPES = {
        ACTION: "Choice",
        CHANGED: "Text",
        INSTANCE_ID: "GUID",
        PARAMETERS: "Text",
        SOFTWARE_AGENT: "AgentName",
        WHEN: "Date",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)
        self.add_namespace(self.get_namespace() or "", self.get_prefered_prefix())

    def get_instance_id(self) -> str | None:
        return self.get_property_value_as_string(self.INSTANCE_ID)

    def set_instance_id(self, value: str) -> None:
        self.add_simple_property(self.INSTANCE_ID, value)

    def get_software_agent(self) -> str | None:
        return self.get_property_value_as_string(self.SOFTWARE_AGENT)

    def set_software_agent(self, value: str) -> None:
        self.add_simple_property(self.SOFTWARE_AGENT, value)

    def get_when(self) -> datetime | None:
        return self.get_date_property_as_calendar(self.WHEN)

    def set_when(self, value: datetime) -> None:
        self.add_simple_property(self.WHEN, value)

    def get_action(self) -> str | None:
        return self.get_property_value_as_string(self.ACTION)

    def set_action(self, value: str) -> None:
        self.add_simple_property(self.ACTION, value)

    def get_changed(self) -> str | None:
        return self.get_property_value_as_string(self.CHANGED)

    def set_changed(self, value: str) -> None:
        self.add_simple_property(self.CHANGED, value)

    def get_parameters(self) -> str | None:
        return self.get_property_value_as_string(self.PARAMETERS)

    def set_parameters(self, value: str) -> None:
        self.add_simple_property(self.PARAMETERS, value)
