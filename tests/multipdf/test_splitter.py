from __future__ import annotations

import io

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.multipdf import Splitter


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n_pages):
        doc.add_page(PDPage())
    return doc


# ---------- split-every-N ----------


def test_default_split_one_page_per_chunk() -> None:
    src = _make_doc(3)
    splitter = Splitter()
    chunks = splitter.split(src)
    assert len(chunks) == 3
    for chunk in chunks:
        assert chunk.get_number_of_pages() == 1
        chunk.close()
    src.close()


def test_split_two_pages_per_chunk_uneven_tail() -> None:
    src = _make_doc(5)
    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)
    sizes = [c.get_number_of_pages() for c in chunks]
    assert sizes == [2, 2, 1]
    for c in chunks:
        c.close()
    src.close()


def test_split_alias_set_split() -> None:
    """``set_split`` is the task-spec alias for ``set_split_at_page``."""
    src = _make_doc(4)
    splitter = Splitter()
    splitter.set_split(2)
    chunks = splitter.split(src)
    assert [c.get_number_of_pages() for c in chunks] == [2, 2]
    for c in chunks:
        c.close()
    src.close()


def test_split_chunk_larger_than_doc_returns_one_doc() -> None:
    src = _make_doc(3)
    splitter = Splitter()
    splitter.set_split_at_page(10)
    chunks = splitter.split(src)
    assert len(chunks) == 1
    assert chunks[0].get_number_of_pages() == 3
    chunks[0].close()
    src.close()


# ---------- page range ----------


def test_split_with_start_and_end_page() -> None:
    src = _make_doc(10)
    splitter = Splitter()
    splitter.set_start_page(3)
    splitter.set_end_page(5)
    chunks = splitter.split(src)
    # 3 pages in range, default split=1 → 3 outputs.
    assert len(chunks) == 3
    for c in chunks:
        assert c.get_number_of_pages() == 1
        c.close()
    src.close()


def test_split_range_combined_with_chunk_size() -> None:
    src = _make_doc(10)
    splitter = Splitter()
    splitter.set_start_page(3)
    splitter.set_end_page(8)
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)
    # 6 pages in range, chunks of 2 → 3 docs of 2 pages each.
    assert [c.get_number_of_pages() for c in chunks] == [2, 2, 2]
    for c in chunks:
        c.close()
    src.close()


# ---------- blank / edge cases ----------


def test_split_blank_input_returns_empty_list() -> None:
    src = _make_doc(0)
    splitter = Splitter()
    chunks = splitter.split(src)
    assert chunks == []
    src.close()


def test_split_range_outside_document_returns_nothing() -> None:
    src = _make_doc(3)
    splitter = Splitter()
    splitter.set_start_page(10)
    splitter.set_end_page(20)
    chunks = splitter.split(src)
    assert chunks == []
    src.close()


# ---------- argument validation ----------


def test_set_split_at_page_rejects_zero() -> None:
    splitter = Splitter()
    with pytest.raises(ValueError, match="smaller than one"):
        splitter.set_split_at_page(0)


def test_set_split_at_page_rejects_negative() -> None:
    splitter = Splitter()
    with pytest.raises(ValueError, match="smaller than one"):
        splitter.set_split_at_page(-1)


def test_set_start_page_rejects_zero() -> None:
    splitter = Splitter()
    with pytest.raises(ValueError, match="smaller than one"):
        splitter.set_start_page(0)


def test_set_end_page_rejects_zero() -> None:
    splitter = Splitter()
    with pytest.raises(ValueError, match="smaller than one"):
        splitter.set_end_page(0)


def test_set_end_page_rejects_below_start() -> None:
    splitter = Splitter()
    splitter.set_start_page(5)
    with pytest.raises(ValueError, match="smaller than startPage"):
        splitter.set_end_page(3)


# ---------- save / round-trip ----------


def test_split_chunks_are_saveable_and_round_trip() -> None:
    src = _make_doc(4)
    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)
    saved: list[bytes] = []
    for c in chunks:
        sink = io.BytesIO()
        c.save(sink)
        saved.append(sink.getvalue())
        c.close()
    src.close()
    for blob in saved:
        with PDDocument.load(blob) as reloaded:
            assert reloaded.get_number_of_pages() == 2


def test_split_subclass_can_override_split_at_page() -> None:
    """Mirrors upstream's protected-override extensibility hook —
    subclasses can override ``split_at_page`` to bucket arbitrarily."""
    class EveryThirdSplitter(Splitter):
        def split_at_page(self, page_number: int) -> bool:
            return page_number % 3 == 0

    src = _make_doc(6)
    chunks = EveryThirdSplitter().split(src)
    # New doc opens at page 0, 3 → 2 chunks of 3 pages.
    assert [c.get_number_of_pages() for c in chunks] == [3, 3]
    for c in chunks:
        c.close()
    src.close()


def test_memory_usage_setting_recorded() -> None:
    """``set_memory_usage_setting`` is advisory in this port — verify
    the setter round-trips so the hook stays available for future
    threading."""
    from pypdfbox.io import MemoryUsageSetting

    splitter = Splitter()
    setting = MemoryUsageSetting.setup_main_memory_only()
    splitter.set_memory_usage_setting(setting)
    assert splitter.get_memory_usage_setting() is setting


def test_stream_cache_create_function_round_trips() -> None:
    splitter = Splitter()

    def make_cache():  # noqa: ANN202
        return None

    splitter.set_stream_cache_create_function(make_cache)
    assert splitter.get_stream_cache_create_function() is make_cache


# ---------- destination document inherits from source ----------


def test_destination_inherits_source_version() -> None:
    src = _make_doc(2)
    src.set_version(1.7)
    splitter = Splitter()
    chunks = splitter.split(src)
    for c in chunks:
        assert c.get_version() == src.get_version()
        c.close()
    src.close()


def test_destination_inherits_source_info_dict() -> None:
    src = _make_doc(2)
    info = src.get_document_information()
    info.set_title("Source title")
    info.set_author("Test author")
    splitter = Splitter()
    chunks = splitter.split(src)
    for c in chunks:
        chunk_info = c.get_document_information()
        assert chunk_info.get_title() == "Source title"
        assert chunk_info.get_author() == "Test author"
        c.close()
    src.close()
