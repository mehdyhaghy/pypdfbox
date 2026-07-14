"""Encrypt-on-write coverage for xref-stream output.

``PDDocument.save`` now defaults to ``CompressParameters.DEFAULT_COMPRESSION``
(upstream PDFBox 3.0 parity): the writer packs non-stream objects into
``/Type /ObjStm`` streams addressed by a ``/Type /XRef`` cross-reference
stream, and the encryption pipeline runs through that path. These tests
pin the encrypted round-trip in both output modes:

* default (compressed) save — xref stream + ObjStm, no classic trailer;
* explicit ``NO_COMPRESSION`` save — classic ``xref`` table + ``trailer``.
"""

from __future__ import annotations

import io

import pytest

# Skip cleanly on checkouts where the security cluster isn't present.
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_security_handler")
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_protection_policy")

from pypdfbox import PDDocument  # noqa: E402
from pypdfbox.cos import COSStream  # noqa: E402
from pypdfbox.pdfwriter.compress import CompressParameters  # noqa: E402
from pypdfbox.pdmodel import PDPage  # noqa: E402
from pypdfbox.pdmodel.encryption.access_permission import (  # noqa: E402
    AccessPermission,
)
from pypdfbox.pdmodel.encryption.standard_protection_policy import (  # noqa: E402
    StandardProtectionPolicy,
)

_CONTENT_PAYLOAD = b"BT /F1 12 Tf 50 700 Td (Hello xref-stream) Tj ET"


def _build_protected_document() -> PDDocument:
    pd = PDDocument()
    page = PDPage()
    pd.add_page(page)
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(_CONTENT_PAYLOAD)
    page.set_contents(stream)
    policy = StandardProtectionPolicy(
        owner_password="owner",
        user_password="user",
        permissions=AccessPermission(),
    )
    pd.protect(policy)
    return pd


def _save_to_bytes(pd: PDDocument, *args) -> bytes:
    sink = io.BytesIO()
    pd.save(sink, *args)
    return sink.getvalue()


def test_encrypted_default_save_uses_xref_stream() -> None:
    """Default (compressed) save of an encrypted document emits an xref
    stream + ObjStm, not a classic ``xref`` table."""
    pd = _build_protected_document()
    saved = _save_to_bytes(pd)

    assert b"/ObjStm" in saved, "expected /Type /ObjStm packing by default"
    assert b"/Type /XRef" in saved or b"/Type/XRef" in saved, (
        "expected a /Type /XRef cross-reference stream by default"
    )
    assert b"\nxref\n" not in saved and b"\ntrailer" not in saved, (
        "classic xref/trailer must not appear in compressed output"
    )

    with PDDocument.load(saved, password="user") as reloaded:
        assert reloaded.is_encrypted()
        assert reloaded.get_number_of_pages() == 1


def test_encrypted_no_compression_save_uses_traditional_xref_table() -> None:
    """``CompressParameters.NO_COMPRESSION`` keeps the classic ``xref``
    table + ``trailer`` pair for encrypted documents."""
    pd = _build_protected_document()
    saved = _save_to_bytes(pd, CompressParameters.NO_COMPRESSION)

    assert b"\nxref\n" in saved or b"\rxref\r" in saved or b"\nxref\r" in saved, (
        "expected a traditional 'xref' section in the saved bytes"
    )
    assert b"trailer" in saved, "expected a 'trailer' keyword in the saved bytes"
    assert b"/ObjStm" not in saved

    with PDDocument.load(saved, password="user") as reloaded:
        assert reloaded.is_encrypted()
        assert reloaded.get_number_of_pages() == 1


@pytest.mark.parametrize(
    "compress_parameters",
    [None, CompressParameters.NO_COMPRESSION],
    ids=["default-compression", "no-compression"],
)
def test_xref_stream_encrypt_on_write_round_trip(compress_parameters) -> None:
    """Full round-trip in both output modes: protect, save, parse back,
    verify the recovered content stream matches the seed."""
    pd = _build_protected_document()
    args = () if compress_parameters is None else (compress_parameters,)
    saved = _save_to_bytes(pd, *args)
    with PDDocument.load(saved, password="user") as reloaded:
        assert reloaded.is_encrypted()
        assert reloaded.get_number_of_pages() == 1
        page = reloaded.get_pages()[0]
        contents = page.get_cos_object().get_dictionary_object("Contents")
        assert isinstance(contents, COSStream)
        with contents.create_input_stream() as src:
            assert src.read() == _CONTENT_PAYLOAD
