from __future__ import annotations

import pytest

from pypdfbox.cos import COSFloat, COSInteger, COSName, COSObject, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


def test_wave574_typed_parse_aliases_return_expected_cos_objects() -> None:
    name_parser = _parser(b"  /A#20Name")
    number_parser = _parser(b" -12.50")
    ref_parser = _parser(b" 12 3 R")

    assert name_parser.parse_cos_name() is COSName.get_pdf_name("A Name")
    parsed_number = number_parser.parse_cos_number()
    parsed_ref = ref_parser.parse_cos_object_reference()

    assert isinstance(parsed_number, COSFloat)
    assert parsed_number.value == -12.5
    assert isinstance(parsed_ref, COSObject)
    assert parsed_ref.get_object_number() == 12
    assert parsed_ref.get_generation_number() == 3


def test_wave574_parse_cos_object_reference_rejects_plain_number() -> None:
    with pytest.raises(PDFParseError, match="expected indirect reference"):
        _parser(b"42").parse_cos_object_reference()


def test_wave574_is_string_accepts_text_and_preserves_position_on_miss() -> None:
    parser = _parser(b"prefix")
    parser.seek(2)

    assert parser.is_string("efi")
    assert parser.position == 2
    assert not parser.is_string(b"efx")
    assert parser.position == 2


def test_wave574_last_index_of_handles_empty_and_bounded_searches() -> None:
    parser = _parser(b"")

    assert parser.last_index_of(b"", b"abc", 3) == -1
    assert parser.last_index_of("aba", b"aba xx aba", 7) == 0
    assert parser.last_index_of(b"aba", b"aba xx aba", 10) == 7
    assert parser.last_index_of(b"missing", b"aba xx aba", 10) == -1


def test_wave574_bf_search_for_objects_ignores_substrings_and_keeps_last_offset() -> None:
    data = (
        b"%PDF-1.4\n"
        b"catalogobj should not match\n"
        b"8 0 obj\n(first)\nendobj\n"
        b"8 0 obj\n(second)\nendobj\n"
        b"9 2 objx should not match\n"
    )

    offsets = _parser(data).bf_search_for_objects()

    # Substrings (``catalogobj`` / ``objx``) are rejected; the duplicated
    # ``8 0 obj`` records the LATER offset (last occurrence wins upstream).
    assert offsets == {COSObjectKey(8, 0): data.rindex(b"8 0 obj")}


def test_wave574_bf_search_for_xref_falls_back_to_xref_stream_object() -> None:
    data = (
        b"%PDF-1.5\n"
        b"4 0 obj\n"
        b"<< /Type /XRef /Size 1 /W [1 1 1] /Length 0 >>\n"
        b"stream\n\nendstream\nendobj\n"
        b"startxref\n999\n%%EOF"
    )

    assert _parser(data).bf_search_for_xref(999) == data.index(b"4 0 obj")


def test_wave574_rebuild_trailer_collects_catalog_info_encrypt_id_and_size() -> None:
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"2 0 obj\n<< /Title (Doc) >>\nendobj\n"
        b"3 0 obj\n<< /Encrypt << /Filter /Standard >> /ID [(a) (b)] >>\nendobj\n"
    )

    trailer = _parser(data).rebuild_trailer()

    root = trailer.get_item(COSName.ROOT)
    info = trailer.get_item(COSName.INFO)
    assert isinstance(root, COSObject)
    assert root.get_object_number() == 1
    assert isinstance(info, COSObject)
    assert info.get_object_number() == 2
    assert trailer.get_dictionary_object(COSName.ENCRYPT) is not None  # type: ignore[attr-defined]
    assert trailer.get_dictionary_object(COSName.get_pdf_name("ID")) is not None
    assert trailer.get_dictionary_object(COSName.SIZE) is COSInteger.get(4)  # type: ignore[attr-defined]
