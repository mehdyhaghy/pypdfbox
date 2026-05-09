from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature

_BYTE_RANGE = COSName.get_pdf_name("ByteRange")
_FILTER = COSName.get_pdf_name("Filter")
_SUB_FILTER = COSName.get_pdf_name("SubFilter")


def test_verify_reports_malformed_byte_range_length_from_existing_dictionary() -> None:
    sig = PDSignature()
    sig.get_cos_object().set_item(_BYTE_RANGE, COSArray.of_cos_integers([0, 4]))
    sig.set_contents(b"not inspected")

    result = sig.verify(b"AAAAxxxxBBBB")

    assert result.is_valid is False
    assert result.errors == ["/ByteRange must have 4 entries, got 2"]
    assert result.computed_digest is None


def test_verify_reports_signed_data_extraction_failure_for_negative_range() -> None:
    sig = PDSignature()
    sig.set_byte_range([-1, 4, 8, 4])
    sig.set_contents(b"not inspected")

    result = sig.verify(b"AAAAxxxxBBBB")

    assert result.is_valid is False
    assert result.errors == ["could not extract signed data from document"]
    assert result.computed_digest is None


def test_get_signed_content_raises_for_malformed_byte_range() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 50, 1])

    with pytest.raises(IndexError, match="missing or malformed /ByteRange"):
        sig.get_signed_content(b"AAAAxxxxBBBB")


def test_get_signed_data_rejects_range_start_after_document_end() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 13, 0])

    assert sig.get_signed_data(b"AAAAxxxxBBBB") is None


def test_filter_getters_ignore_wrong_cos_shapes() -> None:
    sig = PDSignature()
    sig.get_cos_object().set_item(_FILTER, COSArray())
    sig.get_cos_object().set_item(_SUB_FILTER, COSArray())

    assert sig.get_filter() is None
    assert sig.get_sub_filter() is None


def test_empty_cert_string_is_still_returned_as_single_certificate() -> None:
    sig = PDSignature()
    sig.get_cos_object().set_item(COSName.get_pdf_name("Cert"), COSString(""))

    assert sig.get_cert() == [""]
