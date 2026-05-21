"""Wave 1370 — encryption attachment / pipeline staging.

The writer must call ``security_handler.prepare_document`` BEFORE
serialisation (so /Encrypt lands in the trailer and the file-key is
already derived). This file verifies the staging order and the
``/Encrypt`` entry in the on-the-wire trailer.
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary, COSDocument, COSName, COSObject
from pypdfbox.loader import Loader
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)

# ---------- prepare_document gets called BEFORE serialisation -------------


def test_prepare_document_runs_before_writer_emits_trailer() -> None:
    """Stage a sentinel ``prepare_document`` that records the
    pre-serialisation document state. After save, the recorded state
    must show no /Encrypt yet, AND the saved bytes must show /Encrypt
    in the final trailer."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.protect(
            StandardProtectionPolicy(
                owner_password="owner",
                user_password="user",
                permissions=AccessPermission(),
            )
        )

        # Patch the prepare_document on the handler class so it sets a
        # sentinel after preparing (we still want the real preparation
        # to run — encryption must work).
        called: list[bool] = []
        original_prepare = StandardSecurityHandler.prepare_document

        def spy_prepare(self: StandardSecurityHandler, document: object) -> None:
            cos_doc = document.get_document()  # type: ignore[attr-defined]
            trailer = cos_doc.get_trailer()
            # Mark whether /Encrypt was *already* set BEFORE the real
            # prepare_document populated it — must be no (i.e. None).
            pre_encrypt = trailer.get_item(COSName.ENCRYPT)  # type: ignore[attr-defined]
            called.append(pre_encrypt is None)
            original_prepare(self, document)

        # Patch the bound method.
        StandardSecurityHandler.prepare_document = spy_prepare  # type: ignore[method-assign]
        try:
            sink = io.BytesIO()
            doc.save(sink)
            assert called == [True], (
                "prepare_document should have run exactly once, "
                "with no /Encrypt in the trailer beforehand"
            )
            # And the trailer in the emitted bytes carries /Encrypt now.
            assert b"/Encrypt " in sink.getvalue() or b"/Encrypt\n" in sink.getvalue()
        finally:
            StandardSecurityHandler.prepare_document = original_prepare  # type: ignore[method-assign]
    finally:
        doc.close()


# ---------- /Encrypt entry lands in the trailer --------------------------


def test_encrypt_dict_in_trailer_after_save() -> None:
    """Saving with ``protect()`` populates /Encrypt as an indirect object
    and the trailer dict carries an /Encrypt reference."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.protect(
            StandardProtectionPolicy(
                owner_password="owner",
                user_password="user",
                permissions=AccessPermission(),
            )
        )
        sink = io.BytesIO()
        doc.save(sink)
        out = sink.getvalue()
    finally:
        doc.close()

    assert b"/Encrypt " in out or b"/Encrypt\n" in out
    # Standard handler emits /V and /Length keys in the /Encrypt dict.
    assert b"/V " in out or b"/V\n" in out


def test_encrypted_document_round_trips_through_loader() -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.protect(
            StandardProtectionPolicy(
                owner_password="owner",
                user_password="user",
                permissions=AccessPermission(),
            )
        )
        sink = io.BytesIO()
        doc.save(sink)
        out = sink.getvalue()
    finally:
        doc.close()

    # Open with the user password.
    parsed = Loader.load_pdf(out, "user")
    try:
        assert parsed.is_encrypted()
        cat = parsed.get_catalog()
        assert cat is not None
    finally:
        parsed.close()


# ---------- writer pulls handler from PDDocument before _do_write_body ----


def test_security_handler_cached_back_on_pddocument_after_save() -> None:
    """After ``save()`` the PDDocument's ``_security_handler`` must be
    populated — the writer caches it back so a subsequent decrypt() call
    sees an active handler immediately."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.protect(
            StandardProtectionPolicy(
                owner_password="owner",
                user_password="user",
                permissions=AccessPermission(),
            )
        )
        sink = io.BytesIO()
        doc.save(sink)
        # Handler must be set after save.
        assert doc._security_handler is not None  # noqa: SLF001
    finally:
        doc.close()


# ---------- low-level COSDocument pass-through guard ---------------------


def test_low_level_cos_document_with_encrypt_round_trips() -> None:
    """Writing a raw COSDocument carrying an /Encrypt dict directly must
    pass /Encrypt through verbatim — no handler logic runs (handlers
    live on PDDocument, not COSDocument)."""
    doc = COSDocument()
    doc.set_version(1.5)
    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    cat_obj = COSObject(1, 0, resolved=catalog)

    encrypt_dict = COSDictionary()
    encrypt_dict.set_name(COSName.get_pdf_name("Filter"), "Standard")
    encrypt_dict.set_int(COSName.get_pdf_name("V"), 1)
    enc_obj = COSObject(2, 0, resolved=encrypt_dict)

    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, cat_obj)  # type: ignore[attr-defined]
    trailer.set_item(COSName.ENCRYPT, enc_obj)  # type: ignore[attr-defined]
    doc.set_trailer(trailer)

    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(doc)
    out = sink.getvalue()
    assert b"/Encrypt " in out or b"/Encrypt\n" in out
    assert b"/Filter /Standard" in out


# ---------- set_all_security_to_be_removed: /Encrypt stripped ------------


def test_set_all_security_to_be_removed_strips_encrypt_dict() -> None:
    """When the caller wants to drop encryption on save, the trailer
    must NOT carry /Encrypt after the write — even if the document
    started encrypted."""
    # Step 1: build an encrypted doc.
    doc1 = PDDocument()
    try:
        doc1.add_page(PDPage())
        doc1.protect(
            StandardProtectionPolicy(
                owner_password="owner",
                user_password="user",
                permissions=AccessPermission(),
            )
        )
        sink = io.BytesIO()
        doc1.save(sink)
        encrypted = sink.getvalue()
    finally:
        doc1.close()

    # Step 2: load, ask for unencrypted re-save.
    parsed = Loader.load_pdf(encrypted, "user")
    try:
        pd = PDDocument(parsed)
        pd.set_all_security_to_be_removed(True)
        out_sink = io.BytesIO()
        pd.save(out_sink)
        unencrypted = out_sink.getvalue()
        pd.close()
    finally:
        # ``parsed.close()`` was already triggered by pd.close() since
        # PDDocument owns the underlying COSDocument; calling here would
        # double-close — guard with try/except.
        pass

    assert b"/Encrypt" not in unencrypted
