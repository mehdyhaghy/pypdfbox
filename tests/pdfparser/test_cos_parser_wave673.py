from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser


def _parser(data: bytes = b"") -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


class _FailingHandler:
    def decrypt_stream(self, data: bytes, obj_num: int, gen_num: int) -> bytes:
        raise AssertionError("skip-encryption streams must not be decrypted")


def test_wave673_bruteforce_xref_stream_scan_skips_unparseable_candidate() -> None:
    class ParserWithBadCandidate(COSParser):
        def bf_search_for_objects(self) -> dict[COSObjectKey, int]:
            return {COSObjectKey(7, 0): 0}

    parser = ParserWithBadCandidate(RandomAccessReadBuffer(b"not an object"))

    assert parser.bf_search_for_xref(0) == -1


def test_wave673_cos_stream_skip_encryption_blocks_handler_attachment() -> None:
    stream = COSStream()
    stream.set_raw_data(b"plain")
    stream.set_skip_encryption(True)

    stream.set_security_handler(_FailingHandler(), 10, 0)

    with stream.create_input_stream() as src:
        assert src.read() == b"plain"


def test_wave673_cos_stream_closed_output_and_idempotent_close() -> None:
    stream = COSStream()
    stream.set_raw_data(b"body")
    stream.close()

    assert stream.is_closed() is True
    # wave 1563: set_raw_data() now syncs the /Length dict entry (=4) and
    # get_length() reads that entry (upstream parity), so the dict carries one
    # key and repr reports the recorded length even after the body is freed.
    assert repr(stream) == "COSStream(dict_size=1, body_len=4)"
    with pytest.raises(OSError, match="COSStream has been closed"):
        stream.create_output_stream()

    stream.close()
    assert stream.is_closed() is True


def test_wave673_cos_stream_set_filters_none_clears_existing_filter() -> None:
    stream = COSStream()
    stream.set_filters(COSName.FLATE_DECODE)  # type: ignore[attr-defined]

    stream.set_filters(None)

    assert stream.get_filters() is None
    assert stream.has_filters() is False


def test_wave673_cos_stream_rejects_non_name_filter_array_entry() -> None:
    stream = COSStream()

    with pytest.raises(TypeError, match="non-name entry"):
        stream.set_filters(COSArray([COSInteger.get(1)]))


def test_wave673_cos_stream_rejects_non_name_sequence_entry() -> None:
    stream = COSStream()

    with pytest.raises(TypeError, match="filter entry must be COSName or str"):
        stream.set_filters([object()])  # type: ignore[list-item]


def test_wave673_xref_stream_type_autoskips_later_security_handler() -> None:
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XRef"))
    stream.set_raw_data(b"xref-bytes")

    stream.set_security_handler(object(), 9, 0)

    assert stream.is_skip_encryption() is True
    with stream.create_input_stream() as src:
        assert src.read() == b"xref-bytes"
