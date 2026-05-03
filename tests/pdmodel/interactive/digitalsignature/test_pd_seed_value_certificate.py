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


# ---------- has_* predicate helpers ----------


def test_has_predicates_default_to_false() -> None:
    cert = PDSeedValueCertificate()
    assert cert.has_ff() is False
    assert cert.has_subject() is False
    assert cert.has_subject_dn() is False
    assert cert.has_key_usage() is False
    assert cert.has_issuer() is False
    assert cert.has_oid() is False
    assert cert.has_url() is False
    assert cert.has_url_type() is False


def test_has_subject_flips_after_set() -> None:
    cert = PDSeedValueCertificate()
    cert.set_subject([b"\x01\x02"])
    assert cert.has_subject() is True


def test_has_subject_flips_after_add() -> None:
    cert = PDSeedValueCertificate()
    cert.add_subject(b"AAA")
    assert cert.has_subject() is True


def test_has_subject_dn_flips_after_set() -> None:
    cert = PDSeedValueCertificate()
    cert.set_subject_dn([{"cn": "John"}])
    assert cert.has_subject_dn() is True


def test_has_key_usage_flips_after_add() -> None:
    cert = PDSeedValueCertificate()
    assert cert.has_key_usage() is False
    cert.add_key_usage("1XX0X1XXX")
    assert cert.has_key_usage() is True


def test_has_issuer_flips_after_set() -> None:
    cert = PDSeedValueCertificate()
    cert.set_issuer([b"i1"])
    assert cert.has_issuer() is True


def test_has_oid_flips_after_add() -> None:
    cert = PDSeedValueCertificate()
    cert.add_oid(b"\x2a\x03\x04")
    assert cert.has_oid() is True


def test_has_url_flips_after_set() -> None:
    cert = PDSeedValueCertificate()
    cert.set_url("https://example.com/ca")
    assert cert.has_url() is True


def test_has_url_type_flips_after_set() -> None:
    cert = PDSeedValueCertificate()
    cert.set_url_type("Browser")
    assert cert.has_url_type() is True


def test_has_ff_flips_after_set_subject_required() -> None:
    cert = PDSeedValueCertificate()
    assert cert.has_ff() is False
    cert.set_subject_required(True)
    assert cert.has_ff() is True


def test_has_predicates_independent() -> None:
    """Setting one entry must not flip predicates for the others."""
    cert = PDSeedValueCertificate()
    cert.set_url("https://example.com/")
    assert cert.has_url() is True
    assert cert.has_subject() is False
    assert cert.has_issuer() is False
    assert cert.has_oid() is False
    assert cert.has_key_usage() is False
    assert cert.has_subject_dn() is False
    assert cert.has_url_type() is False
    assert cert.has_ff() is False


# ---------- /Ff raw accessors ----------


def test_get_ff_default_is_zero() -> None:
    cert = PDSeedValueCertificate()
    assert cert.get_ff() == 0


def test_get_ff_reflects_individual_flag_setters() -> None:
    cert = PDSeedValueCertificate()
    cert.set_subject_required(True)
    cert.set_url_required(True)
    # FLAG_SUBJECT (1) | FLAG_URL (1<<6) = 1 | 64 = 65
    assert cert.get_ff() == 65


def test_set_ff_round_trip_overwrites_existing_flags() -> None:
    cert = PDSeedValueCertificate()
    cert.set_subject_required(True)  # bit 0
    # Overwrite all flags to a specific bitmask:
    # FLAG_ISSUER | FLAG_KEY_USAGE = 2 | 32 = 34
    cert.set_ff(PDSeedValueCertificate.FLAG_ISSUER | PDSeedValueCertificate.FLAG_KEY_USAGE)
    assert cert.get_ff() == 34
    assert cert.is_subject_required() is False
    assert cert.is_issuer_required() is True
    assert cert.is_key_usage_required() is True


def test_set_ff_zero_clears_all_flags() -> None:
    cert = PDSeedValueCertificate()
    cert.set_subject_required(True)
    cert.set_issuer_required(True)
    cert.set_url_required(True)
    cert.set_ff(0)
    assert cert.get_ff() == 0
    assert cert.is_subject_required() is False
    assert cert.is_issuer_required() is False
    assert cert.is_url_required() is False


def test_get_ff_returns_zero_when_entry_is_wrong_type() -> None:
    """Mirrors upstream ``getInt(FF, 0)`` semantics: non-integer /Ff
    storage falls back to 0 rather than raising."""
    cert = PDSeedValueCertificate()
    cert.get_cos_object().set_item(_FF, COSName.get_pdf_name("not-an-int"))
    assert cert.get_ff() == 0


def test_set_ff_writes_cos_integer() -> None:
    from pypdfbox.cos import COSInteger
    cert = PDSeedValueCertificate()
    cert.set_ff(42)
    item = cert.get_cos_object().get_item(_FF)
    assert isinstance(item, COSInteger)
    assert int(item.value) == 42


# ---------- /URLType constants and predicates ----------


def test_url_type_constants() -> None:
    assert PDSeedValueCertificate.URL_TYPE_BROWSER == "Browser"
    assert PDSeedValueCertificate.URL_TYPE_ASSP == "ASSP"


def test_get_url_type_or_default_returns_browser_when_absent() -> None:
    """Spec: default is Browser when /URLType is absent."""
    cert = PDSeedValueCertificate()
    assert cert.get_url_type() is None
    assert cert.get_url_type_or_default() == "Browser"


def test_get_url_type_or_default_returns_set_value() -> None:
    cert = PDSeedValueCertificate()
    cert.set_url_type("ASSP")
    assert cert.get_url_type_or_default() == "ASSP"


