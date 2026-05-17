"""Tests for :class:`PrintImageLocations`."""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from PIL import Image

from pypdfbox.contentstream.operator import Operator
from pypdfbox.cos.cos_name import COSName
from pypdfbox.examples.util.print_image_locations import PrintImageLocations
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _png_bytes(size: int = 4, colour: str = "red") -> bytes:
    """Return PNG-encoded bytes for a tiny solid-colour image."""
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color=colour).save(buf, format="PNG")
    return buf.getvalue()


def _build_image_pdf(path: Path, *, image_count: int = 1) -> Path:
    """Synthesise a one-page PDF carrying ``image_count`` PNG XObjects."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        cs = PDPageContentStream(doc, page)
        try:
            for i in range(image_count):
                ximg = PDImageXObject.create_from_byte_array(
                    doc, _png_bytes(size=4 + i), f"img{i}.png"
                )
                cs.draw_image(ximg, 10.0 + 80 * i, 10.0, 64.0, 64.0)
        finally:
            cs.close()
        doc.save(path)
    finally:
        doc.close()
    return path


# ---------------------------------------------------------------------------
# Construction / entry points
# ---------------------------------------------------------------------------


def test_constructor_returns_stream_engine_subclass() -> None:
    printer = PrintImageLocations()
    # Must be a PDFStreamEngine descendant (i.e. has get_resources hook).
    assert hasattr(printer, "get_resources")
    assert callable(printer.process_operator)


def test_main_with_no_args_prints_usage(capsys) -> None:
    PrintImageLocations.main([])
    captured = capsys.readouterr()
    assert "Usage" in captured.err
    assert "PrintImageLocations" in captured.err


def test_main_with_none_argv_prints_usage(capsys) -> None:
    PrintImageLocations.main(None)
    captured = capsys.readouterr()
    assert "Usage" in captured.err


def test_main_with_too_many_args_prints_usage(capsys) -> None:
    PrintImageLocations.main(["a", "b"])
    captured = capsys.readouterr()
    assert "Usage" in captured.err


def test_usage_writes_to_stderr(capsys) -> None:
    PrintImageLocations.usage()
    captured = capsys.readouterr()
    assert captured.err.startswith("Usage:")
    assert captured.out == ""


# ---------------------------------------------------------------------------
# run() — blank PDF
# ---------------------------------------------------------------------------


def test_run_blank_pdf(make_pdf: Callable[..., Path], capsys) -> None:
    src = make_pdf("imgs.pdf", page_count=2)
    PrintImageLocations.run(str(src))
    captured = capsys.readouterr()
    # No images → only the per-page header is emitted.
    assert "Processing page: 1" in captured.out
    assert "Processing page: 2" in captured.out
    assert "Found image" not in captured.out


def test_main_single_arg_forwards_to_run(tmp_path, capsys) -> None:
    src = tmp_path / "blank.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(src)
    finally:
        doc.close()
    PrintImageLocations.main([str(src)])
    captured = capsys.readouterr()
    assert "Processing page: 1" in captured.out


# ---------------------------------------------------------------------------
# run() — PDF with images, end-to-end
# ---------------------------------------------------------------------------


def test_run_pdf_with_one_image(tmp_path, capsys) -> None:
    src = _build_image_pdf(tmp_path / "one.pdf", image_count=1)
    PrintImageLocations.run(str(src))
    captured = capsys.readouterr()
    assert "Processing page: 1" in captured.out
    assert "Found image" in captured.out
    assert "raw image size  = 4, 4 in pixels" in captured.out


def test_run_pdf_with_multiple_images(tmp_path, capsys) -> None:
    src = _build_image_pdf(tmp_path / "two.pdf", image_count=2)
    PrintImageLocations.run(str(src))
    captured = capsys.readouterr()
    assert captured.out.count("Found image") == 2


def test_run_falls_back_when_process_page_raises(tmp_path, capsys) -> None:
    """The fallback path walks the page resources directly when the
    stream engine refuses the page."""
    src = _build_image_pdf(tmp_path / "fb.pdf", image_count=1)

    def _boom(self, page):  # noqa: ARG001
        raise NotImplementedError("stream engine offline")

    with patch.object(PrintImageLocations, "process_page", _boom):
        PrintImageLocations.run(str(src))
    captured = capsys.readouterr()
    # The fallback still emits the image discovery row.
    assert "Found image" in captured.out


def test_run_fallback_attribute_error(tmp_path, capsys) -> None:
    src = _build_image_pdf(tmp_path / "fb2.pdf", image_count=1)

    def _attr_err(self, page):  # noqa: ARG001
        raise AttributeError("no process_page")

    with patch.object(PrintImageLocations, "process_page", _attr_err):
        PrintImageLocations.run(str(src))
    captured = capsys.readouterr()
    assert "Found image" in captured.out


# ---------------------------------------------------------------------------
# process_operator — Do branch (image XObject draw)
# ---------------------------------------------------------------------------


class _StubXObject:
    """Duck-typed XObject exposing get_width / get_height."""

    def __init__(self, width: int, height: int) -> None:
        self._w, self._h = width, height

    def get_width(self) -> int:
        return self._w

    def get_height(self) -> int:
        return self._h


class _StubResources:
    def __init__(self, xobj: Any) -> None:
        self._xobj = xobj

    def get_x_object(self, name: Any) -> Any:  # noqa: ARG002
        return self._xobj


def test_process_operator_do_prints_image_metadata(capsys) -> None:
    printer = PrintImageLocations()
    printer._resources = _StubResources(_StubXObject(12, 34))  # type: ignore[attr-defined]
    do_op = Operator.get_operator("Do")
    printer.process_operator(do_op, [COSName.get_pdf_name("Im0")])
    captured = capsys.readouterr()
    assert "Found image" in captured.out
    assert "12, 34" in captured.out


def test_process_operator_do_swallows_resource_error(capsys) -> None:
    class _BrokenResources:
        def get_x_object(self, name: Any) -> Any:  # noqa: ARG002
            raise RuntimeError("broken")

    printer = PrintImageLocations()
    printer._resources = _BrokenResources()  # type: ignore[attr-defined]
    do_op = Operator.get_operator("Do")
    # Must not raise — broad-except in the operator path swallows.
    printer.process_operator(do_op, [COSName.get_pdf_name("Im0")])
    captured = capsys.readouterr()
    assert "Found image" not in captured.out


def test_process_operator_do_no_resources_is_silent(capsys) -> None:
    printer = PrintImageLocations()
    # _resources is None by default on a fresh engine.
    do_op = Operator.get_operator("Do")
    printer.process_operator(do_op, [COSName.get_pdf_name("Im0")])
    captured = capsys.readouterr()
    assert "Found image" not in captured.out


def test_process_operator_non_do_delegates_to_super(capsys) -> None:
    """A non-``Do`` operator hits the ``super().process_operator`` branch
    and must not raise even when the parent dispatch is a no-op."""
    printer = PrintImageLocations()
    save_op = Operator.get_operator("q")  # save-graphics-state
    printer.process_operator(save_op, [])
    # No image output expected.
    captured = capsys.readouterr()
    assert "Found image" not in captured.out


# ---------------------------------------------------------------------------
# _maybe_print_image
# ---------------------------------------------------------------------------


def test_maybe_print_image_with_valid_xobject(capsys) -> None:
    printer = PrintImageLocations()
    printer._maybe_print_image(COSName.get_pdf_name("Logo"), _StubXObject(100, 200))
    captured = capsys.readouterr()
    assert "Found image" in captured.out
    assert "100, 200" in captured.out


def test_maybe_print_image_ignores_non_image_xobject(capsys) -> None:
    """Form XObjects don't expose get_width / get_height and are skipped."""

    class _Form:
        pass

    printer = PrintImageLocations()
    printer._maybe_print_image(COSName.get_pdf_name("F0"), _Form())
    captured = capsys.readouterr()
    assert "Found image" not in captured.out


