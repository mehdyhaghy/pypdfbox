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


def test_zero_length_raw_data_still_counts_as_stream_data() -> None:
    with COSStream() as s:
        s.set_raw_data(b"")
        assert s.has_data()
        assert s.get_length() == 0
        assert s.create_raw_input_stream().read() == b""


def test_zero_length_output_stream_still_counts_as_stream_data() -> None:
    with COSStream() as s:
        with s.create_raw_output_stream():
            pass
        assert s.has_data()
        assert s.get_length() == 0
        assert s.create_input_stream().read() == b""


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
    with pytest.raises(OSError, match="COSStream has been closed"):
        s.set_raw_data(b"x")
    with pytest.raises(OSError, match="COSStream has been closed"):
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


def test_get_filters_returns_none_when_absent() -> None:
    with COSStream() as s:
        assert s.get_filters() is None


def test_get_filters_returns_single_name() -> None:
    with COSStream() as s:
        s.set_item(COSName.FILTER, COSName.FLATE_DECODE)  # type: ignore[attr-defined]
        assert s.get_filters() is COSName.FLATE_DECODE  # type: ignore[attr-defined]


def test_get_filters_returns_array() -> None:
    with COSStream() as s:
        chain = COSArray(
            [COSName.get_pdf_name("ASCII85Decode"), COSName.get_pdf_name("FlateDecode")]
        )
        s.set_item(COSName.FILTER, chain)  # type: ignore[attr-defined]
        result = s.get_filters()
        assert isinstance(result, COSArray)
        names: list[str] = []
        for entry in result:
            assert isinstance(entry, COSName)
            names.append(entry.name)
        assert names == ["ASCII85Decode", "FlateDecode"]


def test_to_text_string_pdfdocencoding() -> None:
    with COSStream() as s:
        s.set_raw_data(b"Hello PDF")
        assert s.to_text_string() == "Hello PDF"


def test_to_text_string_utf16_bom() -> None:
    with COSStream() as s:
        s.set_raw_data(b"\xfe\xff" + "Tëst".encode("utf-16-be"))
        assert s.to_text_string() == "Tëst"


def test_to_text_string_empty_when_no_data() -> None:
    """Mirrors upstream's swallow-and-log behavior — an unreadable body
    yields ``""`` instead of raising."""
    with COSStream() as s:
        assert s.to_text_string() == ""


def test_to_text_string_decodes_through_filter_chain() -> None:
    with COSStream() as s:
        with s.create_output_stream(COSName.FLATE_DECODE) as out:  # type: ignore[attr-defined]
            out.write(b"compressed payload")
        assert s.to_text_string() == "compressed payload"


def test_create_view_no_filter_returns_decoded_buffer() -> None:
    """``create_view`` over an unfiltered stream returns a
    seekable/lengthable ``RandomAccessRead`` view over the raw body."""
    with COSStream() as s:
        s.set_raw_data(b"plain bytes")
        view = s.create_view()
        try:
            assert view.length() == len(b"plain bytes")
            buf = bytearray(view.length())
            n = view.read_into(buf)
            assert n == len(b"plain bytes")
            assert bytes(buf) == b"plain bytes"
        finally:
            view.close()


def test_create_view_with_filter_chain_returns_decoded_buffer() -> None:
    """When ``/Filter`` is set, ``create_view`` runs the decode chain and
    returns a buffer over the decoded payload (not raw)."""
    payload = b"compressed view payload"
    with COSStream() as s:
        with s.create_output_stream(COSName.FLATE_DECODE) as out:  # type: ignore[attr-defined]
            out.write(payload)
        view = s.create_view()
        try:
            buf = bytearray(view.length())
            view.read_into(buf)
            assert bytes(buf) == payload
        finally:
            view.close()


def test_create_view_no_data_raises() -> None:
    with COSStream() as s, pytest.raises(OSError):
        s.create_view()


