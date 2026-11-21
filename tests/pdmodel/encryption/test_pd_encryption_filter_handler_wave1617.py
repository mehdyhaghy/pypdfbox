"""``PDEncryption(COSDictionary)`` installs a security handler for /Filter.

Upstream ``PDEncryption(COSDictionary)`` calls
``SecurityHandlerFactory.INSTANCE.newSecurityHandlerForFilter(getFilter())``,
and ``prepareDecryption`` decrypts with ``encryption.getSecurityHandler()``,
so a loaded document's encryption reports the very handler that decrypted it.
"""

import io
import pathlib

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)

_FIXTURE = (
    pathlib.Path(__file__).parents[2]
    / "fixtures"
    / "pdmodel"
    / "encryption"
    / "rc4_128_empty_user_password.pdf"
)


def _dict_with_filter(name: str | None) -> COSDictionary:
    d = COSDictionary()
    if name is not None:
        d.set_item(COSName.get_pdf_name("Filter"), COSName.get_pdf_name(name))
    return d


def _protected(key_length: int) -> bytes:
    doc = PDDocument()
    doc.add_page(PDPage())
    policy = StandardProtectionPolicy(
        owner_password="owner", user_password="user", permissions=AccessPermission()
    )
    policy.set_encryption_key_length(key_length)
    doc.protect(policy)
    sink = io.BytesIO()
    doc.save(sink)
    doc.close()
    return sink.getvalue()


def test_no_arg_constructor_has_no_handler() -> None:
    assert PDEncryption().has_security_handler() is False


def test_dictionary_without_filter_has_no_handler() -> None:
    enc = PDEncryption(COSDictionary())
    assert enc.has_security_handler() is False
    with pytest.raises(OSError, match="No security handler for filter None"):
        enc.get_security_handler()


def test_standard_filter_installs_standard_handler() -> None:
    enc = PDEncryption(_dict_with_filter("Standard"))
    assert enc.has_security_handler() is True
    assert type(enc.get_security_handler()) is StandardSecurityHandler


def test_pubsec_filter_installs_public_key_handler() -> None:
    enc = PDEncryption(_dict_with_filter("Adobe.PubSec"))
    assert enc.has_security_handler() is True
    assert type(enc.get_security_handler()) is PublicKeySecurityHandler


def test_unknown_filter_has_no_handler() -> None:
    enc = PDEncryption(_dict_with_filter("Custom.Handler"))
    assert enc.has_security_handler() is False
    with pytest.raises(OSError, match="No security handler for filter Custom.Handler"):
        enc.get_security_handler()


def test_each_wrapper_gets_a_fresh_handler() -> None:
    d = _dict_with_filter("Standard")
    assert PDEncryption(d).get_security_handler() is not (
        PDEncryption(d).get_security_handler()
    )


def test_loaded_fixture_reports_the_decrypting_handler() -> None:
    with PDDocument(Loader.load_pdf(_FIXTURE)) as doc:
        assert doc.is_encrypted()
        enc = doc.get_encryption()
        assert enc.has_security_handler() is True
        handler = enc.get_security_handler()
        assert isinstance(handler, StandardSecurityHandler)
        assert handler is doc._security_handler
        assert handler is doc.get_document()._object_security_handler
        assert handler.get_current_access_permission() is not None


@pytest.mark.parametrize("key_length", [40, 128, 256])
def test_loaded_with_password_reports_the_decrypting_handler(key_length: int) -> None:
    with PDDocument(Loader.load_pdf(_protected(key_length), "user")) as doc:
        enc = doc.get_encryption()
        assert enc.has_security_handler() is True
        assert enc.get_security_handler() is doc._security_handler
        assert len(doc.get_pages()) == 1

    with PDDocument.load(_protected(key_length), "user") as doc:
        enc = doc.get_encryption()
        assert enc.get_security_handler() is doc._security_handler
