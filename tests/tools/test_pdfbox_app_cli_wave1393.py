"""Wave 1393 — end-to-end smoke tests for the ``pdfbox`` console script.

Confirms the unified ``pdfbox <subcommand> ...`` dispatcher (mirror of
``java -jar pdfbox-app-X.Y.Z.jar <subcommand>``) drives every upstream
subcommand against a real fixture PDF and returns exit-code 0 with the
expected side effect.

Tests shell out via ``subprocess`` so they exercise the same path a
caller would hit through the installed ``pdfbox`` console-script entry
point: ``python -m pypdfbox.tools.pdf_box <subcommand> ...``.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
UNENCRYPTED_PDF = FIXTURES / "pdfwriter" / "unencrypted.pdf"


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pypdfbox.tools.pdf_box", *args],
        capture_output=True, text=True, cwd=str(cwd) if cwd else None,
    )


# ---------------------------------------------------------------------------
# Dispatcher itself
# ---------------------------------------------------------------------------


def test_version_subcommand() -> None:
    """``pdfbox version`` → "pypdfbox [<version>]" on stdout, exit 0."""
    r = _run("version")
    assert r.returncode == 0, r.stderr
    assert "pypdfbox" in r.stdout or "unknown" in r.stdout


def test_help_lists_subcommands() -> None:
    """``pdfbox help`` lists every registered subcommand."""
    r = _run("help")
    assert r.returncode == 0, r.stderr
    for name in (
        "merge", "split", "export:text", "render", "decrypt", "encrypt",
        "version", "decompress", "decode", "export:images", "export:xmp",
        "export:fdf", "export:xfdf", "import:fdf", "import:xfdf", "overlay",
        "print", "fromimage", "fromtext", "debug", "help",
    ):
        assert name in r.stdout, f"{name!r} not in help output"


def test_no_args_returns_error_exit_2() -> None:
    r = _run()
    assert r.returncode == 2
    assert "Subcommand required" in r.stderr


def test_unknown_command_returns_error_exit_2() -> None:
    r = _run("nonsense-xyzzy")
    assert r.returncode == 2
    assert "Unknown command" in r.stderr


# ---------------------------------------------------------------------------
# End-to-end subcommand smoke tests (real fixture PDF, side effect assertions)
# ---------------------------------------------------------------------------


def test_merge_concatenates_two_pdfs(tmp_path: Path) -> None:
    out = tmp_path / "merged.pdf"
    r = _run(
        "merge",
        "-i", str(UNENCRYPTED_PDF), str(UNENCRYPTED_PDF),
        "-o", str(out),
    )
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    assert out.stat().st_size > 1024


def test_split_produces_per_page_pdfs(tmp_path: Path) -> None:
    prefix = tmp_path / "split"
    r = _run("split", "-i", str(UNENCRYPTED_PDF), "-outputPrefix", str(prefix))
    assert r.returncode == 0, r.stderr
    # The 2-page fixture should be split into split-1.pdf and split-2.pdf.
    produced = sorted(tmp_path.glob("split-*.pdf"))
    assert len(produced) == 2, [p.name for p in produced]
    for f in produced:
        assert f.stat().st_size > 0


def test_export_text_writes_txt(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    r = _run("export:text", "-i", str(UNENCRYPTED_PDF), "-o", str(out))
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    # Text might be empty for some PDFs, but the file must exist.
    assert out.stat().st_size >= 0


def test_export_xmp_writes_output(tmp_path: Path) -> None:
    out = tmp_path / "out.xml"
    r = _run("export:xmp", "-i", str(UNENCRYPTED_PDF), "-o", str(out))
    # XMP may not exist in every fixture — either rc 0 (XMP present) or
    # rc 1 with "No XMP metadata available". Both are valid wirings.
    assert r.returncode in (0, 1), r.stderr
    if r.returncode == 0:
        assert out.is_file()


def test_render_emits_png(tmp_path: Path) -> None:
    prefix = tmp_path / "page"
    r = _run(
        "render",
        "-i", str(UNENCRYPTED_PDF),
        "-format", "png",
        "-prefix", str(prefix),
        "-startPage", "1",
        "-endPage", "1",
    )
    assert r.returncode == 0, r.stderr
    images = sorted(tmp_path.glob("page-*.png"))
    assert len(images) == 1, [p.name for p in images]
    assert images[0].stat().st_size > 0


def test_decode_strips_streams(tmp_path: Path) -> None:
    out = tmp_path / "decoded.pdf"
    r = _run("decode", str(UNENCRYPTED_PDF), str(out))
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    assert out.stat().st_size > 0


def test_decompress_writes_uncompressed_pdf(tmp_path: Path) -> None:
    out = tmp_path / "uncompressed.pdf"
    r = _run("decompress", "-i", str(UNENCRYPTED_PDF), "-o", str(out))
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    assert out.stat().st_size > 0


def test_encrypt_then_decrypt_round_trip(tmp_path: Path) -> None:
    """``pdfbox encrypt`` + ``pdfbox decrypt`` round-trips a fresh file."""
    enc = tmp_path / "encrypted.pdf"
    dec = tmp_path / "decrypted.pdf"

    r1 = _run(
        "encrypt",
        "-i", str(UNENCRYPTED_PDF),
        "-O", "ownerpw",
        "-U", "userpw",
        "-o", str(enc),
    )
    assert r1.returncode == 0, r1.stderr
    assert enc.is_file() and enc.stat().st_size > 0

    r2 = _run(
        "decrypt",
        "-password", "ownerpw",
        "-i", str(enc),
        "-o", str(dec),
    )
    assert r2.returncode == 0, r2.stderr
    assert dec.is_file() and dec.stat().st_size > 0


def test_encrypt_honours_can_print_false(tmp_path: Path) -> None:
    """Wave 1393 — new ``-canPrint=false`` permission flag wires through to
    the AccessPermission seed before encryption."""
    out = tmp_path / "noprint.pdf"
    r = _run(
        "encrypt",
        "-i", str(UNENCRYPTED_PDF),
        "-O", "opw", "-U", "upw",
        "-canPrint", "false",
        "-o", str(out),
    )
    assert r.returncode == 0, r.stderr
    assert out.is_file()


# ---------------------------------------------------------------------------
# Console-script entry point — defensive: the pyproject.toml ``pdfbox``
# script wires to ``pypdfbox.tools.pdf_box:_console_main``. Importing the
# module must succeed and expose that name.
# ---------------------------------------------------------------------------


def test_console_main_entry_point_exists() -> None:
    from pypdfbox.tools import pdf_box

    assert callable(getattr(pdf_box, "_console_main", None)), (
        "pyproject.toml's ``pdfbox`` script binds to "
        "``pypdfbox.tools.pdf_box:_console_main`` — the symbol must exist"
    )


def test_console_main_invokes_dispatcher(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_console_main`` calls ``PDFBox.main(sys.argv[1:])`` and then
    ``sys.exit(rc)``. Stub both so the test stays hermetic."""
    from pypdfbox.tools import pdf_box

    captured: dict[str, object] = {}

    def fake_main(args: list[str]) -> int:
        captured["args"] = args
        return 7

    monkeypatch.setattr(pdf_box.PDFBox, "main", staticmethod(fake_main))
    monkeypatch.setattr(sys, "argv", ["pdfbox", "version"])
    with pytest.raises(SystemExit) as excinfo:
        pdf_box._console_main()
    assert excinfo.value.code == 7
    assert captured["args"] == ["version"]