def test_is_url_type_browser_true_when_absent() -> None:
    """The spec default makes ``Browser`` the effective type even when
    /URLType is not stored."""
    cert = PDSeedValueCertificate()
    assert cert.is_url_type_browser() is True


def test_is_url_type_browser_true_when_explicitly_set() -> None:
    cert = PDSeedValueCertificate()
    cert.set_url_type("Browser")
    assert cert.is_url_type_browser() is True


def test_is_url_type_browser_false_for_assp() -> None:
    cert = PDSeedValueCertificate()
    cert.set_url_type("ASSP")
    assert cert.is_url_type_browser() is False


def test_is_url_type_browser_false_for_third_party_extension() -> None:
    """Third-party URLType extensions (per Adobe spec) aren't Browser."""
    cert = PDSeedValueCertificate()
    cert.set_url_type("CompanyXYZ.Custom")
    assert cert.is_url_type_browser() is False


def test_is_url_type_assp_only_true_when_explicit() -> None:
    cert = PDSeedValueCertificate()
    assert cert.is_url_type_assp() is False  # absent does NOT default to ASSP
    cert.set_url_type("ASSP")
    assert cert.is_url_type_assp() is True
    cert.set_url_type("Browser")
    assert cert.is_url_type_assp() is False


# ---------- /KeyUsage validation + parsing ----------


def test_key_usage_constants() -> None:
    assert PDSeedValueCertificate.KEY_USAGE_LENGTH == 9
    # Indices 0..8 cover the nine X.509 KeyUsage bits, in spec order.
    assert PDSeedValueCertificate.KEY_USAGE_INDEX_DIGITAL_SIGNATURE == 0
    assert PDSeedValueCertificate.KEY_USAGE_INDEX_NON_REPUDIATION == 1
    assert PDSeedValueCertificate.KEY_USAGE_INDEX_KEY_ENCIPHERMENT == 2
    assert PDSeedValueCertificate.KEY_USAGE_INDEX_DATA_ENCIPHERMENT == 3
    assert PDSeedValueCertificate.KEY_USAGE_INDEX_KEY_AGREEMENT == 4
    assert PDSeedValueCertificate.KEY_USAGE_INDEX_KEY_CERT_SIGN == 5
    assert PDSeedValueCertificate.KEY_USAGE_INDEX_CRL_SIGN == 6
    assert PDSeedValueCertificate.KEY_USAGE_INDEX_ENCIPHER_ONLY == 7
    assert PDSeedValueCertificate.KEY_USAGE_INDEX_DECIPHER_ONLY == 8
    assert PDSeedValueCertificate.KEY_USAGE_ALLOWED_CHARS == frozenset("01X")


def test_validate_key_usage_string_accepts_well_formed() -> None:
    PDSeedValueCertificate.validate_key_usage_string("1XX0X1XXX")
    PDSeedValueCertificate.validate_key_usage_string("000000000")
    PDSeedValueCertificate.validate_key_usage_string("111111111")
    PDSeedValueCertificate.validate_key_usage_string("XXXXXXXXX")


def test_validate_key_usage_string_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="9 characters"):
        PDSeedValueCertificate.validate_key_usage_string("1XX")
    with pytest.raises(ValueError, match="9 characters"):
        PDSeedValueCertificate.validate_key_usage_string("1XX0X1XXXX")  # 10 chars
    with pytest.raises(ValueError, match="9 characters"):
        PDSeedValueCertificate.validate_key_usage_string("")


def test_validate_key_usage_string_rejects_bad_chars() -> None:
    with pytest.raises(ValueError, match="0, 1, X"):
        PDSeedValueCertificate.validate_key_usage_string("1XX2X1XXX")
    with pytest.raises(ValueError, match="0, 1, X"):
        PDSeedValueCertificate.validate_key_usage_string("1xx0x1xxx")  # lowercase x


def test_parse_key_usage_returns_indexed_map() -> None:
    parsed = PDSeedValueCertificate.parse_key_usage("10X11X0X1")
    assert parsed == {
        "digital_signature": "1",
        "non_repudiation": "0",
        "key_encipherment": "X",
        "data_encipherment": "1",
        "key_agreement": "1",
        "key_cert_sign": "X",
        "crl_sign": "0",
        "encipher_only": "X",
        "decipher_only": "1",
    }


def test_parse_key_usage_propagates_validation_failure() -> None:
    with pytest.raises(ValueError):
        PDSeedValueCertificate.parse_key_usage("bogus")


# ---------- __str__ / __repr__ ----------


def test_str_empty_dictionary() -> None:
    cert = PDSeedValueCertificate()
    # Default ctor sets /Type but no other entries, so summary is <empty>.
    s = str(cert)
    assert s == "PDSeedValueCertificate(<empty>)"
    assert repr(cert) == s


def test_str_summary_includes_populated_fields() -> None:
    cert = PDSeedValueCertificate()
    cert.set_subject_required(True)
    cert.set_url_required(True)
    cert.add_subject(b"AAA")
    cert.add_subject(b"BBB")
    cert.add_key_usage("1XX0X1XXX")
    cert.set_url("https://ca.example/")
    cert.set_url_type("Browser")
    s = str(cert)
    # /Ff: bit 0 (subject) | bit 6 (url) = 0x41
    assert "ff=0x41" in s
    assert "subject=2" in s
    assert "key_usage=1" in s
    assert "url=https://ca.example/" in s
    assert "url_type=Browser" in s


def test_str_omits_absent_fields() -> None:
    cert = PDSeedValueCertificate()
    cert.set_url("https://ca.example/")
    s = str(cert)
    assert "url=https://ca.example/" in s
    assert "subject=" not in s
    assert "ff=" not in s
    assert "url_type=" not in s
