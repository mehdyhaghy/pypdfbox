"""Parity tests for ``pypdfbox.pdmodel.graphics.PDXObject``.

There is no dedicated ``PDXObjectTest.java`` upstream; the Java class is
exercised indirectly through subclass tests (``PDImageXObjectTest``,
``PDFormXObjectTest``). This file targets the upstream public/protected
surface directly so the abstract base class has its own coverage:

- ``getCOSObject()`` returns the *same* underlying ``COSStream`` that
  was passed in.
- ``getStream()`` returns a ``PDStream`` whose backing ``COSStream`` is
  the original.
- The protected constructors stamp ``/Type /XObject`` and ``/Subtype``
  on the underlying dictionary.
- ``PDXObject(PDDocument, COSName)`` (the third upstream protected
  overload) creates a fresh empty stream backed by the document's
  scratch file.
- ``createXObject(null, ...)`` returns ``null`` (upstream
  TODO-marked branch).
- ``createXObject(<non-stream>, ...)`` raises ``IOException`` (mapped
  to ``OSError`` in pypdfbox).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject


def test_get_cos_object_returns_underlying_stream() -> None:
    # Upstream: ``getCOSObject()`` is final and returns
    # ``stream.getCOSObject()`` directly.
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Form"))
    assert xobject.get_cos_object() is stream


def test_get_stream_returns_pd_stream_wrapper() -> None:
    # Upstream: ``getStream()`` is final and returns the wrapped
    # ``PDStream`` instance unchanged.
    pd_stream = PDStream()
    xobject = PDXObject(pd_stream, COSName.get_pdf_name("Image"))
    assert xobject.get_stream() is pd_stream


def test_constructor_stamps_type_and_subtype_on_cos_stream() -> None:
    # Upstream: the protected ``PDXObject(COSStream, COSName)`` constructor
    # writes ``/Type /XObject`` and ``/Subtype <subtype>`` on the
    # underlying dictionary.
    stream = COSStream()
    PDXObject(stream, COSName.get_pdf_name("Form"))
    assert stream.get_name(COSName.TYPE) == "XObject"  # type: ignore[attr-defined]
    assert stream.get_name(COSName.SUBTYPE) == "Form"  # type: ignore[attr-defined]


def test_constructor_with_pd_stream_stamps_type_and_subtype() -> None:
    # Upstream: ``PDXObject(PDStream, COSName)`` — same stamping behavior
    # but the stream argument is a ``PDStream`` wrapper.
    pd_stream = PDStream()
    PDXObject(pd_stream, COSName.get_pdf_name("Image"))
    cos = pd_stream.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "XObject"  # type: ignore[attr-defined]
    assert cos.get_name(COSName.SUBTYPE) == "Image"  # type: ignore[attr-defined]


def test_constructor_with_pd_document_creates_fresh_stream() -> None:
    """Mirrors the upstream third protected constructor:

    ``protected PDXObject(PDDocument document, COSName subtype)``

    ::
        stream = new PDStream(document);
        stream.getCOSObject().setName(COSName.TYPE, COSName.XOBJECT.getName());
        stream.getCOSObject().setName(COSName.SUBTYPE, subtype.getName());
    """
    from pypdfbox.pdmodel.pd_document import PDDocument

    document = PDDocument()
    try:
        xobject = PDXObject(document, COSName.get_pdf_name("Form"))
        cos = xobject.get_cos_object()
        # /Type /XObject + /Subtype /Form must be present.
        assert cos.get_name(COSName.TYPE) == "XObject"  # type: ignore[attr-defined]
        assert cos.get_name(COSName.SUBTYPE) == "Form"  # type: ignore[attr-defined]
        # The stream should be a fresh wrapper, not the document itself.
        assert isinstance(xobject.get_stream(), PDStream)
    finally:
        document.close()


def test_create_x_object_returns_none_for_null_base() -> None:
    # Upstream's TODO-marked branch: ``if (base == null) return null;``
    assert PDXObject.create_x_object(None) is None


def test_create_x_object_non_stream_raises_io_error() -> None:
    # Upstream: ``throw new IOException("Unexpected object type: ...")``.
    # In pypdfbox ``IOException`` is mapped to ``OSError``.
    with pytest.raises(OSError, match="Unexpected object type"):
        PDXObject.create_x_object(COSDictionary())


def test_create_x_object_invalid_subtype_raises_io_error() -> None:
    # Upstream: ``throw new IOException("Invalid XObject Subtype: ...")``.
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Bogus")  # type: ignore[attr-defined]
    with pytest.raises(OSError, match="Invalid XObject Subtype"):
        PDXObject.create_x_object(stream)
