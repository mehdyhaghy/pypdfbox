from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.color import PDOutputIntent
from pypdfbox.pdmodel.pd_document import PDDocument


def test_fresh_intent_sets_type_output_intent() -> None:
    intent = PDOutputIntent()
    cos = intent.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(COSName.TYPE) == "OutputIntent"  # type: ignore[attr-defined]


def test_subtype_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_subtype("GTS_PDFA1")
    assert intent.get_subtype() == "GTS_PDFA1"


def test_info_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_info("sRGB IEC61966-2.1")
    assert intent.get_info() == "sRGB IEC61966-2.1"


def test_output_condition_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_output_condition("commercial offset press")
    assert intent.get_output_condition() == "commercial offset press"


def test_output_condition_identifier_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_output_condition_identifier("CGATS TR 001")
    assert intent.get_output_condition_identifier() == "CGATS TR 001"


def test_registry_name_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_registry_name("http://www.color.org")
    assert intent.get_registry_name() == "http://www.color.org"


def test_dest_output_profile_round_trip_cos_stream() -> None:
    intent = PDOutputIntent()
    profile = COSStream()
    intent.set_dest_output_profile(profile)
    # get_dest_output_profile now returns a typed PDStream wrapping the
    # underlying COSStream; raw access is via get_dest_output_profile_cos.
    assert intent.get_dest_output_profile_cos() is profile


def test_wrap_existing_dictionary_preserves_type() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("OutputIntent"))  # type: ignore[attr-defined]
    raw.set_name(COSName.get_pdf_name("S"), "GTS_PDFX")
    intent = PDOutputIntent(raw)
    assert intent.get_subtype() == "GTS_PDFX"
    assert intent.get_cos_object() is raw


def test_set_subtype_none_removes_key() -> None:
    intent = PDOutputIntent()
    intent.set_subtype("GTS_PDFA1")
    intent.set_subtype(None)
    assert intent.get_subtype() is None


def test_set_dest_output_profile_none_removes_key() -> None:
    intent = PDOutputIntent()
    intent.set_dest_output_profile(COSStream())
    intent.set_dest_output_profile(None)
    assert intent.get_dest_output_profile() is None


# ---------- upstream-named alias parity ----------


def test_get_dest_output_intent_alias_returns_cos_stream() -> None:
    """Upstream PDOutputIntent#getDestOutputIntent() returns the raw
    ``COSStream`` — pypdfbox mirrors the name as a snake_case alias."""
    intent = PDOutputIntent()
    profile = COSStream()
    intent.set_dest_output_profile(profile)
    assert intent.get_dest_output_intent() is profile


def test_get_dest_output_intent_absent_returns_none() -> None:
    intent = PDOutputIntent()
    assert intent.get_dest_output_intent() is None


# ---------- /DestOutputProfileRef (PDF 2.0) ----------


def test_dest_output_profile_ref_round_trip() -> None:
    intent = PDOutputIntent()
    ref = COSDictionary()
    ref.set_string(COSName.get_pdf_name("FS"), "URL")
    intent.set_dest_output_profile_ref(ref)
    assert intent.get_dest_output_profile_ref() is ref


def test_dest_output_profile_ref_none_removes() -> None:
    intent = PDOutputIntent()
    intent.set_dest_output_profile_ref(COSDictionary())
    intent.set_dest_output_profile_ref(None)
    assert intent.get_dest_output_profile_ref() is None


def test_dest_output_profile_ref_absent_returns_none() -> None:
    intent = PDOutputIntent()
    assert intent.get_dest_output_profile_ref() is None


def test_dest_output_profile_ref_rejects_non_dict() -> None:
    intent = PDOutputIntent()
    with pytest.raises(TypeError):
        intent.set_dest_output_profile_ref("not-a-dict")  # type: ignore[arg-type]


# ---------- (document, color_profile) constructor — upstream parity ----------


