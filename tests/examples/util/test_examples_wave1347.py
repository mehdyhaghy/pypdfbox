"""Wave 1347 coverage-boost tests for two util examples.

Targets the residual uncovered branches in:

* ``pdf_merger_example`` — the xmpbox ImportError fallback and the
  AttributeError fallback when an XmpSerializer call fails part-way.
* ``remove_all_text`` — the PDStream ImportError fallback inside
  ``strip`` and the ContentStreamWriter ImportError fallback inside
  ``write_tokens_to_stream``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from pypdfbox.examples.util.pdf_merger_example import PDFMergerExample
from pypdfbox.examples.util.remove_all_text import RemoveAllText
from pypdfbox.io.random_access_read_buffered_file import RandomAccessReadBufferedFile
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage

# ---------------------------------------------------------------------------
# pdf_merger_example
# ---------------------------------------------------------------------------


def test_create_xmp_metadata_returns_none_when_xmpbox_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 108-109 — when xmpbox isn't importable the helper returns
    ``None`` instead of raising.

    We knock the ``xmpbox.xml.xmp_serializer`` module out of
    ``sys.modules`` *and* mark it un-importable so a fresh
    ``from ... import XmpSerializer`` triggers the ImportError branch.
    """
    monkeypatch.setitem(sys.modules, "pypdfbox.xmpbox.xml.xmp_serializer", None)
    monkeypatch.setitem(sys.modules, "pypdfbox.xmpbox.xmp_metadata", None)
    assert PDFMergerExample().create_xmp_metadata("t", "c", "s") is None


def test_create_xmp_metadata_swallows_attribute_error() -> None:
    """Lines 128-129 — if an xmp schema helper raises AttributeError mid
    construction the function falls back to ``None``.

    Approach: patch the xmpbox shim used inside ``create_xmp_metadata``
    so the first schema-add call surfaces an AttributeError. We can't
    rely on the real xmpbox surface here, so we install a fake module
    that raises and rely on the function's defensive ``except``."""

    class _FakeXMPMetadata:
        @staticmethod
        def create_xmp_metadata() -> Any:
            class _Inner:
                def create_and_add_pdfa_identification_schema(
                    self, *args: Any, **kwargs: Any
                ) -> None:
                    raise AttributeError("simulated missing helper")

            return _Inner()

    class _FakeSerializer:
        def serialize(self, *_args: Any, **_kwargs: Any) -> None:
            pass

    fake_xmp = type(sys)("pypdfbox.xmpbox.xmp_metadata")
    fake_xmp.XMPMetadata = _FakeXMPMetadata
    fake_ser = type(sys)("pypdfbox.xmpbox.xml.xmp_serializer")
    fake_ser.XmpSerializer = _FakeSerializer

    with patch.dict(
        sys.modules,
        {
            "pypdfbox.xmpbox.xmp_metadata": fake_xmp,
            "pypdfbox.xmpbox.xml.xmp_serializer": fake_ser,
        },
    ):
        assert PDFMergerExample().create_xmp_metadata("t", "c", "s") is None


def test_merge_still_succeeds_when_xmp_returns_none(tmp_path: Path) -> None:
    """Round-trip safety: when ``create_xmp_metadata`` returns ``None``
    the merger skips ``set_destination_metadata`` and still emits a
    well-formed PDF (lines 54 false branch + line 58 onwards)."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    for path in (a, b):
        doc = PDDocument()
        try:
            doc.add_page(PDPage())
            doc.save(str(path))
        finally:
            doc.close()
    sources = [
        RandomAccessReadBufferedFile(str(a)),
        RandomAccessReadBufferedFile(str(b)),
    ]
    # Force the xmp helper to return None to pin the no-metadata path.
    example = PDFMergerExample()
    with patch.object(example, "create_xmp_metadata", return_value=None):
        merged = example.merge(sources)
    merged.seek(0)
    assert merged.read(4) == b"%PDF"


# ---------------------------------------------------------------------------
# remove_all_text
# ---------------------------------------------------------------------------


def test_strip_falls_back_when_pd_stream_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 61-65 — when ``PDStream`` (or the writer plumbing it relies
    on) can't be imported, the per-page rewrite is skipped and ``strip``
    still saves the document."""
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(str(src))
    finally:
        doc.close()

    # Knock the PDStream import target out so the localized ``from ...
    # import PDStream`` raises ImportError and the ``except`` branch fires.
    monkeypatch.setitem(sys.modules, "pypdfbox.pdmodel.common.pd_stream", None)
    RemoveAllText.strip(str(src), str(dst))
    assert dst.exists() and dst.stat().st_size > 0


def test_write_tokens_to_stream_no_op_on_content_stream_writer_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 100-101 — when ``ContentStreamWriter`` isn't importable the
    helper silently returns; the caller never sees an exception."""
    monkeypatch.setitem(
        sys.modules, "pypdfbox.pdfwriter.content_stream_writer", None,
    )

    class FakeStream:
        def create_output_stream(self, *_args: Any) -> Any:
            raise RuntimeError("must not be called")

    # Returns None without invoking ``create_output_stream``.
    assert RemoveAllText.write_tokens_to_stream(FakeStream(), []) is None
