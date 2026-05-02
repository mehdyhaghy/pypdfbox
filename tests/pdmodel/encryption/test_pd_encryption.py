from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSString
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.protection_policy import (
    DEFAULT_KEY_LENGTH,
    ProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)

# ---------- PDEncryption ----------


def test_pd_encryption_defaults() -> None:
    enc = PDEncryption()
    assert isinstance(enc.get_cos_object(), COSDictionary)
    assert enc.get_filter() is None
    assert enc.get_sub_filter() is None
    # Spec defaults: V=0 (undocumented), Length=40, R=0.
    assert enc.get_v() == 0
    assert enc.get_length() == 40
    assert enc.get_revision() == 0
    # /EncryptMetadata defaults to true per PDF 32000-1 §7.6.3.2.
    assert enc.is_encrypt_meta_data() is True
    assert enc.get_o() is None
    assert enc.get_u() is None
    assert enc.get_oe() is None
    assert enc.get_ue() is None
    assert enc.get_perms() is None
    assert enc.get_recipients() is None
    assert enc.get_cf() is None
    assert enc.get_stm_f() is None
    assert enc.get_str_f() is None


def test_pd_encryption_round_trip_standard_v4_r4_length128_p_minus_4() -> None:
    enc = PDEncryption()
    enc.set_filter("Standard")
    enc.set_v(4)
    enc.set_revision(4)
    enc.set_length(128)
    enc.set_p(-4)
    enc.set_sub_filter("adbe.pkcs7.detached")
    enc.set_stm_f("StdCF")
    enc.set_str_f("StdCF")

    assert enc.get_filter() == "Standard"
    assert enc.get_v() == 4
    assert enc.get_revision() == 4
    assert enc.get_length() == 128
    assert enc.get_p() == -4
    assert enc.get_sub_filter() == "adbe.pkcs7.detached"
    assert enc.get_stm_f() == "StdCF"
    assert enc.get_str_f() == "StdCF"

    # Wrap a fresh PDEncryption around the same dictionary — should observe
    # all the same values (true round-trip through COS storage).
    rehydrated = PDEncryption(enc.get_cos_object())
    assert rehydrated.get_filter() == "Standard"
    assert rehydrated.get_v() == 4
    assert rehydrated.get_revision() == 4
    assert rehydrated.get_length() == 128
    assert rehydrated.get_p() == -4


def test_pd_encryption_round_trip_o_and_u_bytes() -> None:
    enc = PDEncryption()
    o_hash = bytes(range(32))
    u_hash = bytes(range(32, 64))
    enc.set_o(o_hash)
    enc.set_u(u_hash)
    assert enc.get_o() == o_hash
    assert enc.get_u() == u_hash

    # Round-trip via fresh wrapper.
    rehydrated = PDEncryption(enc.get_cos_object())
    assert rehydrated.get_o() == o_hash
    assert rehydrated.get_u() == u_hash


def test_pd_encryption_round_trip_oe_ue_perms_bytes() -> None:
    enc = PDEncryption()
    oe = bytes([0x10] * 32)
    ue = bytes([0x20] * 32)
    perms = bytes([0xFF] * 16)
    enc.set_oe(oe)
    enc.set_ue(ue)
    enc.set_perms(perms)
    assert enc.get_oe() == oe
    assert enc.get_ue() == ue
    assert enc.get_perms() == perms


def test_pd_encryption_set_o_none_removes_entry() -> None:
    enc = PDEncryption()
    enc.set_o(b"\x01\x02\x03")
    assert enc.get_o() == b"\x01\x02\x03"
    enc.set_o(None)
    assert enc.get_o() is None


def test_pd_encryption_encrypt_metadata_round_trip() -> None:
    enc = PDEncryption()
    enc.set_encrypt_meta_data(False)
    assert enc.is_encrypt_meta_data() is False
    enc.set_encrypt_meta_data(True)
    assert enc.is_encrypt_meta_data() is True


def test_pd_encryption_cf_round_trip() -> None:
    enc = PDEncryption()
    cf = COSDictionary()
    enc.set_cf(cf)
    assert enc.get_cf() is cf


# ---------- AccessPermission ----------


def test_access_permission_default_allows_everything() -> None:
    perm = AccessPermission()
    assert perm.can_print()
    assert perm.can_modify()
    assert perm.can_extract_content()
    assert perm.can_modify_annotations()
    assert perm.can_fill_in_form()
    assert perm.can_extract_for_accessibility()
    assert perm.can_assemble_document()
    assert perm.can_print_degraded()
    assert perm.is_owner_permission()


