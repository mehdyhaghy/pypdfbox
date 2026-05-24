"""Wave 1394 — uncovered defensive branches in ``Splitter``.

Covers:

* Lines 375-376 — ``_finalize_annotation_links`` raising an exception
  during the post-chunk pass: ``_LOG.exception`` is invoked and the
  rest of the loop continues.
* Lines 1219-1223 — cross-chunk resolver returns a 2-tuple whose
  elements aren't ``(str, int)``: warning logged, ``False`` returned
  (null-out fallback).
* Line 1252 — ``_apply_cross_chunk_destination_via_resolver`` returns
  ``True`` early when the destination array has no matching link
  record (orphan destination).
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSInteger, COSNull, COSStream
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
    PDPageFitDestination,
)


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for i in range(n_pages):
        page = PDPage()
        s = COSStream()
        s.set_raw_data(b"% page " + str(i).encode("ascii") + b"\n")
        page.set_contents(s)
        doc.add_page(page)
    return doc


def _fit(page: PDPage) -> PDPageFitDestination:
    dest = PDPageFitDestination()
    dest.set_page(page)
    return dest


# ---------- lines 375-376: _finalize_annotation_links exception ----------


def test_finalize_annotation_links_failure_is_caught_per_chunk(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An exception inside ``_finalize_annotation_links`` is logged and
    suppressed; the rest of the post-chunk pass still runs and split
    returns normally (lines 375-376)."""
    src = _make_doc(2)
    sp = Splitter()

    def _boom(*_a, **_kw):
        raise RuntimeError("simulated annotation linkage failure")

    monkeypatch.setattr(sp, "_finalize_annotation_links", _boom)
    caplog.set_level(logging.ERROR, logger="pypdfbox.multipdf.splitter")
    chunks = sp.split(src)
    try:
        # Even with the failure, the split produced its expected output.
        assert len(chunks) >= 1
        assert any(
            "annotation linkage finalisation failed" in rec.message
            for rec in caplog.records
        )
    finally:
        for c in chunks:
            c.close()
        src.close()


# ---------- lines 1219-1223: resolver returns 2-tuple with wrong element types ----------


def test_cross_chunk_resolver_2tuple_with_non_str_filename_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Resolver returns a 2-tuple whose first element isn't ``str`` →
    null-out fallback (lines 1219-1223)."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    link.set_destination(_fit(src_pages[1]))
    src_pages[0].set_annotations([link])

    sp = Splitter().set_cross_chunk_destination_resolver(
        lambda _dict: (123, 0)  # filename slot is int, not str
    )
    caplog.set_level(logging.WARNING, logger="pypdfbox.multipdf.splitter")
    chunks = sp.split(src)
    try:
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        dest = imported_link.get_destination()
        assert isinstance(dest, PDPageDestination)
        assert dest.get_cos_object().get(0) is COSNull.NULL
        assert any(
            "non-(str,int) tuple" in rec.message for rec in caplog.records
        )
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_cross_chunk_resolver_2tuple_with_non_int_page_index_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Same lines, hit via wrong second element (page_index slot)."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    link.set_destination(_fit(src_pages[1]))
    src_pages[0].set_annotations([link])

    sp = Splitter().set_cross_chunk_destination_resolver(
        lambda _dict: ("foo.pdf", "not-an-int")
    )
    caplog.set_level(logging.WARNING, logger="pypdfbox.multipdf.splitter")
    chunks = sp.split(src)
    try:
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        dest = imported_link.get_destination()
        assert dest.get_cos_object().get(0) is COSNull.NULL
        assert any(
            "non-(str,int) tuple" in rec.message for rec in caplog.records
        )
    finally:
        for c in chunks:
            c.close()
        src.close()


# ---------- line 1252: orphan destination without a link record ----------


def test_apply_cross_chunk_destination_returns_true_for_orphan_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``_dest_to_link_map`` has no entry for ``cloned_array`` (e.g.
    a destination promoted from ``/Dests`` rather than from a link
    annotation), the resolver-rewrite path still applies the page-index
    swap and returns ``True`` (line 1252)."""
    # Build the splitter directly and exercise the helper in isolation —
    # all the bookkeeping fields it consults are simple containers.
    sp = Splitter()
    sp.set_cross_chunk_destination_resolver(
        lambda _dict: ("orphan.pdf", 7)
    )
    sp._dest_to_link_map = {}  # noqa: SLF001
    cloned = COSArray()
    cloned.add(COSInteger.get(0))   # slot 0 — will be overwritten
    cloned.add(COSInteger.get(0))   # filler
    # The source target page dict is opaque to the helper; an empty one
    # works because the resolver doesn't read it.
    from pypdfbox.cos import COSDictionary

    src_page = COSDictionary()
    rewritten = sp._rewrite_cross_chunk_destination(  # noqa: SLF001
        cloned, src_page
    )
    assert rewritten is True
    # The integer-index swap still ran even though no link record was
    # available — slot 0 holds the resolver's page_index.
    slot = cloned.get(0)
    assert isinstance(slot, COSInteger)
    assert slot.value == 7