def test_length_entry_synced_after_raw_output_close() -> None:
    """Mirrors upstream inner ``close()`` (line 249) which calls
    ``setInt(COSName.LENGTH, randomAccess.length())`` so the dictionary
    stays consistent with the body length on commit."""
    with COSStream() as s:
        with s.create_raw_output_stream() as out:
            out.write(b"twelve bytes")
        assert s.get_int(COSName.LENGTH) == 12  # type: ignore[attr-defined]
        assert s.get_length() == 12


def test_length_entry_synced_after_filtered_output_close() -> None:
    """Filtered writer also commits ``/Length`` to the dict on close —
    the encoded raw size, mirroring upstream parity for ``isWriting`` +
    ``setInt(COSName.LENGTH, ...)``."""
    with COSStream() as s:
        with s.create_output_stream(COSName.FLATE_DECODE) as out:  # type: ignore[attr-defined]
            out.write(b"compressed body")
        # Whatever the encoded length is, dictionary entry must equal it.
        assert s.get_int(COSName.LENGTH) == s.get_length()  # type: ignore[attr-defined]
        assert s.get_length() > 0


def test_open_writer_blocks_second_writer() -> None:
    """Upstream guard at lines 222 and 266: opening a second output
    stream while one is already open must raise."""
    with COSStream() as s:
        out = s.create_output_stream()
        try:
            with pytest.raises(RuntimeError):
                s.create_output_stream()
            with pytest.raises(RuntimeError):
                s.create_raw_output_stream()
        finally:
            out.close()


def test_open_writer_blocks_reads_and_length() -> None:
    """Upstream ``isWriting`` guard at lines 137, 333: while a writer is
    open, reading and querying length must raise."""
    with COSStream() as s:
        s.set_raw_data(b"existing")
        out = s.create_raw_output_stream()
        try:
            with pytest.raises(RuntimeError):
                s.create_input_stream()
            with pytest.raises(RuntimeError):
                s.create_raw_input_stream()
            with pytest.raises(RuntimeError):
                s.get_length()
        finally:
            out.close()


def test_check_closed_after_owns_scratch_close() -> None:
    """``check_closed`` raises once the backing scratch file is gone —
    mirrors upstream ``checkClosed()`` (line 105)."""
    s = COSStream()
    s.set_raw_data(b"x")
    s.close()
    with pytest.raises(OSError):
        s.check_closed()


def test_get_stream_cache_returns_internal_scratch() -> None:
    """``get_stream_cache`` returns the ``ScratchFile`` backing this
    stream — mirrors upstream ``getStreamCache()`` (lines 116–124)."""
    s = COSStream()
    cache = s.get_stream_cache()
    assert cache is s._scratch  # noqa: SLF001 — testing the contract


def test_get_stream_cache_returns_supplied_scratch() -> None:
    """When the caller passes a ``ScratchFile`` to the ctor,
    ``get_stream_cache`` returns that same instance — same identity
    invariant upstream ``getStreamCache`` provides for the cached
    ``RandomAccessStreamCache``."""
    sf = ScratchFile(MemoryUsageSetting.setup_main_memory_only())
    try:
        s = COSStream(scratch_file=sf)
        try:
            assert s.get_stream_cache() is sf
        finally:
            s.close()
    finally:
        sf.close()


def test_length_dict_uses_cached_integer_zero() -> None:
    """The internal ``_sync_length_entry`` must route through
    ``COSInteger.get`` so a length of 0 lands as the cached singleton —
    matches upstream ``setInt(COSName.LENGTH, 0)`` semantics where Java
    auto-boxing returns the cached ``Integer`` for values in the small-int
    cache range."""
    with COSStream() as s:
        with s.create_raw_output_stream():
            pass
        length_entry = s.get_dictionary_object(COSName.LENGTH)  # type: ignore[attr-defined]
        assert length_entry is COSInteger.get(0)
