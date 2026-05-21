"""Wave 1365 — coverage round-out for :class:`PDFMergerExample`.

The base smoke test only exercises ``merge`` end-to-end. This module
covers the helper methods (``create_pdf_merger_utility``,
``create_pdf_document_info``, ``create_xmp_metadata``) and the
``ImportError`` / ``AttributeError`` defensive branches in
:meth:`create_xmp_metadata` plus the ``xmp_metadata is None`` branch
through :meth:`merge`.
"""

from __future__ import annotations

import builtins
import io
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.examples.util.pdf_merger_example import PDFMergerExample
from pypdfbox.io.random_access_read_buffered_file import (
    RandomAccessReadBufferedFile,
)
from pypdfbox.multipdf.pdf_merger_utility import PDFMergerUtility
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation


def test_constructor_is_a_no_op() -> None:
    """Cover the trivial ``__init__`` body (line 35)."""
    instance = PDFMergerExample()
    assert isinstance(instance, PDFMergerExample)


def test_create_pdf_document_info_populates_fields() -> None:
    """:meth:`create_pdf_document_info` returns a populated
    ``PDDocumentInformation`` (lines 81-91)."""
    info = PDFMergerExample().create_pdf_document_info(
        "T", "C", "S",
    )
    assert isinstance(info, PDDocumentInformation)
    assert info.get_title() == "T"
    assert info.get_creator() == "C"
    assert info.get_subject() == "S"


def test_create_pdf_merger_utility_wires_sources_and_destination(
    make_pdf: Callable[..., Path],
) -> None:
    """:meth:`create_pdf_merger_utility` builds a real merger with the
    given destination stream and source list (lines 67-79)."""
    a = make_pdf("merger-a.pdf")
    b = make_pdf("merger-b.pdf")
    sources = [
        RandomAccessReadBufferedFile(str(a)),
        RandomAccessReadBufferedFile(str(b)),
    ]
    out = io.BytesIO()
    merger = PDFMergerExample().create_pdf_merger_utility(sources, out)
    assert isinstance(merger, PDFMergerUtility)
    # The merger should have remembered the destination stream — invoke
    # merge_documents() and check the bytes land in ``out``.
    merger.merge_documents()
    assert out.getbuffer().nbytes > 0
    assert out.getvalue().startswith(b"%PDF")


def test_create_xmp_metadata_returns_none_on_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force the ``ImportError`` defensive branch (lines 101-109).

    Wave 1365: poison the ``XmpSerializer`` import path so the inner
    ``try`` raises ``ImportError`` and the helper returns ``None``.
    """
    real_import = builtins.__import__

    def _fake_import(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "pypdfbox.xmpbox.xml.xmp_serializer":
            raise ImportError("simulated missing xmpbox")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    # Also clear any cached module so the import re-runs.
    monkeypatch.setitem(sys.modules, "pypdfbox.xmpbox.xml.xmp_serializer", None)
    result = PDFMergerExample().create_xmp_metadata("T", "C", "S")
    assert result is None


def test_create_xmp_metadata_returns_none_on_attribute_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force the inner ``AttributeError`` branch (lines 128-129).

    Replace ``XMPMetadata.create_xmp_metadata`` with a callable whose
    return value lacks the expected schema helpers — the example then
    raises ``AttributeError`` and falls back to ``None``.
    """
    try:
        from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
    except ImportError:
        pytest.skip("xmpbox not available")

    class _Stub:
        # Intentionally missing every ``create_and_add_*`` method.
        pass

    monkeypatch.setattr(
        XMPMetadata, "create_xmp_metadata", staticmethod(lambda: _Stub()),
    )
    result = PDFMergerExample().create_xmp_metadata("T", "C", "S")
    assert result is None


def test_merge_skips_destination_metadata_when_xmp_is_none(
    monkeypatch: pytest.MonkeyPatch,
    make_pdf: Callable[..., Path],
) -> None:
    """When ``create_xmp_metadata`` returns ``None``, ``merge`` must
    still complete (line 54 — ``if xmp_metadata is not None`` is
    skipped)."""
    monkeypatch.setattr(
        PDFMergerExample, "create_xmp_metadata",
        lambda self, t, c, s: None,
    )
    a = make_pdf("skip-a.pdf")
    b = make_pdf("skip-b.pdf")
    sources = [
        RandomAccessReadBufferedFile(str(a)),
        RandomAccessReadBufferedFile(str(b)),
    ]
    merged = PDFMergerExample().merge(sources)
    assert merged.getvalue().startswith(b"%PDF")


def test_merge_handles_destination_setters_missing(
    monkeypatch: pytest.MonkeyPatch,
    make_pdf: Callable[..., Path],
) -> None:
    """Cover the ``contextlib.suppress(AttributeError)`` guards (lines
    52-56) — if the merger lacks the destination-info setters, ``merge``
    must still succeed."""

    class _ShimMerger:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            self._inner = PDFMergerUtility()

        # Forbid both setters so ``AttributeError`` fires inside the
        # ``contextlib.suppress`` blocks.
        def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
            if name in {
                "set_destination_document_information",
                "set_destination_metadata",
            }:
                raise AttributeError(name)
            return getattr(self._inner, name)

    def _factory(self, sources, out_stream):  # type: ignore[no-untyped-def]
        shim = _ShimMerger()
        for src in sources:
            shim._inner.add_source(src)
        shim._inner.set_destination_stream(out_stream)
        return shim

    monkeypatch.setattr(
        PDFMergerExample, "create_pdf_merger_utility", _factory,
    )
    a = make_pdf("shim-a.pdf")
    b = make_pdf("shim-b.pdf")
    sources = [
        RandomAccessReadBufferedFile(str(a)),
        RandomAccessReadBufferedFile(str(b)),
    ]
    merged = PDFMergerExample().merge(sources)
    assert merged.getvalue().startswith(b"%PDF")


def test_merge_returns_stream_positioned_at_zero(
    make_pdf: Callable[..., Path],
) -> None:
    """The returned BytesIO must be rewound so callers can ``read()``
    from byte zero (line 64)."""
    a = make_pdf("rewind-a.pdf")
    b = make_pdf("rewind-b.pdf")
    sources = [
        RandomAccessReadBufferedFile(str(a)),
        RandomAccessReadBufferedFile(str(b)),
    ]
    merged = PDFMergerExample().merge(sources)
    assert merged.tell() == 0
    head = merged.read(4)
    assert head == b"%PDF"
