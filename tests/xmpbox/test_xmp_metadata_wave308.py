from __future__ import annotations

from pypdfbox.xmpbox import XMPBasicJobTicketSchema, XMPMetadata


def test_create_and_add_basic_job_ticket_schema_sets_empty_about() -> None:
    metadata = XMPMetadata.create_xmp_metadata()

    schema = metadata.create_and_add_basic_job_ticket_schema()

    assert isinstance(schema, XMPBasicJobTicketSchema)
    assert schema.get_about() == ""
    assert schema.get_about_attribute() is None
    assert metadata.get_basic_job_ticket_schema() is schema
