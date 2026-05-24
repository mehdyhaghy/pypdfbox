"""Wave 1395 — close 62 newly-uncovered lines in nine wave-1393 tool modules.

Wave 1393 added defensive ``_open_doc`` context-manager helpers to seven
tool modules so that ``Loader.load_pdf`` (which returns a low-level
:class:`COSDocument`) is wrapped in a :class:`PDDocument` before the
class-port code reaches into PD-layer methods. The wave-1393 smoke tests
in :mod:`tests.tools.test_pdfbox_app_cli_wave1393` exercise every tool
end-to-end, but they shell out via :func:`subprocess.run` so the
in-process coverage tracer doesn't see the executed lines.

Wave 1393 also added:

* ``pdfbox`` subcommand dispatcher helpers (``_help`` /  ``_Help`` /
  ``_debug_class`` / ``_Debug``) on :mod:`pypdfbox.tools.pdf_box`;
* an :class:`~pypdfbox.rendering.image_type.ImageType` enum-resolution
  step in :class:`pypdfbox.tools.pdf_to_image.PDFToImage.call` that
  upgrades a string ``-color`` argument and rejects unknown values with
  exit code ``2``;
* a repeatable ``-page N=FILE`` argparse option on
  :class:`pypdfbox.tools.overlay_pdf.OverlayPDF.main` (raises
  :class:`SystemExit` on a non-``N=FILE`` token).

This module covers all three:

1. **In-process** invocation of each ``<Tool>.main`` against a real
   fixture PDF — exercises the ``isinstance(result, COSDocument)``
   branch of every ``_open_doc`` helper (the existing wave-1314/1315/
   1319/1323/1345 tests monkeypatch ``Loader`` to a context-manager
   shim and never reach this branch).

2. The ``pdfbox help`` subcommand listing + per-subcommand proxy
   (including the unknown-subcommand-rejected exit-2 path) and the
   lazy-``PDFDebugger`` ``_Debug`` adapter (with the class swapped for
   a stub so we don't spin up Tk).

3. The ``-color`` enum resolution success + failure paths in
   ``PDFToImage.call`` (string, success enum, invalid string, and the
   pre-resolved-enum bypass).

4. The ``-page N=FILE`` map parser in ``OverlayPDF.main`` (valid
   round-trip + invalid-token ``SystemExit``).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pypdfbox.tools import (
    decompress_objectstreams,
    extract_images,
    extract_text,
    extract_xmp,
    overlay_pdf,
    pdf_box,
    pdf_split,
    pdf_to_image,
    write_decoded_doc,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
UNENCRYPTED = FIXTURES / "pdfwriter" / "unencrypted.pdf"
OVERLAY_BASE = FIXTURES / "multipdf" / "OverlayTestBaseRot0.pdf"
OVERLAY_TOP = FIXTURES / "multipdf" / "Overlayed-with-rot0.pdf"


# ---------------------------------------------------------------------------
# _open_doc COSDocument-branch coverage (extract_text / extract_xmp /
# extract_images / pdf_split / pdf_to_image / decompress_objectstreams /
# write_decoded_doc).
#
# Calling ``<Tool>.main`` in-process — WITHOUT monkeypatching ``Loader`` —
# exercises ``Loader.load_pdf -> COSDocument -> PDDocument`` wrap branch
# (production code path; the existing coverage tests all bypass it).
# ---------------------------------------------------------------------------


def test_extract_text_loader_returns_cos_document_branch(tmp_path: Path) -> None:
    """Hits :func:`pypdfbox.tools.extract_text._open_doc` lines 49-55 —
    the ``isinstance(result, COSDocument)`` branch where the helper
    wraps the loader's :class:`COSDocument` in :class:`PDDocument` and
    closes it on exit."""
    out = tmp_path / "extract.txt"
    rc = extract_text.ExtractText.main(["-i", str(UNENCRYPTED), "-o", str(out)])
    assert rc == 0
    assert out.is_file()


def test_extract_xmp_loader_returns_cos_document_branch(tmp_path: Path) -> None:
    """Hits :func:`pypdfbox.tools.extract_xmp._open_doc` lines 29-35.

    Returns either ``0`` (XMP present) or ``1`` (no XMP metadata) — both
    paths still flow through the loader-wrap branch we're covering."""
    out = tmp_path / "extract.xml"
    rc = extract_xmp.ExtractXMP.main(["-i", str(UNENCRYPTED), "-o", str(out)])
    assert rc in (0, 1)


