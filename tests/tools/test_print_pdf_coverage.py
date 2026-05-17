"""Coverage-boost tests for ``pypdfbox.tools.print_pdf``.

Targets the branches not exercised by the primary test file:

* :meth:`Duplex.to_sides` for every enum value.
* :meth:`PrintPDF.create_print_request_attribute_set` — all four
  viewer-preferences duplex outcomes plus the unwired/missing-catalog
  fallback.
* :meth:`PrintPDF.to_possible_alternate_media` identity passthrough.
* :meth:`PrintPDF.show_available_printers` writes to stderr.
* :meth:`PrintPDF.get_trays_from_print_service` and
  :meth:`get_media_sizes_from_print_service` empty-list stubs.
* :meth:`PrintPDF.call` — permission-denied probe, Windows
  ``startfile`` OSError, ``TUMBLE`` duplex, ``media_size`` flag.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.tools.print_pdf import Duplex, PrintPDF


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "blank.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(path)
    finally:
        doc.close()
    return path


# ---------- Duplex.to_sides --------------------------------------------


def test_duplex_to_sides_simplex_returns_one_sided() -> None:
    assert Duplex.SIMPLEX.to_sides() == "ONE_SIDED"


def test_duplex_to_sides_duplex_returns_duplex() -> None:
    assert Duplex.DUPLEX.to_sides() == "DUPLEX"


def test_duplex_to_sides_tumble_returns_tumble() -> None:
    assert Duplex.TUMBLE.to_sides() == "TUMBLE"


def test_duplex_to_sides_document_returns_none() -> None:
    # ``Document`` defers to viewer preferences — represented as ``None``.
    assert Duplex.DOCUMENT.to_sides() is None


# ---------- create_print_request_attribute_set -------------------------


class _StubViewerPrefs:
    def __init__(self, duplex_value: str | None) -> None:
        self._duplex = duplex_value

    def get_duplex(self) -> str | None:
        return self._duplex


class _StubCatalog:
    def __init__(self, vp: _StubViewerPrefs | None) -> None:
        self._vp = vp

    def get_viewer_preferences(self) -> _StubViewerPrefs | None:
        return self._vp


class _StubDocument:
    def __init__(self, catalog: _StubCatalog) -> None:
        self._catalog = catalog

    def get_document_catalog(self) -> _StubCatalog:
        return self._catalog


def test_create_pras_with_explicit_duplex_sides() -> None:
    runner = PrintPDF()
    runner.duplex = Duplex.DUPLEX
    pras = runner.create_print_request_attribute_set(_StubDocument(_StubCatalog(None)))
    assert pras == {"Sides": "DUPLEX"}


def test_create_pras_with_document_duplex_flip_long_edge() -> None:
    runner = PrintPDF()
    runner.duplex = Duplex.DOCUMENT
    doc = _StubDocument(_StubCatalog(_StubViewerPrefs("DuplexFlipLongEdge")))
    pras = runner.create_print_request_attribute_set(doc)
    assert pras == {"Sides": "TWO_SIDED_LONG_EDGE"}


def test_create_pras_with_document_duplex_flip_short_edge() -> None:
    runner = PrintPDF()
    runner.duplex = Duplex.DOCUMENT
    doc = _StubDocument(_StubCatalog(_StubViewerPrefs("DuplexFlipShortEdge")))
    pras = runner.create_print_request_attribute_set(doc)
    assert pras == {"Sides": "TWO_SIDED_SHORT_EDGE"}


def test_create_pras_with_document_simplex() -> None:
    runner = PrintPDF()
    runner.duplex = Duplex.DOCUMENT
    doc = _StubDocument(_StubCatalog(_StubViewerPrefs("Simplex")))
    pras = runner.create_print_request_attribute_set(doc)
    assert pras == {"Sides": "ONE_SIDED"}


def test_create_pras_with_unknown_document_duplex_value() -> None:
    runner = PrintPDF()
    runner.duplex = Duplex.DOCUMENT
    doc = _StubDocument(_StubCatalog(_StubViewerPrefs("MysteryValue")))
    pras = runner.create_print_request_attribute_set(doc)
    # Unknown value yields no Sides entry.
    assert pras == {}


def test_create_pras_with_no_viewer_preferences() -> None:
    runner = PrintPDF()
    runner.duplex = Duplex.DOCUMENT
    doc = _StubDocument(_StubCatalog(None))
    pras = runner.create_print_request_attribute_set(doc)
    assert pras == {}


def test_create_pras_with_attributeerror_catalog() -> None:
    """A document whose ``get_document_catalog`` chain raises
    ``AttributeError`` falls through to an empty pras (covers the
    ``except AttributeError`` arm)."""

    class _BadDoc:
        def get_document_catalog(self):  # noqa: ANN201
            raise AttributeError("no catalog")

    runner = PrintPDF()
    runner.duplex = Duplex.DOCUMENT
    pras = runner.create_print_request_attribute_set(_BadDoc())
    assert pras == {}


def test_create_pras_with_viewer_prefs_returning_none_duplex() -> None:
    runner = PrintPDF()
    runner.duplex = Duplex.DOCUMENT
    doc = _StubDocument(_StubCatalog(_StubViewerPrefs(None)))
    pras = runner.create_print_request_attribute_set(doc)
    assert pras == {}


# ---------- misc helpers -------------------------------------------------


def test_to_possible_alternate_media_passthrough() -> None:
    runner = PrintPDF()
    sentinel = object()
    assert runner.to_possible_alternate_media(sentinel) is sentinel


def test_show_available_printers_writes_header_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    PrintPDF().show_available_printers()
    err = capsys.readouterr().err
    assert "Available printer names" in err


def test_get_trays_from_print_service_empty() -> None:
    assert PrintPDF.get_trays_from_print_service(None) == []


def test_get_media_sizes_from_print_service_empty() -> None:
    assert PrintPDF.get_media_sizes_from_print_service(None) == []


# ---------- call() additional branches ----------------------------------


def test_call_returns_4_when_permission_denied(sample_pdf: Path) -> None:
    """Loader probe reports ``can_print() is False`` — call returns 4
    without ever touching the spooler."""
    runner = PrintPDF()
    runner.infile = sample_pdf
    runner.silent_print = True

    fake_ap = mock.MagicMock()
    fake_ap.can_print.return_value = False
    fake_doc = mock.MagicMock()
    fake_doc.__enter__.return_value = fake_doc
    fake_doc.__exit__.return_value = False
    fake_doc.get_current_access_permission.return_value = fake_ap

    fake_loader = mock.MagicMock()
    fake_loader.load_pdf.return_value = fake_doc

    with (
        mock.patch.dict(sys.modules, {"pypdfbox.loader": mock.MagicMock(Loader=fake_loader)}),
        mock.patch("pypdfbox.tools.print_pdf.subprocess.run") as run_mock,
    ):
        rc = runner.call()

    assert rc == 4
    assert not run_mock.called


def test_call_proceeds_when_can_print_returns_true(sample_pdf: Path) -> None:
    """A document with permitted printing falls through to the spooler."""
    runner = PrintPDF()
    runner.infile = sample_pdf
    runner.silent_print = True

    fake_ap = mock.MagicMock()
    fake_ap.can_print.return_value = True
    fake_doc = mock.MagicMock()
    fake_doc.__enter__.return_value = fake_doc
    fake_doc.__exit__.return_value = False
    fake_doc.get_current_access_permission.return_value = fake_ap

    fake_loader = mock.MagicMock()
    fake_loader.load_pdf.return_value = fake_doc

    with (
        mock.patch.dict(sys.modules, {"pypdfbox.loader": mock.MagicMock(Loader=fake_loader)}),
        mock.patch.object(sys, "platform", "linux"),
        mock.patch(
            "pypdfbox.tools.print_pdf.shutil.which", return_value="/usr/bin/lpr"
        ),
        mock.patch("pypdfbox.tools.print_pdf.subprocess.run") as run_mock,
    ):
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        rc = runner.call()

    assert rc == 0
    assert run_mock.called


def test_call_windows_startfile_oserror_returns_4(sample_pdf: Path) -> None:
    runner = PrintPDF()
    runner.infile = sample_pdf
    runner.silent_print = True

    import os as os_module  # noqa: PLC0415

    fake_startfile = mock.MagicMock(side_effect=OSError("spooler unreachable"))
    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.object(os_module, "startfile", fake_startfile, create=True),
    ):
        rc = runner.call()
    assert rc == 4


def test_call_emits_tumble_sides(sample_pdf: Path) -> None:
    runner = PrintPDF()
    runner.infile = sample_pdf
    runner.silent_print = True
    runner.duplex = Duplex.TUMBLE

    with (
        mock.patch.object(sys, "platform", "linux"),
        mock.patch(
            "pypdfbox.tools.print_pdf.shutil.which", return_value="/usr/bin/lpr"
        ),
        mock.patch("pypdfbox.tools.print_pdf.subprocess.run") as run_mock,
    ):
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        rc = runner.call()

    assert rc == 0
    cmd = " ".join(run_mock.call_args.args[0])
    assert "sides=two-sided-short-edge" in cmd


def test_call_emits_simplex_sides(sample_pdf: Path) -> None:
    runner = PrintPDF()
    runner.infile = sample_pdf
    runner.silent_print = True
    runner.duplex = Duplex.SIMPLEX

    with (
        mock.patch.object(sys, "platform", "linux"),
        mock.patch(
            "pypdfbox.tools.print_pdf.shutil.which", return_value="/usr/bin/lpr"
        ),
        mock.patch("pypdfbox.tools.print_pdf.subprocess.run") as run_mock,
    ):
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        rc = runner.call()

    assert rc == 0
    cmd = " ".join(run_mock.call_args.args[0])
    assert "sides=one-sided" in cmd


def test_call_forwards_media_size(sample_pdf: Path) -> None:
    runner = PrintPDF()
    runner.infile = sample_pdf
    runner.silent_print = True
    runner.media_size = "A4"

    with (
        mock.patch.object(sys, "platform", "linux"),
        mock.patch(
            "pypdfbox.tools.print_pdf.shutil.which", return_value="/usr/bin/lpr"
        ),
        mock.patch("pypdfbox.tools.print_pdf.subprocess.run") as run_mock,
    ):
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        rc = runner.call()

    assert rc == 0
    cmd = " ".join(run_mock.call_args.args[0])
    assert "media=A4" in cmd


def test_call_handles_unknown_orientation_forwards_as_is(sample_pdf: Path) -> None:
    """An unmapped orientation string is forwarded verbatim — covers the
    ``mapping.get(..., self.orientation)`` fallback."""
    runner = PrintPDF()
    runner.infile = sample_pdf
    runner.silent_print = True
    runner.orientation = "DIAGONAL"

    with (
        mock.patch.object(sys, "platform", "linux"),
        mock.patch(
            "pypdfbox.tools.print_pdf.shutil.which", return_value="/usr/bin/lpr"
        ),
        mock.patch("pypdfbox.tools.print_pdf.subprocess.run") as run_mock,
    ):
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        rc = runner.call()

    assert rc == 0
    cmd = " ".join(run_mock.call_args.args[0])
    assert "orientation-requested=DIAGONAL" in cmd
