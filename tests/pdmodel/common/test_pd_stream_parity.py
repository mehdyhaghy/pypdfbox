from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.common import PDStream
from pypdfbox.pdmodel.common.filespecification import (
    PDComplexFileSpecification,
    PDFileSpecification,
    PDSimpleFileSpecification,
)

# ---------- alias accessors ----------


def test_get_cos_stream_and_get_stream_alias_get_cos_object() -> None:
    cos = COSStream()
    stream = PDStream(cos)
    assert stream.get_cos_stream() is cos
    assert stream.get_stream() is cos
    assert stream.get_cos_object() is cos


# ---------- /Filter ----------


def test_get_filters_set_filters_round_trip_two_filter_chain() -> None:
    stream = PDStream()
    stream.set_filters(["ASCII85Decode", "FlateDecode"])

    names = stream.get_filters()
    assert [n.name for n in names] == ["ASCII85Decode", "FlateDecode"]
    # Set with COSName values too — should yield the same chain.
    stream.set_filters(
        [
            COSName.ASCII85_DECODE,  # type: ignore[attr-defined]
            COSName.FLATE_DECODE,  # type: ignore[attr-defined]
        ]
    )
    second = stream.get_filters()
    assert second == [
        COSName.ASCII85_DECODE,  # type: ignore[attr-defined]
        COSName.FLATE_DECODE,  # type: ignore[attr-defined]
    ]
    # Always wrapped in a COSArray on storage (matches upstream setFilters(List)).
    raw = stream.get_cos_object().get_dictionary_object(COSName.FILTER)  # type: ignore[attr-defined]
    assert isinstance(raw, COSArray)


# ---------- is_filter_undefined ----------


def test_is_filter_undefined_true_when_filter_absent() -> None:
    stream = PDStream()
    assert stream.is_filter_undefined() is True


def test_is_filter_undefined_false_after_set_filters() -> None:
    stream = PDStream()
    stream.set_filters(COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    assert stream.is_filter_undefined() is False


def test_is_filter_undefined_true_again_after_clear() -> None:
    stream = PDStream()
    stream.set_filters(COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    stream.set_filters(None)
    assert stream.is_filter_undefined() is True


# ---------- /Length ----------


def test_set_length_writes_value_into_dictionary() -> None:
    stream = PDStream()
    stream.set_length(42)
    assert stream.get_length() == 42
    assert (
        stream.get_cos_object().get_int(COSName.LENGTH)  # type: ignore[attr-defined]
        == 42
    )


# ---------- /Metadata typed ----------


def test_get_metadata_typed_returns_cos_stream_when_present() -> None:
    stream = PDStream()
    meta = COSStream()
    meta.set_raw_data(b"<x:xmpmeta/>")
    stream.set_metadata(meta)

    out = stream.get_metadata()
    assert out is meta
    assert isinstance(out, COSStream)


def test_get_metadata_returns_none_when_absent() -> None:
    assert PDStream().get_metadata() is None


# ---------- /F external file spec ----------


def test_get_file_returns_simple_when_f_is_string() -> None:
    stream = PDStream()
    stream.get_cos_object().set_item(
        COSName.get_pdf_name("F"), COSString("payload.bin")
    )
    spec = stream.get_file()
    assert isinstance(spec, PDSimpleFileSpecification)
    assert spec.get_file() == "payload.bin"


def test_get_file_returns_complex_when_f_is_dictionary() -> None:
    stream = PDStream()
    fs_dict = COSDictionary()
    fs_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Filespec"))  # type: ignore[attr-defined]
    fs_dict.set_string("F", "complex.bin")
    stream.get_cos_object().set_item(COSName.get_pdf_name("F"), fs_dict)

    spec = stream.get_file()
    assert isinstance(spec, PDComplexFileSpecification)
    assert spec.get_file() == "complex.bin"


def test_get_file_returns_none_when_absent() -> None:
    assert PDStream().get_file() is None


def test_set_file_round_trip_with_complex_spec() -> None:
    stream = PDStream()
    spec = PDComplexFileSpecification()
    spec.set_file("attachment.bin")
    stream.set_file(spec)

    out = stream.get_file()
    assert isinstance(out, PDFileSpecification)
    assert out.get_file() == "attachment.bin"


def test_set_file_none_removes_entry() -> None:
    stream = PDStream()
    spec = PDComplexFileSpecification()
    spec.set_file("x.bin")
    stream.set_file(spec)
    assert stream.get_file() is not None
    stream.set_file(None)
    assert stream.get_file() is None


# ---------- /FFilter and /FDecodeParms ----------


def test_get_file_filters_absent_returns_empty_list() -> None:
    assert PDStream().get_file_filters() == []


def test_get_file_filters_with_array_returns_chain() -> None:
    stream = PDStream()
    arr = COSArray(
        [
            COSName.ASCII85_DECODE,  # type: ignore[attr-defined]
            COSName.FLATE_DECODE,  # type: ignore[attr-defined]
        ]
    )
    stream.get_cos_object().set_item(COSName.get_pdf_name("FFilter"), arr)
    assert [n.name for n in stream.get_file_filters()] == [
        "ASCII85Decode",
        "FlateDecode",
    ]


def test_get_file_filters_with_single_name_returns_one_element_list() -> None:
    stream = PDStream()
    stream.get_cos_object().set_item(
        COSName.get_pdf_name("FFilter"),
        COSName.FLATE_DECODE,  # type: ignore[attr-defined]
    )
    assert stream.get_file_filters() == [COSName.FLATE_DECODE]  # type: ignore[attr-defined]


def test_get_file_decode_parms_absent_returns_none() -> None:
    assert PDStream().get_file_decode_parms() is None


def test_get_file_decode_parms_with_single_dict() -> None:
    stream = PDStream()
    parms = COSDictionary()
    parms.set_int("Predictor", 12)
    stream.get_cos_object().set_item(COSName.get_pdf_name("FDecodeParms"), parms)

    out = stream.get_file_decode_parms()
    assert out is not None
    assert len(out) == 1
    assert out[0].get_int("Predictor") == 12


def test_get_file_decode_parms_with_array_chain() -> None:
    stream = PDStream()
    p1 = COSDictionary()
    p1.set_int("Predictor", 1)
    p2 = COSDictionary()
    p2.set_int("Predictor", 12)
    stream.get_cos_object().set_item(
        COSName.get_pdf_name("FDecodeParms"), COSArray([p1, p2])
    )

    out = stream.get_file_decode_parms()
    assert out is not None
    assert [d.get_int("Predictor") for d in out] == [1, 12]