def test_access_permission_each_flag_round_trip() -> None:
    pairs = [
        ("can_print", "set_can_print"),
        ("can_modify", "set_can_modify"),
        ("can_extract_content", "set_can_extract_content"),
        ("can_modify_annotations", "set_can_modify_annotations"),
        ("can_fill_in_form", "set_can_fill_in_form"),
        ("can_extract_for_accessibility", "set_can_extract_for_accessibility"),
        ("can_assemble_document", "set_can_assemble_document"),
        ("can_print_degraded", "set_can_print_degraded"),
    ]
    for getter, setter in pairs:
        perm = AccessPermission()
        assert getattr(perm, getter)() is True
        getattr(perm, setter)(False)
        assert getattr(perm, getter)() is False
        # And the other flags should still be set — flipping one bit must not
        # disturb the rest.
        for other_getter, _ in pairs:
            if other_getter == getter:
                continue
            assert getattr(perm, other_getter)() is True
        getattr(perm, setter)(True)
        assert getattr(perm, getter)() is True


def test_access_permission_owner_factory() -> None:
    perm = AccessPermission.get_owner_access_permission()
    assert perm.is_owner_permission() is True
    assert perm.can_print() and perm.can_modify() and perm.can_assemble_document()


def test_access_permission_set_read_only_freezes_state() -> None:
    perm = AccessPermission()
    perm.set_can_print(False)
    perm.set_read_only()
    perm.set_can_print(True)  # no-op once locked
    assert perm.can_print() is False
    assert perm.is_read_only() is True


def test_access_permission_get_permission_bytes_round_trip() -> None:
    perm = AccessPermission()
    perm.set_can_print(False)
    bits = perm.get_permission_bytes()
    rehydrated = AccessPermission(bits)
    assert rehydrated.can_print() is False
    assert rehydrated.can_modify() is True


# ---------- ProtectionPolicy ----------


def test_protection_policy_defaults() -> None:
    pp = ProtectionPolicy()
    assert pp.get_encryption_key_length() == DEFAULT_KEY_LENGTH == 40
    assert pp.is_prefer_aes() is False


def test_protection_policy_setters() -> None:
    pp = ProtectionPolicy()
    pp.set_encryption_key_length(128)
    assert pp.get_encryption_key_length() == 128
    pp.set_encryption_key_length(256)
    assert pp.get_encryption_key_length() == 256
    pp.set_prefer_aes(True)
    assert pp.is_prefer_aes() is True


def test_protection_policy_invalid_key_length() -> None:
    pp = ProtectionPolicy()
    import pytest

    with pytest.raises(ValueError):
        pp.set_encryption_key_length(64)


def test_protection_policy_default_key_length_class_constant() -> None:
    # Mirrors upstream's ``private static final short DEFAULT_KEY_LENGTH``
    # — exposed as a class attribute for parity. Subclasses inherit it.
    from pypdfbox.pdmodel.encryption import StandardProtectionPolicy

    assert ProtectionPolicy.DEFAULT_KEY_LENGTH == 40
    assert ProtectionPolicy.DEFAULT_KEY_LENGTH == DEFAULT_KEY_LENGTH
    # Inherited by subclasses (Java sees the same value through the base).
    assert StandardProtectionPolicy.DEFAULT_KEY_LENGTH == 40
    # Default-constructed instance picks up the class constant as its
    # initial key length.
    assert ProtectionPolicy().get_encryption_key_length() == ProtectionPolicy.DEFAULT_KEY_LENGTH


# ---------- StandardProtectionPolicy ----------


def test_standard_protection_policy_round_trip() -> None:
    perms = AccessPermission()
    perms.set_can_print(False)
    spp = StandardProtectionPolicy(
        owner_password="own3r",
        user_password="us3r",
        permissions=perms,
    )
    assert spp.get_owner_password() == "own3r"
    assert spp.get_user_password() == "us3r"
    assert spp.get_permissions() is perms
    assert spp.get_permissions().can_print() is False
    # Inherits ProtectionPolicy defaults.
    assert spp.get_encryption_key_length() == 40
    assert spp.is_prefer_aes() is False


def test_standard_protection_policy_setters() -> None:
    spp = StandardProtectionPolicy()
    assert spp.get_owner_password() is None
    assert spp.get_user_password() is None
    assert isinstance(spp.get_permissions(), AccessPermission)

    spp.set_owner_password("o")
    spp.set_user_password("u")
    new_perms = AccessPermission(0)
    spp.set_permissions(new_perms)
    assert spp.get_owner_password() == "o"
    assert spp.get_user_password() == "u"
    assert spp.get_permissions() is new_perms


