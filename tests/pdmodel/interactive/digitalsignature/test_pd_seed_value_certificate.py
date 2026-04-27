from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSeedValue,
    PDSeedValueCertificate,
)

_TYPE: COSName = COSName.get_pdf_name("Type")
_FF: COSName = COSName.get_pdf_name("Ff")


# ---------- construction ----------


def test_default_constructor_sets_type_svcert() -> None:
    cert = PDSeedValueCertificate()
    cos = cert.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(_TYPE) == "SVCert"


def test_constructor_accepts_existing_dict() -> None:
    cos = COSDictionary()
    cos.set_int("Ff", 5)
    cert = PDSeedValueCertificate(cos)
    assert cert.get_cos_object() is cos
    # 1 << 0 (subject) and 1 << 2 (oid) -> 5
    assert cert.is_subject_required() is True
    assert cert.is_oid_required() is True
    assert cert.is_issuer_required() is False


# ---------- /Ff flag round-trips ----------


@pytest.mark.parametrize(
    "setter,getter,bit",
    [
        ("set_subject_required", "is_subject_required", 1 << 0),
        ("set_issuer_required", "is_issuer_required", 1 << 1),
        ("set_oid_required", "is_oid_required", 1 << 2),
        ("set_subject_dn_required", "is_subject_dn_required", 1 << 3),
        ("set_key_usage_required", "is_key_usage_required", 1 << 5),
        ("set_url_required", "is_url_required", 1 << 6),
    ],
)
def test_each_flag_roundtrip(setter: str, getter: str, bit: int) -> None:
    cert = PDSeedValueCertificate()
    assert getattr(cert, getter)() is False
    getattr(cert, setter)(True)
    assert getattr(cert, getter)() is True
    assert (cert.get_cos_object().get_int(_FF) & bit) != 0
    getattr(cert, setter)(False)
    assert getattr(cert, getter)() is False


def test_independent_flags_do_not_clobber_each_other() -> None:
    cert = PDSeedValueCertificate()
    cert.set_subject_required(True)
    cert.set_url_required(True)
    assert cert.is_subject_required() is True
    assert cert.is_url_required() is True
    assert cert.is_issuer_required() is False
    assert cert.is_oid_required() is False
    assert cert.is_subject_dn_required() is False
    assert cert.is_key_usage_required() is False


# ---------- /Subject ----------


def test_subject_default_is_none() -> None:
    assert PDSeedValueCertificate().get_subject() is None


def test_set_subject_round_trip() -> None:
    cert = PDSeedValueCertificate()
    cert.set_subject([b"\x01\x02", b"\x03\x04\x05"])
    assert cert.get_subject() == [b"\x01\x02", b"\x03\x04\x05"]


def test_add_subject_appends() -> None:
    cert = PDSeedValueCertificate()
    cert.add_subject(b"AAA")
    cert.add_subject(b"BBB")
    assert cert.get_subject() == [b"AAA", b"BBB"]


def test_remove_subject_removes_first_match() -> None:
    cert = PDSeedValueCertificate()
    cert.add_subject(b"AAA")
    cert.add_subject(b"BBB")
    cert.remove_subject(b"AAA")
    assert cert.get_subject() == [b"BBB"]


# ---------- /SubjectDN ----------


def test_subject_dn_default_is_none() -> None:
    assert PDSeedValueCertificate().get_subject_dn() is None


def test_set_subject_dn_round_trip() -> None:
    cert = PDSeedValueCertificate()
    cert.set_subject_dn(
        [
            {"cn": "John Doe", "o": "Doe Inc."},
            {"cn": "Jane Smith"},
        ]
    )
    got = cert.get_subject_dn()
    assert got == [
        {"cn": "John Doe", "o": "Doe Inc."},
        {"cn": "Jane Smith"},
    ]


# ---------- /KeyUsage ----------


def test_key_usage_default_is_none() -> None:
    assert PDSeedValueCertificate().get_key_usage() is None


def test_set_key_usage_round_trip() -> None:
    cert = PDSeedValueCertificate()
    cert.set_key_usage(["1XX0X1XXX", "0XX1X0XXX"])
    assert cert.get_key_usage() == ["1XX0X1XXX", "0XX1X0XXX"]


def test_add_key_usage_validates_chars() -> None:
    cert = PDSeedValueCertificate()
    cert.add_key_usage("1XX0X1XXX")
    assert cert.get_key_usage() == ["1XX0X1XXX"]
    with pytest.raises(ValueError):
        cert.add_key_usage("1XX2X1XXX")


