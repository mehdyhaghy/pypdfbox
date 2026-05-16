"""Coverage-boost tests for ``pypdfbox.tools.extract_text`` (wave 1318).

Pre-wave the module sat at 61%. Uncovered surface was:
  * ``ExtractText.call`` end-to-end (default outfile, html / md / plain
    branches, debug timing, encoding overrides, console branch,
    add-file-name prefix, permission-denied gating),
  * the ``NullWriter`` / ``AngleCollector`` / ``FilteredTextStripper`` /
    ``FilteredText2Markdown`` helpers,
  * ``get_angle`` for both rotated and degenerate text positions,
  * ``start_processing`` / ``stop_processing`` (debug timing prints),
  * ``create_output_writer`` (console + file branches),
  * ``main`` argparse glue.

Uses the ``_PDLoaderShim`` pattern introduced in wave 1314 to bridge the
raw ``COSDocument`` returned by ``Loader.load_pdf`` to a ``PDDocument``
context manager.
"""

from __future__ import annotations

import contextlib
import math
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.loader import Loader as RealLoader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import extract_text as et_module
from pypdfbox.tools.extract_text import (
    AngleCollector,
    ExtractText,
    FilteredText2Markdown,
    FilteredTextStripper,
    NullWriter,
    get_angle,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ROT0 = FIXTURES / "multipdf" / "rot0.pdf"


class _LiteStripperFactory:
    """Stand-in for ``PDFText2HTML`` / ``PDFText2Markdown`` whose
    ``write_text`` exercises a richer stripper surface than the lite
    plain-text path. We only care that ``call`` routes through the
    right branch — keep the body trivial."""

    def __init__(self) -> None:
        self._start = 1
        self._end = 1

    def set_sort_by_position(self, _v: bool) -> None: ...
    def set_should_separate_by_beads(self, _v: bool) -> None: ...

    def set_start_page(self, p: int) -> None:
        self._start = p

    def set_end_page(self, p: int) -> None:
        self._end = p

    def write_text(self, _doc: Any, output: Any) -> None:
        output.write(f"[stub html/md output start={self._start} end={self._end}]\n")


# ---------------------------------------------------------------------------
# loader shim (wave 1314 pattern)
# ---------------------------------------------------------------------------
class _PDLoaderShim:
    """Bridge ``Loader.load_pdf`` (returns COSDocument) into a PDDocument
    context manager so the ``with Loader.load_pdf(...) as doc`` block in
    ``ExtractText.call`` works."""

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
    monkeypatch.setattr(et_module, "Loader", _PDLoaderShim)
    return _PDLoaderShim


# ---------------------------------------------------------------------------
# get_angle / helper classes
# ---------------------------------------------------------------------------
class _Matrix:
    def __init__(self, shear_y: float, scale_y: float) -> None:
        self._shear_y = shear_y
        self._scale_y = scale_y

    def clone(self) -> _Matrix:
        return _Matrix(self._shear_y, self._scale_y)

    def concatenate(self, _other: object) -> None:
        return None

    def get_shear_y(self) -> float:
        return self._shear_y

    def get_scale_y(self) -> float:
        return self._scale_y


class _FontMatrix(_Matrix):
    pass


class _Font:
    def get_font_matrix(self) -> _FontMatrix:
        return _FontMatrix(0.0, 1.0)


class _TextPosition:
    def __init__(self, shear_y: float, scale_y: float) -> None:
        self._matrix = _Matrix(shear_y, scale_y)

    def get_text_matrix(self) -> _Matrix:
        return self._matrix

    def get_font(self) -> _Font:
        return _Font()


def test_get_angle_zero_for_flat_matrix() -> None:
    tp = _TextPosition(0.0, 1.0)
    assert get_angle(tp) == 0


def test_get_angle_handles_90_degree_rotation() -> None:
    tp = _TextPosition(math.sin(math.radians(90)), math.cos(math.radians(90)))
    assert get_angle(tp) == 90


def test_get_angle_returns_zero_on_attribute_error() -> None:
    class _NoMatrix:
        pass

    assert get_angle(_NoMatrix()) == 0


def test_get_angle_returns_zero_on_not_implemented() -> None:
    class _Broken:
        def get_text_matrix(self) -> _Matrix:
            raise NotImplementedError

    assert get_angle(_Broken()) == 0


def test_extract_text_static_get_angle_delegates() -> None:
    assert ExtractText.get_angle(_TextPosition(0.0, 1.0)) == 0


def test_null_writer_methods_do_not_raise() -> None:
    nw = NullWriter()
    nw.write("ignored")
    nw.write(b"ignored", 0, 3)
    nw.flush()
    nw.close()


def test_angle_collector_records_angles_modulo_360() -> None:
    collector = AngleCollector()
    collector.process_text_position(_TextPosition(0.0, 1.0))
    collector.process_text_position(
        _TextPosition(math.sin(math.radians(90)), math.cos(math.radians(90)))
    )
    angles = collector.get_angles()
    assert 0 in angles
    assert 90 in angles


def test_filtered_text_stripper_only_processes_zero_angle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stripper = FilteredTextStripper()
    seen: list[object] = []

    def _record(_self: object, tp: object) -> None:
        seen.append(tp)

    monkeypatch.setattr(
        "pypdfbox.text.pdf_text_stripper.PDFTextStripper.process_text_position",
        _record,
    )
    flat = _TextPosition(0.0, 1.0)
    rotated = _TextPosition(math.sin(math.radians(90)), math.cos(math.radians(90)))
    stripper.process_text_position(flat)
    stripper.process_text_position(rotated)
    assert seen == [flat]


def test_filtered_text2_markdown_only_processes_zero_angle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    md = FilteredText2Markdown()
    seen: list[object] = []

    def _record(_self: object, tp: object) -> None:
        seen.append(tp)

    monkeypatch.setattr(
        "pypdfbox.tools.pdf_text2_markdown.PDFText2Markdown.process_text_position",
        _record,
    )
    flat = _TextPosition(0.0, 1.0)
    rotated = _TextPosition(math.sin(math.radians(45)), math.cos(math.radians(45)))
    md.process_text_position(flat)
    md.process_text_position(rotated)
    assert seen == [flat]


# ---------------------------------------------------------------------------
# initial state + close()
# ---------------------------------------------------------------------------
def test_default_init_state() -> None:
    et = ExtractText()
    assert et.always_next is False
    assert et.to_console is False
    assert et.debug is False
    assert et.encoding == "UTF-8"
    assert et.end_page == 2**31 - 1
    assert et.to_html is False
    assert et.to_md is False
    assert et.ignore_beads is False
    assert et.password == ""
    assert et.rotation_magic is False
    assert et.sort is False
    assert et.start_page == 1
    assert et.infile is None
    assert et.outfile is None
    assert et.add_file_name is False
    assert et.append is False


def test_close_is_a_no_op() -> None:
    assert ExtractText().close() is None


# ---------------------------------------------------------------------------
# call() error / validation paths
# ---------------------------------------------------------------------------
def test_call_requires_infile() -> None:
    et = ExtractText()
    with pytest.raises(OSError, match="infile is required"):
        et.call()


def test_call_rejects_html_and_md_combo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    et = ExtractText()
    et.infile = ROT0
    et.to_html = True
    et.to_md = True
    rc = et.call()
    assert rc == 1
    assert "can't set md and html" in capsys.readouterr().err


def test_call_returns_4_on_missing_input(
    patched_loader: type[_PDLoaderShim],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    et = ExtractText()
    et.infile = tmp_path / "nope.pdf"
    et.outfile = tmp_path / "out.txt"
    rc = et.call()
    assert rc == 4
    err = capsys.readouterr().err
    assert "Error extracting text" in err


# ---------------------------------------------------------------------------
# call() happy paths
# ---------------------------------------------------------------------------
def test_call_plain_text_writes_output(
    patched_loader: type[_PDLoaderShim], tmp_path: Path,
) -> None:
    et = ExtractText()
    et.infile = ROT0
    et.outfile = tmp_path / "out.txt"
    rc = et.call()
    assert rc == 0
    assert et.outfile.exists()


def test_call_defaults_outfile_using_input_suffix(
    patched_loader: type[_PDLoaderShim], tmp_path: Path,
) -> None:
    src = tmp_path / "fixture.pdf"
    src.write_bytes(ROT0.read_bytes())
    et = ExtractText()
    et.infile = src
    rc = et.call()
    assert rc == 0
    assert et.outfile == src.with_suffix(".txt")
    assert et.outfile.exists()


def test_call_defaults_outfile_to_html_suffix_when_html(
    patched_loader: type[_PDLoaderShim],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # ``PDFText2HTML`` exercises a wider stripper surface than the lite
    # plain-text path; mock it out so this test focuses on the outfile
    # suffix defaulting logic in ``call``.
    monkeypatch.setattr(et_module, "PDFText2HTML", _LiteStripperFactory)
    src = tmp_path / "fixture.pdf"
    src.write_bytes(ROT0.read_bytes())
    et = ExtractText()
    et.infile = src
    et.to_html = True
    rc = et.call()
    assert rc == 0
    assert et.outfile == src.with_suffix(".html")


def test_call_defaults_outfile_to_md_suffix_when_md(
    patched_loader: type[_PDLoaderShim],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(et_module, "PDFText2Markdown", _LiteStripperFactory)
    src = tmp_path / "fixture.pdf"
    src.write_bytes(ROT0.read_bytes())
    et = ExtractText()
    et.infile = src
    et.to_md = True
    rc = et.call()
    assert rc == 0
    assert et.outfile == src.with_suffix(".md")


def test_call_html_overrides_non_utf8_encoding(
    patched_loader: type[_PDLoaderShim],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(et_module, "PDFText2HTML", _LiteStripperFactory)
    et = ExtractText()
    et.infile = ROT0
    et.outfile = tmp_path / "out.html"
    et.to_html = True
    et.encoding = "ISO-8859-1"
    rc = et.call()
    assert rc == 0
    assert et.encoding == "UTF-8"
    assert "encoding parameter is ignored" in capsys.readouterr().out


def test_call_console_branch_emits_encoding_notice(
    patched_loader: type[_PDLoaderShim],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """``to_console`` returns ``sys.stdout`` from ``create_output_writer``.
    The ``finally`` block in ``call`` then calls ``output.close()`` —
    closing stdout would break every later test. Replace the writer
    with a captured no-op so the close is harmless while the
    encoding-notice branch still runs."""
    captured_io: dict[str, Any] = {}

    class _NoCloseStdout:
        def write(self, text: str) -> int:
            captured_io.setdefault("buf", []).append(text)
            return len(text)

        def flush(self) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        ExtractText, "create_output_writer", lambda self: _NoCloseStdout(),
    )
    et = ExtractText()
    et.infile = ROT0
    et.to_console = True
    et.outfile = tmp_path / "ignored.txt"
    rc = et.call()
    assert rc == 0
    captured = capfd.readouterr()
    assert "encoding parameter is ignored" in captured.out


def test_call_add_file_name_prefix_is_written(
    patched_loader: type[_PDLoaderShim], tmp_path: Path,
) -> None:
    et = ExtractText()
    et.infile = ROT0
    et.outfile = tmp_path / "with-name.txt"
    et.add_file_name = True
    assert et.call() == 0
    content = et.outfile.read_text(encoding="utf-8")
    assert f"PDF file: {ROT0}" in content


def test_call_debug_emits_timing_and_target_log(
    patched_loader: type[_PDLoaderShim],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    et = ExtractText()
    et.infile = ROT0
    et.outfile = tmp_path / "debug.txt"
    et.debug = True
    assert et.call() == 0
    err = capsys.readouterr().err
    assert "Loading PDF" in err
    assert "Time for loading" in err
    assert "Starting text extraction" in err
    assert "Time for extraction" in err
    assert f"Writing to {et.outfile}" in err


def test_call_permission_denied_returns_1(
    patched_loader: type[_PDLoaderShim],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """If the document's access permission disallows extraction, ``call``
    returns 1 and prints a notice — exercise the gate without permission."""
    et = ExtractText()
    et.infile = ROT0
    et.outfile = tmp_path / "denied.txt"

    class _Denied:
        def can_extract_content(self) -> bool:
            return False

    monkeypatch.setattr(
        PDDocument, "get_current_access_permission", lambda self: _Denied(),
    )
    rc = et.call()
    assert rc == 1
    assert "do not have permission" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# create_output_writer
# ---------------------------------------------------------------------------
def test_create_output_writer_returns_stdout_in_console_mode() -> None:
    et = ExtractText()
    et.to_console = True
    assert et.create_output_writer() is sys.stdout


def test_create_output_writer_opens_file_in_write_mode(tmp_path: Path) -> None:
    et = ExtractText()
    et.outfile = tmp_path / "writer.txt"
    handle = et.create_output_writer()
    try:
        handle.write("hello")
    finally:
        handle.close()
    assert et.outfile.read_text(encoding="utf-8") == "hello"


def test_create_output_writer_append_mode_keeps_existing(tmp_path: Path) -> None:
    target = tmp_path / "append.txt"
    target.write_text("first\n", encoding="utf-8")
    et = ExtractText()
    et.outfile = target
    et.append = True
    handle = et.create_output_writer()
    try:
        handle.write("second\n")
    finally:
        handle.close()
    assert target.read_text(encoding="utf-8") == "first\nsecond\n"


def test_create_output_writer_requires_outfile() -> None:
    et = ExtractText()
    with pytest.raises(OSError, match="outfile is required"):
        et.create_output_writer()


# ---------------------------------------------------------------------------
# start / stop processing timing helpers
# ---------------------------------------------------------------------------
def test_start_processing_returns_monotonic_milliseconds() -> None:
    et = ExtractText()
    first = et.start_processing("noop")
    second = et.start_processing("noop")
    assert isinstance(first, int)
    assert second >= first


def test_start_processing_in_debug_emits_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    et = ExtractText()
    et.debug = True
    et.start_processing("starting")
    assert "starting" in capsys.readouterr().err


def test_stop_processing_in_debug_prints_elapsed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    et = ExtractText()
    et.debug = True
    start = et.start_processing("noop")
    et.stop_processing("Time: ", start)
    err = capsys.readouterr().err
    assert "Time: " in err
    assert "seconds" in err


def test_stop_processing_without_debug_is_silent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    et = ExtractText()
    et.stop_processing("Time: ", 0)
    assert capsys.readouterr().err == ""


# ---------------------------------------------------------------------------
# extract_pages helper
# ---------------------------------------------------------------------------
def test_extract_pages_iterates_per_page_setting_range() -> None:
    et = ExtractText()
    seen: list[tuple[int, int]] = []

    class _Stripper:
        def __init__(self) -> None:
            self.start = 0
            self.end = 0

        def set_start_page(self, p: int) -> None:
            self.start = p

        def set_end_page(self, p: int) -> None:
            self.end = p

        def write_text(self, _doc: object, _out: object) -> None:
            seen.append((self.start, self.end))

    stripper = _Stripper()
    et.extract_pages(2, 4, stripper, object(), object(), False, False)  # type: ignore[arg-type]
    assert seen == [(2, 2), (3, 3), (4, 4)]


def test_extract_pages_always_next_swallows_oserror() -> None:
    et = ExtractText()

    class _BadStripper:
        def set_start_page(self, _p: int) -> None:
            pass

        def set_end_page(self, _p: int) -> None:
            pass

        def write_text(self, _doc: object, _out: object) -> None:
            raise OSError("bad page")

    # always_next=True -> errors are swallowed and iteration continues.
    et.extract_pages(1, 2, _BadStripper(), object(), object(), False, True)  # type: ignore[arg-type]


def test_extract_pages_propagates_oserror_when_not_always_next() -> None:
    et = ExtractText()

    class _BadStripper:
        def set_start_page(self, _p: int) -> None:
            pass

        def set_end_page(self, _p: int) -> None:
            pass

        def write_text(self, _doc: object, _out: object) -> None:
            raise OSError("bad page")

    with pytest.raises(OSError):
        et.extract_pages(1, 2, _BadStripper(), object(), object(), False, False)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------
def test_main_writes_default_text_file(
    patched_loader: type[_PDLoaderShim], tmp_path: Path,
) -> None:
    out = tmp_path / "via-main.txt"
    rc = ExtractText.main(["-i", str(ROT0), "-o", str(out)])
    assert rc == 0
    assert out.exists()


def test_main_wires_flags_into_runner_attributes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_call(self: ExtractText) -> int:
        captured["sort"] = self.sort
        captured["debug"] = self.debug
        captured["start_page"] = self.start_page
        captured["end_page"] = self.end_page
        captured["html"] = self.to_html
        captured["md"] = self.to_md
        captured["rotation_magic"] = self.rotation_magic
        captured["ignore_beads"] = self.ignore_beads
        captured["password"] = self.password
        captured["infile"] = self.infile
        captured["outfile"] = self.outfile
        captured["add_file_name"] = self.add_file_name
        captured["append"] = self.append
        captured["always_next"] = self.always_next
        captured["console"] = self.to_console
        return 0

    monkeypatch.setattr(ExtractText, "call", _capture_call)
    rc = ExtractText.main(
        [
            "-i", str(ROT0),
            "-o", str(tmp_path / "x.txt"),
            "-sort",
            "-debug",
            "-startPage", "2",
            "-endPage", "5",
            "-html",
            "-rotationMagic",
            "-ignoreBeads",
            "-password", "secret",
            "-addFileName",
            "-append",
            "-alwaysNext",
            "-console",
        ],
    )
    assert rc == 0
    assert captured["sort"] is True
    assert captured["debug"] is True
    assert captured["start_page"] == 2
    assert captured["end_page"] == 5
    assert captured["html"] is True
    assert captured["md"] is False
    assert captured["rotation_magic"] is True
    assert captured["ignore_beads"] is True
    assert captured["password"] == "secret"
    assert captured["infile"] == ROT0
    assert captured["outfile"] == tmp_path / "x.txt"
    assert captured["add_file_name"] is True
    assert captured["append"] is True
    assert captured["always_next"] is True
    assert captured["console"] is True


def test_main_default_outfile_is_none_when_not_passed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _capture_call(self: ExtractText) -> int:
        captured["outfile"] = self.outfile
        return 0

    monkeypatch.setattr(ExtractText, "call", _capture_call)
    ExtractText.main(["-i", str(ROT0)])
    assert captured["outfile"] is None