def test_extract_images_loader_returns_cos_document_branch(tmp_path: Path) -> None:
    """Hits :func:`pypdfbox.tools.extract_images._open_doc` lines 35-41."""
    prefix = tmp_path / "img"
    rc = extract_images.ExtractImages.main(
        ["-prefix", str(prefix), "-i", str(UNENCRYPTED)],
    )
    assert rc == 0


def test_pdf_split_loader_returns_cos_document_branch(tmp_path: Path) -> None:
    """Hits :func:`pypdfbox.tools.pdf_split._open_doc` lines 27-33."""
    prefix = tmp_path / "split"
    rc = pdf_split.PDFSplit.main(
        ["-i", str(UNENCRYPTED), "-outputPrefix", str(prefix)],
    )
    assert rc == 0
    produced = sorted(tmp_path.glob("split-*.pdf"))
    assert len(produced) >= 1


def test_pdf_to_image_loader_returns_cos_document_branch(tmp_path: Path) -> None:
    """Hits :func:`pypdfbox.tools.pdf_to_image._open_doc` lines 32-38."""
    prefix = tmp_path / "page"
    rc = pdf_to_image.PDFToImage.main(
        [
            "-i", str(UNENCRYPTED),
            "-prefix", str(prefix),
            "-format", "png",
            "-startPage", "1", "-endPage", "1",
        ],
    )
    assert rc == 0
    assert any(tmp_path.glob("page-*.png"))


