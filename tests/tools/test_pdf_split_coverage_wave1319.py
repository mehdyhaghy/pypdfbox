"""Coverage-boost tests for :mod:`pypdfbox.tools.pdf_split` (wave 1319).

Existing tests cover the happy path / construct / missing-infile branch.
This wave exercises the previously-uncovered:

* ``-split N`` per-N-page splitting + output-name template
  (``<prefix>-<n>.pdf``).
* ``-startPage`` / ``-endPage`` interplay with the default split count
  (number_of_pages / end_page).
* Default ``-outputPrefix`` derived from the input path when omitted.
* Per-document ``doc.close()`` in the ``finally`` cleanup branch.
* ``OSError`` mapping to exit code 4 (missing-input branch) with the
  expected stderr signal.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.loader import Loader as RealLoader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import pdf_split

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
MULTI = FIXTURES / "multipdf" / "PDFBOX-5811-362972.pdf"  # 4 pages
ROT0 = FIXTURES / "multipdf" / "rot0.pdf"


class _PDLoaderShim:
    @staticmethod
    @contextlib.contextmanager
    def load_pdf(source: Any, password: Any = None) -> Iterator[PDDocument]:
        if isinstance(password, str) and password == "":
            password = None
        cos_doc = RealLoader.load_pdf(source, password)
        pd = PDDocument(cos_doc)
        try:
            yield pd
        finally:
            pd.close()


@pytest.fixture
def patched_loader(monkeypatch: pytest.MonkeyPatch) -> type[_PDLoaderShim]:
    monkeypatch.setattr(pdf_split, "Loader", _PDLoaderShim)
    return _PDLoaderShim


# --------------------------------------------------------------------------
# -split N — per-N-page splitting + output-name template
# --------------------------------------------------------------------------
def test_split_n_pages_writes_named_chunks(
    patched_loader: Any, tmp_path: Path,
) -> None:
    prefix = tmp_path / "out"
    rc = pdf_split.PDFSplit.main([
        "-i", str(MULTI),
        "-outputPrefix", str(prefix),
        "-split", "2",
    ])
    assert rc == 0
    chunks = sorted(tmp_path.glob("out-*.pdf"))
    # 4-page input split by 2 → 2 chunks named -1.pdf / -2.pdf.
    assert [p.name for p in chunks] == ["out-1.pdf", "out-2.pdf"]
    for chunk in chunks:
        assert chunk.read_bytes()[:5] == b"%PDF-"


def test_split_single_page_default(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """No ``-split`` → default split-at-page=1 → one file per page."""
    prefix = tmp_path / "single"
    rc = pdf_split.PDFSplit.main([
        "-i", str(MULTI),
        "-outputPrefix", str(prefix),
    ])
    assert rc == 0
    chunks = sorted(tmp_path.glob("single-*.pdf"))
    assert len(chunks) == 4
    assert [p.name for p in chunks] == [
        "single-1.pdf",
        "single-2.pdf",
        "single-3.pdf",
        "single-4.pdf",
    ]


# --------------------------------------------------------------------------
# -startPage / -endPage branches (each sets ``start_end_page_set``)
# --------------------------------------------------------------------------
def test_start_page_only_splits_full_remainder(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """``-startPage`` without ``-split`` → splitter splits at the
    number-of-pages, producing a single chunk from start to end."""
    prefix = tmp_path / "sp"
    rc = pdf_split.PDFSplit.main([
        "-i", str(MULTI),
        "-outputPrefix", str(prefix),
        "-startPage", "2",
    ])
    assert rc == 0
    chunks = sorted(tmp_path.glob("sp-*.pdf"))
    assert chunks  # at least one chunk written
    for c in chunks:
        assert c.read_bytes()[:5] == b"%PDF-"


def test_end_page_only_splits_at_end_page(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """``-endPage`` without ``-split`` sets split_at_page=end_page."""
    prefix = tmp_path / "ep"
    rc = pdf_split.PDFSplit.main([
        "-i", str(MULTI),
        "-outputPrefix", str(prefix),
        "-endPage", "3",
    ])
    assert rc == 0
    chunks = sorted(tmp_path.glob("ep-*.pdf"))
    assert chunks


def test_explicit_split_wins_over_start_end(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """``-split`` always overrides the start/end implicit split count."""
    prefix = tmp_path / "win"
    rc = pdf_split.PDFSplit.main([
        "-i", str(MULTI),
        "-outputPrefix", str(prefix),
        "-startPage", "1",
        "-endPage", "4",
        "-split", "2",
    ])
    assert rc == 0
    chunks = sorted(tmp_path.glob("win-*.pdf"))
    assert len(chunks) == 2


# --------------------------------------------------------------------------
# Default output prefix (derived from infile when -outputPrefix omitted)
# --------------------------------------------------------------------------
def test_default_output_prefix_derived_from_infile(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """When ``-outputPrefix`` is omitted, the runner derives it from the
    input path's stem and writes alongside the input."""
    src = tmp_path / "input.pdf"
    src.write_bytes(MULTI.read_bytes())
    rc = pdf_split.PDFSplit.main([
        "-i", str(src),
        "-split", "4",  # one chunk for the whole 4-page document
    ])
    assert rc == 0
    # Derived prefix == tmp_path/"input" → emits input-1.pdf.
    out = tmp_path / "input-1.pdf"
    assert out.exists()


