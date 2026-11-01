"""Loading encrypted PDFs that use an empty user password.

Upstream ``Loader.loadPDF(File)`` delegates with an empty password, so a
"restrictions only" document (blank user password, owner password set) is
decrypted on load. pypdfbox used to skip decryption entirely when no
password was given, so text extraction and ``set_all_security_to_be_removed``
saves produced ciphertext (seen on the ISO 32000-1 spec PDF: RC4, R3, P -28).

The fixture ``rc4_128_empty_user_password.pdf`` was generated once with
qpdf (``--encrypt "" owner 128 --use-aes=n --object-streams=generate``):
RC4-128, R3, xref stream, object stream, one page "Hello encrypted world".
"""

import io
from pathlib import Path

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.cos import COSName, COSObjectKey, COSStream
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.text import PDFTextStripper

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "pdmodel"
    / "encryption"
    / "rc4_128_empty_user_password.pdf"
)


def _text(doc: PDDocument) -> str:
    return PDFTextStripper().get_text(doc)


def _build_protected(user_password: str, key_length: int) -> bytes:
    doc = PDDocument()
    page = PDPage()
    doc.add_page(page)
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(b"BT /Helv 12 Tf 50 700 Td (Hello round-trip) Tj ET")
    page.set_contents(stream)
    doc.get_document_information().set_title("Secret title")
    policy = StandardProtectionPolicy(
        owner_password="owner",
        user_password=user_password,
        permissions=AccessPermission(),
    )
    policy.set_encryption_key_length(key_length)
    doc.protect(policy)
    sink = io.BytesIO()
    doc.save(sink)
    doc.close()
    return sink.getvalue()


def _page_content(doc: PDDocument) -> bytes:
    contents = doc.get_pages()[0].get_cos_object().get_dictionary_object(
        COSName.CONTENTS
    )
    assert isinstance(contents, COSStream)
    with contents.create_input_stream() as src:
        return src.read()


def test_load_without_password_decrypts_empty_user_password() -> None:
    with PDDocument.load(_FIXTURE) as doc:
        assert doc.is_encrypted()
        assert "Hello encrypted world" in _text(doc)
        assert doc.get_document_information().get_title() == "Secret title"
        # The user (not owner) password authenticated: restrictions apply.
        assert not doc.get_current_access_permission().can_extract_content()


def test_loader_without_password_matches_empty_password() -> None:
    with (
        PDDocument(Loader.load_pdf(_FIXTURE)) as implicit,
        PDDocument.load(_FIXTURE, "") as explicit,
    ):
        assert _text(implicit) == _text(explicit)


def test_decryption_is_lazy() -> None:
    # Upstream decrypts each object as the parser reads it; loading must
    # not force-parse the whole pool (that made the 22 MB spec PDF take
    # 12 s to open). The page content stream (object 7) is untouched
    # until the page is read, and is then deciphered on demand.
    with PDDocument.load(_FIXTURE) as doc:
        content_ref = doc.get_document().get_object_from_pool(COSObjectKey(7, 0))
        assert not content_ref.is_dereferenced()
        assert b"Hello encrypted world" in _page_content(doc)
        assert content_ref.is_dereferenced()


def test_remove_security_and_save_writes_plaintext() -> None:
    with PDDocument.load(_FIXTURE) as doc:
        doc.set_all_security_to_be_removed(True)
        sink = io.BytesIO()
        doc.save(sink)
    with PDDocument.load(sink.getvalue()) as reloaded:
        assert not reloaded.is_encrypted()
        assert "Hello encrypted world" in _text(reloaded)
        assert reloaded.get_document_information().get_title() == "Secret title"


def test_rc4_40_bit_r3_empty_user_password() -> None:
    # Same shape as the spec PDF: /V 1 /R 3 /Length 40, classic xref table,
    # strings in an indirect object at a direct file offset.
    data = _build_protected(user_password="", key_length=40)
    with PDDocument.load(data) as doc:
        enc = doc.get_encryption()
        assert (enc.get_version(), enc.get_revision(), enc.get_length()) == (
            1,
            3,
            40,
        )
        assert doc.get_document_information().get_title() == "Secret title"
        assert _page_content(doc).startswith(b"BT /Helv 12 Tf")


def test_user_password_protected_document_stays_encrypted() -> None:
    # The empty password does not open it; without a password the
    # document comes back still encrypted and can be decrypted later.
    data = _build_protected(user_password="user", key_length=128)
    with pytest.warns(DeprecationWarning, match="pypdfbox 3.0"), PDDocument.load(data) as doc:
        assert doc.is_encrypted()
        assert not doc.get_current_access_permission().can_extract_content()
        doc.decrypt("user")
        assert doc.get_document_information().get_title() == "Secret title"
        assert _page_content(doc).startswith(b"BT /Helv 12 Tf")


def test_wrong_explicit_password_still_raises() -> None:
    from pypdfbox.pdmodel.encryption.invalid_password_exception import (
        InvalidPasswordException,
    )

    data = _build_protected(user_password="user", key_length=128)
    with pytest.raises(InvalidPasswordException):
        PDDocument.load(data, "nope")


def test_implicit_password_failure_warns_at_caller() -> None:
    # 2.x keeps returning the document encrypted but warns that 3.0 will
    # raise InvalidPasswordException like upstream; the warning points at
    # the caller's file, not at pypdfbox internals.
    data = _build_protected(user_password="user", key_length=128)
    with pytest.warns(DeprecationWarning, match="pypdfbox 3.0") as record:
        doc = PDDocument.load(data)
    doc.close()
    assert record[0].filename == __file__


@pytest.mark.parametrize("source", ["empty_user_password", "plain"])
def test_no_warning_when_load_succeeds(source: str) -> None:
    import warnings

    if source == "plain":
        doc = PDDocument()
        doc.add_page(PDPage())
        sink = io.BytesIO()
        doc.save(sink)
        doc.close()
        data = sink.getvalue()
    else:
        data = _FIXTURE.read_bytes()
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        PDDocument.load(data).close()


def test_explicit_empty_password_raises_like_upstream() -> None:
    from pypdfbox.pdmodel.encryption.invalid_password_exception import (
        InvalidPasswordException,
    )

    data = _build_protected(user_password="user", key_length=128)
    with pytest.raises(InvalidPasswordException):
        PDDocument.load(data, password="")


def test_tools_and_examples_do_not_warn(tmp_path: Path) -> None:
    import warnings

    from pypdfbox.examples.pdmodel.create_bookmarks import CreateBookmarks
    from pypdfbox.examples.util.remove_all_text import RemoveAllText
    from pypdfbox.tools.encrypt import encrypt_pdf

    src = tmp_path / "locked.pdf"
    src.write_bytes(_build_protected(user_password="user", key_length=128))
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        encrypt_pdf(src, tmp_path / "out.pdf", owner_password="o", user_password="u")
        RemoveAllText.strip(str(src), str(tmp_path / "stripped.pdf"))
        with pytest.raises(SystemExit):
            CreateBookmarks.main([str(src), str(tmp_path / "bm.pdf")])
    assert not (tmp_path / "out.pdf").exists()
    assert not (tmp_path / "stripped.pdf").exists()
