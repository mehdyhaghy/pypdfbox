from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream
from pypdfbox.io import MemoryUsageSetting, ScratchFile


def test_empty_stream_state() -> None:
    with COSStream() as s:
        assert not s.has_data()
        assert s.get_length() == 0
        assert s.get_raw_data() == b""


def test_set_and_get_raw_data() -> None:
    with COSStream() as s:
        s.set_raw_data(b"hello world")
        assert s.has_data()
        assert s.get_length() == 11
        assert s.get_raw_data() == b"hello world"


def test_set_raw_data_replaces_previous() -> None:
    with COSStream() as s:
        s.set_raw_data(b"first")
        s.set_raw_data(b"second-much-longer")
        assert s.get_raw_data() == b"second-much-longer"


def test_create_raw_input_stream_returns_snapshot() -> None:
    with COSStream() as s:
        s.set_raw_data(b"abcdef")
        rs = s.create_raw_input_stream()
        assert rs.read() == b"abcdef"
        # Mutating the stream after snapshot does not affect the snapshot.
        s.set_raw_data(b"XYZ")
        rs2 = s.create_raw_input_stream()
        assert rs2.read() == b"XYZ"


def test_create_raw_output_stream_commits_on_close() -> None:
    with COSStream() as s:
        ws = s.create_raw_output_stream()
        ws.write(b"committed bytes")
        ws.close()
        assert s.get_raw_data() == b"committed bytes"


def test_inherits_dictionary_behavior() -> None:
    with COSStream() as s:
        s.set_int(COSName.LENGTH, 99)  # type: ignore[attr-defined]
        s.set_name("Type", "XObject")
        assert s.get_int(COSName.LENGTH) == 99  # type: ignore[attr-defined]
        assert s.get_name("Type") == "XObject"


def test_get_filter_list_absent() -> None:
    with COSStream() as s:
        assert s.get_filter_list() == []


def test_get_filter_list_single_name() -> None:
    with COSStream() as s:
        s.set_item(COSName.FILTER, COSName.get_pdf_name("FlateDecode"))  # type: ignore[attr-defined]
        assert s.get_filter_list() == [COSName.get_pdf_name("FlateDecode")]


def test_get_filter_list_array() -> None:
    with COSStream() as s:
        chain = COSArray(
            [COSName.get_pdf_name("ASCII85Decode"), COSName.get_pdf_name("FlateDecode")]
        )
        s.set_item(COSName.FILTER, chain)  # type: ignore[attr-defined]
        names = s.get_filter_list()
        assert [n.name for n in names] == ["ASCII85Decode", "FlateDecode"]


def test_get_filter_list_invalid_entry_raises() -> None:
    with COSStream() as s:
        bad = COSArray([COSInteger(1)])
        s.set_item(COSName.FILTER, bad)  # type: ignore[attr-defined]
        with pytest.raises(TypeError):
            s.get_filter_list()


def test_uses_supplied_scratch_file() -> None:
    sf = ScratchFile(MemoryUsageSetting.setup_main_memory_only())
    s = COSStream(scratch_file=sf)
    s.set_raw_data(b"shared scratch")
    s.close()
    # External scratch file remains open (caller-owned).
    assert not sf.is_closed()
    sf.close()


def test_internal_scratch_file_closed_with_stream() -> None:
    s = COSStream()
    s.set_raw_data(b"x")
    internal_scratch = s._scratch  # noqa: SLF001 — testing lifecycle
    s.close()
    assert internal_scratch.is_closed()


def test_operations_on_closed_stream_raise() -> None:
    s = COSStream()
    s.close()
    with pytest.raises(ValueError):
        s.set_raw_data(b"x")
    with pytest.raises(ValueError):
        s.create_raw_output_stream()


def test_visitor_dispatches_to_visit_from_stream() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    with COSStream() as s:
        s.accept(v)
        assert v.calls == [("stream", s)]


def test_construct_with_initial_dict_items() -> None:
    pairs = [("Type", COSName.get_pdf_name("XObject")), ("Length", COSInteger(0))]
    with COSStream(items=pairs) as s:
        assert s.get_name("Type") == "XObject"
        assert s.get_int("Length") == 0