# --------------------------------------------------------------------------
# Error path — OSError → exit code 4 + stderr signal
# --------------------------------------------------------------------------
def test_missing_input_exits_4(
    patched_loader: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = pdf_split.PDFSplit.main([
        "-i", str(tmp_path / "absent.pdf"),
        "-outputPrefix", str(tmp_path / "x"),
    ])
    assert rc == 4
    err = capsys.readouterr().err
    assert "Error splitting document" in err


def test_call_missing_infile_raises_oserror() -> None:
    """The ``infile is required`` guard raises ``OSError`` directly (not
    routed through the OSError→4 mapping)."""
    runner = pdf_split.PDFSplit()
    with pytest.raises(OSError, match="infile is required"):
        runner.call()


# --------------------------------------------------------------------------
# Cleanup finally — documents are closed even on a normal exit.
# --------------------------------------------------------------------------
def test_documents_closed_on_normal_exit(
    patched_loader: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The runner's ``finally`` block closes every chunk doc returned
    by ``splitter.split()``. We monkey-patch ``Splitter.split`` to
    return a sentinel doc whose ``close`` is observable."""
    closed: list[bool] = []

    class _FakeChunkDoc:
        def save(self, _path: str) -> None:
            pass

        def close(self) -> None:
            closed.append(True)

    class _StubSplitter:
        def __init__(self) -> None:
            self.split_at: int | None = None

        def set_split_at_page(self, n: int) -> None:
            self.split_at = n

        def set_start_page(self, n: int) -> None:
            pass

        def set_end_page(self, n: int) -> None:
            pass

        def split(self, _doc: object) -> list[_FakeChunkDoc]:
            return [_FakeChunkDoc(), _FakeChunkDoc()]

    monkeypatch.setattr(pdf_split, "Splitter", _StubSplitter)

    prefix = tmp_path / "close"
    rc = pdf_split.PDFSplit.main([
        "-i", str(ROT0),
        "-outputPrefix", str(prefix),
        "-split", "1",
    ])
    assert rc == 0
    assert closed == [True, True]


# --------------------------------------------------------------------------
# Direct construct + per-attribute defaults (already touched by
# test_pdf_split_construct but we cover the negative split-at-page
# branch here for the ``-split == -1`` fallback that lands inside the
# function body).
# --------------------------------------------------------------------------
def test_direct_call_uses_default_prefix(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """Call ``call()`` directly without using ``main()`` — exercises the
    ``output_prefix is None`` branch in the same shape upstream uses."""
    src = tmp_path / "direct.pdf"
    src.write_bytes(ROT0.read_bytes())
    runner = pdf_split.PDFSplit()
    runner.infile = src
    # leave output_prefix=None and split=-1 → defaults to per-page.
    rc = runner.call()
    assert rc == 0
    out = tmp_path / "direct-1.pdf"
    assert out.exists()
