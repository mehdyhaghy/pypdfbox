from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class JobType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.JobType``. Represents the
    ``stJob:Job`` structure used by the XMP Basic Job Ticket schema —
    a triple of ``id`` / ``name`` / ``url`` recording one production job
    that contributed to the asset.

    A lite, dict-backed ``JobType`` lives at
    ``pypdfbox.xmpbox.xmp_basic_job_ticket_schema.JobType`` for the
    cluster-#1 schema's bag-of-dicts storage. That class is preserved
    untouched for back-compat; this structured-type port is the surface
    parsers and writers will move to in the next wave.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/sType/Job#"
    PREFERRED_PREFIX = "stJob"

    ID = "id"
    NAME = "name"
    URL = "url"

    _FIELD_TYPES = {
        ID: "Text",
        NAME: "Text",
        URL: "URL",
    }

    def __init__(
        self,
        metadata: XMPMetadata,
        field_prefix: str | None = None,
    ) -> None:
        super().__init__(metadata, None, field_prefix, None)
        self.add_namespace(self.get_namespace() or "", self.get_prefix())

    def set_id(self, value: str) -> None:
        self.add_simple_property(self.ID, value)

    def set_name(self, value: str) -> None:
        self.add_simple_property(self.NAME, value)

    def set_url(self, value: str) -> None:
        self.add_simple_property(self.URL, value)

    def get_id(self) -> str | None:
        return self.get_property_value_as_string(self.ID)

    def get_name(self) -> str | None:
        return self.get_property_value_as_string(self.NAME)

    def get_url(self) -> str | None:
        return self.get_property_value_as_string(self.URL)
