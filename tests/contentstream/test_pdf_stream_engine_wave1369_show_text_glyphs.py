"""Wave 1369 — show-text glyph-rendering loop parity.

Drives the engine's text-show operators (``Tj`` / ``TJ`` / ``'`` / ``"``)
end-to-end and asserts that the per-glyph hook (``show_glyph``) fires
once per glyph code, with the correct codes in source order. Mirrors
upstream's ``PDFStreamEngine.showText`` → ``showFontGlyph`` →
``showGlyph`` decomposition.

These tests pin both the no-font fall-back path (per-byte dispatch) and
the multi-byte path (font with ``read_code``). They also assert that
``TJ`` arrays mixing strings + numeric advances drive ``show_glyph`` on
each string segment while the numeric entries adjust the text matrix
via :meth:`PDFStreamEngine.apply_text_adjustment`.
"""

from __future__ import annotations

import io
from typing import IO, Any

from pypdfbox.contentstream import (
    PDContentStream,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import (
    BeginText,
    EndText,
    ShowText,
    ShowTextAdjusted,
    ShowTextLine,
    ShowTextLineAndSpace,
)
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDRectangle, PDResources


class _GlyphEngine(PDFStreamEngine):
    """Records every ``show_glyph`` invocation in source order."""

    def __init__(self) -> None:
        super().__init__()
        self.glyphs: list[int] = []
        # ``show_text`` is invoked by the registered text-operator
        # handlers via the engine ``show_text_string`` / ``show_text``
        # hook chain. Override ``show_text_string`` to forward into the
        # decode + ``show_glyph`` loop.
        self.text_strings: list[bytes] = []

    def show_text_string(self, text: bytes) -> None:
        self.text_strings.append(text)
        self.show_text(text)

    def show_glyph(
        self,
        text_rendering_matrix: Any,
        font: Any,
        code: int,
        displacement: Any,
    ) -> None:
        self.glyphs.append(code)


class _BytesContentStream(PDContentStream):
    def __init__(self, data: bytes) -> None:
        self._data = data

    def get_contents(self) -> IO[bytes]:
        return io.BytesIO(self._data)

    def get_contents_for_random_access(self) -> RandomAccessRead:
        return RandomAccessReadBuffer(self._data)

    def get_resources(self) -> PDResources | None:
        return PDResources()

    def get_bbox(self) -> PDRectangle:
        return PDRectangle(0.0, 0.0, 612.0, 792.0)

    def get_matrix(self) -> Any:
        return None


def _register_text_ops(engine: PDFStreamEngine) -> None:
    for cls in (
        BeginText,
        EndText,
        ShowText,
        ShowTextAdjusted,
        ShowTextLine,
        ShowTextLineAndSpace,
    ):
        engine.add_operator(cls())


# ---------- Tj — each byte triggers one show_glyph ----------


def test_tj_dispatches_one_show_glyph_per_byte() -> None:
    """Without an active font we fall back to per-byte dispatch — the
    bytes between the literal-string parens map 1:1 to glyph codes."""
    engine = _GlyphEngine()
    _register_text_ops(engine)
    engine.process_stream(_BytesContentStream(b"BT (Hello) Tj ET"))
    assert engine.glyphs == [ord(c) for c in "Hello"]


def test_tj_with_escaped_octal_dispatches_decoded_byte() -> None:
    """Octal-escaped string bytes still come through one-per-glyph after
    the parser decodes them."""
    engine = _GlyphEngine()
    _register_text_ops(engine)
    # \101 \102 \103 → 'A' 'B' 'C'.
    engine.process_stream(_BytesContentStream(b"BT (\\101\\102\\103) Tj ET"))
    assert engine.glyphs == [ord("A"), ord("B"), ord("C")]


def test_tj_empty_string_dispatches_no_glyphs() -> None:
    engine = _GlyphEngine()
    _register_text_ops(engine)
    engine.process_stream(_BytesContentStream(b"BT () Tj ET"))
    assert engine.glyphs == []


# ---------- TJ — string segments drive show_glyph; numeric entries adjust ----------


def test_tj_array_default_show_text_strings_is_noop() -> None:
    """The bare :class:`PDFStreamEngine`'s ``show_text_strings`` is a
    no-op — cluster #2 leaves array iteration to subclasses (text
    extractor, page renderer). Pin the no-op default."""
    engine = _GlyphEngine()
    _register_text_ops(engine)
    engine.process_stream(_BytesContentStream(b"BT [(He) -120 (llo)] TJ ET"))
    # No subclass override → ``show_text_strings`` does nothing.
    assert engine.glyphs == []


def test_tj_array_subclass_iteration_drives_show_glyph_per_byte() -> None:
    """A subclass that walks the COSArray and forwards each string
    segment through ``show_text`` gets per-byte ``show_glyph`` dispatch
    — proves the array reaches the subclass hook intact."""
    from pypdfbox.cos import COSArray, COSString

    class _ArrayIteratingEngine(_GlyphEngine):
        def show_text_strings(self, array: COSArray) -> None:  # type: ignore[override]
            for entry in array:
                if isinstance(entry, COSString):
                    self.show_text(entry.get_bytes())

    engine = _ArrayIteratingEngine()
    _register_text_ops(engine)
    engine.process_stream(_BytesContentStream(b"BT [(He) -120 (llo)] TJ ET"))
    assert engine.glyphs == [ord(c) for c in "Hello"]


def test_tj_array_only_numbers_dispatches_no_glyphs() -> None:
    """All-numeric TJ array → no strings → no glyphs even when a
    subclass iterates the array (because none of the entries are
    ``COSString``)."""
    from pypdfbox.cos import COSArray, COSString

    class _ArrayIteratingEngine(_GlyphEngine):
        def show_text_strings(self, array: COSArray) -> None:  # type: ignore[override]
            for entry in array:
                if isinstance(entry, COSString):
                    self.show_text(entry.get_bytes())

    engine = _ArrayIteratingEngine()
    _register_text_ops(engine)
    engine.process_stream(_BytesContentStream(b"BT [100 -50 25] TJ ET"))
    assert engine.glyphs == []


# ---------- ' — re-enters via T* then Tj ----------


def test_apostrophe_show_text_line_dispatches_show_glyph() -> None:
    """``'`` decomposes to ``T*`` (next line; unregistered in this engine
    → unsupported, no-op) + ``Tj`` (which fires ``show_glyph``)."""
    engine = _GlyphEngine()
    _register_text_ops(engine)
    engine.process_stream(_BytesContentStream(b"BT (Hi) ' ET"))
    assert engine.glyphs == [ord("H"), ord("i")]


# ---------- " — three string segments → three Tj's worth of glyphs ----------


def test_quote_show_text_line_and_space_dispatches_show_glyph() -> None:
    """``"`` decomposes to ``Tw`` + ``Tc`` + ``'`` (next-line + Tj). Even
    when the Tw/Tc handlers aren't registered (no-op via
    ``unsupported_operator``), the inner Tj still fires."""
    engine = _GlyphEngine()
    _register_text_ops(engine)
    engine.process_stream(_BytesContentStream(b"BT 1 2 (Hi) \" ET"))
    assert engine.glyphs == [ord("H"), ord("i")]


# ---------- multi-byte font path: read_code drives glyph decode ----------


def test_show_text_uses_font_read_code_when_available() -> None:
    """When the active graphics state exposes a font with ``read_code``
    we decode multi-byte codes (one ``read_code`` call → one glyph)
    instead of falling back to per-byte dispatch."""

    class _TwoByteFont:
        def read_code(self, src: Any) -> int | None:
            chunk = src.read(2)
            if len(chunk) < 2:
                return None
            return (chunk[0] << 8) | chunk[1]

    class _GS:
        text_font = _TwoByteFont()

    engine = _GlyphEngine()
    engine._graphics_stack.append(_GS())
    # 6 bytes → 3 two-byte glyph codes.
    engine.show_text(b"\x00\x41\x00\x42\x00\x43")
    assert engine.glyphs == [0x41, 0x42, 0x43]


def test_show_text_font_read_code_short_chunk_breaks_loop() -> None:
    """If ``read_code`` returns ``None`` partway through a buffer (e.g.
    a malformed multi-byte tail), the decode loop breaks rather than
    looping forever."""

    class _LazyFont:
        def read_code(self, src: Any) -> int | None:
            chunk = src.read(2)
            if len(chunk) < 2:
                return None
            return chunk[0]

    class _GS:
        text_font = _LazyFont()

    engine = _GlyphEngine()
    engine._graphics_stack.append(_GS())
    # 3 bytes is one full 2-byte code (returns chunk[0]) then a partial
    # tail → second read_code returns None → loop terminates.
    engine.show_text(b"\xAB\x01\xFF")
    assert engine.glyphs == [0xAB]


# ---------- show_font_glyph default forwards to show_glyph ----------


def test_show_font_glyph_default_chains_into_show_glyph() -> None:
    """The base ``show_font_glyph`` implementation forwards to
    ``show_glyph`` so a subclass can override either layer without
    redundant boilerplate."""

    class _OnlyShowGlyph(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.codes: list[int] = []

        def show_glyph(
            self,
            text_rendering_matrix: Any,
            font: Any,
            code: int,
            displacement: Any,
        ) -> None:
            self.codes.append(code)

    engine = _OnlyShowGlyph()
    engine.show_font_glyph(None, None, 0x41, None)
    engine.show_font_glyph(None, None, 0x42, None)
    assert engine.codes == [0x41, 0x42]


# ---------- show_font_glyph override stops the default chain ----------


def test_show_font_glyph_override_suppresses_show_glyph_chain() -> None:
    """A subclass that overrides ``show_font_glyph`` and does *not* call
    ``super`` blocks the default forward — ``show_glyph`` should not be
    invoked. Pins the upstream-faithful split between the two hooks."""

    class _OnlyFontGlyph(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.font_glyphs: list[int] = []
            self.glyphs: list[int] = []

        def show_font_glyph(
            self,
            text_rendering_matrix: Any,
            font: Any,
            code: int,
            displacement: Any,
        ) -> None:
            self.font_glyphs.append(code)
            # NOTE: intentionally no super() call.

        def show_glyph(
            self,
            text_rendering_matrix: Any,
            font: Any,
            code: int,
            displacement: Any,
        ) -> None:
            self.glyphs.append(code)

    engine = _OnlyFontGlyph()
    engine.show_text(b"AB")
    assert engine.font_glyphs == [ord("A"), ord("B")]
    assert engine.glyphs == []


# ---------- empty input cases ----------


def test_show_text_empty_bytes_dispatches_nothing() -> None:
    engine = _GlyphEngine()
    engine.show_text(b"")
    assert engine.glyphs == []
