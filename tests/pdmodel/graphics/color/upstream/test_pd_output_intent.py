"""Parity tests modelled on upstream PDFBox 3.0 ``PDOutputIntent``.

Upstream does not ship a dedicated ``PDOutputIntentTest`` in
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/color``, so
these tests target the documented behaviour of the public Java API:

* the ``(PDDocument, InputStream)`` constructor sets ``/S = GTS_PDFA1``,
  embeds the ICC bytes through a flate-compressed ``PDStream``, and
  records ``/N`` from the ICC header;
* the simple string accessors round-trip ``/Info``,
  ``/OutputCondition``, ``/OutputConditionIdentifier``, ``/RegistryName``;
* ``getDestOutputIntent()`` exposes the underlying ``COSStream`` (no
  typed wrapping).
"""
from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.color import PDOutputIntent
from pypdfbox.pdmodel.pd_document import PDDocument


_S = COSName.get_pdf_name("S")
_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_DEST_OUTPUT_PROFILE = COSName.get_pdf_name("DestOutputProfile")
_N = COSName.get_pdf_name("N")
_INFO = COSName.get_pdf_name("Info")
_OUTPUT_CONDITION = COSName.get_pdf_name("OutputCondition")
_OUTPUT_CONDITION_IDENTIFIER = COSName.get_pdf_name("OutputConditionIdentifier")
_REGISTRY_NAME = COSName.get_pdf_name("RegistryName")
_FILTER = COSName.FILTER  # type: ignore[attr-defined]
_FLATE_DECODE = COSName.FLATE_DECODE  # type: ignore[attr-defined]


def _icc_blob(colorspace: bytes = b"RGB ", n: int = 3) -> bytes:
    """Build a minimal ICC profile blob.

    Mirrors what ``ICC_Profile.getInstance(colorProfile).getData()`` would
    produce on the Java side: header bytes through offset 39 carrying the
    colour-space signature at 16..19 and the ``acsp`` marker at 36..39.
    """
    head = b"\x00" * 16
    return head + colorspace + b"\x00" * 16 + b"acsp" + b"\x00" * 60


def test_constructor_pd_document_input_stream_sets_subtype_and_profile() -> None:
    """Mirror of the upstream ``PDOutputIntent(PDDocument, InputStream)``
    constructor contract: ``/Type = OutputIntent``, ``/S = GTS_PDFA1``,
    ``/DestOutputProfile`` populated with ``/N`` from the ICC header."""
    doc = PDDocument()
    intent = PDOutputIntent(doc, _icc_blob(b"RGB "))

    cos = intent.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(_TYPE) == "OutputIntent"
    assert cos.get_name(_S) == "GTS_PDFA1"

    dest = intent.get_dest_output_intent()
    assert isinstance(dest, COSStream)
    assert dest.get_int(_N) == 3


def test_constructor_pd_document_input_stream_compresses_via_flate() -> None:
    """Upstream embeds the bytes via ``COSName.FLATE_DECODE`` — the
    resulting stream's ``/Filter`` must reflect that."""
    doc = PDDocument()
    intent = PDOutputIntent(doc, _icc_blob(b"CMYK"))
    dest = intent.get_dest_output_intent()
    assert dest is not None
    filt = dest.get_dictionary_object(_FILTER)
    flate = COSName.get_pdf_name("FlateDecode")
    assert filt == flate or flate in (list(filt) if filt is not None else [])


def test_constructor_pd_document_input_stream_n_for_cmyk() -> None:
    doc = PDDocument()
    intent = PDOutputIntent(doc, _icc_blob(b"CMYK"))
    dest = intent.get_dest_output_intent()
    assert dest is not None
    assert dest.get_int(_N) == 4


def test_constructor_cos_dictionary_wrap() -> None:
    """Mirror of upstream ``PDOutputIntent(COSDictionary)`` —
    ``getCOSObject`` returns the wrapped dict identity-equal."""
    raw = COSDictionary()
    raw.set_item(_TYPE, COSName.get_pdf_name("OutputIntent"))
    intent = PDOutputIntent(raw)
    assert intent.get_cos_object() is raw


def test_info_round_trip() -> None:
    """Upstream ``getInfo``/``setInfo`` parity."""
    intent = PDOutputIntent()
    assert intent.get_info() is None
    intent.set_info("sRGB IEC61966-2.1")
    assert intent.get_info() == "sRGB IEC61966-2.1"
    assert intent.get_cos_object().get_string(_INFO) == "sRGB IEC61966-2.1"


def test_output_condition_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_output_condition("commercial offset press")
    assert intent.get_output_condition() == "commercial offset press"
    assert intent.get_cos_object().get_string(_OUTPUT_CONDITION) == "commercial offset press"


def test_output_condition_identifier_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_output_condition_identifier("CGATS TR 001")
    assert intent.get_output_condition_identifier() == "CGATS TR 001"
    assert (
        intent.get_cos_object().get_string(_OUTPUT_CONDITION_IDENTIFIER)
        == "CGATS TR 001"
    )


def test_registry_name_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_registry_name("http://www.color.org")
    assert intent.get_registry_name() == "http://www.color.org"
    assert (
        intent.get_cos_object().get_string(_REGISTRY_NAME)
        == "http://www.color.org"
    )


def test_get_dest_output_intent_returns_cos_stream_identity() -> None:
    """Upstream ``getDestOutputIntent`` returns the raw ``COSStream``."""
    intent = PDOutputIntent()
    raw = COSStream()
    intent.get_cos_object().set_item(_DEST_OUTPUT_PROFILE, raw)
    assert intent.get_dest_output_intent() is raw
