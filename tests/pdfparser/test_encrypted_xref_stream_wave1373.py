"""Wave 1373 audit verification — encrypted xref-stream entry decoding.

CHANGES.md:332 originally noted the entry decoder was deferred to
"parser cluster #4". Tests here confirm the current implementation
already decodes encrypted-document xref-stream entries correctly:

  * ISO 32000-2 §7.6.2 mandates cross-reference streams are NOT
    encrypted ("All cross-reference streams in the file shall not be
    encrypted") — therefore decoding them requires no security handler.
  * The parser staged at ``_handle_xref_stream_at`` (lines ~812-910)
    calls ``stream.set_skip_encryption(True)`` before invoking
    ``_decode_xref_stream_entries`` so the body is decoded as plaintext
    even when the document-level decrypt walk later attaches a
    handler.

This file pins that behaviour with new build-it-from-scratch fixtures
and round-trip assertions that complement the existing
``test_encrypted_xref_stream.py`` coverage."""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser
from pypdfbox.pdfwriter import COSWriter

pytest.importorskip("pypdfbox.pdmodel.encryption.standard_protection_policy")


def _build_encrypted_xref_stream_pdf(
    *,
    owner_password: str = "owner",
    user_password: str = "user",
    page_text: str = "wave1373-payload-XYZ",
) -> bytes:
    """Mirror of the helper in ``test_encrypted_xref_stream.py`` — built
    once per test to keep the fixture self-contained."""
    from pypdfbox import PDDocument
    from pypdfbox.cos import COSName as _COSName
    from pypdfbox.pdmodel import PDPage
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
    from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    pd = PDDocument()
    page = PDPage(PDRectangle.LETTER)
    pd.add_page(page)
    font = PDType1Font()
    font.get_cos_object().set_name(_COSName.get_pdf_name("BaseFont"), "Helvetica")
    with PDPageContentStream(pd, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.new_line_at_offset(72, 720)
        cs.show_text(page_text)
        cs.end_text()
    pd.protect(
        StandardProtectionPolicy(
            owner_password=owner_password, user_password=user_password
        )
    )
    sink = io.BytesIO()
    with COSWriter(sink, xref_stream=True) as writer:
        writer.write(pd)
    pd.close()
    return sink.getvalue()


def test_encrypted_xref_stream_entries_resolve_every_pool_object() -> None:
    """Every indirect object recorded in the encrypted xref stream must
    be reachable through the resolver. If entries had been deciphered
    twice the byte offsets would be garbled and pool lookups would
    return ``None``."""
    pdf = _build_encrypted_xref_stream_pdf()
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    parser.set_password("user")
    cos_doc = parser.parse()
    assert cos_doc.is_encrypted() is True
    # The xref stream registered every indirect object; resolving each
    # must succeed (no key/offset corruption).
    for cos_obj in cos_doc.get_objects():
        assert cos_obj.get_object() is not None, (
            f"pool entry {cos_obj.get_object_number()} "
            f"{cos_obj.get_generation_number()} could not be resolved — "
            "encrypted xref-stream entries are decoded against the wrong "
            "byte offsets"
        )


def test_encrypted_xref_stream_does_not_double_decrypt() -> None:
    """After parsing succeeds the resolver's xref entries must point at
    *real* indirect-object headers in the file (i.e. a byte sequence
    starting with ``digit digit obj``). This guards against a regression
    where the body would be deciphered through the security handler in
    addition to the spec-exempt skip — the entries' offsets would then
    point at garbage."""
    pdf = _build_encrypted_xref_stream_pdf()
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    parser.set_password("user")
    parser.parse()
    # Pull every uncompressed entry — those are the ones whose offset is
    # a literal file byte position.
    for key, entry in parser._resolver.get_xref_table().items():  # noqa: SLF001
        if entry.compressed_index >= 0 and entry.type.name != "COMPRESSED":
            offset = entry.offset
            window = pdf[offset : offset + 32]
            # Header is ``N G obj`` — first char must be an ASCII digit.
            if window:
                first = window[:1]
                assert first.isdigit(), (
                    f"xref entry for {key.object_number} {key.generation_number} "
                    f"points at byte {offset} ({window!r}) — does not look like "
                    "an indirect-object header. Possible double-decrypt."
                )


def test_xref_stream_dictionary_keys_survive_pool_walk() -> None:
    """The xref stream's own dictionary (``/Size``, ``/Root``, ``/Encrypt``)
    must still be readable after the document pool walk. A double-decipher
    would have garbled the dictionary keys via the post-walk handler
    reapplication.

    Per ISO 32000-1 §7.5.8 the cross-reference STREAM dictionary IS the
    document trailer in xref-stream mode, so the surviving keys are read off
    ``cos_doc.get_trailer()``. (As of wave 1501 pypdfbox matches PDFBox's
    ``COSWriter.doWriteXRefInc``: the xref stream serialises its body via
    ``getStream()`` BEFORE its own ``doWriteObject``, so it carries no
    self-entry and is therefore not an enumerable pool object — it is located
    via ``startxref``, exactly like upstream. The trailer/xref-stream dict is
    still fully parsed and decipher-clean.)"""
    from pypdfbox.pdmodel import PDDocument

    pdf = _build_encrypted_xref_stream_pdf()
    with PDDocument.load(pdf, password="user") as doc:
        cos_doc = doc.get_document()
        trailer = cos_doc.get_trailer()
        assert isinstance(trailer, COSDictionary)
        # The trailer IS the xref-stream dict — its keys must be intact.
        assert trailer.get_dictionary_object(COSName.get_pdf_name("Size")) is not None
        assert trailer.get_dictionary_object(COSName.ROOT) is not None
