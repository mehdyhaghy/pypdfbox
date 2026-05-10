"""End-to-end round-trip tests for encryption-on-write through ``COSWriter``.

Each test follows the same shape:

1. Build a fresh ``PDDocument`` in memory (one page, one content stream).
2. ``protect()`` it with a ``StandardProtectionPolicy``.
3. ``save`` to bytes — the writer's encryption pipeline ciphers every
   stream + indirect-object string through the standard handler.
4. ``Loader.load_pdf`` the saved bytes with the matching password.
5. Verify the round-tripped page count, ``is_encrypted`` flag, and the
   recovered content-stream bytes.
"""

from __future__ import annotations

import io

import pytest

# Skip cleanly on checkouts where the security cluster isn't present.
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_security_handler")
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_protection_policy")

from pypdfbox import Loader, PDDocument  # noqa: E402
from pypdfbox.cos import COSStream  # noqa: E402
from pypdfbox.pdmodel import PDPage  # noqa: E402
from pypdfbox.pdmodel.encryption.access_permission import (  # noqa: E402
    AccessPermission,
)
from pypdfbox.pdmodel.encryption.standard_protection_policy import (  # noqa: E402
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (  # noqa: E402
    PDInvalidPasswordException,
)

# ---------------------------------------------------------------- helpers


_CONTENT_PAYLOAD = b"BT /F1 12 Tf 50 700 Td (Hello round-trip) Tj ET"


def _build_document_with_content() -> tuple[PDDocument, bytes]:
    """Construct a fresh PDDocument with a single page whose /Contents is a
    raw (unfiltered) stream containing ``_CONTENT_PAYLOAD``. Returns the
    document plus the exact payload bytes for later comparison."""
    pd = PDDocument()
    page = PDPage()
    pd.add_page(page)

    # Build the content stream — no filters, so raw bytes == decoded bytes.
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(_CONTENT_PAYLOAD)
    page.set_contents(stream)
    return pd, _CONTENT_PAYLOAD


def _save_to_bytes(pd: PDDocument) -> bytes:
    sink = io.BytesIO()
    pd.save(sink)
    return sink.getvalue()


def _first_page_contents(pd: PDDocument) -> bytes:
    """Pull the **decoded** bytes of the first page's /Contents stream.

    ``PDPage.get_contents`` returns the still-encrypted raw bytes (it
    reads through ``create_raw_input_stream``), so we go one level
    deeper here and use ``create_input_stream`` which runs the security
    handler's decrypt pass before any /Filter chain."""
    from pypdfbox.cos import COSArray, COSStream

    page = pd.get_pages()[0]
    contents = page.get_cos_object().get_dictionary_object("Contents")
    if isinstance(contents, COSStream):
        with contents.create_input_stream() as src:
            return src.read()
    if isinstance(contents, COSArray):
        chunks: list[bytes] = []
        for i in range(contents.size()):
            entry = contents.get_object(i)
            if isinstance(entry, COSStream):
                with entry.create_input_stream() as src:
                    chunks.append(src.read())
        return b"\n".join(chunks)
    return b""


# -------------------------------------------------------------- tests


def test_round_trip_with_user_password() -> None:
    """Save with both passwords set, reload using the user password,
    confirm the encryption flag, page count, and content bytes."""
    pd, payload = _build_document_with_content()
    policy = StandardProtectionPolicy(
        owner_password="owner",
        user_password="user",
        permissions=AccessPermission(),
    )
    pd.protect(policy)
    saved = _save_to_bytes(pd)
    pd.close()

    # Sanity: the cleartext payload should NOT appear verbatim in the
    # saved bytes — proves the stream body really got enciphered. Without
    # this check a passthrough bug would slip past the round-trip below.
    assert _CONTENT_PAYLOAD not in saved

    # is_encrypted before decrypt: load WITHOUT a password to capture the
    # parser-level state, then close before re-loading with credentials.
    encrypted_doc = Loader.load_pdf(saved)
    try:
        assert encrypted_doc.is_encrypted() is True
    finally:
        encrypted_doc.close()

    # Decrypt path: Loader.load_pdf with the user password.
    with PDDocument.load(saved, password="user") as reloaded:
        assert reloaded.is_encrypted() is True  # /Encrypt still in trailer
        assert reloaded.get_number_of_pages() == 1
        recovered = _first_page_contents(reloaded)
        assert recovered == payload


def test_round_trip_with_blank_user_password() -> None:
    """Owner-only protection (blank user password) — common for "anyone
    can read but only owner can edit" PDFs. Decrypt with the empty
    string."""
    pd, payload = _build_document_with_content()
    policy = StandardProtectionPolicy(
        owner_password="ownerOnly",
        user_password="",
        permissions=AccessPermission(),
    )
    pd.protect(policy)
    saved = _save_to_bytes(pd)
    pd.close()

    assert _CONTENT_PAYLOAD not in saved

    with PDDocument.load(saved, password="") as reloaded:
        assert reloaded.is_encrypted() is True
        assert reloaded.get_number_of_pages() == 1
        assert _first_page_contents(reloaded) == payload


def test_round_trip_owner_password_decrypt() -> None:
    """The owner password must also unlock the file (algorithm 7 path)."""
    pd, payload = _build_document_with_content()
    policy = StandardProtectionPolicy(
        owner_password="owner-key",
        user_password="user-key",
        permissions=AccessPermission(),
    )
    pd.protect(policy)
    saved = _save_to_bytes(pd)
    pd.close()

    with PDDocument.load(saved, password="owner-key") as reloaded:
        assert reloaded.is_encrypted() is True
        assert _first_page_contents(reloaded) == payload


def test_wrong_password_rejected_on_round_trip() -> None:
    """A reload with a non-matching password raises the documented error."""
    pd, _payload = _build_document_with_content()
    policy = StandardProtectionPolicy(
        owner_password="owner",
        user_password="user",
        permissions=AccessPermission(),
    )
    pd.protect(policy)
    saved = _save_to_bytes(pd)
    pd.close()

    with pytest.raises(PDInvalidPasswordException):
        Loader.load_pdf(saved, "nope")


def test_protect_then_save_propagates_security_handler() -> None:
    """After ``save`` runs the encryption pipeline, the document caches
    the active handler so later ``get_current_access_permission`` calls
    don't return the no-permission default."""
    pd, _payload = _build_document_with_content()
    policy = StandardProtectionPolicy(
        owner_password="o",
        user_password="u",
        permissions=AccessPermission(),
    )
    pd.protect(policy)
    _ = _save_to_bytes(pd)
    assert pd._security_handler is not None  # noqa: SLF001
    pd.close()
