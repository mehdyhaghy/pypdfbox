"""Coverage-boost tests for ``pypdfbox.tools.decompress_objectstreams``
(wave 1316).

The tool is a tiny CLI wrapper: load a PDF via the project loader, then
save it with a no-compression policy so object streams aren't re-emitted.
Pre-wave, the module sat at 38% coverage — the ``call()`` body, error
mapping (``OSError`` → exit code 4), default-output handling, and the
``main`` argparse entry point were untested.

The ``Loader`` in this module returns a raw ``COSDocument``; saving
requires the PD-layer wrapper. The shim mirrors the
``_PDLoaderShim`` introduced in wave 1314 to bridge the two layers
during testing.
"""
from __future__ import annotations

import contextlib
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.loader import Loader as RealLoader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import decompress_objectstreams

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ROT0 = FIXTURES / "multipdf" / "rot0.pdf"
ROT90 = FIXTURES / "multipdf" / "rot90.pdf"


class _PDLoaderShim:
    """Bridge: ``Loader.load_pdf`` -> ``PDDocument`` context manager."""

    @staticmethod
    @contextlib.contextmanager
    def load_pdf(source: Any, password: Any = None) -> Iterator[PDDocument]:
        cos_doc = RealLoader.load_pdf(source, password)
        pd = PDDocument(cos_doc)
        try:
            yield pd
        finally:
            pd.close()


@pytest.fixture
def patched_loader(monkeypatch: pytest.MonkeyPatch) -> type[_PDLoaderShim]:
    monkeypatch.setattr(decompress_objectstreams, "Loader", _PDLoaderShim)
    return _PDLoaderShim


# --------------------------------------------------------------------------
# happy path
# --------------------------------------------------------------------------
def test_main_writes_output_pdf(patched_loader: Any, tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    rc = decompress_objectstreams.DecompressObjectstreams.main(
        ["-i", str(ROT90), "-o", str(out)],
    )
    assert rc == 0
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_main_works_against_rot0_fixture(patched_loader: Any, tmp_path: Path) -> None:
    """Sanity: a second fixture file confirms the tool isn't tied to a
    particular sample."""
    out = tmp_path / "rot0-decompressed.pdf"
    rc = decompress_objectstreams.DecompressObjectstreams.main(
        ["-i", str(ROT0), "-o", str(out)],
    )
    assert rc == 0
    assert out.read_bytes()[:5] == b"%PDF-"


# --------------------------------------------------------------------------
# error mapping
# --------------------------------------------------------------------------
def test_main_returns_4_when_input_missing(
    patched_loader: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = decompress_objectstreams.DecompressObjectstreams.main(
        ["-i", str(tmp_path / "nope.pdf"), "-o", str(tmp_path / "out.pdf")],
    )
    assert rc == 4
    err = capsys.readouterr().err
    assert "Error processing file" in err
    # The class-name prefix is the ``[FileNotFoundError]`` / ``[OSError]``
    # tag; either is fine — we just want the type information present.
    assert "[" in err and "]" in err


def test_main_propagates_oserror_from_save(
    patched_loader: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """If the inner ``doc.save`` raises ``OSError``, the runner catches it
    and returns 4 rather than bubbling the exception."""
    out = tmp_path / "out.pdf"

    def _raise_save(self: PDDocument, target: Any, *_a: Any, **_kw: Any) -> None:
        raise OSError("disk full simulation")

    monkeypatch.setattr(PDDocument, "save", _raise_save)
    rc = decompress_objectstreams.DecompressObjectstreams.main(
        ["-i", str(ROT0), "-o", str(out)],
    )
    assert rc == 4
    assert "disk full" in capsys.readouterr().err


# --------------------------------------------------------------------------
# direct ``call`` API
# --------------------------------------------------------------------------
def test_call_requires_infile() -> None:
    runner = decompress_objectstreams.DecompressObjectstreams()
    with pytest.raises(OSError, match="infile is required"):
        runner.call()


def test_call_with_explicit_outfile(patched_loader: Any, tmp_path: Path) -> None:
    runner = decompress_objectstreams.DecompressObjectstreams()
    runner.infile = ROT90
    runner.outfile = tmp_path / "explicit.pdf"
    assert runner.call() == 0
    assert runner.outfile.exists()


def test_call_defaults_outfile_branch_selects_input(
    patched_loader: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``outfile`` is None the runner selects ``infile`` as the save
    target (mirrors upstream's "overwrite input" behaviour). Capture the
    save target without actually writing — overwriting a still-open
    lazily-parsed PDF would corrupt the in-flight indirect-ref reads."""
    captured: dict[str, Any] = {}

    def _capture_save(
        self: PDDocument, target: Any, *args: Any, **kw: Any,
    ) -> None:
        captured["target"] = target

    monkeypatch.setattr(PDDocument, "save", _capture_save)
    src = tmp_path / "to-be-overwritten.pdf"
    shutil.copy(ROT90, src)
    runner = decompress_objectstreams.DecompressObjectstreams()
    runner.infile = src
    runner.outfile = None
    assert runner.call() == 0
    assert captured["target"] == src


# --------------------------------------------------------------------------
# initial state + flag defaults
# --------------------------------------------------------------------------
def test_default_attributes_are_unset() -> None:
    runner = decompress_objectstreams.DecompressObjectstreams()
    assert runner.usage_help_requested is False
    assert runner.infile is None
    assert runner.outfile is None


def test_main_parses_argv_into_attributes(
    patched_loader: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main`` builds a runner, wires ``-i`` / ``-o`` to its attributes,
    and returns its exit code. Patch ``call`` to capture the wired state
    without running the loader."""
    captured: dict[str, Any] = {}

    def _capture_call(self: decompress_objectstreams.DecompressObjectstreams) -> int:
        captured["infile"] = self.infile
        captured["outfile"] = self.outfile
        return 0

    monkeypatch.setattr(
        decompress_objectstreams.DecompressObjectstreams, "call", _capture_call,
    )
    out = tmp_path / "captured.pdf"
    rc = decompress_objectstreams.DecompressObjectstreams.main(
        ["-i", str(ROT0), "-o", str(out)],
    )
    assert rc == 0
    assert captured["infile"] == ROT0
    assert captured["outfile"] == out


def test_main_default_outfile_is_none_when_omitted(
    patched_loader: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_call(self: decompress_objectstreams.DecompressObjectstreams) -> int:
        captured["outfile"] = self.outfile
        return 0

    monkeypatch.setattr(
        decompress_objectstreams.DecompressObjectstreams, "call", _capture_call,
    )
    decompress_objectstreams.DecompressObjectstreams.main(["-i", str(ROT0)])
    assert captured["outfile"] is None
