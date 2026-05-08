from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption


def test_wave315_set_crypt_filter_dictionary_accepts_cos_name_key() -> None:
    encryption = PDEncryption()
    crypt_filter = PDCryptFilterDictionary()
    key = COSName.get_pdf_name("DefaultCryptFilter")

    encryption.set_crypt_filter_dictionary(key, crypt_filter)

    cf = encryption.get_cf()
    assert cf is not None
    assert cf.get_dictionary_object(key) is crypt_filter.get_cos_object()
    fetched = encryption.get_default_crypt_filter_dictionary()
    assert fetched is not None
    assert fetched.get_cos_object() is crypt_filter.get_cos_object()


def test_wave315_get_crypt_filter_dictionary_accepts_cos_name_key() -> None:
    encryption = PDEncryption()
    raw_cf = COSDictionary()
    raw_filter = COSDictionary()
    key = COSName.get_pdf_name("RecipientCF")
    raw_cf.set_item(key, raw_filter)
    encryption.set_cf(raw_cf)

    fetched = encryption.get_crypt_filter_dictionary(key)

    assert fetched is not None
    assert fetched.get_cos_object() is raw_filter
