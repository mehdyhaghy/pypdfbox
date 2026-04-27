from __future__ import annotations

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.graphics import PDXObject


def test_get_subtype_returns_image() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Image"))
    assert xobject.get_subtype() == "Image"


def test_get_subtype_returns_form() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Form"))
    assert xobject.get_subtype() == "Form"


def test_get_subtype_returns_custom_subtype_name() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("PS"))
    assert xobject.get_subtype() == "PS"


def test_get_metadata_returns_none_when_absent() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Form"))
    assert xobject.get_metadata() is None


def test_get_metadata_returns_pd_metadata_when_present() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Image"))

    metadata_stream = COSStream()
    xobject.get_cos_object().set_item(
        COSName.METADATA,  # type: ignore[attr-defined]
        metadata_stream,
    )

    metadata = xobject.get_metadata()
    assert metadata is not None
    assert isinstance(metadata, PDMetadata)
    assert metadata.get_cos_object() is metadata_stream


def test_set_metadata_round_trip() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Form"))

    metadata = PDMetadata(b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>")
    xobject.set_metadata(metadata)

    fetched = xobject.get_metadata()
    assert fetched is not None
    assert fetched.get_cos_object() is metadata.get_cos_object()


def test_set_metadata_none_removes_key() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Image"))

    metadata = PDMetadata(b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>")
    xobject.set_metadata(metadata)
    assert xobject.get_metadata() is not None

    xobject.set_metadata(None)
    assert xobject.get_metadata() is None
    assert xobject.get_cos_object().get_item(COSName.METADATA) is None  # type: ignore[attr-defined]
