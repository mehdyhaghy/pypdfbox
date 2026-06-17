"""Fuzz / parity hammering for ``PDSignature`` — wave 1585.

Targets the signature-dictionary model surface: ``/ByteRange`` round-trip,
``/Contents`` raw-bytes decode, ``get_signed_content`` byte-range extraction
(skipping the ``/Contents`` region exactly as upstream's
``COSFilterInputStream`` does), ``/Filter`` / ``/SubFilter`` / ``/Name`` /
``/Location`` / ``/Reason`` / ``/ContactInfo`` accessors, ``/M`` sign-date
storage, the SubFilter/Filter constant values, an absent ``/ByteRange``
(``None``) and a direct-hex ``/Contents`` COSString.

Behavioral oracle: Apache PDFBox 3.0.7 ``PDSignature`` /
``COSFilterInputStream``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature

_BYTE_RANGE = COSName.get_pdf_name("ByteRange")
_CONTENTS = COSName.get_pdf_name("Contents")
_SUB_FILTER = COSName.get_pdf_name("SubFilter")


# --------------------------------------------------------------- /ByteRange


def test_byte_range_absent_is_none() -> None:
    assert PDSignature().get_byte_range() is None


def test_byte_range_round_trip() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 840, 960, 240])
    assert sig.get_byte_range() == [0, 840, 960, 240]


@pytest.mark.parametrize(
    "br",
    [
        [0, 0, 0, 0],
        [0, 1, 2, 3],
        [10, 20, 30, 40],
        [0, 100000, 100128, 5000],
    ],
    ids=["zeros", "small", "midsize", "large"],
)
def test_byte_range_various_round_trip(br: list[int]) -> None:
    sig = PDSignature()
    sig.set_byte_range(br)
    assert sig.get_byte_range() == br


def test_set_byte_range_emits_direct_array() -> None:
    # Upstream PDSignature.setByteRange marks the array direct so COSWriter
    # can splice real offsets in place.
    sig = PDSignature()
    sig.set_byte_range([0, 10, 20, 30])
    arr = sig.get_cos_object().get_dictionary_object(_BYTE_RANGE)
    assert isinstance(arr, COSArray)
    assert arr.is_direct()


@pytest.mark.parametrize("n", [0, 1, 2, 3, 5, 6, 8], ids=lambda n: f"len{n}")
def test_set_byte_range_rejects_non_four(n: int) -> None:
    with pytest.raises(ValueError):
        PDSignature().set_byte_range(list(range(n)))


def test_set_byte_range_none_removes() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 1, 2, 3])
    sig.set_byte_range(None)
    assert sig.get_byte_range() is None
    assert not sig.has_byte_range()


def test_byte_range_non_array_is_none() -> None:
    # Upstream getByteRange returns int[0] when /ByteRange is not an array;
    # the lite port maps that to None (pinned divergence).
    sig = PDSignature()
    sig.get_cos_object().set_item(_BYTE_RANGE, COSInteger.get(5))
    assert sig.get_byte_range() is None


def test_byte_range_odd_length_preserved() -> None:
    # getByteRange returns WHATEVER length the array has — no shape coercion.
    sig = PDSignature()
    arr = COSArray.of_cos_integers([0, 10, 20])
    sig.get_cos_object().set_item(_BYTE_RANGE, arr)
    assert sig.get_byte_range() == [0, 10, 20]


def test_byte_range_non_number_entry_becomes_minus_one() -> None:
    # COSArray.getInt substitutes -1 for any non-number element.
    sig = PDSignature()
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("Bogus"))
    arr.add(COSInteger.get(20))
    arr.add(COSInteger.get(30))
    sig.get_cos_object().set_item(_BYTE_RANGE, arr)
    assert sig.get_byte_range() == [0, -1, 20, 30]


# --------------------------------------------------------------- /Contents


def test_contents_absent_is_none() -> None:
    assert PDSignature().get_contents() is None


def test_contents_round_trip_raw_bytes() -> None:
    blob = bytes(range(256))
    sig = PDSignature()
    sig.set_contents(blob)
    assert sig.get_contents() == blob


def test_contents_set_marks_force_hex() -> None:
    sig = PDSignature()
    sig.set_contents(b"\x30\x82\x01\x00")
    cs = sig.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(cs, COSString)
    assert cs.is_force_hex_form()


def test_contents_direct_hex_string_decoded() -> None:
    # A /Contents stored as a direct COSString (e.g. constructed from a hex
    # literal <DEADBEEF>) returns the decoded raw bytes.
    sig = PDSignature()
    cs = COSString.parse_hex("DEADBEEF")
    sig.get_cos_object().set_item(_CONTENTS, cs)
    assert sig.get_contents() == b"\xde\xad\xbe\xef"


def test_contents_none_removes() -> None:
    sig = PDSignature()
    sig.set_contents(b"abc")
    sig.set_contents(None)
    assert sig.get_contents() is None
    assert not sig.has_contents()


def test_contents_empty_bytes() -> None:
    sig = PDSignature()
    sig.set_contents(b"")
    assert sig.get_contents() == b""


def test_contents_non_string_is_none() -> None:
    sig = PDSignature()
    sig.get_cos_object().set_item(_CONTENTS, COSInteger.get(7))
    assert sig.get_contents() is None


# ------------------------------------------------ get_signed_content / data


def _make_signed_doc() -> tuple[bytes, list[int]]:
    """Build a fake PDF byte blob with a /Contents region and the matching
    /ByteRange [s1, l1, s2, l2] that brackets it.
    """
    head = b"%PDF-1.7\nbefore-the-signature-contents-placeholder<"
    contents_hex = b"00" * 32  # the /Contents hex placeholder region
    tail = b">after-the-contents-bytes\n%%EOF\n"
    doc = head + contents_hex + tail
    s1, l1 = 0, len(head)
    s2 = len(head) + len(contents_hex)
    l2 = len(tail)
    return doc, [s1, l1, s2, l2]


def test_get_signed_content_skips_contents_region() -> None:
    doc, br = _make_signed_doc()
    sig = PDSignature()
    sig.set_byte_range(br)
    signed = sig.get_signed_content(doc)
    s1, l1, s2, l2 = br
    assert signed == doc[s1 : s1 + l1] + doc[s2 : s2 + l2]
    # The /Contents hex region must NOT be present in the signed bytes.
    assert b"00" * 32 not in signed


def test_get_signed_data_matches_slices() -> None:
    doc, br = _make_signed_doc()
    sig = PDSignature()
    sig.set_byte_range(br)
    s1, l1, s2, l2 = br
    assert sig.get_signed_data(doc) == doc[s1 : s1 + l1] + doc[s2 : s2 + l2]


def test_get_signed_content_empty_when_no_byte_range() -> None:
    # Absent /ByteRange => upstream getByteRange() is int[0] => empty result,
    # no exception.
    assert PDSignature().get_signed_content(b"anything") == b""


def test_get_signed_data_none_when_no_byte_range() -> None:
    assert PDSignature().get_signed_data(b"anything") is None


def test_get_signed_content_full_concatenation() -> None:
    doc = bytes(range(100))
    sig = PDSignature()
    sig.set_byte_range([0, 10, 50, 10])
    assert sig.get_signed_content(doc) == doc[0:10] + doc[50:60]


def test_get_signed_data_out_of_bounds_is_none() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 10, 90, 50])
    assert sig.get_signed_data(b"x" * 100) is None


def test_get_signed_content_odd_length_drops_trailing() -> None:
    # COSFilterInputStream pairs length//2 times: [a,b,c] reads only [a,b].
    doc = bytes(range(50))
    sig = PDSignature()
    arr = COSArray.of_cos_integers([0, 10, 40])
    sig.get_cos_object().set_item(_BYTE_RANGE, arr)
    assert sig.get_signed_content(doc) == doc[0:10]


def test_get_signed_content_skip_past_eof_raises_oserror() -> None:
    # A second range starting beyond EOF forces a skip the source can't
    # satisfy => upstream IOException => OSError.
    sig = PDSignature()
    sig.set_byte_range([0, 5, 1000, 10])
    with pytest.raises(OSError):
        sig.get_signed_content(b"x" * 20)


def test_get_signed_content_negative_length_raises_indexerror() -> None:
    # A negative computed span drives a negative read length =>
    # IndexOutOfBoundsException => IndexError.
    sig = PDSignature()
    arr = COSArray.of_cos_integers([10, -5, 0, 0])
    sig.get_cos_object().set_item(_BYTE_RANGE, arr)
    with pytest.raises(IndexError):
        sig.get_signed_content(b"x" * 20)


# ------------------------------------- /Filter /SubFilter /Name /Location ...


def test_filter_round_trip() -> None:
    sig = PDSignature()
    sig.set_filter(PDSignature.FILTER_ADOBE_PPKLITE)
    assert sig.get_filter() == "Adobe.PPKLite"


def test_sub_filter_round_trip() -> None:
    sig = PDSignature()
    sig.set_sub_filter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED)
    assert sig.get_sub_filter() == "adbe.pkcs7.detached"


def test_filter_stored_as_name() -> None:
    sig = PDSignature()
    sig.set_filter("Adobe.PPKLite")
    v = sig.get_cos_object().get_item(COSName.get_pdf_name("Filter"))
    assert isinstance(v, COSName)
    assert v.get_name() == "Adobe.PPKLite"


def test_sub_filter_read_from_string_value() -> None:
    # getNameAsString is permissive: a /SubFilter written as a COSString
    # is still read back as the string.
    sig = PDSignature()
    sig.get_cos_object().set_item(_SUB_FILTER, COSString("adbe.pkcs7.detached"))
    assert sig.get_sub_filter() == "adbe.pkcs7.detached"


@pytest.mark.parametrize(
    "setter,getter,value",
    [
        ("set_name", "get_name", "Alice Example"),
        ("set_location", "get_location", "Paris, FR"),
        ("set_reason", "get_reason", "I approve"),
        ("set_contact_info", "get_contact_info", "alice@example.com"),
    ],
    ids=["name", "location", "reason", "contact"],
)
def test_string_fields_round_trip(setter: str, getter: str, value: str) -> None:
    sig = PDSignature()
    getattr(sig, setter)(value)
    assert getattr(sig, getter)() == value


@pytest.mark.parametrize(
    "setter,getter,haser",
    [
        ("set_name", "get_name", "has_name"),
        ("set_location", "get_location", "has_location"),
        ("set_reason", "get_reason", "has_reason"),
        ("set_contact_info", "get_contact_info", "has_contact_info"),
        ("set_filter", "get_filter", "has_filter"),
        ("set_sub_filter", "get_sub_filter", "has_sub_filter"),
    ],
    ids=["name", "location", "reason", "contact", "filter", "subfilter"],
)
def test_string_field_none_removes(setter: str, getter: str, haser: str) -> None:
    sig = PDSignature()
    getattr(sig, setter)("something")
    assert getattr(sig, haser)()
    getattr(sig, setter)(None)
    assert getattr(sig, getter)() is None
    assert not getattr(sig, haser)()


def test_string_fields_default_none() -> None:
    sig = PDSignature()
    assert sig.get_name() is None
    assert sig.get_location() is None
    assert sig.get_reason() is None
    assert sig.get_contact_info() is None
    assert sig.get_filter() is None
    assert sig.get_sub_filter() is None


# --------------------------------------------------------------- /M sign date


def test_sign_date_round_trip() -> None:
    sig = PDSignature()
    sig.set_sign_date("D:20260616120000+00'00'")
    assert sig.get_sign_date() == "D:20260616120000+00'00'"


def test_sign_date_absent_is_none() -> None:
    assert PDSignature().get_sign_date() is None


def test_sign_date_none_removes() -> None:
    sig = PDSignature()
    sig.set_sign_date("D:20260616120000Z")
    sig.set_sign_date(None)
    assert sig.get_sign_date() is None
    assert not sig.has_sign_date()


def test_sign_date_as_datetime_parses() -> None:
    sig = PDSignature()
    sig.set_sign_date("D:20260616120000+00'00'")
    dt = sig.get_sign_date_as_datetime()
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 6
    assert dt.day == 16


def test_sign_date_as_datetime_absent_is_none() -> None:
    assert PDSignature().get_sign_date_as_datetime() is None


# ---------------------------------------------------- SubFilter / Filter consts


def test_subfilter_constant_values() -> None:
    assert PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED == "adbe.pkcs7.detached"
    assert PDSignature.SUBFILTER_ADBE_PKCS7_SHA1 == "adbe.pkcs7.sha1"
    assert PDSignature.SUBFILTER_ETSI_CADES_DETACHED == "ETSI.CAdES.detached"
    assert PDSignature.SUBFILTER_ADBE_X509_RSA_SHA1 == "adbe.x509.rsa_sha1"
    assert PDSignature.SUBFILTER_ETSI_RFC3161 == "ETSI.RFC3161"


def test_filter_constant_values() -> None:
    assert PDSignature.FILTER_ADOBE_PPKLITE == "Adobe.PPKLite"
    assert PDSignature.FILTER_ENTRUST_PPKEF == "Entrust.PPKEF"
    assert PDSignature.FILTER_CICI_SIGNIT == "CICI.SignIt"
    assert PDSignature.FILTER_VERISIGN_PPKVS == "VeriSign.PPKVS"


@pytest.mark.parametrize(
    "sub,pred",
    [
        ("adbe.pkcs7.detached", "is_pkcs7_detached"),
        ("adbe.pkcs7.sha1", "is_pkcs7_sha1"),
        ("adbe.x509.rsa_sha1", "is_x509_rsa_sha1"),
        ("ETSI.CAdES.detached", "is_etsi_cades_detached"),
        ("ETSI.RFC3161", "is_etsi_rfc3161"),
    ],
    ids=["detached", "sha1", "x509", "cades", "rfc3161"],
)
def test_subfilter_predicates(sub: str, pred: str) -> None:
    sig = PDSignature()
    sig.set_sub_filter(sub)
    assert getattr(sig, pred)()


def test_fresh_signature_type_is_sig() -> None:
    sig = PDSignature()
    assert sig.get_type() == "Sig"
    assert sig.is_signature()
    assert not sig.is_doc_time_stamp()


def test_from_existing_dictionary_keeps_entries() -> None:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Filter"), "Adobe.PPKLite")
    d.set_name(_SUB_FILTER, "adbe.pkcs7.detached")
    sig = PDSignature(d)
    assert sig.get_filter() == "Adobe.PPKLite"
    assert sig.get_sub_filter() == "adbe.pkcs7.detached"
    # Constructing from an existing dict must not stamp /Type.
    assert sig.get_cos_object() is d
