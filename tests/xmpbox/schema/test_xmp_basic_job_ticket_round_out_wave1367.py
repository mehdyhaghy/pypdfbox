"""Branch-coverage round-out (wave 1367) for ``XMPBasicJobTicketSchema``.

Pins job round-trip semantics for the lite and Wave-32 typed JobType
helpers, including the dict storage shape, namespace registration on
typed-set, the clear-jobs path, and the singular ``remove_job`` matcher
on missing entries.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.type.job_type import JobType as TypedJobType
from pypdfbox.xmpbox.xmp_basic_job_ticket_schema import (
    JobType as LiteJobType,
)
from pypdfbox.xmpbox.xmp_basic_job_ticket_schema import (
    XMPBasicJobTicketSchema,
)
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


@pytest.fixture()
def schema() -> XMPBasicJobTicketSchema:
    return XMPBasicJobTicketSchema(XMPMetadata.create_xmp_metadata())


def test_add_job_with_string_args_then_get_lite(
    schema: XMPBasicJobTicketSchema,
) -> None:
    schema.add_job("J1", "First job", "http://example.org/j1")
    jobs = schema.get_jobs()
    assert jobs is not None
    assert len(jobs) == 1
    assert jobs[0].get_id() == "J1"
    assert jobs[0].get_name() == "First job"
    assert jobs[0].get_url() == "http://example.org/j1"


def test_get_jobs_returns_none_when_unset(
    schema: XMPBasicJobTicketSchema,
) -> None:
    assert schema.get_jobs() is None


def test_clear_jobs_drops_property(schema: XMPBasicJobTicketSchema) -> None:
    schema.add_job("J1", "name", "http://x")
    schema.clear_jobs()
    assert schema.get_jobs() is None


def test_remove_job_no_match_is_noop(schema: XMPBasicJobTicketSchema) -> None:
    schema.add_job("Existing", "x", "http://x")
    not_there = LiteJobType(schema.get_metadata())
    not_there.set_id("Other")
    schema.remove_job(not_there)
    jobs = schema.get_jobs()
    assert jobs is not None and len(jobs) == 1


def test_add_job_typed_registers_namespace(
    schema: XMPBasicJobTicketSchema,
) -> None:
    job = TypedJobType(schema.get_metadata())
    job.set_id("T1")
    job.set_name("Typed job")
    job.set_url("http://example.org/typed")
    schema.add_job_typed(job)
    # The stJob namespace should be registered on the schema.
    ns = schema.get_namespaces()
    assert TypedJobType.PREFERRED_PREFIX in ns
    assert ns[TypedJobType.PREFERRED_PREFIX] == TypedJobType.NAMESPACE


def test_jobs_round_trip_through_typed_setter(
    schema: XMPBasicJobTicketSchema,
) -> None:
    job_a = TypedJobType(schema.get_metadata())
    job_a.set_id("A")
    job_a.set_name("First")
    job_b = TypedJobType(schema.get_metadata())
    job_b.set_id("B")
    job_b.set_url("http://example.org/b")
    schema.set_jobs_property([job_a, job_b])
    out = schema.get_jobs_property()
    assert out is not None
    assert len(out) == 2
    # Only fields set are populated on round-trip; URL on job_a stays None.
    assert out[0].get_id() == "A"
    assert out[0].get_name() == "First"
    assert out[0].get_url() is None


def test_lite_job_type_equality_and_hash() -> None:
    j1 = LiteJobType()
    j1.set_id("X")
    j2 = LiteJobType()
    j2.set_id("X")
    j3 = LiteJobType()
    j3.set_id("Y")
    assert j1 == j2
    assert j1 != j3
    # Same hash bucket for equal jobs.
    assert hash(j1) == hash(j2)


def test_lite_job_type_as_dict_omits_unset_fields() -> None:
    job = LiteJobType()
    job.set_name("Only name")
    assert job.as_dict() == {"name": "Only name"}
    job.set_id("ID")
    job.set_url("http://u")
    assert job.as_dict() == {"id": "ID", "name": "Only name", "url": "http://u"}


def test_add_job_uses_default_prefix_on_subsequent_adds(
    schema: XMPBasicJobTicketSchema,
) -> None:
    # The first add carries no explicit prefix, so the default is used.
    schema.add_job("J1", "First", "http://j1")
    # Second add without explicit prefix should still pick the default
    # (mirrors upstream "use same prefix for all jobs").
    schema.add_job("J2", "Second", "http://j2")
    jobs = schema.get_jobs()
    assert jobs is not None
    assert [j.get_id() for j in jobs] == ["J1", "J2"]


def test_typed_get_jobs_returns_none_when_unset(
    schema: XMPBasicJobTicketSchema,
) -> None:
    assert schema.get_jobs_property() is None
