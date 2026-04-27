from __future__ import annotations

from pypdfbox.xmpbox import (
    JobType,
    XMPBasicJobTicketSchema,
    XMPMetadata,
)
from pypdfbox.xmpbox.type.job_type import JobType as TypedJobType


def _schema() -> XMPBasicJobTicketSchema:
    return XMPBasicJobTicketSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix_match_upstream() -> None:
    schema = _schema()
    assert XMPBasicJobTicketSchema.NAMESPACE == "http://ns.adobe.com/xap/1.0/bj/"
    assert XMPBasicJobTicketSchema.PREFERRED_PREFIX == "xmpBJ"
    assert schema.get_namespace() == "http://ns.adobe.com/xap/1.0/bj/"
    assert schema.get_prefix() == "xmpBJ"


def test_jobtype_namespace_and_prefix_match_upstream() -> None:
    assert JobType.NAMESPACE == "http://ns.adobe.com/xap/1.0/sType/Job#"
    assert JobType.PREFERRED_PREFIX == "stJob"
    assert JobType.ID == "id"
    assert JobType.NAME == "name"
    assert JobType.URL == "url"


def test_default_jobs_is_none() -> None:
    schema = _schema()
    assert schema.get_jobs() is None
    assert schema.get_property(XMPBasicJobTicketSchema.JOB_REF) is None


def test_jobtype_round_trip_dict() -> None:
    job = JobType()
    job.set_id("J1")
    job.set_name("AnnualReport")
    job.set_url("https://example.com/jobs/J1")
    assert job.get_id() == "J1"
    assert job.get_name() == "AnnualReport"
    assert job.get_url() == "https://example.com/jobs/J1"

    data = job.as_dict()
    assert data == {
        "id": "J1",
        "name": "AnnualReport",
        "url": "https://example.com/jobs/J1",
    }
    rebuilt = JobType.from_dict(data)
    assert rebuilt == job


def test_add_job_appends_dict_entry() -> None:
    schema = _schema()
    schema.add_job("J1", "AnnualReport", "https://example.com/jobs/J1")
    bag = schema.get_property(XMPBasicJobTicketSchema.JOB_REF)
    assert isinstance(bag, list)
    assert bag == [
        {
            "id": "J1",
            "name": "AnnualReport",
            "url": "https://example.com/jobs/J1",
        }
    ]


def test_get_jobs_returns_typed_instances() -> None:
    schema = _schema()
    schema.add_job("J1", "First", "https://example.com/1")
    schema.add_job("J2", "Second", "https://example.com/2")
    jobs = schema.get_jobs()
    assert jobs is not None
    assert len(jobs) == 2
    assert jobs[0].get_id() == "J1"
    assert jobs[0].get_name() == "First"
    assert jobs[0].get_url() == "https://example.com/1"
    assert jobs[1].get_id() == "J2"
    assert jobs[1].get_name() == "Second"
    assert jobs[1].get_url() == "https://example.com/2"


def test_add_job_type_registers_namespace() -> None:
    schema = _schema()
    job = JobType()
    job.set_id("J9")
    job.set_name("Custom")
    job.set_url("https://example.com/9")
    schema.add_job_type(job)

    namespaces = schema.get_namespaces()
    assert namespaces.get("stJob") == "http://ns.adobe.com/xap/1.0/sType/Job#"

    jobs = schema.get_jobs()
    assert jobs is not None
    assert jobs[0] == job


def test_remove_job() -> None:
    schema = _schema()
    schema.add_job("J1", "First", "https://example.com/1")
    schema.add_job("J2", "Second", "https://example.com/2")

    target = JobType()
    target.set_id("J1")
    target.set_name("First")
    target.set_url("https://example.com/1")
    schema.remove_job(target)

    jobs = schema.get_jobs()
    assert jobs is not None
    assert len(jobs) == 1
    assert jobs[0].get_id() == "J2"


def test_clear_jobs_removes_property() -> None:
    schema = _schema()
    schema.add_job("J1", "First", "https://example.com/1")
    schema.clear_jobs()
    assert schema.get_jobs() is None
    assert schema.get_property(XMPBasicJobTicketSchema.JOB_REF) is None


def test_metadata_accessors_install_and_reuse_schema() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    assert metadata.get_basic_job_ticket_schema() is None

    first = metadata.add_xmp_basic_job_ticket_schema()
    assert isinstance(first, XMPBasicJobTicketSchema)
    assert metadata.get_basic_job_ticket_schema() is first

    again = metadata.add_xmp_basic_job_ticket_schema()
    assert again is first

    fresh = metadata.create_and_add_basic_job_ticket_schema()
    assert fresh is not first
    assert isinstance(fresh, XMPBasicJobTicketSchema)


