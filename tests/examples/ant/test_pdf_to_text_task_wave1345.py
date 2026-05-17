"""Wave 1345 — coverage round-out for :class:`PDFToTextTask`.

Targets the remaining uncovered ``_iter_fileset`` branches:

* the ``DirectoryScanner``-alike path (``get_included_files`` +
  ``get_basedir``) — lines 129-131;
* the single ``str | Path`` path — line 133;
* the ``TypeError`` fall-through — lines 136-137.

The first three pdf-bearing tests in
``test_pdf_to_text_task.py`` already exercise the iterable-of-paths
branch; only the alternate shapes need extra coverage here.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.ant.pdf_to_text_task import PDFToTextTask


class _DirectoryScannerLike:
    """Mirror of the Ant ``DirectoryScanner`` surface used by upstream
    ``addFileset`` — :class:`PDFToTextTask` only needs
    ``get_included_files`` and (optionally) ``get_basedir``.
    """

    def __init__(self, base: Path, names: list[str]) -> None:
        self._base = base
        self._names = names

    def get_basedir(self) -> str:
        return str(self._base)

    def get_included_files(self) -> list[str]:
        return list(self._names)


def test_iter_fileset_handles_directory_scanner_alike(tmp_path: Path) -> None:
    """Covers the ``hasattr(file_set, 'get_included_files')`` branch —
    lines 129-131."""
    scanner = _DirectoryScannerLike(tmp_path, ["a.pdf", "b.pdf"])
    result = PDFToTextTask._iter_fileset(scanner)
    assert result == [tmp_path / "a.pdf", tmp_path / "b.pdf"]


def test_iter_fileset_handles_scanner_without_basedir(tmp_path: Path) -> None:
    """The default-base lambda fires when ``get_basedir`` is missing —
    ensures the second half of line 130 is reachable too."""

    class _BarebonesScanner:
        def get_included_files(self) -> list[str]:
            return ["only.pdf"]

    result = PDFToTextTask._iter_fileset(_BarebonesScanner())
    # Defaults to ``Path(".")``.
    assert result == [Path(".") / "only.pdf"]


def test_iter_fileset_handles_single_str(tmp_path: Path) -> None:
    """A single string value is wrapped in a one-element list — line 133."""
    result = PDFToTextTask._iter_fileset(str(tmp_path / "single.pdf"))
    assert result == [tmp_path / "single.pdf"]


def test_iter_fileset_handles_single_path(tmp_path: Path) -> None:
    """A single :class:`pathlib.Path` value is wrapped likewise — line 133."""
    pdf = tmp_path / "lone.pdf"
    result = PDFToTextTask._iter_fileset(pdf)
    assert result == [pdf]


def test_iter_fileset_returns_empty_on_non_iterable() -> None:
    """A non-iterable, non-path value (e.g. an int) hits the ``TypeError``
    branch and returns ``[]`` — lines 134-137."""
    assert PDFToTextTask._iter_fileset(42) == []


def test_iter_fileset_returns_empty_on_arbitrary_object() -> None:
    """A bare ``object()`` also falls to the ``TypeError`` rescue."""
    assert PDFToTextTask._iter_fileset(object()) == []
