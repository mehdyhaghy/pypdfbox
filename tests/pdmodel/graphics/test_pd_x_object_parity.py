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


def test_get_sub_type_alias_matches_get_subtype() -> None:
    # Mechanical snake_case translation of upstream ``getSubType()``.
    # Both spellings must remain live and agree.
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Image"))
    assert xobject.get_sub_type() == xobject.get_subtype() == "Image"


def test_get_sub_type_returns_none_when_subtype_missing() -> None:
    # ``PDXObject`` without a stamped /Subtype (constructed indirectly).
    stream = COSStream()
    # Drop the /Subtype entry to simulate a malformed stream.
    xobject = PDXObject(stream, COSName.get_pdf_name("Form"))
    stream.remove_item(COSName.SUBTYPE)  # type: ignore[attr-defined]
    assert xobject.get_sub_type() is None
    assert xobject.get_subtype() is None


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


def test_eq_uses_backing_stream_identity() -> None:
    stream = COSStream()
    a = PDXObject(stream, COSName.get_pdf_name("Image"))
    b = PDXObject(stream, COSName.get_pdf_name("Image"))
    assert a == b
    assert hash(a) == hash(b)


def test_eq_distinguishes_separate_streams() -> None:
    a = PDXObject(COSStream(), COSName.get_pdf_name("Image"))
    b = PDXObject(COSStream(), COSName.get_pdf_name("Image"))
    assert a != b


def test_eq_returns_notimplemented_for_other_types() -> None:
    a = PDXObject(COSStream(), COSName.get_pdf_name("Image"))
    assert (a == "not an x-object") is False


def test_repr_includes_subtype() -> None:
    a = PDXObject(COSStream(), COSName.get_pdf_name("Form"))
    text = repr(a)
    assert "Form" in text
    assert "PDXObject" in text
