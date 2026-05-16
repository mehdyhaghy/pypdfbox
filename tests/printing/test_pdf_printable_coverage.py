"""Coverage boost for :mod:`pypdfbox.printing.pdf_printable`.

Exercises :meth:`PDFPrintable.render`, :meth:`PDFPrintable.print`, and
the rotated-box helpers — branches the original wave-1281 test file
does not touch.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.printing.pdf_printable import PDFPrintable, Scaling


def _make_doc(n: int = 1) -> PDDocument:
    doc = PDDocument()
    for _ in range(n):
        doc.add_page(PDPage())
    return doc


def test_render_invokes_render_image(monkeypatch: Any) -> None:
    doc = _make_doc()
    try:
        printable = PDFPrintable(doc)
        captured: dict[str, Any] = {}

        class _FakeRenderer:
            def __init__(self, _doc: Any) -> None:
                captured["init"] = _doc

            def render_image(self, idx: int) -> str:
                captured["render_image"] = idx
                return "image"

            def render_image_with_dpi(self, idx: int, dpi: float) -> str:
                captured["render_image_with_dpi"] = (idx, dpi)
                return "image-dpi"

        import pypdfbox.rendering.pdf_renderer as renderer_mod

        monkeypatch.setattr(renderer_mod, "PDFRenderer", _FakeRenderer)

        result = printable.render(0)
        assert result == "image"
        assert captured["render_image"] == 0
    finally:
        doc.close()


def test_render_uses_dpi_when_positive(monkeypatch: Any) -> None:
    doc = _make_doc()
    try:
        printable = PDFPrintable(doc, dpi=150.0)
        captured: dict[str, Any] = {}

        class _FakeRenderer:
            def __init__(self, _doc: Any) -> None:
                pass

            def render_image(self, idx: int) -> str:
                captured["plain"] = idx
                return "img"

            def render_image_with_dpi(self, idx: int, dpi: float) -> str:
                captured["dpi"] = (idx, dpi)
                return "img-dpi"

        import pypdfbox.rendering.pdf_renderer as renderer_mod

        monkeypatch.setattr(renderer_mod, "PDFRenderer", _FakeRenderer)
        assert printable.render(2) == "img-dpi"
        assert captured["dpi"] == (2, 150.0)
        assert "plain" not in captured
    finally:
        doc.close()


def test_render_defaults_to_stored_page_index(monkeypatch: Any) -> None:
    doc = _make_doc()
    try:
        printable = PDFPrintable(doc)
        printable._page_index = 7  # type: ignore[attr-defined]

        class _FakeRenderer:
            def __init__(self, _doc: Any) -> None:
                pass

            def render_image(self, idx: int) -> str:
                return f"img-{idx}"

        import pypdfbox.rendering.pdf_renderer as renderer_mod

        monkeypatch.setattr(renderer_mod, "PDFRenderer", _FakeRenderer)
        assert printable.render() == "img-7"
    finally:
        doc.close()


def test_print_returns_page_exists(monkeypatch: Any) -> None:
    doc = _make_doc()
    try:
        printable = PDFPrintable(doc)

        class _FakeRenderer:
            def __init__(self, _doc: Any) -> None:
                pass

            def render_image(self, _idx: int) -> str:
                return "pillow-image"

        import pypdfbox.rendering.pdf_renderer as renderer_mod

        monkeypatch.setattr(renderer_mod, "PDFRenderer", _FakeRenderer)
        assert printable.print(page_index=0) == 0
    finally:
        doc.close()


def test_print_returns_no_such_page_on_index_error(monkeypatch: Any) -> None:
    doc = _make_doc()
    try:
        printable = PDFPrintable(doc)

        class _Broken:
            def __init__(self, _doc: Any) -> None:
                pass

            def render_image(self, _idx: int) -> str:
                raise IndexError("no such page")

        import pypdfbox.rendering.pdf_renderer as renderer_mod

        monkeypatch.setattr(renderer_mod, "PDFRenderer", _Broken)
        assert printable.print(page_index=999) == 1
    finally:
        doc.close()


def test_print_uses_default_page_index_when_none(monkeypatch: Any) -> None:
    doc = _make_doc()
    try:
        printable = PDFPrintable(doc)
        printable._page_index = 3  # type: ignore[attr-defined]
        captured: list[int] = []

        class _FakeRenderer:
            def __init__(self, _doc: Any) -> None:
                pass

            def render_image(self, idx: int) -> str:
                captured.append(idx)
                return "img"

        import pypdfbox.rendering.pdf_renderer as renderer_mod

        monkeypatch.setattr(renderer_mod, "PDFRenderer", _FakeRenderer)
        assert printable.print() == 0
        assert captured == [3]
    finally:
        doc.close()


def test_print_draws_image_on_graphics(monkeypatch: Any) -> None:
    doc = _make_doc()
    try:
        printable = PDFPrintable(doc)

        class _FakeRenderer:
            def __init__(self, _doc: Any) -> None:
                pass

            def render_image(self, _idx: int) -> str:
                return "the-image"

        import pypdfbox.rendering.pdf_renderer as renderer_mod

        monkeypatch.setattr(renderer_mod, "PDFRenderer", _FakeRenderer)

        class _Graphics:
            def __init__(self) -> None:
                self.drew: list[tuple[Any, int, int]] = []

            def draw_image(self, img: Any, x: int, y: int) -> None:
                self.drew.append((img, x, y))

        g = _Graphics()
        assert printable.print(graphics=g, page_index=0) == 0
        assert g.drew == [("the-image", 0, 0)]
    finally:
        doc.close()


def test_print_swallows_draw_image_errors(monkeypatch: Any) -> None:
    doc = _make_doc()
    try:
        printable = PDFPrintable(doc)

        class _FakeRenderer:
            def __init__(self, _doc: Any) -> None:
                pass

            def render_image(self, _idx: int) -> str:
                return "img"

        import pypdfbox.rendering.pdf_renderer as renderer_mod

        monkeypatch.setattr(renderer_mod, "PDFRenderer", _FakeRenderer)

        class _Bad:
            def draw_image(self, *_args: Any, **_kwargs: Any) -> None:
                raise TypeError("nope")

        # Should still return 0 — the draw_image error is suppressed.
        assert printable.print(graphics=_Bad(), page_index=0) == 0
    finally:
        doc.close()


def test_get_rotated_media_box_with_real_page() -> None:
    doc = _make_doc()
    try:
        page = doc.get_pages()[0]
        printable = PDFPrintable(doc)
        box = printable.get_rotated_media_box(page)
        # Default media box is letter — width > 0, height > 0.
        assert box[2] > 0
        assert box[3] > 0
    finally:
        doc.close()


def test_get_rotated_crop_box_with_real_page() -> None:
    doc = _make_doc()
    try:
        page = doc.get_pages()[0]
        printable = PDFPrintable(doc)
        box = printable.get_rotated_crop_box(page)
        assert box[2] > 0
    finally:
        doc.close()


def test_rotated_box_returns_zeros_for_none_page() -> None:
    assert PDFPrintable._rotated_box(None, "media") == (0.0, 0.0, 0.0, 0.0)


def test_rotated_box_returns_zeros_when_page_returns_none_box() -> None:
    class _P:
        def get_media_box(self) -> None:
            return None

    assert PDFPrintable._rotated_box(_P(), "media") == (0.0, 0.0, 0.0, 0.0)


def test_rotated_box_swaps_dimensions_on_90_degree_rotation() -> None:
    rect = PDRectangle(0.0, 0.0, 100.0, 200.0)

    class _P:
        def get_media_box(self) -> PDRectangle:
            return rect

        def get_rotation(self) -> int:
            return 90

    box = PDFPrintable._rotated_box(_P(), "media")
    # width/height swapped
    assert box[2] == 200.0
    assert box[3] == 100.0


def test_rotated_box_keeps_dimensions_for_other_rotations() -> None:
    rect = PDRectangle(0.0, 0.0, 100.0, 200.0)

    class _P:
        def get_media_box(self) -> PDRectangle:
            return rect

        def get_rotation(self) -> int:
            return 180

    box = PDFPrintable._rotated_box(_P(), "media")
    assert box[2] == 100.0
    assert box[3] == 200.0


def test_rotated_box_handles_bad_rotation_value() -> None:
    rect = PDRectangle(0.0, 0.0, 50.0, 60.0)

    class _P:
        def get_media_box(self) -> PDRectangle:
            return rect

        def get_rotation(self) -> str:
            return "not-an-int"

    box = PDFPrintable._rotated_box(_P(), "media")
    # rotation falls back to 0, so width/height not swapped
    assert box[2] == 50.0
    assert box[3] == 60.0


def test_rotated_box_uses_crop_getter_when_requested() -> None:
    rect = PDRectangle(10.0, 20.0, 110.0, 220.0)

    class _P:
        def get_crop_box(self) -> PDRectangle:
            return rect

    box = PDFPrintable._rotated_box(_P(), "crop")
    assert box[0] == 10.0
    assert box[1] == 20.0


def test_scaling_enum_membership() -> None:
    # Sanity check on the Scaling enum surface so the import path is exercised.
    assert Scaling.SHRINK_TO_FIT.value == "SHRINK_TO_FIT"
    assert Scaling.ACTUAL_SIZE in list(Scaling)
