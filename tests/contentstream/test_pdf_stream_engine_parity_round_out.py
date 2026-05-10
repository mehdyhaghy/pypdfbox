"""Parity round-out for :class:`PDFStreamEngine` accessors and
marked-content hooks added to track upstream's surface."""

from __future__ import annotations

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.cos import COSDictionary, COSName

# ---------- get_initial_matrix / set_initial_matrix ----------


def test_get_initial_matrix_default_is_none() -> None:
    engine = PDFStreamEngine()
    assert engine.get_initial_matrix() is None


def test_set_initial_matrix_round_trip() -> None:
    engine = PDFStreamEngine()
    sentinel = object()
    engine.set_initial_matrix(sentinel)
    assert engine.get_initial_matrix() is sentinel


def test_set_initial_matrix_accepts_none_to_clear() -> None:
    engine = PDFStreamEngine()
    engine.set_initial_matrix(object())
    engine.set_initial_matrix(None)
    assert engine.get_initial_matrix() is None


# ---------- is_should_process_color_operators ----------


def test_should_process_color_operators_default_true() -> None:
    # Mirrors upstream default — colour operators run unless the engine
    # is in a Type3 d1 charproc or an uncoloured tiling pattern.
    engine = PDFStreamEngine()
    assert engine.is_should_process_color_operators() is True


def test_should_process_color_operators_can_be_disabled() -> None:
    engine = PDFStreamEngine()
    engine._set_should_process_color_operators(False)
    assert engine.is_should_process_color_operators() is False
    engine._set_should_process_color_operators(True)
    assert engine.is_should_process_color_operators() is True


# ---------- begin/end marked-content sequence + marked-content point ----------


def test_begin_marked_content_sequence_default_is_no_op() -> None:
    # Base hook returns None and does not raise. Subclasses override.
    engine = PDFStreamEngine()
    assert (
        engine.begin_marked_content_sequence(COSName.get_pdf_name("Span"), None)
        is None
    )


def test_begin_marked_content_sequence_accepts_properties() -> None:
    engine = PDFStreamEngine()
    props = COSDictionary()
    props.set_name("MCID", "0")
    assert (
        engine.begin_marked_content_sequence(
            COSName.get_pdf_name("Span"), props
        )
        is None
    )


def test_end_marked_content_sequence_default_is_no_op() -> None:
    engine = PDFStreamEngine()
    assert engine.end_marked_content_sequence() is None


def test_marked_content_point_default_is_no_op() -> None:
    engine = PDFStreamEngine()
    assert (
        engine.marked_content_point(COSName.get_pdf_name("Pt"), None) is None
    )


def test_marked_content_point_overridable_by_subclass() -> None:
    captured: list[tuple[COSName, COSDictionary | None]] = []

    class _Recorder(PDFStreamEngine):
        def marked_content_point(
            self, tag: COSName, properties: COSDictionary | None
        ) -> None:
            captured.append((tag, properties))

    engine = _Recorder()
    tag = COSName.get_pdf_name("Pt")
    engine.marked_content_point(tag, None)
    assert captured == [(tag, None)]
