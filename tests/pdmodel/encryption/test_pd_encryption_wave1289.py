"""PDEncryption default crypt-filter name aliases (Wave 1289).

Covers the friendly :py:meth:`get_default_stream_filter_name` /
:py:meth:`set_default_stream_filter_name` aliases (and their string
counterparts) added on top of the existing
``get_stream_filter_name`` / ``get_string_filter_name`` methods, plus a
sanity check that the wire spelling on ``/StmF`` / ``/StrF`` does not
change when the aliases are used.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption


def test_default_stream_filter_name_defaults_to_identity() -> None:
    enc = PDEncryption()
    assert enc.get_default_stream_filter_name() == "Identity"


def test_default_string_filter_name_defaults_to_identity() -> None:
    enc = PDEncryption()
    assert enc.get_default_string_filter_name() == "Identity"


def test_set_default_stream_filter_name_writes_stm_f() -> None:
    enc = PDEncryption()
    enc.set_default_stream_filter_name("StdCF")
    # Round-trip via raw name access — the alias must persist to /StmF.
    assert enc.get_default_stream_filter_name() == "StdCF"
    assert enc.get_stream_filter_name() == "StdCF"
    assert enc.get_stm_f() == "StdCF"


def test_set_default_string_filter_name_writes_str_f() -> None:
    enc = PDEncryption()
    enc.set_default_string_filter_name("StdCF")
    assert enc.get_default_string_filter_name() == "StdCF"
    assert enc.get_string_filter_name() == "StdCF"
    assert enc.get_str_f() == "StdCF"


def test_default_filter_aliases_round_trip_through_cos() -> None:
    """The COS dictionary should carry the same name written via either API."""
    enc = PDEncryption()
    enc.set_default_stream_filter_name("StdCF")
    enc.set_default_string_filter_name("StdCF")

    raw = enc.get_cos_object()
    stm = raw.get_dictionary_object("StmF")
    strf = raw.get_dictionary_object("StrF")
    assert isinstance(stm, COSName) and stm.get_name() == "StdCF"
    assert isinstance(strf, COSName) and strf.get_name() == "StdCF"


def test_crypt_filter_dictionary_typed_round_trip() -> None:
    """get_crypt_filter_dictionary returns the typed wrapper for /CF entries."""
    enc = PDEncryption()
    cfd = PDCryptFilterDictionary()
    cfd.set_cfm("AESV2")
    cfd.set_length(16)
    enc.set_crypt_filter_dictionary("StdCF", cfd)

    looked_up = enc.get_crypt_filter_dictionary("StdCF")
    assert looked_up is not None
    assert isinstance(looked_up, PDCryptFilterDictionary)
    assert looked_up.get_cfm() == "AESV2"
    assert looked_up.get_length() == 16


def test_get_crypt_filter_dictionary_missing_returns_none() -> None:
    enc = PDEncryption()
    assert enc.get_crypt_filter_dictionary("StdCF") is None


def test_get_crypt_filter_dictionary_accepts_cos_name_key() -> None:
    enc = PDEncryption()
    cfd = PDCryptFilterDictionary()
    cfd.set_cfm("V2")
    enc.set_crypt_filter_dictionary(COSName.get_pdf_name("MyFilter"), cfd)
    fetched = enc.get_crypt_filter_dictionary(COSName.get_pdf_name("MyFilter"))
    assert fetched is not None
    assert fetched.get_cfm() == "V2"


def test_crypt_filter_dictionary_marked_direct() -> None:
    """PDFBOX-4436 workaround — /CF entries should be direct objects."""
    enc = PDEncryption()
    cfd = PDCryptFilterDictionary()
    cfd.set_cfm("AESV2")
    enc.set_crypt_filter_dictionary("StdCF", cfd)
    cf_dict = enc.get_cf()
    assert isinstance(cf_dict, COSDictionary)
    entry = cf_dict.get_dictionary_object("StdCF")
    assert isinstance(entry, COSDictionary)
    # Direct entries embed inline rather than as indirect references.
    assert entry.is_direct() is True
