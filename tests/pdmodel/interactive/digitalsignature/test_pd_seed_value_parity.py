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
    assert sv.is_v_required() is False
    assert sv.is_reason_required() is False
    assert sv.is_legal_attestation_required() is False
    assert sv.is_add_rev_info_required() is False
    assert sv.is_digest_method_required() is False


def test_default_v_is_none() -> None:
    sv = PDSeedValue()
    assert sv.get_v() is None


def test_default_constructor_sets_type_sv_and_direct() -> None:
    sv = PDSeedValue()
    cos = sv.get_cos_object()
    assert cos.get_name("Type") == "SV"
    # Mirrors upstream: dictionary.setDirect(true) in the no-arg ctor.
    assert cos.is_direct() is True


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
    sv.set_v_required(True)
    assert sv.is_v_required() is True

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


def test_v_required_uses_correct_bit_position() -> None:
    sv = PDSeedValue()
    sv.set_v_required(True)
    # /Ff bit 3 = 1 << 2 = 4 (PDF 32000-1 Table 234).
    assert (sv.get_cos_object().get_int(_FF) & PDSeedValue.FLAG_V) != 0
    assert sv.get_cos_object().get_int(_FF) == 4


def test_set_v_round_trip_float() -> None:
    sv = PDSeedValue()
    sv.set_v(1.5)
    assert sv.get_v() == 1.5


def test_set_v_accepts_int_returns_float() -> None:
    sv = PDSeedValue()
    sv.set_v(2)
    assert sv.get_v() == 2.0


def test_set_v_none_clears() -> None:
    sv = PDSeedValue()
    sv.set_v(1.0)
    assert sv.get_v() is not None
    sv.set_v(None)
    assert sv.get_v() is None


def test_filter_round_trip_and_clear() -> None:
    sv = PDSeedValue()
    assert sv.get_filter() is None
    sv.set_filter("Adobe.PPKLite")
    assert sv.get_filter() == "Adobe.PPKLite"
    sv.set_filter(None)
    assert sv.get_filter() is None


def test_sub_filter_round_trip() -> None:
    sv = PDSeedValue()
    assert sv.get_sub_filter() is None
    sv.set_sub_filter(["adbe.pkcs7.detached", "ETSI.CAdES.detached"])
    assert sv.get_sub_filter() == ["adbe.pkcs7.detached", "ETSI.CAdES.detached"]
    sv.set_sub_filter(None)
    assert sv.get_sub_filter() is None


def test_reasons_round_trip() -> None:
    sv = PDSeedValue()
    assert sv.get_reasons() is None
    sv.set_reasons(["I agree", "I am the author"])
    assert sv.get_reasons() == ["I agree", "I am the author"]
    sv.set_reasons(None)
    assert sv.get_reasons() is None


def test_flag_constants_match_upstream_bit_positions() -> None:
    """PDF 32000-1 Table 234 — /Ff bit positions per upstream PDFBox."""
    assert PDSeedValue.FLAG_FILTER == 1
    assert PDSeedValue.FLAG_SUBFILTER == 1 << 1
    assert PDSeedValue.FLAG_V == 1 << 2
    assert PDSeedValue.FLAG_REASON == 1 << 3
    assert PDSeedValue.FLAG_LEGAL_ATTESTATION == 1 << 4
    assert PDSeedValue.FLAG_ADD_REV_INFO == 1 << 5
    assert PDSeedValue.FLAG_DIGEST_METHOD == 1 << 6


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