def test_field_prefix_override_is_respected() -> None:
    schema = _schema()
    schema.add_job("J1", "First", "https://example.com/1", field_prefix="customJob")
    namespaces = schema.get_namespaces()
    assert "customJob" in namespaces
    assert namespaces["customJob"] == "http://ns.adobe.com/xap/1.0/sType/Job#"


def test_partial_jobtype_dict_skips_unset_fields() -> None:
    job = JobType()
    job.set_id("only-id")
    data = job.as_dict()
    assert data == {"id": "only-id"}
    rebuilt = JobType.from_dict(data)
    assert rebuilt.get_id() == "only-id"
    assert rebuilt.get_name() is None
    assert rebuilt.get_url() is None


# --- Wave 33: typed structured-Job accessors (round-trip + interop) ----------


def test_get_jobs_property_returns_none_when_unset() -> None:
    schema = _schema()
    assert schema.get_jobs_property() is None


def test_set_and_get_jobs_property_typed_round_trip() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicJobTicketSchema(metadata)

    a = TypedJobType(metadata)
    a.set_id("J1")
    a.set_name("First")
    a.set_url("https://example.com/1")

    b = TypedJobType(metadata)
    b.set_id("J2")
    b.set_name("Second")
    b.set_url("https://example.com/2")

    schema.set_jobs_property([a, b])

    typed = schema.get_jobs_property()
    assert typed is not None
    assert len(typed) == 2
    assert isinstance(typed[0], TypedJobType)
    assert typed[0].get_id() == "J1"
    assert typed[0].get_name() == "First"
    assert typed[0].get_url() == "https://example.com/1"
    assert typed[1].get_id() == "J2"
    assert typed[1].get_name() == "Second"
    assert typed[1].get_url() == "https://example.com/2"


def test_set_jobs_property_replaces_existing_entries() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicJobTicketSchema(metadata)
    schema.add_job("legacy", "legacy-name", "https://example.com/legacy")

    fresh = TypedJobType(metadata)
    fresh.set_id("new")
    fresh.set_name("new-name")
    fresh.set_url("https://example.com/new")
    schema.set_jobs_property([fresh])

    typed = schema.get_jobs_property()
    assert typed is not None
    assert len(typed) == 1
    assert typed[0].get_id() == "new"


def test_add_job_typed_appends_to_existing_bag() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicJobTicketSchema(metadata)
    schema.add_job("J1", "First", "https://example.com/1")

    extra = TypedJobType(metadata)
    extra.set_id("J2")
    extra.set_name("Second")
    extra.set_url("https://example.com/2")
    schema.add_job_typed(extra)

    # both flavours of accessor see the same two entries
    assert schema.get_property(XMPBasicJobTicketSchema.JOB_REF) == [
        {"id": "J1", "name": "First", "url": "https://example.com/1"},
        {"id": "J2", "name": "Second", "url": "https://example.com/2"},
    ]

    typed = schema.get_jobs_property()
    assert typed is not None
    assert [j.get_id() for j in typed] == ["J1", "J2"]

    lite = schema.get_jobs()
    assert lite is not None
    assert [j.get_id() for j in lite] == ["J1", "J2"]


def test_add_job_typed_registers_namespace() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicJobTicketSchema(metadata)
    job = TypedJobType(metadata)
    job.set_id("J9")
    schema.add_job_typed(job)

    namespaces = schema.get_namespaces()
    assert namespaces.get("stJob") == "http://ns.adobe.com/xap/1.0/sType/Job#"


def test_typed_and_lite_accessors_share_storage() -> None:
    """Lite ``add_job`` then read back via typed ``get_jobs_property`` (and v.v.)."""
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicJobTicketSchema(metadata)
    schema.add_job("L1", "lite", "https://example.com/L1")

    typed = schema.get_jobs_property()
    assert typed is not None
    assert typed[0].get_id() == "L1"
    assert typed[0].get_name() == "lite"
    assert typed[0].get_url() == "https://example.com/L1"

    extra = TypedJobType(metadata)
    extra.set_id("T2")
    extra.set_name("typed")
    extra.set_url("https://example.com/T2")
    schema.add_job_typed(extra)

    lite = schema.get_jobs()
    assert lite is not None
    assert [j.get_id() for j in lite] == ["L1", "T2"]


def test_typed_partial_jobtype_skips_unset_fields() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicJobTicketSchema(metadata)

    partial = TypedJobType(metadata)
    partial.set_id("only-id")
    schema.add_job_typed(partial)

    bag = schema.get_property(XMPBasicJobTicketSchema.JOB_REF)
    assert bag == [{"id": "only-id"}]

    typed = schema.get_jobs_property()
    assert typed is not None
    assert typed[0].get_id() == "only-id"
    assert typed[0].get_name() is None
    assert typed[0].get_url() is None
