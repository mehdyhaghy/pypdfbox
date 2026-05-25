"""Wave 1397 branch-coverage tests for ``XMPBasicJobTicketSchema``.

Closes False-branch arrows in the typed-Job accessors where the
backing list contains non-dict entries or the typed Job has only a
subset of fields populated:

* ``get_jobs`` 210->209 — non-dict entry in JOB_REF bag is skipped
* ``_dict_to_typed_job`` 249->251 — ID absent, Name+URL present
* ``get_jobs_property`` 287->286 — non-dict entry in JOB_REF bag is skipped
"""

from __future__ import annotations

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type.job_type import JobType as TypedJobType
from pypdfbox.xmpbox.xmp_basic_job_ticket_schema import XMPBasicJobTicketSchema


def _schema() -> XMPBasicJobTicketSchema:
    return XMPBasicJobTicketSchema(XMPMetadata.create_xmp_metadata())


def test_get_jobs_skips_non_dict_entries() -> None:
    """Closes 210->209: a list with a non-dict entry only surfaces
    the dict entries."""
    schema = _schema()
    schema._properties["JobRef"] = [  # noqa: SLF001
        {"id": "job-1", "name": "A", "url": "http://x"},
        "this-should-be-skipped",
        {"id": "job-2", "name": "B", "url": "http://y"},
    ]
    jobs = schema.get_jobs()
    assert jobs is not None
    assert len(jobs) == 2


def test_dict_to_typed_job_with_only_name_and_url() -> None:
    """Closes 249->251: ID absent — only Name + URL populated."""
    schema = _schema()
    job = schema._dict_to_typed_job(  # noqa: SLF001
        {TypedJobType.NAME: "no-id-job", TypedJobType.URL: "http://example.com"}
    )
    assert job.get_id() is None
    assert job.get_name() == "no-id-job"
    assert job.get_url() == "http://example.com"


def test_get_jobs_property_skips_non_dict_entries() -> None:
    """Closes 287->286: a list with a non-dict entry only surfaces
    the dict entries."""
    schema = _schema()
    schema._properties["JobRef"] = [  # noqa: SLF001
        {TypedJobType.ID: "x", TypedJobType.NAME: "Foo"},
        42,
        {TypedJobType.NAME: "Bar"},
    ]
    out = schema.get_jobs_property()
    assert out is not None
    assert len(out) == 2
    assert {j.get_name() for j in out} == {"Foo", "Bar"}
