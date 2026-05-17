"""Wave 1341 coverage-boost tests for :class:`FDFDocument`.

Targets the remaining low-traffic branches:

* :meth:`set_catalog` with a trailer-less :class:`COSDocument` (lines
  147-149) — synthesises a fresh COSDocument so the trailer is None
  on entry.
* :meth:`set_xfdf` Element overload (line 222), bytes/bytearray
  overload (lines 223-226), and the TypeError fallback when given
  something the dispatch can't classify (line 228).
* :meth:`close` exercising a non-None ``_fdf_source`` whose
  ``close()`` raises — proves the swallow-and-log compatibility hook
  (lines 295-301).
"""

from __future__ import annotations

import io
from xml.dom.minidom import parseString

import pytest

from pypdfbox.cos import COSDocument
from pypdfbox.pdmodel.fdf.fdf_catalog import FDFCatalog
from pypdfbox.pdmodel.fdf.fdf_document import FDFDocument


def test_set_catalog_creates_trailer_when_missing() -> None:
    """If the underlying :class:`COSDocument` has no trailer,
    :meth:`set_catalog` synthesises one before wiring ``/Root``.
    Exercises the ``trailer is None`` branch (lines 147-149)."""
    doc = COSDocument()
    # COSDocument starts with no trailer; FDFDocument should accept it.
    assert doc.get_trailer() is None
    fdf = FDFDocument(doc)
    try:
        catalog = FDFCatalog()
        fdf.set_catalog(catalog)
        trailer = fdf.get_document().get_trailer()
        assert trailer is not None
        # Sanity: /Root indirects the same dictionary the catalog wraps.
        root = trailer.get_dictionary_object("Root")
        assert root is catalog.get_cos_object()
    finally:
        fdf.close()


def test_set_xfdf_accepts_element() -> None:
    """:meth:`set_xfdf` accepts a bare :class:`xml.dom.minidom.Element`
    (line 222 — ``isinstance(xfdf, Element)`` branch)."""
    sample = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<xfdf xmlns="http://ns.adobe.com/xfdf/"><fields>'
        '<field name="first"><value>v</value></field>'
        "</fields></xfdf>"
    )
    doc = parseString(sample)
    root_element = doc.documentElement  # <xfdf> element

    fdf = FDFDocument()
    try:
        fdf.set_xfdf(root_element)
        fields = fdf.get_catalog().get_fdf().get_fields()
        assert fields is not None
        assert fields[0].get_partial_field_name() == "first"
    finally:
        fdf.close()


def test_set_xfdf_accepts_bytearray() -> None:
    """The ``bytes`` and ``bytearray`` branch is shared
    (lines 223-226). Drive the bytearray side so the ``isinstance``
    check exercises the second tuple member."""
    sample = bytearray(
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<xfdf xmlns="http://ns.adobe.com/xfdf/"><fields>'
        b'<field name="ba"><value>v</value></field>'
        b"</fields></xfdf>"
    )
    fdf = FDFDocument()
    try:
        fdf.set_xfdf(sample)
        fields = fdf.get_catalog().get_fdf().get_fields()
        assert fields is not None and fields[0].get_partial_field_name() == "ba"
    finally:
        fdf.close()


def test_set_xfdf_accepts_readable_stream() -> None:
    """The ``hasattr(xfdf, 'read')`` overload (lines 225-226) parses an
    open binary stream end-to-end."""
    sample = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<xfdf xmlns="http://ns.adobe.com/xfdf/"><fields>'
        b'<field name="stream"><value>v</value></field>'
        b"</fields></xfdf>"
    )
    fdf = FDFDocument()
    try:
        fdf.set_xfdf(io.BytesIO(sample))
        fields = fdf.get_catalog().get_fdf().get_fields()
        assert fields is not None and fields[0].get_partial_field_name() == "stream"
    finally:
        fdf.close()


def test_set_xfdf_rejects_unsupported_type() -> None:
    """An int (no ``read``, not bytes/bytearray, not an Element / Document)
    must raise :class:`TypeError` (line 228)."""
    fdf = FDFDocument()
    try:
        with pytest.raises(TypeError, match="expected an XML document"):
            fdf.set_xfdf(12345)  # type: ignore[arg-type]
    finally:
        fdf.close()


class _CloseRecorder:
    """Minimal stand-in for a :class:`RandomAccessRead`. Records when
    its :meth:`close` is invoked so the assertion below can verify the
    constructor-passed ``fdf_source`` is closed by :meth:`FDFDocument.close`.
    """

    def __init__(self, raise_on_close: bool = False) -> None:
        self.closed = False
        self._raise_on_close = raise_on_close

    def close(self) -> None:
        self.closed = True
        if self._raise_on_close:
            raise OSError("simulated close failure")


def test_close_drains_fdf_source() -> None:
    """When constructed with an ``fdf_source``, :meth:`close` invokes
    the source's :meth:`close` callback (lines 295-297)."""
    src = _CloseRecorder()
    fdf = FDFDocument(None, src)  # type: ignore[arg-type]
    fdf.close()
    assert src.closed is True


def test_close_swallows_fdf_source_close_errors() -> None:
    """If the ``fdf_source.close()`` raises, :meth:`FDFDocument.close`
    must swallow the follow-on error (lines 300-301 — the
    ``contextlib.suppress(Exception)`` branch)."""
    src = _CloseRecorder(raise_on_close=True)
    fdf = FDFDocument(None, src)  # type: ignore[arg-type]
    # No exception — close() is best-effort and absorbs failures.
    fdf.close()
    assert src.closed is True
    assert fdf.is_closed()