def _icc_with_signature(colorspace: bytes = b"RGB ") -> bytes:
    """Build a minimal ICC blob: 16 bytes of header + 4-byte colour-space
    signature at offset 16 + filler + 'acsp' magic at offset 36."""
    head = b"\x00" * 16
    return head + colorspace + b"\x00" * 16 + b"acsp" + b"\x00" * 60


def test_document_input_stream_constructor_sets_subtype_and_profile() -> None:
    doc = PDDocument()
    blob = _icc_with_signature(b"RGB ")
    intent = PDOutputIntent(doc, blob)
    # Upstream forces /S = GTS_PDFA1 in this constructor shape.
    assert intent.get_subtype() == "GTS_PDFA1"
    cos_stream = intent.get_dest_output_intent()
    assert isinstance(cos_stream, COSStream)
    # /N should be auto-derived from the ICC colour-space signature.
    assert cos_stream.get_int(COSName.get_pdf_name("N")) == 3


def test_document_input_stream_constructor_infers_n_for_cmyk() -> None:
    doc = PDDocument()
    blob = _icc_with_signature(b"CMYK")
    intent = PDOutputIntent(doc, blob)
    cos_stream = intent.get_dest_output_intent()
    assert cos_stream is not None
    assert cos_stream.get_int(COSName.get_pdf_name("N")) == 4


def test_document_input_stream_constructor_unknown_colorspace_raises() -> None:
    doc = PDDocument()
    # ZZZZ is not a known ICC colour-space signature → can't infer /N.
    blob = _icc_with_signature(b"ZZZZ")
    with pytest.raises(ValueError):
        PDOutputIntent(doc, blob)


def test_document_input_stream_constructor_explicit_num_components() -> None:
    doc = PDDocument()
    # Override even when the signature is recognisable.
    blob = _icc_with_signature(b"RGB ")
    intent = PDOutputIntent(doc, blob, num_components=7)
    cos_stream = intent.get_dest_output_intent()
    assert cos_stream is not None
    assert cos_stream.get_int(COSName.get_pdf_name("N")) == 7


def test_document_constructor_requires_color_profile() -> None:
    doc = PDDocument()
    with pytest.raises(TypeError):
        PDOutputIntent(doc)  # type: ignore[arg-type]


# ---------- get_n_for_profile() helper ----------


def test_get_n_for_profile_absent_returns_none() -> None:
    intent = PDOutputIntent()
    assert intent.get_n_for_profile() is None


def test_get_n_for_profile_reads_explicit_n() -> None:
    """Prefer the explicit ``/N`` integer set on the ``DestOutputProfile``
    stream — no ICC header decode required."""
    intent = PDOutputIntent()
    cos = COSStream()
    cos.set_int(COSName.get_pdf_name("N"), 4)
    intent.set_dest_output_profile(cos)
    assert intent.get_n_for_profile() == 4


def test_get_n_for_profile_reflects_constructor_blob() -> None:
    doc = PDDocument()
    intent = PDOutputIntent(doc, _icc_with_signature(b"CMYK"))
    assert intent.get_n_for_profile() == 4


def test_get_n_for_profile_reflects_set_data() -> None:
    intent = PDOutputIntent()
    blob = _icc_with_signature(b"RGB ")
    intent.set_data(blob, num_components=3)
    assert intent.get_n_for_profile() == 3


def test_document_input_stream_constructor_compresses_bytes() -> None:
    """Upstream embeds the ICC bytes via ``COSName.FLATE_DECODE`` —
    after construction the stream's /Filter must reflect that."""
    doc = PDDocument()
    blob = _icc_with_signature(b"RGB ")
    intent = PDOutputIntent(doc, blob)
    cos_stream = intent.get_dest_output_intent()
    assert cos_stream is not None
    filt = cos_stream.get_dictionary_object(COSName.FILTER)  # type: ignore[attr-defined]
    # /Filter should be the FlateDecode COSName (single-filter form).
    assert filt is not None
    assert COSName.get_pdf_name("FlateDecode") in (
        [filt] if isinstance(filt, COSName) else list(filt)
    )
