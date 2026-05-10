"""Wave 1272: parity coverage for ``PDCryptFilterDictionary``'s
upstream-spelled ``is_encrypt_meta_data`` / ``set_encrypt_meta_data``
accessors (Encrypt / Meta / Data word boundary)."""

from __future__ import annotations

from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)


def test_is_encrypt_meta_data_default_true() -> None:
    cf = PDCryptFilterDictionary()
    assert cf.is_encrypt_meta_data() is True


def test_set_encrypt_meta_data_round_trips() -> None:
    cf = PDCryptFilterDictionary()
    cf.set_encrypt_meta_data(False)
    assert cf.is_encrypt_meta_data() is False
    # Both spellings observe the same dictionary entry.
    assert cf.get_encrypt_metadata() is False
    cf.set_encrypt_meta_data(True)
    assert cf.is_encrypt_meta_data() is True


def test_set_encrypt_metadata_visible_through_meta_data_alias() -> None:
    cf = PDCryptFilterDictionary()
    cf.set_encrypt_metadata(False)
    assert cf.is_encrypt_meta_data() is False
