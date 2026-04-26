"""Per-object crypt-filter dispatch on ``StandardSecurityHandler``.

Covers PDF 32000-1 §7.6.5 — the ``/Encrypt`` dictionary may declare
*different* algorithms for streams (``/StmF``), strings (``/StrF``) and
embedded files (``/EFF``), each pointing at a named entry in ``/CF`` whose
``/CFM`` names the algorithm (``V2`` = RC4, ``AESV2`` = AES-128-CBC,
``AESV3`` = AES-256-CBC, ``Identity`` = no cipher).

Tests focus on **routing**: that the right cipher is invoked for the right
object kind. Round-trip parity for each cipher individually is already
covered by ``test_standard_security_handler.py``.
"""

from __future__ import annotations

from unittest.mock import patch

from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)

# --------------------------------------------------------------------------
# Helpers — build encryption dicts wired with a custom /CF routing table.

_DOC_ID = b"\x00" * 16


def _password_pair_for_v4(key_len_bytes: int = 16) -> tuple[bytes, bytes]:
    """Return /O and /U for the empty user/owner password at R=4."""
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        b"", b"", 4, key_len_bytes
    )
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        b"", o, -3904, _DOC_ID, 4, key_len_bytes
    )
    return o, u


def _build_v4_encryption(
    *,
    cf_entries: dict[str, str],
    stm_f: str,
    str_f: str,
    eff: str | None = None,
) -> PDEncryption:
    """Build a V=4 R=4 ``/Encrypt`` dictionary with arbitrary /CF entries.

    ``cf_entries`` maps ``/CF`` filter name → ``/CFM`` value. ``stm_f`` /
    ``str_f`` / ``eff`` are written as the corresponding name entries on the
    encryption dictionary itself.
    """
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
    enc.set_stm_f(stm_f)
    enc.set_str_f(str_f)
    if eff is not None:
        enc.set_eff(eff)
    o, u = _password_pair_for_v4()
    enc.set_o(o)
    enc.set_u(u)
    return enc


def _prepared_handler(encryption: PDEncryption) -> StandardSecurityHandler:
    handler = StandardSecurityHandler()
    handler.prepare_for_decryption(
        encryption, _DOC_ID, StandardDecryptionMaterial("")
    )
    return handler


# --------------------------------------------------------------------------
# Routing-table population.


def test_routing_table_empty_for_v_lt_4() -> None:
    """V=2 (legacy RC4-128) has no /CF — the routing slots stay None so
    SecurityHandler's single-algorithm path runs."""
    enc = PDEncryption()
    enc.set_filter("Standard")
    enc.set_v(2)
    enc.set_revision(3)
    enc.set_length(128)
    enc.set_p(-3904)
    o = StandardSecurityHandler._compute_owner_password_r2_r4(b"", b"", 3, 16)
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        b"", o, -3904, _DOC_ID, 3, 16
    )
    enc.set_o(o)
    enc.set_u(u)

    handler = _prepared_handler(enc)
    assert handler.get_stream_cfm() is None
    assert handler.get_string_cfm() is None
    assert handler.get_embedded_file_cfm() is None


def test_routing_table_v4_stmf_aesv2_strf_identity() -> None:
    """Mixed: streams encrypted (AESV2), strings pass-through (Identity)."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="StdCF",
        str_f="Identity",
    )
    handler = _prepared_handler(enc)
    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_string_cfm() == "Identity"
    # /EFF absent → embedded files inherit /StmF.
    assert handler.get_embedded_file_cfm() == "AESV2"


def test_routing_table_eff_overrides_stmf() -> None:
    """When /EFF is declared, embedded files use it instead of /StmF."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="StdCF",
        str_f="StdCF",
        eff="Identity",
    )
    handler = _prepared_handler(enc)
    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_embedded_file_cfm() == "Identity"


def test_routing_table_mixed_rc4_streams_aes_strings() -> None:
    """Two named CF entries — streams use V2 (RC4), strings use AESV2."""
    enc = _build_v4_encryption(
        cf_entries={"RC4Filter": "V2", "AESFilter": "AESV2"},
        stm_f="RC4Filter",
        str_f="AESFilter",
    )
    handler = _prepared_handler(enc)
    assert handler.get_stream_cfm() == "V2"
    assert handler.get_string_cfm() == "AESV2"


# --------------------------------------------------------------------------
# Cipher dispatch — verify the right cipher is invoked for the right object
# kind. We mock-cipher each algorithm so the test is independent of the real
# crypto round-trip (which is already covered by the standard handler tests).


def test_dispatch_strings_unchanged_when_strf_identity() -> None:
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="StdCF",
        str_f="Identity",
    )
    handler = _prepared_handler(enc)
    plaintext = b"hello identity"
    # Identity → bytes pass straight through, no key derivation, no cipher.
    assert handler.encrypt_string(plaintext, 7, 0) == plaintext
    assert handler.decrypt_string(plaintext, 7, 0) == plaintext