def test_add_key_usage_chars_builds_string() -> None:
    cert = PDSeedValueCertificate()
    cert.add_key_usage_chars("1", "X", "X", "0", "X", "1", "X", "X", "X")
    assert cert.get_key_usage() == ["1XX0X1XXX"]


def test_remove_key_usage_removes_first_match() -> None:
    cert = PDSeedValueCertificate()
    cert.set_key_usage(["1XX0X1XXX", "0XX1X0XXX"])
    cert.remove_key_usage("1XX0X1XXX")
    assert cert.get_key_usage() == ["0XX1X0XXX"]


# ---------- /Issuer ----------


def test_issuer_round_trip() -> None:
    cert = PDSeedValueCertificate()
    assert cert.get_issuer() is None
    cert.set_issuer([b"i1", b"i2"])
    assert cert.get_issuer() == [b"i1", b"i2"]
    cert.add_issuer(b"i3")
    assert cert.get_issuer() == [b"i1", b"i2", b"i3"]
    cert.remove_issuer(b"i2")
    assert cert.get_issuer() == [b"i1", b"i3"]


# ---------- /OID ----------


def test_oid_round_trip() -> None:
    cert = PDSeedValueCertificate()
    assert cert.get_oid() is None
    cert.set_oid([b"\x2a\x03\x04", b"\x2a\x03\x05"])
    assert cert.get_oid() == [b"\x2a\x03\x04", b"\x2a\x03\x05"]
    cert.add_oid(b"\x2a\x03\x06")
    assert cert.get_oid() == [b"\x2a\x03\x04", b"\x2a\x03\x05", b"\x2a\x03\x06"]
    cert.remove_oid(b"\x2a\x03\x05")
    assert cert.get_oid() == [b"\x2a\x03\x04", b"\x2a\x03\x06"]


# ---------- /URL + /URLType ----------


def test_url_round_trip() -> None:
    cert = PDSeedValueCertificate()
    assert cert.get_url() is None
    cert.set_url("https://example.com/ca")
    assert cert.get_url() == "https://example.com/ca"


def test_url_type_round_trip_writes_name() -> None:
    cert = PDSeedValueCertificate()
    assert cert.get_url_type() is None
    cert.set_url_type("Browser")
    assert cert.get_url_type() == "Browser"
    # /URLType is a name, not a string.
    cos = cert.get_cos_object()
    item = cos.get_item("URLType")
    assert isinstance(item, COSName)
    assert item.get_name() == "Browser"


# ---------- integration with PDSeedValue ----------


def test_pd_seed_value_certificate_round_trip() -> None:
    sv = PDSeedValue()
    assert sv.get_seed_value_certificate() is None
    assert sv.get_certificate() is None  # PRD-required short alias

    cert = PDSeedValueCertificate()
    cert.add_subject(b"DERBYTES")
    cert.set_url("https://ca.example/path")

    sv.set_seed_value_certificate(cert)

    got = sv.get_seed_value_certificate()
    assert isinstance(got, PDSeedValueCertificate)
    assert got.get_cos_object() is cert.get_cos_object()
    assert got.get_subject() == [b"DERBYTES"]
    assert got.get_url() == "https://ca.example/path"

    # Short alias returns the same typed value.
    short = sv.get_certificate()
    assert isinstance(short, PDSeedValueCertificate)
    assert short.get_cos_object() is cert.get_cos_object()


def test_pd_seed_value_set_certificate_short_alias() -> None:
    sv = PDSeedValue()
    cert = PDSeedValueCertificate()
    cert.set_url_required(True)
    sv.set_certificate(cert)
    got = sv.get_seed_value_certificate()
    assert got is not None and got.is_url_required() is True


def test_pd_seed_value_set_certificate_accepts_raw_dict() -> None:
    sv = PDSeedValue()
    cos = COSDictionary()
    cos.set_int("Ff", PDSeedValueCertificate.FLAG_SUBJECT)
    sv.set_seed_value_certificate(cos)
    got = sv.get_seed_value_certificate()
    assert got is not None
    assert got.is_subject_required() is True


def test_pd_seed_value_set_certificate_none_clears() -> None:
    sv = PDSeedValue()
    sv.set_certificate(PDSeedValueCertificate())
    assert sv.get_certificate() is not None
    sv.set_certificate(None)
    assert sv.get_certificate() is None


# ---------- COS shape sanity ----------


def test_subject_array_contains_cos_strings() -> None:
    cert = PDSeedValueCertificate()
    cert.set_subject([b"\x00\x01"])
    cos = cert.get_cos_object()
    arr = cos.get_dictionary_object("Subject")
    assert isinstance(arr, COSArray)
    inner = arr.get(0)
    assert isinstance(inner, COSString)
    assert inner.get_bytes() == b"\x00\x01"
