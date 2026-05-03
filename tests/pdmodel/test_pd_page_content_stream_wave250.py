"""Wave 250 — PDPageContentStream remaining gaps.

Mirrors the per-operator ``inTextMode`` guards that
:class:`PDAbstractContentStream` enforces in upstream:

- Path construction (``move_to``, ``line_to``, ``curve_to`` family,
  ``close_path``, ``add_rect``), path painting (``stroke``, ``fill``,
  ``fill_even_odd``, ``fill_and_stroke``, ``fill_and_stroke_even_odd``,
  ``close_and_stroke``, ``close_fill_and_stroke``,
  ``close_fill_and_stroke_even_odd``, ``end_path``), clipping (``clip``,
  ``clip_path``, ``clip_path_even_odd``, ``clip_even_odd``), and
  ``shading_fill`` MUST be outside a ``BT``/``ET`` block — they raise
  :class:`RuntimeError` when called inside text mode (mirroring
  upstream's ``IllegalStateException``).

- ``transform``, ``save_graphics_state``, and ``restore_graphics_state``
  also reject text-mode callers.

- ``new_line``, ``new_line_at_offset``, and ``set_text_matrix`` MUST
  be inside a ``BT``/``ET`` block — they raise :class:`RuntimeError`
  when called outside text mode (mirroring upstream's
  ``IllegalStateException`` "Error: must call beginText() before <op>").
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _make_page(doc: PDDocument) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    return page


# ------------------------------------------------------------------
# Path construction operators reject text-block callers
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("call_name", "args"),
    [
        ("move_to", (10.0, 20.0)),
        ("line_to", (30.0, 40.0)),
        ("curve_to", (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)),
        ("curve_to_1", (1.0, 2.0, 3.0, 4.0)),
        ("curve_to_2", (1.0, 2.0, 3.0, 4.0)),
        ("curve_to1", (1.0, 2.0, 3.0, 4.0)),
        ("curve_to2", (1.0, 2.0, 3.0, 4.0)),
        ("close_path", ()),
        ("add_rect", (0.0, 0.0, 50.0, 50.0)),
    ],
)
def test_path_construction_rejected_inside_text_block(
    call_name: str, args: tuple[float, ...]
) -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError, match="not allowed within a text block"):
            getattr(cs, call_name)(*args)
        cs.end_text()


# ------------------------------------------------------------------
# Path-painting operators reject text-block callers
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "call_name",
    [
        "stroke",
        "close_and_stroke",
        "fill",
        "fill_even_odd",
        "fill_and_stroke",
        "fill_and_stroke_even_odd",
        "close_fill_and_stroke",
        "close_fill_and_stroke_even_odd",
        "end_path",
    ],
)
def test_path_painting_rejected_inside_text_block(call_name: str) -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError, match="not allowed within a text block"):
            getattr(cs, call_name)()
        cs.end_text()


# ------------------------------------------------------------------
# Clipping operators reject text-block callers
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "call_name",
    ["clip", "clip_even_odd", "clip_path", "clip_path_even_odd"],
)
def test_clip_rejected_inside_text_block(call_name: str) -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError, match="not allowed within a text block"):
            getattr(cs, call_name)()
        cs.end_text()


# ------------------------------------------------------------------
# Graphics state / transform reject text-block callers
# ------------------------------------------------------------------


def test_transform_rejected_inside_text_block() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError, match="transform.*text block"):
            cs.transform(1, 0, 0, 1, 10, 20)
        cs.end_text()


def test_save_graphics_state_rejected_inside_text_block() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(
            RuntimeError, match="save_graphics_state.*text block"
        ):
            cs.save_graphics_state()
        cs.end_text()


def test_restore_graphics_state_rejected_inside_text_block() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(
            RuntimeError, match="restore_graphics_state.*text block"
        ):
            cs.restore_graphics_state()
        cs.end_text()


# ------------------------------------------------------------------
# Text-positioning operators require an active text block
# ------------------------------------------------------------------


def test_new_line_at_offset_requires_begin_text() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        with pytest.raises(
            RuntimeError, match="begin_text.*new_line_at_offset"
        ):
            cs.new_line_at_offset(10.0, 20.0)


def test_new_line_requires_begin_text() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        with pytest.raises(RuntimeError, match="begin_text.*new_line"):
            cs.new_line()


def test_set_text_matrix_requires_begin_text() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        with pytest.raises(
            RuntimeError, match="begin_text.*set_text_matrix"
        ):
            cs.set_text_matrix(1, 0, 0, 1, 0, 0)


def test_set_text_matrix_iterable_form_requires_begin_text() -> None:
    """The Matrix-decomposition path also enforces the in-text-mode guard
    — verifies the guard runs before component extraction."""
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        with pytest.raises(RuntimeError, match="begin_text"):
            cs.set_text_matrix([1, 0, 0, 1, 5, 6])


# ------------------------------------------------------------------
# Positive paths still work — nothing got accidentally over-restricted
# ------------------------------------------------------------------


def test_path_ops_outside_text_block_still_emit() -> None:
    """The guard kicks in only inside a text block — outside, all
    operators emit unchanged."""
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(10, 10)
        cs.line_to(20, 20)
        cs.curve_to(0, 0, 0, 0, 30, 30)
        cs.close_path()
        cs.stroke()
        cs.add_rect(0, 0, 5, 5)
        cs.fill()
        cs.save_graphics_state()
        cs.transform(1, 0, 0, 1, 5, 5)
        cs.restore_graphics_state()
    body = page.get_contents()
    assert b" m\n" in body
    assert b" l\n" in body
    assert b" c\n" in body
    assert b"h\n" in body
    assert b"S\n" in body
    assert b" re\n" in body
    assert b"f\n" in body
    assert b"q\n" in body
    assert b"cm\n" in body
    assert b"Q\n" in body


def test_text_positioning_inside_text_block_still_emits() -> None:
    """The require-text-mode guard only fires outside BT/ET — inside, all
    text-positioning operators emit unchanged."""
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.new_line_at_offset(10, 20)
        cs.set_text_matrix(1, 0, 0, 1, 0, 0)
        cs.new_line()
        cs.end_text()
    body = page.get_contents()
    assert b"BT\n" in body
    assert b"10 20 Td\n" in body
    assert b"1 0 0 1 0 0 Tm\n" in body
    assert b"T*\n" in body
    assert b"ET\n" in body


def test_shading_fill_rejected_inside_text_block() -> None:
    doc = PDDocument()
    page = _make_page(doc)

    class _DummyShading:
        def get_cos_object(self) -> object:
            from pypdfbox.cos import COSDictionary  # noqa: PLC0415

            d = COSDictionary()
            d.set_int("ShadingType", 2)
            return d

    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(
            RuntimeError, match="shading_fill.*text block"
        ):
            cs.shading_fill(_DummyShading())
        cs.end_text()


# ------------------------------------------------------------------
# Failed text-block guards leave state machine consistent
# ------------------------------------------------------------------


def test_failed_path_op_inside_text_does_not_break_text_mode() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        # Guard fires — but text mode flag stays True.
        with pytest.raises(RuntimeError):
            cs.move_to(0, 0)
        assert cs.is_in_text_mode() is True
        cs.end_text()
        assert cs.is_in_text_mode() is False


def test_failed_text_op_outside_text_does_not_break_path_mode() -> None:
    """Failing text-positioning calls outside BT/ET shouldn't perturb the
    text-mode flag."""
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        with pytest.raises(RuntimeError):
            cs.new_line()
        assert cs.is_in_text_mode() is False
        # Path ops still work afterward.
        cs.move_to(1, 2)
        cs.stroke()
    body = page.get_contents()
    assert b"1 2 m\n" in body
    assert b"S\n" in body
