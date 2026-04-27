from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.digitalsignature import PDSeedValue

_FF: COSName = COSName.get_pdf_name("Ff")


# ---------- defaults ----------


def test_defaults_lists_are_empty() -> None:
    sv = PDSeedValue()
    assert sv.get_digest_method() == []
    assert sv.get_legal_attestation() == []


def test_defaults_required_flags_all_false() -> None:
    sv = PDSeedValue()
    assert sv.is_filter_required() is False
    assert sv.is_sub_filter_required() is False
    assert sv.is_reason_required() is False
    assert sv.is_legal_attestation_required() is False
    assert sv.is_add_rev_info_required() is False
    assert sv.is_digest_method_required() is False


def test_default_certificate_is_none() -> None:
    sv = PDSeedValue()
    assert sv.get_seed_value_certificate() is None


# ---------- round-trip accessors ----------


def test_round_trip_digest_method() -> None:
    sv = PDSeedValue()
    sv.set_digest_method(["SHA256", "SHA384", "SHA512"])
    assert sv.get_digest_method() == ["SHA256", "SHA384", "SHA512"]


def test_round_trip_legal_attestation() -> None:
    sv = PDSeedValue()
    sv.set_legal_attestation(["No Modifications Permitted", "Form Filling OK"])
    assert sv.get_legal_attestation() == [
        "No Modifications Permitted",
        "Form Filling OK",
    ]


def test_round_trip_seed_value_certificate() -> None:
    sv = PDSeedValue()
    cert = COSDictionary()
    cert.set_name("Type", "SVCert")
    sv.set_seed_value_certificate(cert)
    got = sv.get_seed_value_certificate()
    # get_seed_value_certificate now returns a typed PDSeedValueCertificate
    # wrapper around the underlying COSDictionary.
    assert got is not None
    assert got.get_cos_object() is cert
    assert got.get_cos_object().get_name("Type") == "SVCert"


# ---------- /Ff flag bit set/get ----------


def test_set_and_read_each_required_flag() -> None:
    sv = PDSeedValue()
    sv.set_filter_required(True)
    assert sv.is_filter_required() is True

    sv = PDSeedValue()
    sv.set_sub_filter_required(True)
    assert sv.is_sub_filter_required() is True

    sv = PDSeedValue()
    sv.set_reason_required(True)
    assert sv.is_reason_required() is True

    sv = PDSeedValue()
    sv.set_legal_attestation_required(True)
    assert sv.is_legal_attestation_required() is True

    sv = PDSeedValue()
    sv.set_add_rev_info_required(True)
    assert sv.is_add_rev_info_required() is True

    sv = PDSeedValue()
    sv.set_digest_method_required(True)
    assert sv.is_digest_method_required() is True


def test_independent_flags_do_not_clobber_each_other() -> None:
    sv = PDSeedValue()
    sv.set_filter_required(True)
    sv.set_digest_method_required(True)
    # Both bits should be set simultaneously; nothing else should be.
    assert sv.is_filter_required() is True
    assert sv.is_digest_method_required() is True
    assert sv.is_sub_filter_required() is False
    assert sv.is_reason_required() is False
    assert sv.is_legal_attestation_required() is False
    assert sv.is_add_rev_info_required() is False


def test_clearing_a_flag_leaves_siblings_intact() -> None:
    sv = PDSeedValue()
    sv.set_filter_required(True)
    sv.set_sub_filter_required(True)
    sv.set_reason_required(True)
    # Clear the middle one.
    sv.set_sub_filter_required(False)
    assert sv.is_sub_filter_required() is False
    assert sv.is_filter_required() is True
    assert sv.is_reason_required() is True


def test_setting_false_when_unset_keeps_flag_unset() -> None:
    sv = PDSeedValue()
    sv.set_filter_required(False)
    assert sv.is_filter_required() is False
    # /Ff should exist as an integer (0) but the bit must read False.
    cos = sv.get_cos_object()
    assert cos.get_int(_FF, default=-1) == 0
