"""Crypt-filter fuzz — /CF, /StmF, /StrF, /EFF, /CFM, /EncryptMetadata.

Hammers the per-object crypt-filter routing of PDF 32000-1 §7.6.5 against
the behaviour of Apache PDFBox 3.0.7:

* ``/StmF`` (default stream filter) and ``/StrF`` (default string filter)
  resolving to a named ``/CF`` entry — or the reserved ``Identity`` name.
* the named ``/CF`` entry's ``/CFM`` (``V2`` = RC4, ``AESV2`` = AES-128,
  ``AESV3`` = AES-256, ``Identity`` / ``None``).
* ``/EncryptMetadata`` true/false deciding whether a ``/Type /Metadata``
  stream is deciphered on the ``SecurityHandler.decrypt`` dict-walk path.
* the ``Identity`` filter passing data through unchanged, a ``/StmF
  Identity`` leaving streams cleartext while strings may still be enciphered.
* ``/EFF`` (embedded-file filter) defaulting to ``/StmF`` when absent.
* a missing ``/CF`` entry and ``/Length`` defaults.

Wave 1584. Companion to ``test_per_object_crypt_filter.py`` (routing table)
and ``test_aes_crypt_filter_fuzz_wave1573.py`` (AES round-trip).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)

_DOC_ID = b"\x00" * 16
_TARGET = "pypdfbox.pdmodel.encryption.standard_security_handler"


# --------------------------------------------------------------------------
# Builders.


def _password_pair_for_v4(
    key_len_bytes: int = 16, encrypt_metadata: bool = True
) -> tuple[bytes, bytes]:
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        b"", b"", 4, key_len_bytes
    )
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        b"", o, -3904, _DOC_ID, 4, key_len_bytes, encrypt_metadata
    )
    return o, u


def _build_v4_encryption(
    *,
    cf_entries: dict[str, str],
    stm_f: str | None,
    str_f: str | None,
    eff: str | None = None,
    encrypt_metadata: bool | None = None,
) -> PDEncryption:
    enc = PDEncryption()
    enc.set_filter("Standard")
    enc.set_v(4)
    enc.set_revision(4)
    enc.set_length(128)
    enc.set_p(-3904)
    for name, cfm in cf_entries.items():
        cf = PDCryptFilterDictionary()
        cf.set_cfm(cfm)
        cf.set_length(16)
        enc.set_crypt_filter_dictionary(name, cf)
    if stm_f is not None:
        enc.set_stm_f(stm_f)
    if str_f is not None:
        enc.set_str_f(str_f)
    if eff is not None:
        enc.set_eff(eff)
    if encrypt_metadata is not None:
        enc.set_encrypt_meta_data(encrypt_metadata)
    o, u = _password_pair_for_v4(
        encrypt_metadata=True if encrypt_metadata is None else encrypt_metadata
    )
    enc.set_o(o)
    enc.set_u(u)
    return enc


def _prepared(encryption: PDEncryption) -> StandardSecurityHandler:
    handler = StandardSecurityHandler()
    handler.prepare_for_decryption(
        encryption, _DOC_ID, StandardDecryptionMaterial("")
    )
    return handler


class _FakeStream:
    """Minimal stand-in exercising ``SecurityHandler.decrypt_stream_in_place``.

    Exposes the duck-typed surface the in-place decrypt path probes:
    ``get_cos_name`` (for /Type), ``get_raw_bytes`` / ``set_raw_bytes``.
    """

    def __init__(self, type_name: str | None, raw: bytes) -> None:
        self._type = COSName.get_pdf_name(type_name) if type_name else None
        self._raw = raw

    def get_cos_name(self, key: COSName) -> COSName | None:
        if key == COSName.TYPE:
            return self._type
        return None

    def get_raw_bytes(self) -> bytes:
        return self._raw

    def set_raw_bytes(self, data: bytes) -> None:
        self._raw = data


# ==========================================================================
# /StmF and /StrF resolution against /CF (named entry vs. Identity).


def test_stmf_named_cf_resolves_cfm() -> None:
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f="StdCF", str_f="StdCF"
    )
    handler = _prepared(enc)
    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_string_cfm() == "AESV2"


def test_stmf_identity_streams_not_encrypted_strings_aes() -> None:
    """/StmF Identity ⇒ streams pass through; /StrF AESV2 ⇒ strings cipher."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f="Identity", str_f="StdCF"
    )
    handler = _prepared(enc)
    assert handler.get_stream_cfm() == "Identity"
    assert handler.get_string_cfm() == "AESV2"
    payload = b"stream bytes \x00\x01"
    assert handler.decrypt_stream(payload, 9, 0) == payload
    assert handler.encrypt_stream(payload, 9, 0) == payload