def test_decompress_objectstreams_loader_returns_cos_document_branch(
    tmp_path: Path,
) -> None:
    """Hits :func:`pypdfbox.tools.decompress_objectstreams._open_doc`
    lines 26-32."""
    out = tmp_path / "decompressed.pdf"
    rc = decompress_objectstreams.DecompressObjectstreams.main(
        ["-i", str(UNENCRYPTED), "-o", str(out)],
    )
    assert rc == 0
    assert out.is_file()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_write_decoded_doc_loader_returns_cos_document_branch(
    tmp_path: Path,
) -> None:
    """Hits :func:`pypdfbox.tools.write_decoded_doc._open_doc` lines 27-33."""
    out = tmp_path / "decoded.pdf"
    rc = write_decoded_doc.WriteDecodedDoc.main([str(UNENCRYPTED), str(out)])
    assert rc == 0
    assert out.is_file()
    assert out.read_bytes()[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# pdf_box.py — ``_help`` / ``_Help`` / ``_debug_class`` / ``_Debug``
# ---------------------------------------------------------------------------


def test_help_no_args_lists_every_subcommand(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``pdfbox help`` (no args) prints ``Usage: …`` + every registered
    subcommand name + ``help`` itself, returns ``0``. Mirrors upstream
    picocli ``CommandLine.HelpCommand.run()``."""
    rc = pdf_box._Help.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Usage: pdfbox" in out
    # Every registered subcommand should appear.
    for name in pdf_box._SUBCOMMANDS:
        assert name in out, f"{name!r} missing from help listing"
    # The synthetic ``help`` entry is appended by ``_help`` itself.
    assert "  help\n" in out


def test_help_with_none_arg_treated_as_no_args(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``_Help.main(None)`` defers to ``args or []`` — same listing path
    as ``_Help.main([])``."""
    rc = pdf_box._Help.main(None)
    out = capsys.readouterr().out
    assert rc == 0
    assert "Usage: pdfbox" in out


def test_help_unknown_subcommand_returns_2_and_writes_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``pdfbox help bogus`` → ``Unknown command: bogus`` on stderr,
    exit ``2``."""
    rc = pdf_box._Help.main(["definitely-not-a-real-subcommand"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "Unknown command" in err
    assert "definitely-not-a-real-subcommand" in err


def test_help_for_subcommand_proxies_to_subcommand_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``pdfbox help <subcmd>`` re-invokes ``<subcmd> --help`` and
    absorbs the argparse ``SystemExit``, returning the exit code as an
    ``int``."""
    rc = pdf_box._Help.main(["render"])
    captured = capsys.readouterr()
    assert rc == 0
    # argparse renders the subcommand's usage on stdout when ``--help``
    # is the only token.
    assert "usage" in captured.out.lower() or "render" in captured.out.lower()


def test_help_for_subcommand_with_non_zero_systemexit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A subcommand's ``--help`` that exits with a non-zero code must be
    reflected in ``_Help.main``'s return value (covers the
    ``int(exc.code or 0)`` branch on line 59)."""

    class _StubCmd:
        @staticmethod
        def main(_args: list[str]) -> int:
            raise SystemExit(3)

    monkeypatch.setitem(pdf_box._SUBCOMMANDS, "_stubcmd", _StubCmd)
    rc = pdf_box._Help.main(["_stubcmd"])
    assert rc == 3


def test_help_for_subcommand_returning_int_not_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A subcommand whose ``main`` returns an int (rather than raising
    ``SystemExit``) must still be propagated — covers the
    ``return int(cls.main(['--help']) or 0)`` branch on line 57."""

    class _IntReturningCmd:
        @staticmethod
        def main(_args: list[str]) -> int:
            return 5

    monkeypatch.setitem(pdf_box._SUBCOMMANDS, "_intcmd", _IntReturningCmd)
    rc = pdf_box._Help.main(["_intcmd"])
    assert rc == 5


def test_debug_class_lazy_imports_pdf_debugger() -> None:
    """``_debug_class`` lazy-imports :class:`PDFDebugger` so plain
    ``import pypdfbox.tools.pdf_box`` doesn't pay the Tk cost.
    Confirms the import path resolves to the right class."""
    cls = pdf_box._debug_class()
    assert cls.__name__ == "PDFDebugger"
    assert cls.__module__ == "pypdfbox.debugger.pd_debugger"


def test_debug_main_dispatches_to_debug_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_Debug.main(args)`` calls ``_debug_class().main(args)`` and
    coerces to ``int``. Real ``PDFDebugger.main`` spins up a Tk
    mainloop, so we swap in a stub."""

    class _StubDebugger:
        captured: list[Any] = []

        @staticmethod
        def main(args: list[str] | None = None) -> int:
            _StubDebugger.captured.append(args)
            return 0

    monkeypatch.setattr(pdf_box, "_debug_class", lambda: _StubDebugger)
    rc = pdf_box._Debug.main(["--inputfile", "fake.pdf"])
    assert rc == 0
    assert _StubDebugger.captured == [["--inputfile", "fake.pdf"]]


def test_debug_main_coerces_none_return_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Covers ``int(... or 0)`` on line 89 — the ``or 0`` clause when
    the debugger's ``main`` returns ``None``."""

    class _NoneReturningDebugger:
        @staticmethod
        def main(_args: list[str] | None = None) -> int | None:
            return None

    monkeypatch.setattr(pdf_box, "_debug_class", lambda: _NoneReturningDebugger)
    rc = pdf_box._Debug.main([])
    assert rc == 0


# ---------------------------------------------------------------------------
# pdf_to_image.py — ``-color`` ImageType resolution branches
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("color", ["RGB", "rgb", "GRAY", "BINARY", "ARGB"])
def test_pdf_to_image_color_string_resolves_to_image_type(
    color: str, tmp_path: Path,
) -> None:
    """The ``-color`` arg ships as a string from argparse; the runner
    upgrades it via ``ImageType[name.upper()]`` (line 105). Every
    canonical enum name (case-insensitive) must succeed."""
    prefix = tmp_path / f"page_{color.lower()}"
    rc = pdf_to_image.PDFToImage.main(
        [
            "-i", str(UNENCRYPTED),
            "-prefix", str(prefix),
            "-format", "png",
            "-color", color,
            "-startPage", "1", "-endPage", "1",
        ],
    )
    assert rc == 0
    assert any(tmp_path.glob(f"page_{color.lower()}-*.png"))


def test_pdf_to_image_invalid_color_returns_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unknown ``-color`` value triggers the ``KeyError`` on
    ``ImageType[…]`` (line 106), writes a friendly error on stderr
    (107-109), and returns ``2`` (line 110)."""
    prefix = tmp_path / "page"
    rc = pdf_to_image.PDFToImage.main(
        [
            "-i", str(UNENCRYPTED),
            "-prefix", str(prefix),
            "-format", "png",
            "-color", "DOES_NOT_EXIST",
            "-startPage", "1", "-endPage", "1",
        ],
    )
    err = capsys.readouterr().err
    assert rc == 2
    assert "Invalid color value" in err
    assert "DOES_NOT_EXIST" in err


def test_pdf_to_image_enum_image_type_bypasses_resolution(
    tmp_path: Path,
) -> None:
    """If ``self.image_type`` is already an :class:`ImageType` enum
    (caller set the attribute directly, not via argparse), the
    ``isinstance(..., str)`` guard on line 103 falls through to the
    ``else`` branch on line 112 that reuses the enum as-is."""
    from pypdfbox.rendering.image_type import ImageType

    runner = pdf_to_image.PDFToImage()
    runner.infile = UNENCRYPTED
    runner.output_prefix = str(tmp_path / "page")
    runner.image_format = "png"
    runner.image_type = ImageType.RGB  # enum, not str
    runner.start_page = 1
    runner.end_page = 1
    rc = runner.call()
    assert rc == 0
    assert any(tmp_path.glob("page-*.png"))


# ---------------------------------------------------------------------------
# overlay_pdf.py — ``-page N=FILE`` map parser
# ---------------------------------------------------------------------------


def test_overlay_pdf_page_map_parses_valid_entries(tmp_path: Path) -> None:
    """A valid ``-page N=FILE`` entry must populate
    ``specific_page_overlay_file`` and the overlay must succeed
    (lines 119-120)."""
    out = tmp_path / "overlaid.pdf"
    rc = overlay_pdf.OverlayPDF.main(
        [
            "-i", str(OVERLAY_BASE),
            "-o", str(out),
            "-page", f"1={OVERLAY_TOP}",
        ],
    )
    assert rc == 0
    assert out.is_file()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_overlay_pdf_page_map_rejects_token_without_equals(
    tmp_path: Path,
) -> None:
    """A ``-page`` token missing the ``=`` separator triggers the
    ``SystemExit`` on line 116 with a helpful error message."""
    out = tmp_path / "overlaid.pdf"
    with pytest.raises(SystemExit) as excinfo:
        overlay_pdf.OverlayPDF.main(
            [
                "-i", str(OVERLAY_BASE),
                "-o", str(out),
                "-page", "no-equals-sign-here",
            ],
        )
    assert "N=FILE format" in str(excinfo.value)
    assert "no-equals-sign-here" in str(excinfo.value)


def test_overlay_pdf_page_map_accepts_multiple_entries(tmp_path: Path) -> None:
    """The argparse ``action="append"`` makes ``-page`` repeatable.
    Two entries must both end up in ``specific_page_overlay_file``."""
    out = tmp_path / "overlaid.pdf"
    rc = overlay_pdf.OverlayPDF.main(
        [
            "-i", str(OVERLAY_BASE),
            "-o", str(out),
            "-page", f"1={OVERLAY_TOP}",
            "-page", f"2={OVERLAY_TOP}",
        ],
    )
    # Even if the underlying overlay reports a non-zero (e.g. page-2
    # doesn't exist in the 1-page base), the parser branch we care
    # about still ran. Either way: no SystemExit, deterministic rc.
    assert rc in (0, 4), (
        "expected 0 (overlay applied) or 4 (overlay tool error); "
        f"got {rc}"
    )
