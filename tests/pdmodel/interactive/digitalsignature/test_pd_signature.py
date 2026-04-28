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


# ---------------------------------------------------------------------------
# /Type, /Cert, /M accessors
# ---------------------------------------------------------------------------


def test_pd_signature_get_type_default_sig() -> None:
    sig = PDSignature()
    assert sig.get_type() == "Sig"


def test_pd_signature_set_type_round_trip_and_remove() -> None:
    sig = PDSignature()
    sig.set_type("DocTimeStamp")
    assert sig.get_type() == "DocTimeStamp"
    sig.set_type(None)
    assert sig.get_type() is None


def test_pd_signature_cert_single_string_round_trip() -> None:
    sig = PDSignature()
    assert sig.get_cert() is None
    sig.set_cert("DER-bytes-as-string")
    # Single-string storage is still surfaced as a one-element list on read.
    assert sig.get_cert() == ["DER-bytes-as-string"]


def test_pd_signature_cert_array_round_trip() -> None:
    sig = PDSignature()
    sig.set_cert(["leaf-cert", "intermediate-cert", "root-cert"])
    assert sig.get_cert() == ["leaf-cert", "intermediate-cert", "root-cert"]


def test_pd_signature_cert_set_none_removes_entry() -> None:
    sig = PDSignature()
    sig.set_cert("anything")
    sig.set_cert(None)
    assert sig.get_cert() is None
    assert not sig.get_cos_object().contains_key("Cert")


def test_pd_signature_set_sign_date_round_trip() -> None:
    sig = PDSignature()
    assert sig.get_sign_date() is None
    sig.set_sign_date("D:20260427120000Z")
    assert sig.get_sign_date() == "D:20260427120000Z"
    sig.set_sign_date(None)
    assert sig.get_sign_date() is None


def test_pd_signature_set_byte_range_rejects_wrong_length() -> None:
    import pytest

    sig = PDSignature()
    with pytest.raises(ValueError, match="exactly 4"):
        sig.set_byte_range([0, 100, 200])
    with pytest.raises(ValueError, match="exactly 4"):
        sig.set_byte_range([0, 100, 200, 300, 400])