def test_strf_identity_strings_not_encrypted_streams_aes() -> None:
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f="StdCF", str_f="Identity"
    )
    handler = _prepared(enc)
    assert handler.get_string_cfm() == "Identity"
    s = b"a string"
    assert handler.decrypt_string(s, 4, 0) == s
    assert handler.encrypt_string(s, 4, 0) == s


def test_both_identity_passthrough() -> None:
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f="Identity", str_f="Identity"
    )
    handler = _prepared(enc)
    data = b"\xde\xad\xbe\xef" * 8
    assert handler.decrypt_stream(data, 2, 0) == data
    assert handler.decrypt_string(data, 2, 0) == data


@pytest.mark.parametrize(
    ("cfm", "expect_aes"),
    [("V2", False), ("AESV2", True), ("AESV3", True)],
)
def test_cfm_dispatch_aes_vs_rc4(cfm: str, expect_aes: bool) -> None:
    """Each /CFM routes its object kind to the matching cipher primitive."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": cfm}, stm_f="StdCF", str_f="Identity"
    )
    handler = _prepared(enc)
    with (
        patch(f"{_TARGET}._aes128_cbc_decrypt", return_value=b"AES") as aes,
        patch(f"{_TARGET}._rc4", return_value=b"RC4") as rc4,
    ):
        out = handler.decrypt_stream(b"\x00" * 32, 1, 0)
    if expect_aes:
        assert out == b"AES"
        assert aes.call_count == 1
        assert rc4.call_count == 0
    else:
        assert out == b"RC4"
        assert rc4.call_count == 1
        assert aes.call_count == 0


def test_cfm_aesv3_uses_file_key_directly() -> None:
    """AESV3 ⇒ AES-256 with the file key, no per-object salt."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV3"}, stm_f="StdCF", str_f="StdCF"
    )
    handler = _prepared(enc)
    file_key = handler.get_encryption_key()
    captured: dict[str, bytes] = {}

    def _spy(key: bytes, data: bytes) -> bytes:
        captured["key"] = key
        return b"OUT"

    with patch(f"{_TARGET}._aes128_cbc_decrypt", side_effect=_spy):
        handler.decrypt_stream(b"\x00" * 32, 11, 7)
    assert captured["key"] == file_key


def test_cfm_v2_rc4_no_aes_salt() -> None:
    """V2 ⇒ RC4 with the per-object key derived WITHOUT the sAlT suffix."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "V2"}, stm_f="StdCF", str_f="StdCF"
    )
    handler = _prepared(enc)
    expected_key = handler.compute_object_key(3, 0, aes=False)
    captured: dict[str, bytes] = {}

    def _spy(key: bytes, data: bytes) -> bytes:
        captured["key"] = key
        return b"OUT"

    with patch(f"{_TARGET}._rc4", side_effect=_spy):
        handler.decrypt_stream(b"abc", 3, 0)
    assert captured["key"] == expected_key


def test_cfm_aesv2_uses_salted_object_key() -> None:
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f="StdCF", str_f="StdCF"
    )
    handler = _prepared(enc)
    salted = handler.compute_object_key(5, 0, aes=True)
    unsalted = handler.compute_object_key(5, 0, aes=False)
    assert salted != unsalted
    captured: dict[str, bytes] = {}

    def _spy(key: bytes, data: bytes) -> bytes:
        captured["key"] = key
        return b"OUT"

    with patch(f"{_TARGET}._aes128_cbc_decrypt", side_effect=_spy):
        handler.decrypt_stream(b"\x00" * 32, 5, 0)
    assert captured["key"] == salted


# ==========================================================================
# Missing /CF entry / unknown filter names.


def test_stmf_names_missing_cf_entry_falls_back_to_name_heuristic() -> None:
    """/StmF points at a name with NO /CF entry but the name itself is a
    known algorithm — PDFBox treats the name as the algorithm."""
    enc = _build_v4_encryption(
        cf_entries={}, stm_f="AESV2", str_f="V2"
    )
    handler = _prepared(enc)
    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_string_cfm() == "V2"


def test_stmf_unknown_name_no_cf_entry_resolves_identity_default() -> None:
    """A /StmF name that is neither Identity nor a known algorithm and has no
    /CF entry resolves to None → the slot keeps the routing default. With /CF
    present the absent-resolution is the legacy fallback (None)."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f="Mystery", str_f="StdCF"
    )
    handler = _prepared(enc)
    # Unknown name, no matching /CF entry, not a known algo → None (legacy).
    assert handler.get_stream_cfm() is None
    assert handler.get_string_cfm() == "AESV2"


