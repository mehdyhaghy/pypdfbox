"""Tests for ``pypdfbox.examples.lucene.lucene_pdf_document``."""
from __future__ import annotations

import pytest

from pypdfbox.examples.lucene.lucene_pdf_document import LucenePDFDocument


def test_set_text_stripper_assigns_attribute() -> None:
    doc = LucenePDFDocument()
    stripper = object()
    doc.set_text_stripper(stripper)  # type: ignore[arg-type]
    assert doc._stripper is stripper


def test_convert_document_raises_not_implemented() -> None:
    doc = LucenePDFDocument()
    with pytest.raises(NotImplementedError):
        doc.convert_document("nonexistent.pdf")


def test_get_document_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        LucenePDFDocument.get_document("nonexistent.pdf")


def test_create_uid_with_explicit_time_is_deterministic() -> None:
    uid = LucenePDFDocument.create_uid("file:///tmp/foo.pdf", 0)
    assert uid.endswith("19700101000000")
    # Path separator should not appear verbatim in the UID for filesystem
    # paths; the helper replaces it with a tab token (the Python port's
    # stand-in for the upstream NUL separator).
    assert "/" not in uid.split("\t")[0] or "file:" in uid


def test_create_uid_without_time_uses_zero_for_missing_path() -> None:
    uid = LucenePDFDocument.create_uid("/no/such/path.pdf")
    # Missing file -> mtime defaults to 0 -> epoch timestamp.
    assert uid.endswith("19700101000000")


def test_time_to_string_format() -> None:
    out = LucenePDFDocument.time_to_string(0)
    assert out == "19700101000000"
    assert len(out) == 14


def test_add_content_raises_not_implemented() -> None:
    doc = LucenePDFDocument()
    with pytest.raises(NotImplementedError):
        doc.add_content(object(), object(), "foo.pdf")


def test_add_field_helpers_are_no_ops() -> None:
    doc = LucenePDFDocument()
    # No-op stubs - just exercising that the surface exists.
    doc.add_keyword_field(object(), "k", "v")
    doc.add_text_field(object(), "k", "v")
    LucenePDFDocument.add_unindexed_field(object(), "k", "v")
    doc.add_unstored_keyword_field(object(), "k", "v")
