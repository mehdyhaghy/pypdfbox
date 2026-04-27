"""
Ported upstream tests for ``org.apache.xmpbox.schema.XMPBasicJobTicketSchema``.

Upstream (PDFBox 3.0.x ``xmpbox/src/test/java/org/apache/xmpbox/schema/``) does
**not** ship a dedicated ``XMPBasicJobTicketSchemaTest.java``. Schema coverage
upstream comes via the integration suite that exercises ``XMPMetadata`` end to
end. This file therefore mirrors the smoke-coverage pattern other ported
upstream files use: confirm the structured-type contract upstream's
``@StructuredType`` / ``@PropertyType`` annotations declare for the schema and
its companion ``JobType`` struct.
"""

from __future__ import annotations

from pypdfbox.xmpbox import (
    JobType,
    XMPBasicJobTicketSchema,
    XMPMetadata,
)


def test_structured_type_namespace_and_prefix() -> None:
    # @StructuredType(preferedPrefix = "xmpBJ",
    #                 namespace = "http://ns.adobe.com/xap/1.0/bj/")
    assert XMPBasicJobTicketSchema.PREFERRED_PREFIX == "xmpBJ"
    assert XMPBasicJobTicketSchema.NAMESPACE == "http://ns.adobe.com/xap/1.0/bj/"


def test_job_ref_constant_local_name() -> None:
    # public static final String JOB_REF = "JobRef";
    assert XMPBasicJobTicketSchema.JOB_REF == "JobRef"


def test_jobtype_structured_type_namespace_and_prefix() -> None:
    # @StructuredType(preferedPrefix = "stJob",
    #                 namespace = "http://ns.adobe.com/xap/1.0/sType/Job#")
    assert JobType.PREFERRED_PREFIX == "stJob"
    assert JobType.NAMESPACE == "http://ns.adobe.com/xap/1.0/sType/Job#"


def test_jobtype_field_local_names() -> None:
    # public static final String ID = "id";   NAME = "name";   URL = "url";
    assert JobType.ID == "id"
    assert JobType.NAME == "name"
    assert JobType.URL == "url"


def test_constructor_with_metadata_only() -> None:
    # public XMPBasicJobTicketSchema(XMPMetadata metadata) { this(metadata, null); }
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicJobTicketSchema(metadata)
    assert schema.get_metadata() is metadata
    assert schema.get_namespace() == XMPBasicJobTicketSchema.NAMESPACE
    assert schema.get_prefix() == XMPBasicJobTicketSchema.PREFERRED_PREFIX


def test_constructor_with_metadata_and_own_prefix() -> None:
    # public XMPBasicJobTicketSchema(XMPMetadata metadata, String ownPrefix)
    metadata = XMPMetadata.create_xmp_metadata()
    schema = XMPBasicJobTicketSchema(metadata, "myBJ")
    assert schema.get_prefix() == "myBJ"


def test_add_job_three_arg_overload() -> None:
    # public void addJob(String id, String name, String url)
    schema = XMPBasicJobTicketSchema(XMPMetadata.create_xmp_metadata())
    schema.add_job("J1", "First", "https://example.com/1")
    jobs = schema.get_jobs()
    assert jobs is not None
    assert len(jobs) == 1
    assert jobs[0].get_id() == "J1"
    assert jobs[0].get_name() == "First"
    assert jobs[0].get_url() == "https://example.com/1"


def test_add_job_four_arg_overload_with_field_prefix() -> None:
    # public void addJob(String id, String name, String url, String fieldPrefix)
    schema = XMPBasicJobTicketSchema(XMPMetadata.create_xmp_metadata())
    schema.add_job("J1", "First", "https://example.com/1", "stJob")
    jobs = schema.get_jobs()
    assert jobs is not None
    assert jobs[0].get_id() == "J1"


def test_add_job_with_jobtype_overload() -> None:
    # public void addJob(JobType job)
    schema = XMPBasicJobTicketSchema(XMPMetadata.create_xmp_metadata())
    job = JobType()
    job.set_id("J1")
    job.set_name("First")
    job.set_url("https://example.com/1")
    schema.add_job_type(job)
    jobs = schema.get_jobs()
    assert jobs is not None
    assert jobs[0] == job


def test_get_jobs_returns_none_when_unset() -> None:
    # getJobs() returns null when JOB_REF property is absent
    schema = XMPBasicJobTicketSchema(XMPMetadata.create_xmp_metadata())
    assert schema.get_jobs() is None
