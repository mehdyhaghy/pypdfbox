"""Wave 1347 — coverage-boost pass, Agent B.

Covers the residual missing branches in seven targets:

* ``examples.interactive.form.create_multi_widgets_form`` — ``__init__``,
  the ``set_widgets`` exception fallback.
* ``examples.interactive.form.create_simple_form`` — ``__init__``, the
  ``set_value`` exception fallback warning.
* ``examples.pdmodel.create_separation_color_box`` — ``__init__``, the
  "too many args" usage error path.
* ``examples.signature.tsa_client`` — the real ``urlopen`` transport path
  (stubbed; no network).
* ``tools.export_fdf`` — the ``AttributeError`` shim branch + the
  ``__main__`` block.
* ``tools.export_xfdf`` — the ``AttributeError`` shim branch + the
  ``__main__`` block.
* ``tools.overlay_pdf`` — the ``finally`` block's ``OSError`` from
  ``overlayer.close()`` + the ``__main__`` block.
"""

from __future__ import annotations

import hashlib
import io
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from pypdfbox.examples.interactive.form.create_multi_widgets_form import (
    CreateMultiWidgetsForm,
)
from pypdfbox.examples.interactive.form.create_simple_form import (
    CreateSimpleForm,
)
from pypdfbox.examples.pdmodel.create_separation_color_box import (
    CreateSeparationColorBox,
)
from pypdfbox.examples.signature.tsa_client import TSAClient
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.tools import export_fdf as export_fdf_mod
from pypdfbox.tools import export_xfdf as export_xfdf_mod
from pypdfbox.tools import overlay_pdf as overlay_pdf_mod


# ---------------------------------------------------------------------------
# create_multi_widgets_form.py
# ---------------------------------------------------------------------------
def test_create_multi_widgets_form_init() -> None:
    """Construct the (essentially-utility) class to cover ``__init__``."""
    assert CreateMultiWidgetsForm() is not None


def test_create_multi_widgets_form_set_widgets_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force ``set_widgets`` to raise so the ``except`` fallback path
    (lines 104-107) is exercised."""
    from pypdfbox.pdmodel.interactive.form import pd_terminal_field

    original = pd_terminal_field.PDTerminalField.set_widgets

    def _raises(self, widgets):  # noqa: ANN001 - pytest monkeypatch
        raise RuntimeError("simulated upstream gap")

    monkeypatch.setattr(
        pd_terminal_field.PDTerminalField, "set_widgets", _raises,
    )
    try:
        out = tmp_path / "multi.pdf"
        CreateMultiWidgetsForm.create(str(out))
        assert out.exists()
    finally:
        monkeypatch.setattr(
            pd_terminal_field.PDTerminalField, "set_widgets", original,
        )


# ---------------------------------------------------------------------------
# create_simple_form.py
# ---------------------------------------------------------------------------
def test_create_simple_form_init() -> None:
    assert CreateSimpleForm() is not None


def test_create_simple_form_set_value_fallback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force ``set_value`` to raise so the warning branch (lines 94-97)
    is exercised."""
    from pypdfbox.pdmodel.interactive.form import pd_text_field

    def _raises(self, value):  # noqa: ANN001
        raise RuntimeError("simulated set_value failure")

    monkeypatch.setattr(pd_text_field.PDTextField, "set_value", _raises)
    out = tmp_path / "simple.pdf"
    CreateSimpleForm.create(str(out))
    assert out.exists()
    captured = capsys.readouterr()
    assert "set_value skipped" in captured.err


# ---------------------------------------------------------------------------
# create_separation_color_box.py
# ---------------------------------------------------------------------------
def test_create_separation_color_box_init() -> None:
    assert CreateSeparationColorBox() is not None