# ---------- /Recipients (public-key handler helpers) ----------


def test_set_recipients_round_trip() -> None:
    enc = PDEncryption()
    envelopes = [b"first envelope bytes", b"\x00\x01\x02", b""]
    enc.set_recipients(envelopes)

    array = enc.get_recipients()
    assert array is not None
    assert array.size() == 3
    assert array.is_direct()
    # Stored as COSString preserving exact bytes.
    for i, raw in enumerate(envelopes):
        entry = array.get(i)
        assert isinstance(entry, COSString)
        assert entry.get_bytes() == raw


def test_set_recipients_replaces_existing() -> None:
    enc = PDEncryption()
    enc.set_recipients([b"a", b"b"])
    enc.set_recipients([b"only"])
    assert enc.get_recipients_length() == 1
    rec = enc.get_recipient_string_at(0)
    assert rec is not None
    assert rec.get_bytes() == b"only"


def test_get_recipients_length_returns_zero_when_absent() -> None:
    enc = PDEncryption()
    assert enc.get_recipients_length() == 0


def test_get_recipient_string_at_returns_none_when_absent() -> None:
    enc = PDEncryption()
    assert enc.get_recipient_string_at(0) is None


def test_get_recipient_string_at_returns_cos_string() -> None:
    enc = PDEncryption()
    enc.set_recipients([b"alpha", b"beta"])
    first = enc.get_recipient_string_at(0)
    second = enc.get_recipient_string_at(1)
    assert isinstance(first, COSString)
    assert isinstance(second, COSString)
    assert first.get_bytes() == b"alpha"
    assert second.get_bytes() == b"beta"


def test_set_recipients_accepts_tuple() -> None:
    enc = PDEncryption()
    enc.set_recipients((b"x", b"y"))
    assert enc.get_recipients_length() == 2


# ---------- stream/string filter name (Identity-defaulting accessors) ----------


def test_get_stream_filter_name_defaults_to_identity() -> None:
    enc = PDEncryption()
    # Raw absent state → None on get_stm_f, but Identity on get_stream_filter_name.
    assert enc.get_stm_f() is None
    assert enc.get_stream_filter_name() == "Identity"


def test_get_string_filter_name_defaults_to_identity() -> None:
    enc = PDEncryption()
    assert enc.get_str_f() is None
    assert enc.get_string_filter_name() == "Identity"


def test_set_stream_filter_name_round_trip() -> None:
    enc = PDEncryption()
    enc.set_stream_filter_name("StdCF")
    assert enc.get_stream_filter_name() == "StdCF"
    assert enc.get_stm_f() == "StdCF"


def test_set_string_filter_name_round_trip() -> None:
    enc = PDEncryption()
    enc.set_string_filter_name("StdCF")
    assert enc.get_string_filter_name() == "StdCF"
    assert enc.get_str_f() == "StdCF"


def test_recipients_array_after_get_recipients_for_existing_array() -> None:
    """``get_recipients`` returns the stored COSArray when /Recipients exists."""
    enc = PDEncryption()
    enc.set_recipients([b"a"])
    arr = enc.get_recipients()
    assert isinstance(arr, COSArray)


# ---------- get_owner_key / get_user_key (revision-aware padding) ----------


def test_get_owner_key_returns_none_when_absent() -> None:
    enc = PDEncryption()
    assert enc.get_owner_key() is None
    assert enc.get_user_key() is None


def test_get_owner_key_pads_to_32_for_revision_4() -> None:
    """For R ≤ 4, ``getOwnerKey`` returns a 32-byte buffer (zero-padded)."""
    enc = PDEncryption()
    enc.set_revision(4)
    enc.set_o(b"\x01\x02\x03")
    o = enc.get_owner_key()
    assert o is not None
    assert len(o) == 32
    assert o[:3] == b"\x01\x02\x03"
    assert o[3:] == b"\x00" * 29


def test_get_user_key_pads_to_32_for_revision_2() -> None:
    enc = PDEncryption()
    enc.set_revision(2)
    enc.set_u(b"\xAA")
    u = enc.get_user_key()
    assert u is not None
    assert len(u) == 32
    assert u[0] == 0xAA
    assert u[1:] == b"\x00" * 31


def test_get_owner_key_pads_to_48_for_revision_5() -> None:
    enc = PDEncryption()
    enc.set_revision(5)
    enc.set_o(b"\xFF" * 32)
    o = enc.get_owner_key()
    assert o is not None
    assert len(o) == 48
    assert o[:32] == b"\xFF" * 32
    assert o[32:] == b"\x00" * 16