def test_absent_strf_with_cf_defaults_to_identity() -> None:
    """/CF present, /StmF set, /StrF ABSENT → strings default to Identity
    (PDF 32000-1 §7.6.4.4 Table 20), not the document AES cipher."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f="StdCF", str_f=None
    )
    handler = _prepared(enc)
    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_string_cfm() == "Identity"
    s = b"cleartext string"
    assert handler.decrypt_string(s, 1, 0) == s


def test_absent_stmf_with_cf_defaults_to_identity() -> None:
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f=None, str_f="StdCF"
    )
    handler = _prepared(enc)
    assert handler.get_stream_cfm() == "Identity"
    assert handler.get_string_cfm() == "AESV2"


# ==========================================================================
# /EFF embedded-file filter.


def test_eff_defaults_to_stmf_when_absent() -> None:
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f="StdCF", str_f="StdCF"
    )
    handler = _prepared(enc)
    assert handler.get_embedded_file_cfm() == "AESV2"


def test_eff_overrides_stmf() -> None:
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2", "EmbCF": "V2"},
        stm_f="StdCF",
        str_f="StdCF",
        eff="EmbCF",
    )
    handler = _prepared(enc)
    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_embedded_file_cfm() == "V2"


def test_eff_identity_embedded_files_not_encrypted() -> None:
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="StdCF",
        str_f="StdCF",
        eff="Identity",
    )
    handler = _prepared(enc)
    assert handler.get_embedded_file_cfm() == "Identity"
    payload = b"embedded file body"
    assert handler.decrypt_stream(payload, 8, 0, is_embedded_file=True) == payload
    # ...while ordinary streams still cipher.
    with patch(f"{_TARGET}._aes128_cbc_decrypt", return_value=b"AES") as aes:
        handler.decrypt_stream(b"\x00" * 32, 8, 0, is_embedded_file=False)
    assert aes.call_count == 1


# ==========================================================================
# /Length default in the crypt filter dictionary.


def test_crypt_filter_length_default_is_40_bits() -> None:
    """PDCryptFilterDictionary.get_length default mirrors upstream getInt(40)."""
    cf = PDCryptFilterDictionary()
    assert cf.get_length() == 40


def test_crypt_filter_length_explicit() -> None:
    cf = PDCryptFilterDictionary()
    cf.set_length(16)
    assert cf.get_length() == 16
    assert cf.has_length()


def test_crypt_filter_cfm_roundtrip() -> None:
    cf = PDCryptFilterDictionary()
    assert cf.get_cfm() is None
    for name in ("V2", "AESV2", "AESV3", "None", "Identity"):
        cf.set_cfm(name)
        assert cf.get_cfm() == name
        assert cf.has_cfm()
    cf.clear_cfm()
    assert cf.get_cfm() is None


# ==========================================================================
# /EncryptMetadata — default true, and effect on the dict-walk decrypt.


def test_encrypt_metadata_default_true() -> None:
    enc = PDEncryption()
    assert enc.is_encrypt_meta_data() is True
    cf = PDCryptFilterDictionary()
    assert cf.get_encrypt_metadata() is True


def test_encrypt_metadata_false_roundtrip() -> None:
    enc = PDEncryption()
    enc.set_encrypt_meta_data(False)
    assert enc.is_encrypt_meta_data() is False


def test_decrypt_metadata_flag_set_from_encrypt_metadata_true() -> None:
    """Regression: prepare_for_decryption must propagate /EncryptMetadata to
    the base handler's decrypt-metadata flag (upstream
    setDecryptMetadata(encryption.isEncryptMetaData()))."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="StdCF",
        str_f="StdCF",
        encrypt_metadata=True,
    )
    handler = _prepared(enc)
    assert handler.is_decrypt_metadata() is True


def test_decrypt_metadata_flag_set_from_encrypt_metadata_false() -> None:
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="StdCF",
        str_f="StdCF",
        encrypt_metadata=False,
    )
    handler = _prepared(enc)
    assert handler.is_decrypt_metadata() is False


def test_metadata_stream_skipped_when_encrypt_metadata_false() -> None:
    """With /EncryptMetadata false, the dict-walk decrypt leaves a
    /Type /Metadata stream untouched (upstream SecurityHandler.decryptStream
    short-circuits on ``!decryptMetadata && Metadata``)."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="StdCF",
        str_f="StdCF",
        encrypt_metadata=False,
    )
    handler = _prepared(enc)
    raw = b"\x01\x02\x03\x04 cleartext metadata bytes"
    stream = _FakeStream("Metadata", raw)
    with patch(f"{_TARGET}._aes128_cbc_decrypt") as aes:
        handler.decrypt_stream_in_place(stream, 6, 0)
    # Untouched: no cipher ran, raw unchanged.
    assert stream.get_raw_bytes() == raw
    assert aes.call_count == 0


def test_metadata_stream_decrypted_when_encrypt_metadata_true() -> None:
    """With /EncryptMetadata true, a /Type /Metadata stream (NOT a cleartext
    XMP packet) is run through the cipher on the dict-walk path."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="StdCF",
        str_f="StdCF",
        encrypt_metadata=True,
    )
    handler = _prepared(enc)
    raw = b"\xaa" * 48
    stream = _FakeStream("Metadata", raw)
    with patch(
        f"{_TARGET}._aes128_cbc_decrypt", return_value=b"PLAIN"
    ) as aes:
        handler.decrypt_stream_in_place(stream, 6, 0)
    assert aes.call_count == 1
    assert stream.get_raw_bytes() == b"PLAIN"