def test_dispatch_streams_aes_decrypted_when_stmf_aesv2() -> None:
    """/StmF=StdCF (AESV2) routes streams through AES-128 — verify by mocking
    the AES helper and checking it was the one invoked (not RC4)."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="StdCF",
        str_f="Identity",
    )
    handler = _prepared_handler(enc)
    target = "pypdfbox.pdmodel.encryption.standard_security_handler"
    with (
        patch(f"{target}._aes128_cbc_decrypt", return_value=b"AES-OUT") as aes,
        patch(f"{target}._rc4", return_value=b"RC4-OUT") as rc4,
    ):
        out = handler.decrypt_stream(b"\x00" * 32, 5, 0)
    assert out == b"AES-OUT"
    assert aes.call_count == 1
    assert rc4.call_count == 0


def test_dispatch_strings_aes_when_strf_aesv2_streams_rc4_when_stmf_v2() -> None:
    """Mixed routing — strings AES, streams RC4 — both ciphers exercised in
    one handler. Each path must call exactly the cipher named by its /CFM."""
    enc = _build_v4_encryption(
        cf_entries={"RC4Filter": "V2", "AESFilter": "AESV2"},
        stm_f="RC4Filter",
        str_f="AESFilter",
    )
    handler = _prepared_handler(enc)
    target = "pypdfbox.pdmodel.encryption.standard_security_handler"
    with (
        patch(f"{target}._aes128_cbc_decrypt", return_value=b"AES-OUT") as aes,
        patch(f"{target}._rc4", return_value=b"RC4-OUT") as rc4,
    ):
        str_out = handler.decrypt_string(b"hello", 1, 0)
        strm_out = handler.decrypt_stream(b"\x00" * 32, 1, 0)
    assert str_out == b"AES-OUT"
    assert strm_out == b"RC4-OUT"
    assert aes.call_count == 1
    assert rc4.call_count == 1


def test_dispatch_embedded_file_uses_eff_filter() -> None:
    """is_embedded_file=True routes through /EFF, not /StmF."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="StdCF",
        str_f="StdCF",
        eff="Identity",
    )
    handler = _prepared_handler(enc)
    payload = b"embedded-bytes"
    target = "pypdfbox.pdmodel.encryption.standard_security_handler"
    with patch(f"{target}._aes128_cbc_decrypt") as aes:
        out = handler.decrypt_stream(payload, 9, 0, is_embedded_file=True)
    # /EFF=Identity → embedded file passes through, AES is never called.
    assert out == payload
    assert aes.call_count == 0


def test_dispatch_embedded_file_falls_back_to_stmf_when_eff_absent() -> None:
    """No /EFF → embedded files use /StmF (spec default)."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="StdCF",
        str_f="Identity",
    )
    handler = _prepared_handler(enc)
    target = "pypdfbox.pdmodel.encryption.standard_security_handler"
    with patch(f"{target}._aes128_cbc_decrypt", return_value=b"AES-OUT") as aes:
        out = handler.decrypt_stream(b"\x00" * 32, 9, 0, is_embedded_file=True)
    assert out == b"AES-OUT"
    assert aes.call_count == 1


def test_dispatch_aesv3_uses_file_key_directly() -> None:
    """V=5 / AESV3 — file key passed straight to AES, no per-object hashing."""
    # Build a V=5 R=6 encryption + handler the same way the existing r6
    # round-trip test does, then verify the AES dispatcher is called with
    # the *file* key (not a per-object derivation).
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)
    file_key = b"\x42" * 32
    handler.set_encryption_key(file_key)

    enc = PDEncryption()
    enc.set_v(5)
    enc.set_revision(6)
    enc.set_length(256)
    cf = PDCryptFilterDictionary()
    cf.set_cfm("AESV3")
    cf.set_length(32)
    enc.set_std_crypt_filter_dictionary(cf)
    enc.set_stm_f("StdCF")
    enc.set_str_f("StdCF")
    handler._populate_routing_table(enc)
    assert handler.get_stream_cfm() == "AESV3"

    target = "pypdfbox.pdmodel.encryption.standard_security_handler"
    with patch(f"{target}._aes128_cbc_decrypt", return_value=b"AES-OUT") as aes:
        out = handler.decrypt_stream(b"\x00" * 32, 7, 0)
    assert out == b"AES-OUT"
    aes.assert_called_once()
    # The first positional arg to the AES helper is the key. AESV3 uses the
    # file key directly — no per-object MD5 mixing.
    assert aes.call_args.args[0] == file_key


def test_unknown_cf_filter_name_falls_back_to_legacy_path() -> None:
    """If /StmF names a filter that isn't in /CF and isn't a known algorithm
    name, _resolve_cfm returns None — the legacy single-algo path runs."""
    enc = _build_v4_encryption(
        cf_entries={"StdCF": "AESV2"},
        stm_f="GhostFilter",  # not in /CF
        str_f="StdCF",
    )
    handler = _prepared_handler(enc)
    assert handler.get_stream_cfm() is None
    assert handler.get_string_cfm() == "AESV2"


# --------------------------------------------------------------------------
# Write side — prepare_document populates the routing table too.


def test_prepare_document_v4_aes_installs_std_cf_and_routes() -> None:
    """V=4 AES write path installs /CF/StdCF/CFM=AESV2 and routes accordingly."""
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )

    policy = StandardProtectionPolicy("owner", "user", None)
    # Force AES at 128 bits → V=4 / R=4 / AESV2 path.
    policy.set_encryption_key_length(128)
    policy.set_prefer_aes(True)

    captured: dict[str, PDEncryption] = {}

    class _Doc:
        def set_encryption_dictionary(self, enc: PDEncryption) -> None:
            captured["enc"] = enc

    handler = StandardSecurityHandler(policy)
    handler.prepare_document(_Doc())

    enc = captured["enc"]
    std = enc.get_std_crypt_filter_dictionary()
    assert std is not None
    assert std.get_cfm() == "AESV2"
    assert enc.get_stm_f() == "StdCF"
    assert enc.get_str_f() == "StdCF"
    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_string_cfm() == "AESV2"
    # /EFF defaults to /StmF on the write side too.
    assert handler.get_embedded_file_cfm() == "AESV2"