def test_create_separation_color_box_too_many_args(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Two or more arguments triggers the usage-error path (lines 70-73)."""
    with pytest.raises(SystemExit) as ei:
        CreateSeparationColorBox.main(["a.pdf", "b.pdf"])
    assert ei.value.code == 1
    err = capsys.readouterr().err
    assert "Usage" in err


# ---------------------------------------------------------------------------
# tsa_client.py — exercise the real urlopen transport seam (stubbed).
# ---------------------------------------------------------------------------
class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *_args: object) -> None:
        pass


def test_tsa_client_falls_back_to_urlopen_when_no_transport() -> None:
    """When ``transport=None`` the client should hit ``urlopen`` — we
    monkey-patch ``urlopen`` in the module to avoid any real network IO
    while still covering lines 104-106."""
    received: dict[str, object] = {}

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        received["url"] = req.full_url
        received["data"] = req.data
        received["timeout"] = timeout
        received["headers"] = dict(req.header_items())
        return _FakeResp(b"signed-token-from-tsa")

    client = TSAClient(
        url="http://tsa.test.invalid/sign",
        username=None,
        password=None,
        digest=hashlib.sha256(),
        transport=None,
    )

    with patch(
        "pypdfbox.examples.signature.tsa_client.urlopen",
        side_effect=fake_urlopen,
    ):
        token = client.get_time_stamp_token(io.BytesIO(b"document-bytes"))

    assert token == b"signed-token-from-tsa"
    assert received["url"] == "http://tsa.test.invalid/sign"
    assert received["timeout"] == 30
    # Ensure the request payload was forwarded and not empty.
    assert isinstance(received["data"], bytes)
    assert b"tsp-req" in received["data"]


# ---------------------------------------------------------------------------
# tools/export_fdf.py + export_xfdf.py — AttributeError shim + __main__.
# ---------------------------------------------------------------------------
def _build_form_pdf(path: Path) -> Path:
    """Build a minimal PDF carrying an empty AcroForm."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        acro = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(acro)
        doc.save(str(path))
    finally:
        doc.close()
    return path


def test_export_fdf_attribute_error_branch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Make ``export_fdf`` raise ``AttributeError`` so lines 37-38 trip
    the OSError-translation branch."""
    src = _build_form_pdf(tmp_path / "form.pdf")

    def _raise_attr(self):  # noqa: ANN001
        raise AttributeError("simulated missing export_fdf")

    monkeypatch.setattr(PDAcroForm, "export_fdf", _raise_attr)

    runner = export_fdf_mod.ExportFDF()
    runner.infile = src
    runner.outfile = tmp_path / "out.fdf"
    rc = runner.call()
    assert rc == 4
    err = capsys.readouterr().err
    assert "export_fdf unsupported" in err or "Error exporting FDF" in err


def test_export_fdf_main_block_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drive lines 63-65 by executing the module as ``__main__``."""
    src = _build_form_pdf(tmp_path / "form.pdf")
    out = tmp_path / "out.fdf"
    monkeypatch.setattr(
        sys,
        "argv",
        ["exportfdf", "-i", str(src), "-o", str(out)],
    )
    with pytest.raises(SystemExit) as ei:
        runpy.run_module(
            "pypdfbox.tools.export_fdf",
            run_name="__main__",
        )
    assert ei.value.code == 0
    assert out.exists()


def test_export_xfdf_attribute_error_branch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Make ``export_fdf`` raise ``NotImplementedError`` so lines 34-35
    trip the OSError-translation branch."""
    src = _build_form_pdf(tmp_path / "form.pdf")

    def _raise_ni(self):  # noqa: ANN001
        raise NotImplementedError("simulated")

    monkeypatch.setattr(PDAcroForm, "export_fdf", _raise_ni)

    runner = export_xfdf_mod.ExportXFDF()
    runner.infile = src
    runner.outfile = tmp_path / "out.xfdf"
    rc = runner.call()
    assert rc == 4
    err = capsys.readouterr().err
    assert "export_fdf unsupported" in err or "Error exporting XFDF" in err


def test_export_xfdf_main_block_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drive lines 60-62 by executing the module as ``__main__``."""
    src = _build_form_pdf(tmp_path / "form.pdf")
    out = tmp_path / "out.xfdf"
    monkeypatch.setattr(
        sys,
        "argv",
        ["exportxfdf", "-i", str(src), "-o", str(out)],
    )
    with pytest.raises(SystemExit) as ei:
        runpy.run_module(
            "pypdfbox.tools.export_xfdf",
            run_name="__main__",
        )
    assert ei.value.code == 0
    assert out.exists()


# ---------------------------------------------------------------------------
# tools/overlay_pdf.py — finally-block OSError + __main__.
# ---------------------------------------------------------------------------
def _build_simple_pdf(path: Path) -> Path:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(str(path))
    finally:
        doc.close()
    return path


def test_overlay_pdf_close_oserror_branch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force ``Overlay.close`` to raise ``OSError`` from the ``finally``
    cleanup path so lines 67-71 are exercised."""
    from pypdfbox.multipdf import overlay as overlay_mod

    src = _build_simple_pdf(tmp_path / "in.pdf")
    overlay_doc = _build_simple_pdf(tmp_path / "ov.pdf")
    out = tmp_path / "out.pdf"

    original_close = overlay_mod.Overlay.close

    def _raises(self):  # noqa: ANN001
        # Run the real close to keep handles tidy, then raise so the
        # OverlayPDF wrapper's finally block trips the error branch.
        try:
            original_close(self)
        finally:
            raise OSError("simulated close failure")

    monkeypatch.setattr(overlay_mod.Overlay, "close", _raises)

    rc = overlay_pdf_mod.OverlayPDF.main([
        "-i", str(src),
        "-o", str(out),
        "-default", str(overlay_doc),
    ])
    assert rc == 4
    err = capsys.readouterr().err
    assert "Error adding overlay" in err


def test_overlay_pdf_main_block_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drive line 108 by executing the module as ``__main__``."""
    src = _build_simple_pdf(tmp_path / "in.pdf")
    overlay_doc = _build_simple_pdf(tmp_path / "ov.pdf")
    out = tmp_path / "out.pdf"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "overlaypdf",
            "-i", str(src),
            "-o", str(out),
            "-default", str(overlay_doc),
        ],
    )
    with pytest.raises(SystemExit) as ei:
        runpy.run_module(
            "pypdfbox.tools.overlay_pdf",
            run_name="__main__",
        )
    assert ei.value.code == 0
    assert out.exists()