def test_get_user_key_pads_to_48_for_revision_6() -> None:
    enc = PDEncryption()
    enc.set_revision(6)
    enc.set_u(b"\xAB" * 16)
    u = enc.get_user_key()
    assert u is not None
    assert len(u) == 48
    assert u[:16] == b"\xAB" * 16
    assert u[16:] == b"\x00" * 32


def test_get_owner_key_truncates_overlong_buffer() -> None:
    enc = PDEncryption()
    enc.set_revision(4)
    # 64 bytes — twice the R≤4 length; expect truncation to 32.
    enc.set_o(bytes(range(64)))
    o = enc.get_owner_key()
    assert o is not None
    assert len(o) == 32
    assert o == bytes(range(32))


def test_set_owner_key_round_trip() -> None:
    enc = PDEncryption()
    enc.set_owner_key(b"\x10" * 32)
    assert enc.get_o() == b"\x10" * 32


def test_set_user_key_none_removes_entry() -> None:
    enc = PDEncryption()
    enc.set_user_key(b"\x42" * 32)
    assert enc.get_u() == b"\x42" * 32
    enc.set_user_key(None)
    assert enc.get_u() is None


# ---------- get_owner_encryption_key / get_user_encryption_key ----------


def test_get_owner_encryption_key_returns_none_when_absent() -> None:
    enc = PDEncryption()
    assert enc.get_owner_encryption_key() is None
    assert enc.get_user_encryption_key() is None


def test_get_owner_encryption_key_pads_to_32() -> None:
    enc = PDEncryption()
    enc.set_oe(b"\xCD")
    oe = enc.get_owner_encryption_key()
    assert oe is not None
    assert len(oe) == 32
    assert oe[0] == 0xCD
    assert oe[1:] == b"\x00" * 31


def test_get_user_encryption_key_pads_to_32() -> None:
    enc = PDEncryption()
    enc.set_ue(b"\x01\x02")
    ue = enc.get_user_encryption_key()
    assert ue is not None
    assert len(ue) == 32
    assert ue[:2] == b"\x01\x02"
    assert ue[2:] == b"\x00" * 30


def test_get_user_encryption_key_truncates_overlong_buffer() -> None:
    enc = PDEncryption()
    # 40 bytes — longer than the 32-byte target; expect truncation.
    enc.set_ue(bytes(range(40)))
    ue = enc.get_user_encryption_key()
    assert ue is not None
    assert len(ue) == 32
    assert ue == bytes(range(32))


def test_get_owner_encryption_key_does_not_depend_on_revision() -> None:
    """Unlike ``getOwnerKey``, /OE is always 32 bytes regardless of /R.
    Mirrors upstream ``getOwnerEncryptionKey`` which is unconditional 32.
    """
    enc = PDEncryption()
    enc.set_revision(6)
    enc.set_oe(b"\x77" * 8)
    oe = enc.get_owner_encryption_key()
    assert oe is not None
    assert len(oe) == 32


def test_set_owner_encryption_key_round_trip() -> None:
    enc = PDEncryption()
    enc.set_owner_encryption_key(b"\x33" * 32)
    assert enc.get_oe() == b"\x33" * 32
    enc.set_owner_encryption_key(None)
    assert enc.get_oe() is None


def test_set_user_encryption_key_round_trip() -> None:
    enc = PDEncryption()
    enc.set_user_encryption_key(b"\x44" * 32)
    assert enc.get_ue() == b"\x44" * 32


# ---------- get_version / set_version / get_permissions / set_permissions ----------


def test_get_version_alias_matches_get_v() -> None:
    enc = PDEncryption()
    enc.set_v(4)
    assert enc.get_version() == 4
    assert enc.get_version() == enc.get_v()


def test_set_version_alias_matches_set_v() -> None:
    enc = PDEncryption()
    enc.set_version(5)
    assert enc.get_v() == 5
    assert enc.get_version() == 5


def test_get_permissions_alias_matches_get_p() -> None:
    enc = PDEncryption()
    enc.set_p(-3904)
    assert enc.get_permissions() == -3904
    assert enc.get_permissions() == enc.get_p()


def test_set_permissions_alias_matches_set_p() -> None:
    enc = PDEncryption()
    enc.set_permissions(-44)
    assert enc.get_p() == -44
    assert enc.get_permissions() == -44


def test_version_and_permissions_default_to_zero() -> None:
    """Both get_version (alias of get_v) and get_permissions (alias of get_p)
    fall back to 0 on a fresh dictionary, matching upstream defaults."""
    enc = PDEncryption()
    assert enc.get_version() == 0
    assert enc.get_permissions() == 0