def test_cleartext_xmp_metadata_left_untouched_even_when_encrypt_true() -> None:
    """PDFBOX-3173 — a /Type /Metadata stream already starting with the XMP
    marker <?xpacket is treated as cleartext and not deciphered, even though
    /EncryptMetadata is true."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="StdCF",
        str_f="StdCF",
        encrypt_metadata=True,
    )
    handler = _prepared(enc)
    raw = b"<?xpacket begin=...?> rest of cleartext xmp"
    stream = _FakeStream("Metadata", raw)
    with patch(f"{_TARGET}._aes128_cbc_decrypt") as aes:
        handler.decrypt_stream_in_place(stream, 6, 0)
    assert stream.get_raw_bytes() == raw
    assert aes.call_count == 0


def test_xref_stream_never_decrypted() -> None:
    """A /Type /XRef stream is always skipped on the dict-walk path."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f="StdCF", str_f="StdCF"
    )
    handler = _prepared(enc)
    raw = b"\x99" * 32
    stream = _FakeStream("XRef", raw)
    with patch(f"{_TARGET}._aes128_cbc_decrypt") as aes:
        handler.decrypt_stream_in_place(stream, 6, 0)
    assert stream.get_raw_bytes() == raw
    assert aes.call_count == 0


def test_stmf_identity_stream_in_place_short_circuits() -> None:
    """/StmF Identity ⇒ even the in-place dict-walk decrypt leaves the body
    alone (the _is_identity guard fires before any cipher)."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f="Identity", str_f="StdCF"
    )
    handler = _prepared(enc)
    # The base in-place path checks _stream_filter_name; set it to match the
    # document /StmF so the Identity short-circuit is exercised.
    handler.set_stream_filter_name(COSName.get_pdf_name("Identity"))
    raw = b"\x55" * 32
    stream = _FakeStream("FlateDecode", raw)
    with patch(f"{_TARGET}._aes128_cbc_decrypt") as aes:
        handler.decrypt_stream_in_place(stream, 6, 0)
    assert stream.get_raw_bytes() == raw
    assert aes.call_count == 0


# ==========================================================================
# get_crypt_filter_dictionary lookups.


def test_get_crypt_filter_dictionary_missing_returns_none() -> None:
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f="StdCF", str_f="StdCF"
    )
    assert enc.get_crypt_filter_dictionary("NotThere") is None
    assert enc.get_std_crypt_filter_dictionary() is not None
    assert enc.get_std_crypt_filter_dictionary().get_cfm() == "AESV2"


def test_get_crypt_filter_dictionary_no_cf_returns_none() -> None:
    enc = PDEncryption()
    assert enc.get_crypt_filter_dictionary("StdCF") is None
    assert enc.has_cf() is False


def test_set_crypt_filter_dictionary_creates_cf() -> None:
    enc = PDEncryption()
    cf = PDCryptFilterDictionary()
    cf.set_cfm("AESV3")
    enc.set_crypt_filter_dictionary("StdCF", cf)
    assert enc.has_cf() is True
    got = enc.get_crypt_filter_dictionary("StdCF")
    assert got is not None
    assert got.get_cfm() == "AESV3"


def test_stmf_default_identity_name_when_absent() -> None:
    """get_stream_filter_name / get_string_filter_name return Identity when
    the entry is absent (upstream default)."""
    enc = PDEncryption()
    assert enc.get_stream_filter_name() == "Identity"
    assert enc.get_string_filter_name() == "Identity"
    assert enc.get_stm_f() is None
    assert enc.get_str_f() is None


# ==========================================================================
# /CF dictionary entries are themselves never decrypted (PDFBOX-2936).


def test_cf_subdictionary_not_decrypted() -> None:
    """A dictionary carrying a /CF key is returned unchanged by the decrypt
    dispatch — its crypt-filter sub-dict must stay cleartext."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"}, stm_f="StdCF", str_f="StdCF"
    )
    handler = _prepared(enc)
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("CF"), COSDictionary())
    assert handler.decrypt(d, 1, 0) is d
