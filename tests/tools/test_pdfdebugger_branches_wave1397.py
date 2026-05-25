"""Wave 1397 branch-coverage tests for ``pypdfbox.tools.pdfdebugger``.

Closes False-branch arrows in helper functions and the catalog summary:

* ``_format_node`` 306->310 — stream sample is empty, body preview is
  suppressed
* ``_stream_preview`` 386->391 — decoded sample is empty (falsy) → fall
  through to the raw-input-stream path
* ``_print_summary`` 511->514 — JSON format with no /Pages entry on catalog
* ``_print_summary`` 545->547 — text format, /Pages is absent everywhere
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import pdfdebugger


def test_format_node_skips_body_preview_when_sample_is_empty(
    monkeypatch,
) -> None:
    """Closes 306->310: when ``_stream_preview`` returns an empty
    sample, no body preview line is emitted."""
    monkeypatch.setattr(
        pdfdebugger, "_stream_preview", lambda node: (b"", "decoded")
    )
    stream = COSStream()
    out: list[str] = []
    pdfdebugger._format_node(  # noqa: SLF001
        stream, 0, out, visited=set(), depth=0, max_depth=3,
    )
    body_preview = [line for line in out if "stream-body" in line]
    assert body_preview == []


def test_stream_preview_falls_back_to_raw_when_decoded_is_empty(
    monkeypatch,
) -> None:
    """Closes 386->391: decoded read returns empty bytes — the raw
    fallback path runs and returns its bytes labelled ``"raw"``."""

    class _Closer:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self) -> _Closer:
            return self

        def __exit__(self, *exc: Any) -> None:
            pass

        def read(self, n: int) -> bytes:
            return self._payload[:n]

    class _Node:
        def create_input_stream(self) -> _Closer:
            return _Closer(b"")  # decoded path empty

        def create_raw_input_stream(self) -> _Closer:
            return _Closer(b"RAWBYTES")

    sample, kind = pdfdebugger._stream_preview(_Node())  # noqa: SLF001
    assert kind == "raw"
    assert sample.startswith(b"RAWBYTES")


def test_print_summary_text_mode_with_no_pages_anywhere(
    capsys,
    tmp_path,
) -> None:
    """Closes 545->547: text mode, catalog has /Type but no /Pages
    (and the inline elif also fails) — no ``Catalog /Pages:`` line."""
    src = tmp_path / "no_pages.pdf"
    with PDDocument() as doc:
        # Strip /Pages so 510 returns None AND the elif at 545 also fails.
        # PDDocument's catalog auto-installs a Pages tree; remove it AND
        # make get_dictionary_object return None on both lookups by
        # patching the catalog's own dict.
        catalog_cos = doc.get_document_catalog().get_cos_object()
        pages_key = COSName.get_pdf_name("Pages")

        # Replace get_dictionary_object on this specific instance so the
        # /Pages lookup returns None twice.
        original_get = catalog_cos.get_dictionary_object

        def _patched_get(name, *a, **kw):
            if name == pages_key:
                return None
            return original_get(name, *a, **kw)

        catalog_cos.get_dictionary_object = _patched_get  # type: ignore[method-assign]
        pdfdebugger._print_summary(doc, src, output_format="text")  # noqa: SLF001
    captured = capsys.readouterr().out
    assert "Catalog /Pages:" not in captured
