"""Hand-written coverage for :class:`RemoveAllText`."""

from __future__ import annotations

import sys
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.examples.pdmodel._font_helpers import make_standard14_type1_font
from pypdfbox.examples.util.remove_all_text import RemoveAllText
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


@pytest.fixture
def patched_operator_module() -> Any:
    """Provide the missing ``pypdfbox.contentstream.operator.operator``
    module so the happy-path branch of ``create_tokens_without_text`` can
    be exercised.

    The source file references a module path that does not yet exist in
    pypdfbox; the helper re-exports the real ``Operator`` (from
    ``pdf_stream_parser``) under that name and tears the shim down on
    exit.
    """
    mod_name = "pypdfbox.contentstream.operator.operator"
    from pypdfbox.pdfparser.pdf_stream_parser import Operator as PDFOperator

    shim = types.ModuleType(mod_name)
    shim.Operator = PDFOperator
    sys.modules[mod_name] = shim
    try:
        yield shim
    finally:
        sys.modules.pop(mod_name, None)


def test_constructor_is_a_no_op() -> None:
    # The Java ctor is package-private but pypdfbox exposes the class —
    # constructing it must not raise.
    assert isinstance(RemoveAllText(), RemoveAllText)


def test_main_with_no_args_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    RemoveAllText.main([])
    err = capsys.readouterr().err
    assert "Usage" in err and "RemoveAllText" in err


def test_main_with_one_arg_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    RemoveAllText.main(["only-input.pdf"])
    err = capsys.readouterr().err
    assert "Usage" in err


def test_main_with_none_argv_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    RemoveAllText.main(None)
    err = capsys.readouterr().err
    assert "Usage" in err


def test_usage_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    RemoveAllText.usage()
    err = capsys.readouterr().err
    assert "<input-pdf>" in err and "<output-pdf>" in err


def test_main_with_two_args_invokes_strip(
    make_pdf: Callable[..., Path], tmp_path: Path,
) -> None:
    src = make_pdf("main-in.pdf")
    dst = tmp_path / "main-out.pdf"
    RemoveAllText.main([str(src), str(dst)])
    assert dst.exists() and dst.stat().st_size > 0


def test_strip_blank_pdf(make_pdf: Callable[..., Path], tmp_path: Path) -> None:
    src = make_pdf("strip.pdf")
    dst = tmp_path / "stripped.pdf"
    RemoveAllText.strip(str(src), str(dst))
    assert dst.exists() and dst.stat().st_size > 0


def test_strip_pdf_with_text(tmp_path: Path) -> None:
    src = tmp_path / "with-text.pdf"
    dst = tmp_path / "stripped-text.pdf"
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = make_standard14_type1_font(FontName.HELVETICA)
        with PDPageContentStream(doc, page) as cs:
            cs.begin_text()
            cs.new_line_at_offset(20, 700)
            cs.set_font(font, 12)
            cs.show_text("hello world")
            cs.end_text()
        doc.save(str(src))
    finally:
        doc.close()
    RemoveAllText.strip(str(src), str(dst))
    assert dst.exists() and dst.stat().st_size > 0


def test_strip_encrypted_pdf_short_circuits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "encrypted.pdf"
    dst = tmp_path / "should-not-exist.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.protect(
            StandardProtectionPolicy("owner-pw", "user-pw", AccessPermission()),
        )
        doc.save(str(src))
    finally:
        doc.close()
    RemoveAllText.strip(str(src), str(dst))
    err = capsys.readouterr().err
    assert "Encrypted" in err
    assert not dst.exists()


def test_process_resources_none_is_a_no_op() -> None:
    RemoveAllText.process_resources(None)


def test_process_resources_skips_objects_without_x_object_accessor() -> None:
    class Bare:
        pass

    # Should silently no-op when ``get_x_object_names`` is missing.
    RemoveAllText.process_resources(Bare())


def test_process_resources_swallows_get_x_object_errors() -> None:
    seen: list[str] = []

    class FormChild:
        def get_resources(self) -> Any:
            seen.append("recursed")
            return None

    class Resources:
        def get_x_object_names(self) -> list[str]:
            return ["explodes", "form"]

        def get_x_object(self, name: str) -> Any:
            if name == "explodes":
                raise ValueError("boom")
            return FormChild()

    RemoveAllText.process_resources(Resources())
    assert seen == ["recursed"]


def test_process_resources_skips_xobjects_without_get_resources() -> None:
    class NoResources:
        pass

    class Resources:
        def get_x_object_names(self) -> list[str]:
            return ["plain"]

        def get_x_object(self, name: str) -> Any:
            return NoResources()

    # Doesn't raise — recursion only fires for form-like XObjects.
    RemoveAllText.process_resources(Resources())


def test_create_tokens_without_text_returns_empty_on_import_error() -> None:
    # Without the shim in ``patched_operator_module``, the import for the
    # parser side fails and ``create_tokens_without_text`` returns ``[]``.
    sys.modules.pop("pypdfbox.contentstream.operator.operator", None)
    assert RemoveAllText.create_tokens_without_text(object()) == []


def test_create_tokens_without_text_swallows_parser_errors() -> None:
    sys.modules.pop("pypdfbox.contentstream.operator.operator", None)
    # Pass an object the parser cannot consume — fallback returns [].
    class NotAStream:
        pass
    assert RemoveAllText.create_tokens_without_text(NotAStream()) == []


def test_create_tokens_strips_tj(patched_operator_module: Any) -> None:
    src = b"BT /F1 12 Tf 20 700 Td (Hello) Tj ET"
    toks = RemoveAllText.create_tokens_without_text(RandomAccessReadBuffer(src))
    reprs = [repr(t) for t in toks]
    # ``(Hello)`` and ``Tj`` were both removed; the BT/ET pair survives.
    assert any("BT" in r for r in reprs)
    assert any("ET" in r for r in reprs)
    assert not any("Tj" in r for r in reprs)
    assert not any("Hello" in r for r in reprs)


def test_create_tokens_strips_tj_array(patched_operator_module: Any) -> None:
    src = b"BT [(Hello)] TJ ET"
    toks = RemoveAllText.create_tokens_without_text(RandomAccessReadBuffer(src))
    reprs = [repr(t) for t in toks]
    assert not any("TJ" in r for r in reprs)
    assert not any("Hello" in r for r in reprs)


def test_create_tokens_strips_apostrophe(patched_operator_module: Any) -> None:
    src = b"BT (Hi) ' ET"
    toks = RemoveAllText.create_tokens_without_text(RandomAccessReadBuffer(src))
    reprs = [repr(t) for t in toks]
    # SHOW_TEXT_LINE ``'`` operator was stripped along with its string arg.
    assert all(c not in r for r in reprs for c in ("'", "Hi"))


def test_create_tokens_strips_quotation(patched_operator_module: Any) -> None:
    src = b'BT 1 2 (Hi) " ET'
    toks = RemoveAllText.create_tokens_without_text(RandomAccessReadBuffer(src))
    reprs = [repr(t) for t in toks]
    # SHOW_TEXT_LINE_AND_SPACE ``"`` strips its 3 preceding operands too.
    assert not any('"' in r for r in reprs)
    assert not any("Hi" in r for r in reprs)


def test_write_tokens_to_stream_no_op_when_import_fails() -> None:
    # No ContentStreamWriter is exposed in the lite port; the helper
    # silently does nothing rather than raising.
    class FakeStream:
        def create_output_stream(self, *_args: Any) -> Any:
            raise RuntimeError("must not be called")

    RemoveAllText.write_tokens_to_stream(FakeStream(), [])