def test_maybe_print_image_accepts_plain_string_name(capsys) -> None:
    """The fallback path may pass a raw string name; the helper must
    still produce output."""
    printer = PrintImageLocations()
    printer._maybe_print_image("Im0", _StubXObject(7, 9))
    captured = capsys.readouterr()
    assert "Found image" in captured.out
    assert "7, 9" in captured.out


# ---------------------------------------------------------------------------
# _walk_page_x_objects (the fallback)
# ---------------------------------------------------------------------------


def test_walk_page_x_objects_returns_when_no_resources() -> None:
    class _Page:
        def get_resources(self) -> Any:
            return None

    printer = PrintImageLocations()
    printer._walk_page_x_objects(_Page())  # must not raise


def test_walk_page_x_objects_returns_when_no_x_object_names() -> None:
    class _Res:
        # No get_x_object_names attribute.
        pass

    class _Page:
        def get_resources(self) -> Any:
            return _Res()

    printer = PrintImageLocations()
    printer._walk_page_x_objects(_Page())  # must not raise


def test_walk_page_x_objects_continues_on_xobject_error(capsys) -> None:
    class _Res:
        def get_x_object_names(self) -> list[Any]:
            return ["good", "bad"]

        def get_x_object(self, name: Any) -> Any:
            if name == "bad":
                raise RuntimeError("broken")
            return _StubXObject(3, 5)

    class _Page:
        def get_resources(self) -> Any:
            return _Res()

    printer = PrintImageLocations()
    printer._walk_page_x_objects(_Page())
    captured = capsys.readouterr()
    # The good entry is printed; the bad one is swallowed.
    assert captured.out.count("Found image") == 1
    assert "3, 5" in captured.out


# ---------------------------------------------------------------------------
# show_form
# ---------------------------------------------------------------------------


def test_show_form_swallows_attribute_error() -> None:
    """The helper only swallows ``AttributeError``. Force the super call
    to raise that exact type via a stub override."""
    printer = PrintImageLocations()

    def _raise_attr(self, form):  # noqa: ARG001
        raise AttributeError("no impl")

    with patch(
        "pypdfbox.contentstream.pdf_stream_engine.PDFStreamEngine.show_form",
        _raise_attr,
    ):
        printer.show_form(object())  # must not raise


def test_show_form_propagates_non_attribute_error() -> None:
    """Sanity check that the contextlib.suppress is narrow — a
    ``RuntimeError`` from the parent still escapes."""
    printer = PrintImageLocations()
    # super().show_form raises RuntimeError when no current page is set.
    with pytest.raises(RuntimeError):
        printer.show_form(object())


# ---------------------------------------------------------------------------
# Missing-file behaviour — run() bubbles up the load failure.
# ---------------------------------------------------------------------------


def test_run_raises_on_missing_file(tmp_path) -> None:
    missing = tmp_path / "nope.pdf"
    with pytest.raises((FileNotFoundError, OSError)):
        PrintImageLocations.run(str(missing))
