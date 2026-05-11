"""Tests for ``pypdfbox.tools.print_pdf.PrintPDF.call``.

Mocks ``subprocess.run`` / ``os.startfile`` / ``shutil.which`` so the
host's print spooler is never invoked.
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


def test_call_missing_input_returns_4() -> None:
    assert PrintPDF().call() == 4


def test_call_nonexistent_file_returns_4(tmp_path: Path) -> None:
    runner = PrintPDF()
    runner.infile = tmp_path / "missing.pdf"
    assert runner.call() == 4


def test_call_invokes_lpr_on_posix(sample_pdf: Path) -> None:
    runner = PrintPDF()
    runner.infile = sample_pdf
    runner.silent_print = True
    runner.printer_name = "MyPrinter"
    runner.orientation = "LANDSCAPE"
    runner.duplex = Duplex.DUPLEX
    runner.tray = "Tray1"

    with mock.patch.object(sys, "platform", "linux"), \
         mock.patch("pypdfbox.tools.print_pdf.shutil.which", return_value="/usr/bin/lpr"), \
         mock.patch("pypdfbox.tools.print_pdf.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        rc = runner.call()

    assert rc == 0
    assert run_mock.called
    cmd = run_mock.call_args.args[0]
    assert cmd[0] == "/usr/bin/lpr"
    assert "-P" in cmd
    assert "MyPrinter" in cmd
    assert "orientation-requested=4" in " ".join(cmd)
    assert "sides=two-sided-long-edge" in " ".join(cmd)
    assert cmd[-1] == str(sample_pdf)


def test_call_returns_4_when_lpr_missing(sample_pdf: Path) -> None:
    runner = PrintPDF()
    runner.infile = sample_pdf
    runner.silent_print = True
    with mock.patch.object(sys, "platform", "linux"), \
         mock.patch("pypdfbox.tools.print_pdf.shutil.which", return_value=None):
        rc = runner.call()
    assert rc == 4


def test_call_returns_4_when_lpr_fails(sample_pdf: Path) -> None:
    runner = PrintPDF()
    runner.infile = sample_pdf
    runner.silent_print = True
    with mock.patch.object(sys, "platform", "linux"), \
         mock.patch("pypdfbox.tools.print_pdf.shutil.which", return_value="/usr/bin/lpr"), \
         mock.patch(
             "pypdfbox.tools.print_pdf.subprocess.run",
             side_effect=subprocess.CalledProcessError(1, ["lpr"]),
         ):
        rc = runner.call()
    assert rc == 4


def test_call_uses_startfile_on_windows(sample_pdf: Path) -> None:
    runner = PrintPDF()
    runner.infile = sample_pdf
    runner.silent_print = True
    import os as os_module  # noqa: PLC0415

    fake_startfile = mock.MagicMock()
    # On non-Windows hosts ``os.startfile`` does not exist; patch it in
    # for the duration of the test.
    with mock.patch.object(sys, "platform", "win32"), \
         mock.patch.object(os_module, "startfile", fake_startfile, create=True):
        rc = runner.call()
    assert rc == 0
    fake_startfile.assert_called_once_with(str(sample_pdf), "print")


def test_call_non_silent_logs_warning(sample_pdf: Path, caplog) -> None:
    runner = PrintPDF()
    runner.infile = sample_pdf
    runner.silent_print = False
    with mock.patch.object(sys, "platform", "linux"), \
         mock.patch("pypdfbox.tools.print_pdf.shutil.which", return_value="/usr/bin/lpr"), \
         mock.patch("pypdfbox.tools.print_pdf.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        with caplog.at_level("WARNING", logger="pypdfbox.tools.print_pdf"):
            rc = runner.call()
    assert rc == 0
    assert any("non-silent" in rec.message for rec in caplog.records)


def test_main_round_trip(sample_pdf: Path) -> None:
    with mock.patch.object(sys, "platform", "linux"), \
         mock.patch("pypdfbox.tools.print_pdf.shutil.which", return_value="/usr/bin/lpr"), \
         mock.patch("pypdfbox.tools.print_pdf.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        rc = PrintPDF.main([
            "-silentPrint",
            "-duplex", "SIMPLEX",
            "-i", str(sample_pdf),
        ])
    assert rc == 0
    assert run_mock.called
