"""Tests for ``PDCryptFilterDictionary`` plus the ``/CF`` dispatch wired
through ``PDEncryption`` and ``StandardSecurityHandler``."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)

# ---------- PDCryptFilterDictionary ----------


def test_fresh_crypt_filter_has_type_crypt_filter() -> None:
    cf = PDCryptFilterDictionary()
    assert cf.get_cos_object().get_name("Type") == "CryptFilter"


def test_wrap_existing_dictionary_does_not_inject_type() -> None:
    raw = COSDictionary()
    cf = PDCryptFilterDictionary(raw)
    # When wrapping a pre-existing dictionary we leave the entries untouched
    # so callers can wrap arbitrary parsed content without surprise mutations.
    assert cf.get_cos_object() is raw
    assert raw.get_name("Type") is None


def test_round_trip_cfm_length_encrypt_metadata() -> None:
    cf = PDCryptFilterDictionary()
    cf.set_cfm(PDCryptFilterDictionary.CFM_AESV2)
    cf.set_length(16)
    cf.set_encrypt_metadata(False)

    assert cf.get_cfm() == "AESV2"
    assert cf.get_length() == 16
    assert cf.get_encrypt_metadata() is False

    # Re-wrap the same dictionary and observe the same values — true round trip.
    rehydrated = PDCryptFilterDictionary(cf.get_cos_object())
    assert rehydrated.get_cfm() == "AESV2"
    assert rehydrated.get_length() == 16
    assert rehydrated.get_encrypt_metadata() is False


def test_default_length_is_5_bytes_default_encrypt_metadata_true() -> None:
    cf = PDCryptFilterDictionary()
    # Spec defaults: 5 bytes (40-bit RC4) and EncryptMetadata=true.
    assert cf.get_length() == 5
    assert cf.get_encrypt_metadata() is True


def test_cfm_constants_match_spec() -> None:
    assert PDCryptFilterDictionary.CFM_NONE == "None"
    assert PDCryptFilterDictionary.CFM_V2 == "V2"
    assert PDCryptFilterDictionary.CFM_AESV2 == "AESV2"
    assert PDCryptFilterDictionary.CFM_AESV3 == "AESV3"


def test_recipients_round_trip() -> None:
    cf = PDCryptFilterDictionary()
    assert cf.get_recipients() is None
    arr = COSArray()
    cf.set_recipients(arr)
    assert cf.get_recipients() is arr


# ---------- PDEncryption /CF dispatch ----------


def test_set_std_crypt_filter_dictionary_round_trip() -> None:
    enc = PDEncryption()
    cf = PDCryptFilterDictionary()
    cf.set_cfm(PDCryptFilterDictionary.CFM_AESV2)
    cf.set_length(16)

    enc.set_std_crypt_filter_dictionary(cf)
    # /CF was created and contains /StdCF pointing at our dictionary.
    cf_dict = enc.get_cf()
    assert cf_dict is not None
    assert cf_dict.get_dictionary_object("StdCF") is cf.get_cos_object()

    fetched = enc.get_std_crypt_filter_dictionary()
    assert fetched is not None
    assert fetched.get_cos_object() is cf.get_cos_object()
    assert fetched.get_cfm() == "AESV2"
    assert fetched.get_length() == 16


def test_get_crypt_filter_dictionary_returns_none_when_cf_absent() -> None:
    enc = PDEncryption()
    assert enc.get_crypt_filter_dictionary("StdCF") is None
    assert enc.get_std_crypt_filter_dictionary() is None
    assert enc.get_default_crypt_filter_dictionary() is None


def test_get_crypt_filter_dictionary_named_lookup() -> None:
    enc = PDEncryption()
    custom = PDCryptFilterDictionary()
    custom.set_cfm(PDCryptFilterDictionary.CFM_V2)
    custom.set_length(16)
    enc.set_crypt_filter_dictionary("CustomFilter", custom)

    fetched = enc.get_crypt_filter_dictionary("CustomFilter")
    assert fetched is not None
    assert fetched.get_cos_object() is custom.get_cos_object()
    assert fetched.get_cfm() == "V2"
    # Unknown filter name returns None.
    assert enc.get_crypt_filter_dictionary("NotThere") is None


def test_set_default_crypt_filter_dictionary_round_trip() -> None:
    enc = PDEncryption()
    cf = PDCryptFilterDictionary()
    cf.set_cfm(PDCryptFilterDictionary.CFM_AESV3)
    enc.set_default_crypt_filter_dictionary(cf)
    fetched = enc.get_default_crypt_filter_dictionary()
    assert fetched is not None
    assert fetched.get_cfm() == "AESV3"


def test_remove_v45_filters_strips_cf_stmf_strf_eff() -> None:
    enc = PDEncryption()
    cf = PDCryptFilterDictionary()
    cf.set_cfm(PDCryptFilterDictionary.CFM_AESV2)
    enc.set_std_crypt_filter_dictionary(cf)
    enc.set_stm_f("StdCF")
    enc.set_str_f("StdCF")
    enc.get_cos_object().set_name("EFF", "StdCF")

    enc.remove_v45_filters()

    assert enc.get_cf() is None
    assert enc.get_stm_f() is None
    assert enc.get_str_f() is None
    assert enc.get_cos_object().get_dictionary_object("EFF") is None


# ---------- StandardSecurityHandler is_aes() reads /CF/StdCF/CFM ----------


def _build_v4_encryption_with_stdcf(cfm: str | None) -> PDEncryption:
    """Build a V=4 R=4 /Encrypt dictionary referencing /CF/StdCF.

    Computes /O and /U for the empty password so prepare_for_decryption can
    validate. ``cfm`` of ``None`` means the StdCF entry exists but has no
    /CFM key (forces fallback to /StmF name heuristic).
    """
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(4)
    encryption.set_revision(4)
    encryption.set_length(128)
    encryption.set_p(-3904)
    # Default crypt filter for streams + strings is /CF/StdCF.
    encryption.set_stm_f("StdCF")
    encryption.set_str_f("StdCF")

    std_cf = PDCryptFilterDictionary()
    if cfm is not None:
        std_cf.set_cfm(cfm)
    std_cf.set_length(16)
    encryption.set_std_crypt_filter_dictionary(std_cf)

    document_id = b"\x00" * 16
    o = StandardSecurityHandler._compute_owner_password_r2_r4(b"", b"", 4, 16)
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        b"", o, -3904, document_id, 4, 16
    )
    encryption.set_o(o)
    encryption.set_u(u)
    return encryption


def test_is_aes_true_when_std_cf_cfm_aesv2() -> None:
    encryption = _build_v4_encryption_with_stdcf("AESV2")
    handler = StandardSecurityHandler()
    handler.prepare_for_decryption(
        encryption, b"\x00" * 16, StandardDecryptionMaterial("")
    )
    assert handler.is_aes() is True


def test_is_aes_false_when_std_cf_cfm_v2() -> None:
    encryption = _build_v4_encryption_with_stdcf("V2")
    handler = StandardSecurityHandler()
    handler.prepare_for_decryption(
        encryption, b"\x00" * 16, StandardDecryptionMaterial("")
    )
    assert handler.is_aes() is False


def test_is_aes_falls_back_to_stmf_name_when_cf_absent() -> None:
    """Legacy writers may put AESV2 directly in /StmF without a /CF entry."""
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(4)
    encryption.set_revision(4)
    encryption.set_length(128)
    encryption.set_p(-3904)
    encryption.set_stm_f("AESV2")

    document_id = b"\x00" * 16
    o = StandardSecurityHandler._compute_owner_password_r2_r4(b"", b"", 4, 16)
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        b"", o, -3904, document_id, 4, 16
    )
    encryption.set_o(o)
    encryption.set_u(u)

    handler = StandardSecurityHandler()
    handler.prepare_for_decryption(
        encryption, document_id, StandardDecryptionMaterial("")
    )
    assert handler.is_aes() is True


def test_get_stream_and_string_filter_name_helpers() -> None:
    enc = PDEncryption()
    assert StandardSecurityHandler.get_stream_filter_name(enc) is None
    assert StandardSecurityHandler.get_string_filter_name(enc) is None
    enc.set_stm_f("StdCF")
    enc.set_str_f("Identity")
    assert StandardSecurityHandler.get_stream_filter_name(enc) == "StdCF"
    assert StandardSecurityHandler.get_string_filter_name(enc) == "Identity"
