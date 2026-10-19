"""Hand-written tests for the ``-hinting`` CLI option (PDFBOX-3293) on
``PDFToImage`` and ``PrintPDF``, plus ``PrintPDF -subsampling`` (forward-
ported from the same 3.0.9 change set)."""

import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from PIL import Image

from pypdfbox.tools import pdf_to_image
from pypdfbox.tools.print_pdf import PrintPDF

_ROT0 = Path(__file__).resolve().parents[1] / "fixtures" / "multipdf" / "rot0.pdf"


class _SpyRenderer:
    instances: list[_SpyRenderer] = []

    def __init__(self, document: Any) -> None:
        self.hinting: bool | None = None
        self.subsampling: bool | None = None
        _SpyRenderer.instances.append(self)

    def set_subsampling_allowed(self, allowed: bool) -> None:
        self.subsampling = allowed

    def set_hinting_enabled(self, enabled: bool) -> None:
        self.hinting = enabled

    def render_image_with_dpi(self, page_index: int, dpi: int, image_type: Any) -> Image.Image:
        return Image.new("RGB", (4, 4), "white")


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> type[_SpyRenderer]:
    _SpyRenderer.instances = []
    monkeypatch.setattr(pdf_to_image, "PDFRenderer", _SpyRenderer)
    return _SpyRenderer


@pytest.mark.parametrize(("flag", "expected"), [([], False), (["-hinting"], True)])
def test_pdf_to_image_hinting_option(
    spy: type[_SpyRenderer], tmp_path: Path, flag: list[str], expected: bool
) -> None:
    rc = pdf_to_image.PDFToImage.main(
        ["-i", str(_ROT0), "-prefix", str(tmp_path / "out"), "-format", "png", *flag]
    )
    assert rc == 0
    assert spy.instances[0].hinting is expected
    assert spy.instances[0].subsampling is False


def test_pdf_to_image_default_attribute() -> None:
    assert pdf_to_image.PDFToImage().hinting is False


def test_pdf_to_image_renderer_without_hinting_setter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _Legacy:
        def __init__(self, document: Any) -> None:
            pass

        def render_image_with_dpi(self, page_index: int, dpi: int, image_type: Any) -> Image.Image:
            return Image.new("RGB", (4, 4), "white")

    monkeypatch.setattr(pdf_to_image, "PDFRenderer", _Legacy)
    rc = pdf_to_image.PDFToImage.main(
        ["-i", str(_ROT0), "-prefix", str(tmp_path / "x"), "-format", "png", "-hinting"]
    )
    assert rc == 0


@pytest.mark.parametrize(
    ("args", "hinting", "subsampling"),
    [
        ([], False, False),
        (["-hinting"], True, False),
        (["-subsampling"], False, True),
        (["-hinting", "-subsampling"], True, True),
    ],
)
def test_print_pdf_option_parsing(args: list[str], hinting: bool, subsampling: bool) -> None:
    seen: dict[str, PrintPDF] = {}

    def _call(self: PrintPDF) -> int:
        seen["runner"] = self
        return 0

    with mock.patch.object(PrintPDF, "call", _call):
        assert PrintPDF.main(["-i", str(_ROT0), *args]) == 0
    assert seen["runner"].hinting is hinting
    assert seen["runner"].subsampling is subsampling


def test_print_pdf_defaults() -> None:
    runner = PrintPDF()
    assert runner.hinting is False
    assert runner.subsampling is False


def test_print_pdf_hinting_does_not_change_spool_command() -> None:
    """The OS-spooler port does not rasterize, so the flag is recorded only."""
    commands = []
    for hinting in (False, True):
        runner = PrintPDF()
        runner.infile = _ROT0
        runner.silent_print = True
        runner.hinting = hinting
        with (
            mock.patch.object(sys, "platform", "linux"),
            mock.patch("pypdfbox.tools.print_pdf.shutil.which", return_value="/usr/bin/lpr"),
            mock.patch("pypdfbox.tools.print_pdf.subprocess.run") as run_mock,
        ):
            run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0)
            assert runner.call() == 0
        commands.append(run_mock.call_args.args[0])
    assert commands[0] == commands[1]
