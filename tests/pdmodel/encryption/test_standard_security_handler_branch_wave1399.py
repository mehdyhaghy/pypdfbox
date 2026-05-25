"""Wave 1399 — close residual partial branches on ``standard_security_handler``.

Targets the 5 partial arrows surviving after wave 1396:

* 712->716 — ``_is_aes_v4`` falls through to /StmF heuristic when the
  named crypt filter has /CFM=None.
* 739->744 — ``_resolve_cfm`` falls through to legacy filter-name
  heuristic when the named crypt filter has /CFM=None.
* 1148->exit — ``prepare_document`` against a document that does NOT
  expose ``set_encryption_dictionary`` (no-op exit).
* 1187->1201 — ``_get_document_id_bytes`` against an object whose
  ``size`` attribute is not callable.
* 1750->1752 — ``_validate_perms_r5_r6`` with a positive (high bit
  clear) permissions integer that matches /P.
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSString
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)

# ---------- 712->716 — _is_aes_v4 with /CFM=None falls back to StmF ---------


def test_is_aes_v4_cfm_none_falls_back_to_filter_name_heuristic() -> None:
    """A /CF/StdCF entry whose ``get_cfm()`` returns ``None`` makes
    ``_is_aes_v4`` fall through to the legacy /StmF == AESV2/V3 check.

    Closes the False arm of the ``cfm is not None`` guard at line 712.
    """
    encryption = PDEncryption()
    encryption.set_v(4)
    encryption.set_revision(4)
    encryption.set_stm_f("AESV2")  # legacy: name directly in /StmF
    # Install a /CF/AESV2 entry with NO /CFM attribute set → get_cfm() → None.
    cf = PDCryptFilterDictionary()
    # Deliberately do NOT call set_cfm — leaves /CFM absent.
    encryption.set_crypt_filter_dictionary("AESV2", cf)

    assert StandardSecurityHandler._is_aes_v4(encryption) is True


def test_is_aes_v4_cfm_none_with_unknown_filter_name_returns_false() -> None:
    """When /CF has no /CFM AND /StmF is not a known algorithm token,
    ``_is_aes_v4`` returns False (closes the False return on L716)."""
    encryption = PDEncryption()
    encryption.set_v(4)
    encryption.set_revision(4)
    encryption.set_stm_f("CustomFilter")
    cf = PDCryptFilterDictionary()  # no /CFM
    encryption.set_crypt_filter_dictionary("CustomFilter", cf)

    assert StandardSecurityHandler._is_aes_v4(encryption) is False


# ---------- 739->744 — _resolve_cfm /CF entry with /CFM=None ----------------


def test_resolve_cfm_falls_back_to_filter_name_heuristic_when_cfm_missing() -> None:
    """A /CF entry whose ``get_cfm()`` is ``None`` makes ``_resolve_cfm``
    fall through to treating the filter name as the algorithm. Closes
    False arm at L739."""
    encryption = PDEncryption()
    encryption.set_v(4)
    cf = PDCryptFilterDictionary()  # no /CFM
    encryption.set_crypt_filter_dictionary("AESV3", cf)

    # filter_name is one of the algorithm tokens → legacy heuristic resolves it.
    assert StandardSecurityHandler._resolve_cfm(encryption, "AESV3") == "AESV3"


def test_resolve_cfm_unknown_filter_name_returns_none() -> None:
    """A filter name that is not one of the legacy algorithm tokens
    returns ``None`` (legacy path). Closes the final return at L747."""
    encryption = PDEncryption()
    encryption.set_v(4)
    cf = PDCryptFilterDictionary()  # no /CFM
    encryption.set_crypt_filter_dictionary("MyCustomFilter", cf)

    assert StandardSecurityHandler._resolve_cfm(encryption, "MyCustomFilter") is None


# ---------- 1148->exit — prepare_document on doc lacking setter ------------


def test_prepare_document_no_set_encryption_dictionary_attribute_no_op_exits() -> None:
    """``prepare_document`` against a document object that does NOT
    expose ``set_encryption_dictionary`` exits cleanly after running
    the routing-table cache. Closes the False arm of the
    ``hasattr(document, "set_encryption_dictionary")`` guard at L1148.
    """
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )

    handler = StandardSecurityHandler()
    policy = StandardProtectionPolicy("owner-pw", "user-pw")
    policy.set_encryption_key_length(128)
    handler.set_protection_policy(policy)

    class _DocNoSetter:
        """Lacks ``set_encryption_dictionary`` — only a /ID lookup helper."""

        def get_document(self) -> object | None:
            return None

    # Must not raise — guard at L1148 evaluates False and the function
    # returns cleanly.
    handler.prepare_document(_DocNoSetter())


# ---------- 1187->1201 — _get_document_id_bytes non-callable .size ----------


def test_get_document_id_bytes_non_callable_size_falls_through_to_empty() -> None:
    """A COSArray-like object whose ``size`` is a non-callable attribute
    (e.g. an integer field on a Java-translated DTO) falls through to
    the final ``return b""``. Closes False arm at L1187."""

    class _DTONonCallableSize:
        # size as data attribute, not a method.
        size = 1

    assert StandardSecurityHandler._get_document_id_bytes(_DTONonCallableSize()) == b""


def test_get_document_id_bytes_cos_array_round_trip() -> None:
    """A real COSArray with a /ID[0] COSString round-trips through
    ``_get_document_id_bytes`` — sanity check that the True arm at
    L1187 still works after the new False-arm tests."""
    arr = COSArray()
    arr.add(COSString(b"\xAA" * 16))
    assert StandardSecurityHandler._get_document_id_bytes(arr) == b"\xAA" * 16


# ---------- 1750->1752 — _validate_perms_r5_r6 with positive perm-int -------


def test_validate_perms_r5_r6_with_positive_permission_int_succeeds() -> None:
    """A /Perms whose decoded permission int has the high bit *clear*
    (a positive 32-bit int) matches /P verbatim, skipping the
    two's-complement adjustment at L1751. Closes the False arm of the
    ``perms_p & 0x80000000`` guard at L1750."""
    # 1) Pick a small positive permission integer (high bit clear).
    permissions = 0x0000_0010  # 16 — high bit definitely 0
    # 2) Build the plaintext Perms block per ISO 32000-2 §7.6.4.4.10:
    #     bytes[0..3]   = little-endian permission int
    #     bytes[4..7]   = 0xFF padding (don't care)
    #     bytes[8]      = 'T' or 'F' (encrypt_metadata)
    #     bytes[9..11]  = 'a' 'd' 'b'
    #     bytes[12..15] = arbitrary
    plain = bytearray(16)
    plain[0] = permissions & 0xFF
    plain[1] = (permissions >> 8) & 0xFF
    plain[2] = (permissions >> 16) & 0xFF
    plain[3] = (permissions >> 24) & 0xFF
    plain[8] = ord("T")
    plain[9] = ord("a")
    plain[10] = ord("d")
    plain[11] = ord("b")

    # Encrypt the plaintext under a known 32-byte key so _decrypt_perms_r5_r6
    # gives us back ``plain`` verbatim.
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    file_key = b"\x11" * 32
    enc = Cipher(algorithms.AES(file_key), modes.ECB()).encryptor()
    ciphertext = enc.update(bytes(plain)) + enc.finalize()

    ok = StandardSecurityHandler._validate_perms_r5_r6(
        file_key, ciphertext, permissions, encrypt_metadata=True
    )
    assert ok is True


# ---------- /CF crypt filter variants — encrypt + decrypt round-trip ----


def test_encrypt_decrypt_round_trip_r4_aes_via_cf_filter() -> None:
    """Behavioural round-trip: R=4 with AES-128 routed through an
    explicit /CF/StdCF entry. Confirms the full prepare-document →
    set-encryption-dictionary → routing-table path works end to end."""
    import io

    from pypdfbox import PDDocument
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel import PDPage
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )

    pd = PDDocument()
    page = PDPage()
    pd.add_page(page)
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(b"Hello R4-AES round-trip")
    page.set_contents(stream)

    policy = StandardProtectionPolicy("owner-pw", "user-pw")
    policy.set_encryption_key_length(128)
    policy.set_prefer_aes(True)  # forces R=4 + AESV2 via /CF
    pd.protect(policy)

    sink = io.BytesIO()
    pd.save(sink)
    pd.close()

    with PDDocument.load(sink.getvalue(), password="user-pw") as reopened:
        assert reopened.get_number_of_pages() == 1


def test_encrypt_decrypt_round_trip_r6_aes256_custom_permissions() -> None:
    """Behavioural round-trip: R=6 / V=5 / AES-256 with a custom
    permission set (print disabled). Validates the full r6 dictionary
    build + reload path."""
    import io

    from pypdfbox import PDDocument
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel import PDPage
    from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )

    pd = PDDocument()
    page = PDPage()
    pd.add_page(page)
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(b"R6 custom-perm payload")
    page.set_contents(stream)

    perms = AccessPermission()
    perms.set_can_print(False)
    policy = StandardProtectionPolicy("owner-pw", "user-pw", perms)
    policy.set_encryption_key_length(256)
    pd.protect(policy)

    sink = io.BytesIO()
    pd.save(sink)
    pd.close()

    with PDDocument.load(sink.getvalue(), password="user-pw") as reopened:
        # Confirm the custom permission survived the round-trip.
        recovered = reopened.get_current_access_permission()
        assert recovered.can_print() is False
