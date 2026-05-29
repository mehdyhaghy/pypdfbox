"""Wave 1369 — process_page vs process_stream entry-point dispatch parity.

Pins the differences between the public entry points:

- ``process_page`` initialises page context (current page, resources,
  initial matrix), drives the contents, then *resets* the page context
  on exit — even if dispatch raised.
- ``process_stream`` does NOT touch the page context — it bumps
  ``_level`` and may swap the active resources (when the stream owns
  ``/Resources``) but otherwise leaves the engine alone.
- ``process_child_stream`` is the form/annotation/Type3 reentry point —
  swaps in a page context for the dispatch window then restores prior
  context on exit.
- ``process_stream_operators`` is the bare dispatch-driver used by the
  group / annotation paths — no level bump, no resources swap, just
  parse+dispatch.
- ``process_form`` is the convenience alias for ``process_stream``.

These three entry points are easy to mix up if a future refactor
unifies their fences; this file pins the upstream-faithful boundaries.
"""

from __future__ import annotations

import io
from typing import IO, Any

import pytest

from pypdfbox.contentstream import (
    Operator,
    OperatorProcessor,
    PDContentStream,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import BeginText, EndText
from pypdfbox.cos import COSBase, COSStream
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDPage, PDRectangle, PDResources


class _BytesContentStream(PDContentStream):
    def __init__(self, data: bytes, own_resources: PDResources | None = None) -> None:
        self._data = data
        self._own = own_resources

    def get_contents(self) -> IO[bytes]:
        return io.BytesIO(self._data)

    def get_contents_for_random_access(self) -> RandomAccessRead:
        return RandomAccessReadBuffer(self._data)

    def get_resources(self) -> PDResources | None:
        return self._own

    def get_bbox(self) -> PDRectangle:
        return PDRectangle(0.0, 0.0, 612.0, 792.0)

    def get_matrix(self) -> Any:
        return None


# ---------- process_page resets current-page context on exit ----------


def test_process_page_sets_then_clears_current_page() -> None:
    """Inside ``process_page`` the engine reports the page via
    ``get_current_page`` and ``is_processing_page``; both clear on
    return."""

    captured = {"during": None, "during_flag": None}

    class _Engine(PDFStreamEngine):
        def begin_text(self) -> None:
            # Sneak in a peek during dispatch.
            captured["during"] = self.get_current_page()
            captured["during_flag"] = self.is_processing_page()

    engine = _Engine()
    engine.add_operator(BeginText())
    engine.add_operator(EndText())
    page = PDPage()
    cs = COSStream()
    with cs.create_raw_output_stream() as out:
        out.write(b"BT ET")
    page.set_contents(cs)
    engine.process_page(page)
    assert captured["during"] is page
    assert captured["during_flag"] is True
    # After return: page context is cleared.
    assert engine.get_current_page() is None
    assert engine.is_processing_page() is False


def test_process_page_clears_context_even_on_exception() -> None:
    """If a handler raises, the engine still resets ``_current_page``
    on the way out (the ``finally`` in ``process_page``)."""

    class _Boom(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            raise RuntimeError("kaboom")

        def get_name(self) -> str:
            return "BT"

    engine = PDFStreamEngine()
    engine.add_operator(_Boom())
    page = PDPage()
    cs = COSStream()
    with cs.create_raw_output_stream() as out:
        out.write(b"BT")
    page.set_contents(cs)
    with pytest.raises(RuntimeError, match="kaboom"):
        engine.process_page(page)
    assert engine.get_current_page() is None
    assert engine.is_processing_page() is False


def test_process_page_seeds_resources_from_page() -> None:
    """``init_page`` seeds the engine's resources from the page."""
    engine = PDFStreamEngine()
    page = PDPage()
    page_res = PDResources()
    page.set_resources(page_res)
    engine.init_page(page)
    # The engine's resources slot now mirrors the page's resources.
    assert engine.get_resources() is not None


def test_init_page_with_none_raises_value_error() -> None:
    """Mirrors upstream's defensive null-check on the page argument."""
    engine = PDFStreamEngine()
    with pytest.raises(ValueError, match="Page cannot be null"):
        engine.init_page(None)  # type: ignore[arg-type]


def test_process_page_empty_contents_is_noop() -> None:
    """A page with no ``/Contents`` is a silent no-op — no parser
    invocation, no handler dispatch."""
    engine = PDFStreamEngine()
    page = PDPage()
    page.clear_contents()
    engine.process_page(page)
    # No raise; current_page already cleared on exit.
    assert engine.get_current_page() is None


# ---------- process_stream does not set current-page context ----------


def test_process_stream_does_not_touch_current_page_context() -> None:
    """``process_stream`` is the bare entry point — it does not set the
    engine's current-page context (the caller is expected to have done
    so already if the dispatch needs one)."""
    engine = PDFStreamEngine()
    assert engine.get_current_page() is None
    engine.process_stream(_BytesContentStream(b"q Q"))
    assert engine.get_current_page() is None


def test_process_stream_does_not_bump_level_during_dispatch() -> None:
    """``process_stream`` does NOT touch ``_level`` — upstream's private
    ``processStream`` leaves the recursion level alone; only ``DrawObject``
    (the ``Do`` form-XObject handler) bumps it, so the ``getLevel() > 50``
    cap counts form-XObject ``Do`` recursion depth and nothing else (wave
    1472)."""

    levels: list[int] = []

    class _Peek(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            levels.append(self.get_context().get_level())

        def get_name(self) -> str:
            return "q"

    engine = PDFStreamEngine()
    engine.add_operator(_Peek())
    assert engine.get_level() == 0
    engine.process_stream(_BytesContentStream(b"q"))
    assert engine.get_level() == 0
    assert levels == [0]


def test_process_stream_swaps_resources_for_dispatch_window() -> None:
    """When the content stream owns ``/Resources``, those become the
    active resources for the dispatch window; on return the prior
    resources are restored."""

    captured: dict[str, Any] = {}

    class _Peek(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            captured["during"] = self.get_context().get_resources()

        def get_name(self) -> str:
            return "q"

    engine = PDFStreamEngine()
    engine.add_operator(_Peek())
    outer = PDResources()
    inner = PDResources()
    engine._resources = outer
    engine.process_stream(_BytesContentStream(b"q", own_resources=inner))
    assert captured["during"] is inner
    # Outer restored on return.
    assert engine.get_resources() is outer


def test_process_stream_keeps_outer_resources_when_inner_has_none() -> None:
    """A content stream with no ``/Resources`` of its own leaves the
    parent frame in place during dispatch."""

    captured: dict[str, Any] = {}

    class _Peek(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            captured["during"] = self.get_context().get_resources()

        def get_name(self) -> str:
            return "q"

    engine = PDFStreamEngine()
    engine.add_operator(_Peek())
    outer = PDResources()
    engine._resources = outer
    engine.process_stream(_BytesContentStream(b"q", own_resources=None))
    assert captured["during"] is outer


def test_process_stream_finally_resets_level_on_exception() -> None:
    """If dispatch raises, the level still decrements on the way out
    (the ``finally`` in ``process_stream``)."""

    class _Boom(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            raise RuntimeError("nope")

        def get_name(self) -> str:
            return "q"

    engine = PDFStreamEngine()
    engine.add_operator(_Boom())
    assert engine.get_level() == 0
    with pytest.raises(RuntimeError, match="nope"):
        engine.process_stream(_BytesContentStream(b"q"))
    assert engine.get_level() == 0


# ---------- process_child_stream swaps in then restores page context ----------


def test_process_child_stream_sets_then_restores_page_context() -> None:
    """``process_child_stream(stream, page)`` makes the engine see
    ``page`` as the current page for the dispatch window."""

    captured: dict[str, Any] = {}

    class _Peek(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            ctx = self.get_context()
            captured["during"] = ctx.get_current_page()
            captured["during_flag"] = ctx.is_processing_page()

        def get_name(self) -> str:
            return "q"

    engine = PDFStreamEngine()
    engine.add_operator(_Peek())
    # Engine starts with no page.
    assert engine.get_current_page() is None
    new_page = PDPage()
    engine.process_child_stream(_BytesContentStream(b"q"), new_page)
    assert captured["during"] is new_page
    assert captured["during_flag"] is True
    # Restored on return.
    assert engine.get_current_page() is None
    assert engine.is_processing_page() is False


def test_process_child_stream_with_no_page_leaves_context_untouched() -> None:
    """When ``page=None`` the engine doesn't mutate ``_current_page``
    at all — useful for nested streams that piggy-back on an outer
    page context."""

    captured: dict[str, Any] = {}

    class _Peek(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            captured["during"] = self.get_context().get_current_page()

        def get_name(self) -> str:
            return "q"

    engine = PDFStreamEngine()
    engine.add_operator(_Peek())
    outer_page = PDPage()
    engine._current_page = outer_page
    engine.process_child_stream(_BytesContentStream(b"q"), page=None)
    assert captured["during"] is outer_page  # untouched
    assert engine.get_current_page() is outer_page  # untouched on return


# ---------- process_stream_operators: bare dispatch, no level bump, no resources swap ----------


def test_process_stream_operators_does_not_bump_level() -> None:
    """``process_stream_operators`` is the bare driver — used by the
    transparency-group / annotation paths which already manage the
    level around the call. It must NOT bump ``_level``."""

    levels: list[int] = []

    class _Peek(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            levels.append(self.get_context().get_level())

        def get_name(self) -> str:
            return "q"

    engine = PDFStreamEngine()
    engine.add_operator(_Peek())
    assert engine.get_level() == 0
    engine.process_stream_operators(_BytesContentStream(b"q"))
    assert engine.get_level() == 0
    assert levels == [0]  # not bumped during dispatch


def test_process_stream_operators_does_not_swap_resources() -> None:
    """``process_stream_operators`` does NOT push the stream's
    ``/Resources`` — that's the caller's responsibility."""

    captured: dict[str, Any] = {}

    class _Peek(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            captured["during"] = self.get_context().get_resources()

        def get_name(self) -> str:
            return "q"

    engine = PDFStreamEngine()
    engine.add_operator(_Peek())
    outer = PDResources()
    inner = PDResources()
    engine._resources = outer
    # The stream owns ``inner`` but the bare driver should NOT swap.
    engine.process_stream_operators(_BytesContentStream(b"q", own_resources=inner))
    assert captured["during"] is outer  # untouched
    assert engine.get_resources() is outer


# ---------- process_form is alias for process_stream ----------


def test_process_form_is_alias_for_process_stream() -> None:
    """``process_form`` exists for upstream-name parity with
    ``processForm(PDFormXObject)``; it routes through ``process_stream``."""
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    levels: list[int] = []

    class _Peek(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            levels.append(self.get_context().get_level())

        def get_name(self) -> str:
            return "q"

    engine = PDFStreamEngine()
    engine.add_operator(_Peek())
    # Use a form-xobject backed by a small content stream.
    cs = COSStream()
    with cs.create_raw_output_stream() as out:
        out.write(b"q")
    form = PDFormXObject(cs)
    engine.process_form(form)
    # ``process_stream`` does NOT touch the level → neither does
    # ``process_form``. Only ``DrawObject`` bumps it (wave 1472).
    assert levels == [0]
    assert engine.get_level() == 0
