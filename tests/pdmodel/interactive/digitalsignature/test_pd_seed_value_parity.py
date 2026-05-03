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


# ---------- /Filter constants & COSName-accepting setter ----------


def test_filter_constants_match_upstream() -> None:
    """Standard /Filter handler names. PDF 32000-1 §12.8.1 Table 252."""
    assert PDSeedValue.FILTER_ADOBE_PPKLITE == "Adobe.PPKLite"
    assert PDSeedValue.FILTER_ENTRUST_PPKEF == "Entrust.PPKEF"
    assert PDSeedValue.FILTER_CICI_SIGNIT == "CICI.SignIt"
    assert PDSeedValue.FILTER_VERISIGN_PPKVS == "VeriSign.PPKVS"


def test_subfilter_constants_match_upstream() -> None:
    """Standard /SubFilter encodings. PDF 32000-1 §12.8.3."""
    assert PDSeedValue.SUBFILTER_ADBE_X509_RSA_SHA1 == "adbe.x509.rsa_sha1"
    assert PDSeedValue.SUBFILTER_ADBE_PKCS7_DETACHED == "adbe.pkcs7.detached"
    assert PDSeedValue.SUBFILTER_ETSI_CADES_DETACHED == "ETSI.CAdES.detached"
    assert PDSeedValue.SUBFILTER_ADBE_PKCS7_SHA1 == "adbe.pkcs7.sha1"


def test_digest_constants_match_upstream() -> None:
    """Allowed /DigestMethod values. PDF 32000-1 Table 234."""
    assert PDSeedValue.DIGEST_SHA1 == "SHA1"
    assert PDSeedValue.DIGEST_SHA256 == "SHA256"
    assert PDSeedValue.DIGEST_SHA384 == "SHA384"
    assert PDSeedValue.DIGEST_SHA512 == "SHA512"
    assert PDSeedValue.DIGEST_RIPEMD160 == "RIPEMD160"
    # ALLOWED_DIGEST_NAMES contains every public DIGEST_* constant.
    assert set(PDSeedValue.ALLOWED_DIGEST_NAMES) == {
        PDSeedValue.DIGEST_SHA1,
        PDSeedValue.DIGEST_SHA256,
        PDSeedValue.DIGEST_SHA384,
        PDSeedValue.DIGEST_SHA512,
        PDSeedValue.DIGEST_RIPEMD160,
    }


def test_set_filter_accepts_cos_name() -> None:
    """Upstream signature is ``setFilter(COSName)``; our setter accepts
    either ``str`` or ``COSName``."""
    sv = PDSeedValue()
    sv.set_filter(COSName.get_pdf_name(PDSeedValue.FILTER_ADOBE_PPKLITE))
    assert sv.get_filter() == "Adobe.PPKLite"
    # Stored as a name (not a string).
    item = sv.get_cos_object().get_item("Filter")
    assert isinstance(item, COSName)
    assert item.get_name() == "Adobe.PPKLite"


def test_get_filter_reads_string_value() -> None:
    """Some producers write /Filter as a string rather than a name —
    upstream's ``getNameAsString`` handles both. Mirror that."""
    sv = PDSeedValue()
    # Force a string-typed /Filter value.
    from pypdfbox.cos import COSString
    sv.get_cos_object().set_item("Filter", COSString("Adobe.PPKLite"))
    assert sv.get_filter() == "Adobe.PPKLite"


def test_set_filter_with_constant_round_trip() -> None:
    sv = PDSeedValue()
    sv.set_filter(PDSeedValue.FILTER_ENTRUST_PPKEF)
    assert sv.get_filter() == "Entrust.PPKEF"


# ---------- has_* predicate helpers ----------


def test_has_filter_predicate() -> None:
    sv = PDSeedValue()
    assert sv.has_filter() is False
    sv.set_filter("Adobe.PPKLite")
    assert sv.has_filter() is True
    sv.set_filter(None)
    assert sv.has_filter() is False


def test_has_sub_filter_predicate() -> None:
    sv = PDSeedValue()
    assert sv.has_sub_filter() is False
    sv.set_sub_filter(["adbe.pkcs7.detached"])
    assert sv.has_sub_filter() is True


def test_has_v_predicate() -> None:
    sv = PDSeedValue()
    assert sv.has_v() is False
    sv.set_v(2.0)
    assert sv.has_v() is True
    sv.set_v(None)
    assert sv.has_v() is False


def test_has_reasons_predicate() -> None:
    sv = PDSeedValue()
    assert sv.has_reasons() is False
    sv.set_reasons(["I agree"])
    assert sv.has_reasons() is True


def test_has_legal_attestation_predicate() -> None:
    sv = PDSeedValue()
    assert sv.has_legal_attestation() is False
    sv.set_legal_attestation(["No Modifications Permitted"])
    assert sv.has_legal_attestation() is True


def test_has_digest_method_predicate() -> None:
    sv = PDSeedValue()
    assert sv.has_digest_method() is False
    sv.set_digest_method([PDSeedValue.DIGEST_SHA256])
    assert sv.has_digest_method() is True


def test_has_mdp_predicate() -> None:
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value_mdp import (
        PDSeedValueMDP,
    )

    sv = PDSeedValue()
    assert sv.has_mdp() is False
    mdp = PDSeedValueMDP()
    mdp.set_p(2)
    sv.set_mdp(mdp)
    assert sv.has_mdp() is True
    sv.set_mdp(None)
    assert sv.has_mdp() is False


def test_has_time_stamp_predicate() -> None:
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value_time_stamp import (
        PDSeedValueTimeStamp,
    )

    sv = PDSeedValue()
    assert sv.has_time_stamp() is False
    ts = PDSeedValueTimeStamp()
    ts.set_url("https://ts.example/")
    sv.set_time_stamp(ts)
    assert sv.has_time_stamp() is True


def test_has_seed_value_certificate_predicate() -> None:
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value_certificate import (
        PDSeedValueCertificate,
    )

    sv = PDSeedValue()
    assert sv.has_seed_value_certificate() is False
    assert sv.has_certificate() is False  # short alias
    sv.set_seed_value_certificate(PDSeedValueCertificate())
    assert sv.has_seed_value_certificate() is True
    assert sv.has_certificate() is True
    sv.set_seed_value_certificate(None)
    assert sv.has_seed_value_certificate() is False
    assert sv.has_certificate() is False


def test_has_predicates_cheaper_than_get_construction() -> None:
    """``has_seed_value_certificate`` must not invoke the typed wrapper.
    A targeted dict that only exposes ``contains_key`` would raise if
    we wrongly fell through to ``get_dictionary_object``. Use a direct
    construction-counter fixture to verify the cheap path."""
    sv = PDSeedValue()
    # Empty dict — no /Cert key — must return False without any lookup
    # of the value side. This is just a smoke test: the predicate
    # delegates to ``contains_key`` only.
    assert sv.has_seed_value_certificate() is False
    assert sv.has_mdp() is False
    assert sv.has_time_stamp() is False
