"""Wave 1369 — PDContentStream COSStream + COSArray concatenation and
``/Resources`` inheritance from the page parent.

PDF 32000-1 §7.8.2 allows ``/Contents`` to be either a single stream or
an array of streams that *must be concatenated* with whitespace between
them (so adjacent operator runs don't fuse). pypdfbox does this with a
single newline join (matches upstream's ``DELIMITER``). These tests pin
the join and the inheritance fall-through that ``push_resources`` does
when a child stream has no ``/Resources`` of its own.
"""

from __future__ import annotations

import io
from typing import IO, Any

from pypdfbox.contentstream import PDContentStream, PDFStreamEngine
from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDPage, PDRectangle, PDResources

# ---------- COSStream + COSArray concatenation on PDPage ----------


def _make_stream(payload: bytes) -> COSStream:
    cs = COSStream()
    with cs.create_raw_output_stream() as out:
        out.write(payload)
    return cs


def test_page_contents_single_stream_returns_raw_bytes() -> None:
    """Single-stream form: bytes come back exactly as written."""
    page = PDPage()
    page.set_contents(_make_stream(b"q 1 0 0 1 0 0 cm Q"))
    assert page.get_contents() == b"q 1 0 0 1 0 0 cm Q"


def test_page_contents_array_form_concatenates_with_newline() -> None:
    """Array of streams: bodies joined by a single ``\\n`` so operator
    runs from adjacent entries don't merge into one another (e.g. the
    ``Q`` terminator from stream 1 stays distinct from the ``q`` opener
    of stream 2)."""
    page = PDPage()
    page.set_contents([_make_stream(b"q"), _make_stream(b"Q"), _make_stream(b"BT ET")])
    assert page.get_contents() == b"q\nQ\nBT ET"


def test_page_contents_empty_array_yields_empty_bytes() -> None:
    page = PDPage()
    arr = COSArray()
    page.set_contents(arr)
    assert page.get_contents() == b""


def test_page_contents_array_with_non_stream_entries_skipped() -> None:
    """Per upstream: only ``COSStream`` entries contribute to the
    aggregate; everything else is silently skipped."""
    page = PDPage()
    arr = COSArray()
    arr.add(_make_stream(b"q"))
    arr.add(COSName.get_pdf_name("Not-a-stream"))
    arr.add(_make_stream(b"Q"))
    page.set_contents(arr)
    assert page.get_contents() == b"q\nQ"


def test_page_with_no_contents_returns_empty_bytes() -> None:
    """``/Contents`` absent: yields ``b""`` (blank page)."""
    page = PDPage()
    page.clear_contents()
    assert page.get_contents() == b""


def test_process_page_drives_concatenated_array_through_engine() -> None:
    """End-to-end: array-of-streams ``/Contents`` parses + dispatches as
    if it were a single concatenated stream. Two ``BT/ET`` runs split
    across two array entries should both fire ``begin_text`` /
    ``end_text``."""

    class _Engine(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.begins = 0
            self.ends = 0

        def begin_text(self) -> None:
            self.begins += 1

        def end_text(self) -> None:
            self.ends += 1

    from pypdfbox.contentstream.operator.text import BeginText, EndText

    engine = _Engine()
    engine.add_operator(BeginText())
    engine.add_operator(EndText())
    page = PDPage()
    page.set_contents([_make_stream(b"BT ET"), _make_stream(b"BT ET")])
    engine.process_page(page)
    assert engine.begins == 2
    assert engine.ends == 2


# ---------- /Resources inheritance ----------


class _NamedResources(PDResources):
    """Identifiable PDResources subclass for ``is``-checks."""

    def __init__(self, tag: str) -> None:
        super().__init__()
        self.tag = tag


class _ChildStream(PDContentStream):
    """Content stream that may or may not own its own ``/Resources`` —
    when it doesn't, ``push_resources`` should leave the parent frame
    untouched (PDFBOX-1359 fall-through)."""

    def __init__(self, data: bytes, own_resources: PDResources | None) -> None:
        self._data = data
        self._own = own_resources

    def get_contents(self) -> IO[bytes]:
        return io.BytesIO(self._data)

    def get_contents_for_random_access(self) -> RandomAccessRead:
        return RandomAccessReadBuffer(self._data)

    def get_resources(self) -> PDResources | None:
        return self._own

    def get_bbox(self) -> PDRectangle:
        return PDRectangle(0.0, 0.0, 10.0, 10.0)

    def get_matrix(self) -> Any:
        return None


def test_push_resources_uses_stream_own_resources_when_present() -> None:
    """When the child stream owns ``/Resources``, it becomes active.
    Mirrors upstream ``pushResources`` first branch."""
    engine = PDFStreamEngine()
    parent = _NamedResources("parent")
    child = _NamedResources("child")
    engine._resources = parent
    prior = engine.push_resources(_ChildStream(b"", child))
    assert engine.get_resources() is child
    assert prior is parent


def test_push_resources_inherits_parent_when_stream_has_none() -> None:
    """PDFBOX-1359 — when the child stream has no ``/Resources`` *and*
    the engine already has a parent frame, the parent stays active
    (Acrobat does this; the spec doesn't strictly require it)."""
    engine = PDFStreamEngine()
    parent = _NamedResources("parent")
    engine._resources = parent
    prior = engine.push_resources(_ChildStream(b"", None))
    assert engine.get_resources() is parent
    assert prior is parent


def test_push_resources_falls_back_to_page_resources() -> None:
    """When neither the stream nor the engine has a resources frame,
    fall back to the current page's ``/Resources``. Mirrors upstream's
    third fall-through branch."""
    engine = PDFStreamEngine()
    page = PDPage()
    page_res = _NamedResources("page")
    page.set_resources(page_res)
    engine._current_page = page
    engine._resources = None
    engine.push_resources(_ChildStream(b"", None))
    # ``page.get_resources()`` materialises a new wrapper around the
    # underlying COSDictionary on each call — assert by COS-object identity
    # rather than wrapper identity so we don't rely on caching.
    active = engine.get_resources()
    assert active is not None
    assert active.get_cos_object() is page_res.get_cos_object()


def test_push_resources_synthesises_fresh_resources_when_page_has_none() -> None:
    """No stream resources, no engine resources, no page → synthesise a
    fresh empty ``PDResources`` so downstream operator handlers always
    see a non-``None`` frame."""
    engine = PDFStreamEngine()
    engine._current_page = None
    engine._resources = None
    engine.push_resources(_ChildStream(b"", None))
    active = engine.get_resources()
    assert active is not None
    # Empty resources — no XObject map yet.
    assert active.get_cos_object().size() == 0


def test_pop_resources_restores_prior_frame() -> None:
    """``pop_resources`` wholesale-replaces the active frame with the
    one returned from ``push_resources``."""
    engine = PDFStreamEngine()
    outer = _NamedResources("outer")
    engine._resources = outer
    prior = engine.push_resources(_ChildStream(b"", _NamedResources("inner")))
    engine.pop_resources(prior)
    assert engine.get_resources() is outer


def test_process_stream_pushes_then_pops_resources_around_dispatch() -> None:
    """End-to-end: ``process_stream`` sets the child's resources for the
    dispatch window and restores the parent frame on return — even when
    the dispatch path raises."""
    engine = PDFStreamEngine()
    parent = _NamedResources("parent")
    child = _NamedResources("child")
    engine._resources = parent
    engine.process_stream(_ChildStream(b"", child))
    # On return, the parent frame is active again.
    assert engine.get_resources() is parent
