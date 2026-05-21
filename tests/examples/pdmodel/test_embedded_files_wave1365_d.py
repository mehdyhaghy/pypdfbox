"""Wave 1365 — coverage round-out for :class:`EmbeddedFiles`.

Existing waves cover ``do_it`` end-to-end and the zero-arg usage gate.
This module deepens to:

* the ``__init__`` no-op body,
* the ``usage`` direct-call path (writes to stderr),
* the wrong-arg-count branch for 0 / 2 / 3 args,
* a structural assertion on the produced PDF (one page, ``/Names``
  carries ``/EmbeddedFiles``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.pdmodel.embedded_files import EmbeddedFiles
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.pd_document import PDDocument


def test_constructor_is_a_no_op() -> None:
    """Cover the no-op ``__init__`` body (line 17)."""
    instance = EmbeddedFiles()
    assert isinstance(instance, EmbeddedFiles)


def test_usage_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """Direct ``usage`` invocation must surface a non-empty stderr line
    (lines 101-102)."""
    EmbeddedFiles().usage()
    captured = capsys.readouterr()
    assert "EmbeddedFiles" in captured.err
    assert "<output-file>" in captured.err


def test_main_zero_args_invokes_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The ``len(argv) != 1`` branch (line 96) triggers ``usage()``."""
    EmbeddedFiles.main([])
    captured = capsys.readouterr()
    assert "EmbeddedFiles" in captured.err


def test_main_two_args_invokes_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Two args also fails the ``len(argv) != 1`` check."""
    EmbeddedFiles.main(["a.pdf", "b.pdf"])
    captured = capsys.readouterr()
    assert "EmbeddedFiles" in captured.err


def test_main_three_args_invokes_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Three args also fails the check."""
    EmbeddedFiles.main(["a.pdf", "b.pdf", "c.pdf"])
    captured = capsys.readouterr()
    assert "EmbeddedFiles" in captured.err


def test_main_none_argv_invokes_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``main(None)`` is normalised to ``[]``."""
    EmbeddedFiles.main(None)
    captured = capsys.readouterr()
    assert "EmbeddedFiles" in captured.err


def test_main_one_arg_writes_pdf(tmp_path: Path) -> None:
    """The 1-arg branch (line 99) drives ``do_it`` and writes a PDF."""
    out = tmp_path / "main-do-it.pdf"
    EmbeddedFiles.main([str(out)])
    assert out.exists()
    assert out.stat().st_size > 0


def test_produced_pdf_has_embedded_files_name_tree(tmp_path: Path) -> None:
    """The saved PDF's catalog ``/Names`` entry must carry an
    embedded-files tree (lines 81-84)."""
    out = tmp_path / "structure.pdf"
    EmbeddedFiles().do_it(str(out))
    with Loader.load_pdf(out) as cos_doc:
        doc = PDDocument(cos_doc)
        catalog = doc.get_document_catalog()
        names = catalog.get_names()
        assert names is not None
        # The name dictionary's embedded-files accessor must surface a
        # tree node (round-trip-safe regardless of port stage).
        ef = names.get_embedded_files() if hasattr(names, "get_embedded_files") else None
        assert ef is not None


def test_produced_pdf_has_one_page(tmp_path: Path) -> None:
    """``do_it`` adds exactly one page (line 44)."""
    out = tmp_path / "one-page.pdf"
    EmbeddedFiles().do_it(str(out))
    with Loader.load_pdf(out) as cos_doc:
        doc = PDDocument(cos_doc)
        assert doc.get_number_of_pages() == 1
