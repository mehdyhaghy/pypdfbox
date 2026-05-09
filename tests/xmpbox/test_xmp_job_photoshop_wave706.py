from __future__ import annotations

from pypdfbox.xmpbox import JobType, PhotoshopSchema, XMPBasicJobTicketSchema, XMPMetadata
from pypdfbox.xmpbox.type.job_type import JobType as TypedJobType


def _metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_lite_job_type_prefix_comparison_hash_and_repr_edges() -> None:
    job = JobType(field_prefix="custom")
    job.set_prefix(None)
    job.set_id("J1")
    job.set_name("Press")

    assert job.get_prefix() == JobType.PREFERRED_PREFIX
    assert job.__eq__(object()) is NotImplemented
    assert hash(job) == hash(("J1", "Press", None))
    assert repr(job) == "JobType(id='J1', name='Press', url=None)"


def test_job_schema_non_list_storage_is_not_treated_as_job_bag() -> None:
    schema = XMPBasicJobTicketSchema(_metadata())
    schema.set_property(XMPBasicJobTicketSchema.JOB_REF, "not-a-bag")

    assert schema.get_jobs() == []
    assert schema.get_jobs_property() == []

    target = JobType()
    target.set_id("missing")
    schema.remove_job(target)
    assert schema.get_property(XMPBasicJobTicketSchema.JOB_REF) == "not-a-bag"

    schema.add_job("J1", "First", "https://example.com/1")
    assert schema.get_property(XMPBasicJobTicketSchema.JOB_REF) == "not-a-bag"


def test_typed_job_accessors_register_custom_prefixes() -> None:
    metadata = _metadata()
    schema = XMPBasicJobTicketSchema(metadata)
    job = TypedJobType(metadata)
    job.set_prefix("customJob")
    job.set_id("J1")

    schema.set_jobs_property([job])
    assert schema.get_namespaces()["customJob"] == TypedJobType.NAMESPACE

    other = TypedJobType(metadata)
    other.set_prefix("otherJob")
    other.set_name("Second")
    schema.add_job_typed(other)

    assert schema.get_namespaces()["otherJob"] == TypedJobType.NAMESPACE
    assert schema.get_property(XMPBasicJobTicketSchema.JOB_REF) == [
        {"id": "J1"},
        {"name": "Second"},
    ]


def test_photoshop_integer_getter_accepts_int_and_text_fallback_containers() -> None:
    schema = PhotoshopSchema(_metadata())

    schema.set_property(PhotoshopSchema.URGENCY, 5)
    assert schema.get_urgency() == 5

    schema.set_property(PhotoshopSchema.URGENCY, [" 6 "])
    assert schema.get_urgency() == 6

    schema.set_property(PhotoshopSchema.URGENCY, {"x-default": "bad"})
    assert schema.get_urgency() is None
