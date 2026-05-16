"""Tests for ``Stream.is_xml_metadata_stream`` (wave 1312)."""

from __future__ import annotations

from pypdfbox.cos import COSName, COSStream
from pypdfbox.debugger.streampane.stream import Stream


def test_is_xml_metadata_stream_true_for_xml_subtype() -> None:
    """A stream whose ``/Subtype`` is ``XML`` is an XMP metadata stream."""

    cos = COSStream()
    cos.set_item("Type", COSName.get_pdf_name("Metadata"))
    cos.set_item("Subtype", COSName.get_pdf_name("XML"))
    cos.set_data(b"<x/>")
    assert Stream.is_xml_metadata_stream(cos) is True
    # Private alias preserved for legacy call sites.
    assert Stream._is_xml_metadata_stream(cos) is True  # noqa: SLF001


def test_is_xml_metadata_stream_false_for_missing_or_other_subtype() -> None:
    """Streams without ``/Subtype`` or with a non-XML subtype are not XMP."""

    bare = COSStream()
    bare.set_data(b"hi")
    assert Stream.is_xml_metadata_stream(bare) is False

    image = COSStream()
    image.set_item("Subtype", COSName.get_pdf_name("Image"))
    image.set_data(b"img")
    assert Stream.is_xml_metadata_stream(image) is False
