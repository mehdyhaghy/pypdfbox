from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)


def test_optional_entry_has_helpers_require_well_formed_cos_values() -> None:
    raw = COSDictionary()
    raw.set_item("CFM", COSString("AESV2"))
    raw.set_item("Length", COSString("16"))
    raw.set_item("Recipients", COSDictionary())
    raw.set_item("EncryptMetadata", COSName.get_pdf_name("false"))

    crypt_filter = PDCryptFilterDictionary(raw)

    assert crypt_filter.get_cfm() is None
    assert crypt_filter.get_length() == 40
    assert crypt_filter.get_recipients() is None
    assert crypt_filter.get_encrypt_metadata() is True
    assert crypt_filter.has_cfm() is False
    assert crypt_filter.has_length() is False
    assert crypt_filter.has_recipients() is False
    assert crypt_filter.has_encrypt_metadata() is False


def test_optional_entry_has_and_clear_helpers_round_trip() -> None:
    crypt_filter = PDCryptFilterDictionary()
    recipients = COSArray()
    recipients.add(COSString(b"recipient"))

    assert crypt_filter.has_cfm() is False
    assert crypt_filter.has_length() is False
    assert crypt_filter.has_recipients() is False
    assert crypt_filter.has_encrypt_metadata() is False

    crypt_filter.set_cfm(PDCryptFilterDictionary.CFM_AESV2)
    crypt_filter.set_length(16)
    crypt_filter.set_recipients(recipients)
    crypt_filter.set_encrypt_metadata(False)

    assert crypt_filter.has_cfm() is True
    assert crypt_filter.has_length() is True
    assert crypt_filter.has_recipients() is True
    assert crypt_filter.has_encrypt_metadata() is True
    assert crypt_filter.get_cfm() == "AESV2"
    assert crypt_filter.get_length() == 16
    assert crypt_filter.get_recipients() is recipients
    assert crypt_filter.get_encrypt_metadata() is False

    crypt_filter.clear_cfm()
    crypt_filter.clear_length()
    crypt_filter.clear_recipients()
    crypt_filter.clear_encrypt_metadata()

    assert crypt_filter.get_cfm() is None
    assert crypt_filter.get_length() == 40
    assert crypt_filter.get_recipients() is None
    assert crypt_filter.get_encrypt_metadata() is True
    assert crypt_filter.has_cfm() is False
    assert crypt_filter.has_length() is False
    assert crypt_filter.has_recipients() is False
    assert crypt_filter.has_encrypt_metadata() is False


def test_set_cfm_none_clears_entry_like_other_name_setters() -> None:
    crypt_filter = PDCryptFilterDictionary()
    crypt_filter.set_cfm(PDCryptFilterDictionary.CFM_AESV3)

    crypt_filter.set_cfm(None)

    assert crypt_filter.get_cfm() is None
    assert crypt_filter.has_cfm() is False


def test_has_helpers_accept_well_formed_numeric_and_boolean_subclasses() -> None:
    raw = COSDictionary()
    raw.set_item("CFM", COSName.get_pdf_name("V2"))
    raw.set_item("Length", COSInteger.get(5))
    raw.set_item("Recipients", COSArray())
    raw.set_item("EncryptMetadata", COSBoolean.TRUE)

    crypt_filter = PDCryptFilterDictionary(raw)

    assert crypt_filter.has_cfm() is True
    assert crypt_filter.has_length() is True
    assert crypt_filter.has_recipients() is True
    assert crypt_filter.has_encrypt_metadata() is True
