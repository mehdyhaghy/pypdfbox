from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import AbstractStructuredType
from pypdfbox.xmpbox.type import JobType as StructuredJobType
from pypdfbox.xmpbox.xmp_basic_job_ticket_schema import JobType as LiteJobType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_structured_job_type_is_structured(metadata: XMPMetadata) -> None:
    job = StructuredJobType(metadata)
    assert isinstance(job, AbstractStructuredType)


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    job = StructuredJobType(metadata)
    assert job.get_namespace() == "http://ns.adobe.com/xap/1.0/sType/Job#"
    assert job.get_prefix() == "stJob"


def test_field_prefix_override(metadata: XMPMetadata) -> None:
    job = StructuredJobType(metadata, "myJob")
    assert job.get_prefix() == "myJob"
    assert job.get_prefered_prefix() == "stJob"


def test_initial_fields_none(metadata: XMPMetadata) -> None:
    job = StructuredJobType(metadata)
    assert job.get_id() is None
    assert job.get_name() is None
    assert job.get_url() is None


def test_set_and_get_fields(metadata: XMPMetadata) -> None:
    job = StructuredJobType(metadata)
    job.set_id("j1")
    job.set_name("Print Run")
    job.set_url("http://jobs.example.com/1")
    assert job.get_id() == "j1"
    assert job.get_name() == "Print Run"
    assert job.get_url() == "http://jobs.example.com/1"


def test_namespace_registered_at_construction(metadata: XMPMetadata) -> None:
    job = StructuredJobType(metadata)
    ns_map = job.get_all_namespaces_with_prefix()
    assert ns_map.get("http://ns.adobe.com/xap/1.0/sType/Job#") == "stJob"


def test_lite_class_still_available_via_module() -> None:
    assert LiteJobType.NAMESPACE == "http://ns.adobe.com/xap/1.0/sType/Job#"
    assert LiteJobType.PREFERRED_PREFIX == "stJob"
    assert LiteJobType.ID == "id"
    assert LiteJobType.NAME == "name"
    assert LiteJobType.URL == "url"


def test_field_constants() -> None:
    assert StructuredJobType.ID == "id"
    assert StructuredJobType.NAME == "name"
    assert StructuredJobType.URL == "url"


def test_url_field_is_typed_as_url(metadata: XMPMetadata) -> None:
    """Mirror of upstream ``@PropertyType(type = Types.URL)`` on
    :data:`JobType.URL`: the stored property must be a :class:`URLType`,
    not a plain :class:`TextType`."""
    from pypdfbox.xmpbox.type.url_type import URLType

    job = StructuredJobType(metadata)
    job.set_url("http://jobs.example.com/1")
    prop = job.get_property(StructuredJobType.URL)
    assert isinstance(prop, URLType)


def test_id_and_name_fields_are_typed_as_text(metadata: XMPMetadata) -> None:
    """Mirror of upstream ``@PropertyType(type = Types.Text)`` on
    :data:`JobType.ID` and :data:`JobType.NAME`."""
    from pypdfbox.xmpbox.type.text_type import TextType

    job = StructuredJobType(metadata)
    job.set_id("j1")
    job.set_name("Print Run")
    assert isinstance(job.get_property(StructuredJobType.ID), TextType)
    assert isinstance(job.get_property(StructuredJobType.NAME), TextType)
