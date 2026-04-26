from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSeedValue,
    PDSignature,
    PDSignatureLock,
)

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]


def test_pd_signature_fresh_has_type_sig() -> None:
    sig = PDSignature()
    assert sig.get_cos_object().get_name(_TYPE) == "Sig"


def test_pd_signature_round_trip_filter_subfilter_name_reason() -> None:
    sig = PDSignature()
    sig.set_filter("Adobe.PPKLite")
    sig.set_sub_filter("adbe.pkcs7.detached")
    sig.set_name("Alice Example")
    sig.set_reason("I approve this document")

    assert sig.get_filter() == "Adobe.PPKLite"
    assert sig.get_sub_filter() == "adbe.pkcs7.detached"
    assert sig.get_name() == "Alice Example"
    assert sig.get_reason() == "I approve this document"


def test_pd_signature_byte_range_round_trip() -> None:
    sig = PDSignature()
    assert sig.get_byte_range() is None
    sig.set_byte_range([0, 100, 200, 50])
    assert sig.get_byte_range() == [0, 100, 200, 50]


def test_pd_signature_optional_fields_default_none() -> None:
    sig = PDSignature()
    assert sig.get_filter() is None
    assert sig.get_sub_filter() is None
    assert sig.get_name() is None
    assert sig.get_location() is None
    assert sig.get_reason() is None
    assert sig.get_contact_info() is None
    assert sig.get_sign_date() is None
    assert sig.get_contents() is None


def test_pd_seed_value_fresh_has_type_sv() -> None:
    sv = PDSeedValue()
    assert sv.get_cos_object().get_name(_TYPE) == "SV"


def test_pd_seed_value_sub_filter_round_trip() -> None:
    sv = PDSeedValue()
    sv.set_sub_filter(["adbe.pkcs7.detached", "ETSI.CAdES.detached"])
    assert sv.get_sub_filter() == ["adbe.pkcs7.detached", "ETSI.CAdES.detached"]

    sv.set_v(2)
    assert sv.get_v() == 2

    sv.set_reasons(["personal", "legal"])
    assert sv.get_reasons() == ["personal", "legal"]


def test_pd_signature_lock_fresh_has_type_sig_field_lock() -> None:
    lock = PDSignatureLock()
    assert lock.get_cos_object().get_name(_TYPE) == "SigFieldLock"


def test_pd_signature_lock_round_trip_action_and_fields() -> None:
    lock = PDSignatureLock()
    lock.set_action("Include")
    lock.set_fields(["sig1", "sig2"])

    assert lock.get_action() == "Include"
    assert lock.get_fields() == ["sig1", "sig2"]

    lock.set_p(2)
    assert lock.get_p() == 2
