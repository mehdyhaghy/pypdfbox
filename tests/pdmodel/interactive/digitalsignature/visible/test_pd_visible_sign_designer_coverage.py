"""Coverage-boost tests for ``PDVisibleSignDesigner`` (wave 1318).

Pre-wave the module sat at 62%. The uncovered surface was:
  * the image-bytes / image-stream ``__init__`` branches,
  * ``set_image`` with both callable and attribute-shaped width/height,
  * ``zoom`` / ``coordinates`` / axis + dimension fluent setters,
  * the ``signature_image(path)`` file-reader path,
  * ``calculate_page_size`` / ``calculate_page_size_from_file`` /
    ``calculate_page_size_from_random_access_read`` happy-path and
    defensive branches,
  * the ``NotImplementedError`` parity stubs for signature text,
  * formatter rectangle round-trip + image-size-percent round-trip,
  * the ``_IdentityAffineTransform`` defaults.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sign_designer import (
    PDVisibleSignDesigner,
    _IdentityAffineTransform,
)


# ---------------------------------------------------------------------------
# image ingestion
# ---------------------------------------------------------------------------
def test_init_with_bytes_image_stream_stores_raw_bytes() -> None:
    designer = PDVisibleSignDesigner(image_stream=b"PNGDATA")
    assert designer.get_image() == b"PNGDATA"


def test_init_with_bytearray_image_stream_stores_bytes() -> None:
    designer = PDVisibleSignDesigner(image_stream=bytearray(b"abc"))
    assert designer.get_image() == b"abc"


def test_init_with_file_like_image_stream_reads_to_end() -> None:
    designer = PDVisibleSignDesigner(image_stream=io.BytesIO(b"streamdata"))
    assert designer.get_image() == b"streamdata"


def test_read_image_stream_public_method_with_file_like() -> None:
    designer = PDVisibleSignDesigner()
    designer.read_image_stream(io.BytesIO(b"public"))
    assert designer.get_image() == b"public"


def test_set_image_records_callable_width_height() -> None:
    class _Img:
        def get_width(self) -> int:
            return 320

        def get_height(self) -> int:
            return 240

    designer = PDVisibleSignDesigner()
    designer.set_image(_Img())
    assert designer.get_width() == 320.0
    assert designer.get_height() == 240.0


def test_set_image_records_attribute_width_height() -> None:
    class _Img:
        width = 100
        height = 50

    designer = PDVisibleSignDesigner()
    designer.set_image(_Img())
    assert designer.get_width() == 100.0
    assert designer.get_height() == 50.0


def test_set_image_preserves_object_without_dimensions() -> None:
    marker = object()
    designer = PDVisibleSignDesigner()
    designer.set_image(marker)
    assert designer.get_image() is marker
    assert designer.get_width() is None
    assert designer.get_height() is None


# ---------------------------------------------------------------------------
# fluent setters
# ---------------------------------------------------------------------------
def test_zoom_scales_width_and_height_by_percentage() -> None:
    designer = PDVisibleSignDesigner()
    designer.width(100.0).height(50.0)
    designer.zoom(50.0)
    assert designer.get_width() == 150.0
    assert designer.get_height() == 75.0
    # Upstream zoom writes the new integer dimensions into the formatter
    # rectangle (Java PDVisibleSignDesigner.zoom, line 285).
    params = designer.get_formatter_rectangle_parameters()
    assert params[2] == 150
    assert params[3] == 75


def test_width_height_update_formatter_rectangle() -> None:
    # Java width(float)/height(float) cast into formatterRectangleParameters
    # [2]/[3] (lines 360/381).
    designer = PDVisibleSignDesigner()
    designer.width(123.7).height(45.9)
    params = designer.get_formatter_rectangle_parameters()
    assert params[2] == 123
    assert params[3] == 45


def test_set_image_updates_formatter_rectangle() -> None:
    class _Img:
        width = 64
        height = 32

    designer = PDVisibleSignDesigner()
    designer.set_image(_Img())
    params = designer.get_formatter_rectangle_parameters()
    assert params[2] == 64
    assert params[3] == 32


def test_zoom_no_op_when_dimensions_unset() -> None:
    designer = PDVisibleSignDesigner()
    # Zoom on the freshly built designer should not raise even though
    # _image_width / _image_height are still None.
    result = designer.zoom(50.0)
    assert result is designer
    assert designer.get_width() is None
    assert designer.get_height() is None


def test_coordinates_sets_axes_and_returns_self() -> None:
    designer = PDVisibleSignDesigner()
    result = designer.coordinates(12.5, 7.25)
    assert result is designer
    assert designer.get_x_axis() == 12.5
    assert designer.get_y_axis() == 7.25
    # Parity-alias accessors return the same values.
    assert designer.getx_axis() == 12.5
    assert designer.gety_axis() == 7.25


def test_x_axis_and_y_axis_fluent_setters() -> None:
    designer = PDVisibleSignDesigner()
    designer.x_axis(1.0).y_axis(2.0)
    assert designer.get_x_axis() == 1.0
    assert designer.get_y_axis() == 2.0


def test_page_width_and_page_height_setters() -> None:
    designer = PDVisibleSignDesigner()
    designer.page_width(612.0).page_height(792.0)
    assert designer.get_page_width() == 612.0
    assert designer.get_page_height() == 792.0
    # ``get_template_height`` is the legacy alias for page height.
    assert designer.get_template_height() == 792.0


def test_signature_field_name_round_trip() -> None:
    designer = PDVisibleSignDesigner()
    assert designer.get_signature_field_name() == "sig"
    designer.signature_field_name("custom")
    assert designer.get_signature_field_name() == "custom"


def test_formatter_rectangle_parameters_round_trip_returns_copy() -> None:
    designer = PDVisibleSignDesigner()
    default_params = designer.get_formatter_rectangle_parameters()
    assert default_params == [0, 0, 100, 50]
    # Mutating the returned list does not affect internal state.
    default_params.append(999)
    assert designer.get_formatter_rectangle_parameters() == [0, 0, 100, 50]

    designer.formatter_rectangle_parameters([1, 2, 3, 4])
    assert designer.get_formatter_rectangle_parameters() == [1, 2, 3, 4]


def test_image_size_in_percents_round_trip() -> None:
    designer = PDVisibleSignDesigner()
    assert designer.get_image_size_in_percents() == 0.0
    designer.image_size_in_percents(35.5)
    assert designer.get_image_size_in_percents() == 35.5


def test_transform_round_trip() -> None:
    designer = PDVisibleSignDesigner()
    # An _IdentityAffineTransform exposes the six affine components, so the
    # defensive-copy path snapshots them into a fresh, distinct instance
    # (mirrors upstream's ``new AffineTransform(at)``).
    supplied = _IdentityAffineTransform(2.0, 0.0, 0.0, 3.0, 5.0, 7.0)
    result = designer.transform(supplied)
    assert result is designer
    stored = designer.get_transform()
    assert stored is not supplied
    assert (stored.m00, stored.m10, stored.m01, stored.m11, stored.m02, stored.m12) == (
        2.0, 0.0, 0.0, 3.0, 5.0, 7.0,
    )


def test_adjust_for_rotation_returns_self() -> None:
    designer = PDVisibleSignDesigner()
    assert designer.adjust_for_rotation() is designer


def _designer_at_rotation(rotation: int) -> PDVisibleSignDesigner:
    designer = PDVisibleSignDesigner()
    designer.page_width(600.0).page_height(800.0)
    designer.width(100.0).height(40.0)
    designer.coordinates(10.0, 20.0)
    designer._rotation = rotation
    return designer


def test_adjust_for_rotation_90() -> None:
    # Java case 90 (lines 222-233): yAxis = pageHeight - xAxis - imageWidth,
    # xAxis = old yAxis, width/height swap, affine = (0, h/w, -w/h, 0, w, 0).
    d = _designer_at_rotation(90)
    d.adjust_for_rotation()
    assert d.get_x_axis() == 20.0
    assert d.get_y_axis() == 800.0 - 10.0 - 100.0  # 690.0
    assert d.get_width() == 40.0  # swapped
    assert d.get_height() == 100.0
    t = d.get_transform()
    assert (t.m00, t.m10, t.m01, t.m11, t.m02, t.m12) == (
        0.0, 40.0 / 100.0, -100.0 / 40.0, 0.0, 100.0, 0.0,
    )


def test_adjust_for_rotation_180() -> None:
    # Java case 180 (lines 236-242): xAxis = pageWidth - xAxis - imageWidth,
    # yAxis = pageHeight - yAxis - imageHeight, affine = (-1, 0, 0, -1, w, h).
    d = _designer_at_rotation(180)
    d.adjust_for_rotation()
    assert d.get_x_axis() == 600.0 - 10.0 - 100.0  # 490.0
    assert d.get_y_axis() == 800.0 - 20.0 - 40.0  # 740.0
    assert d.get_width() == 100.0
    assert d.get_height() == 40.0
    t = d.get_transform()
    assert (t.m00, t.m10, t.m01, t.m11, t.m02, t.m12) == (
        -1.0, 0.0, 0.0, -1.0, 100.0, 40.0,
    )


def test_adjust_for_rotation_270() -> None:
    # Java case 270 (lines 245-256): xAxis = pageWidth - yAxis - imageHeight,
    # yAxis = old xAxis, width/height swap, affine = (0, -h/w, w/h, 0, 0, h).
    d = _designer_at_rotation(270)
    d.adjust_for_rotation()
    assert d.get_x_axis() == 600.0 - 20.0 - 40.0  # 540.0
    assert d.get_y_axis() == 10.0
    assert d.get_width() == 40.0  # swapped
    assert d.get_height() == 100.0
    t = d.get_transform()
    assert (t.m00, t.m10, t.m01, t.m11, t.m02, t.m12) == (
        0.0, -40.0 / 100.0, 100.0 / 40.0, 0.0, 0.0, 40.0,
    )


# ---------------------------------------------------------------------------
# file / document page-size discovery
# ---------------------------------------------------------------------------
class _MediaBox:
    def __init__(self, width: float, height: float) -> None:
        self._w = width
        self._h = height

    def get_width(self) -> float:
        return self._w

    def get_height(self) -> float:
        return self._h


class _FakePage:
    def __init__(self, width: float, height: float, rotation: int = 0) -> None:
        self._box = _MediaBox(width, height)
        self._rotation = rotation

    def get_media_box(self) -> _MediaBox:
        return self._box

    def get_rotation(self) -> int:
        return self._rotation


class _FakeDocument:
    def __init__(self, pages: list[_FakePage]) -> None:
        self._pages = pages

    def get_pages(self) -> list[_FakePage]:
        return self._pages


def test_calculate_page_size_records_dimensions() -> None:
    designer = PDVisibleSignDesigner()
    doc = _FakeDocument([_FakePage(595.0, 842.0, rotation=450)])
    designer.calculate_page_size(doc, 1)
    assert designer.get_page_width() == 595.0
    assert designer.get_page_height() == 842.0
    # Upstream sets imageSizeInPercents to 100 and rotation to
    # getRotation() % 360 (Java calculatePageSize, lines 195-207).
    assert designer.get_image_size_in_percents() == 100.0
    assert designer._rotation == 90


def test_calculate_page_size_rejects_page_below_one() -> None:
    # Upstream throws IllegalArgumentException for page < 1.
    designer = PDVisibleSignDesigner()
    doc = _FakeDocument([_FakePage(595.0, 842.0)])
    with pytest.raises(ValueError, match="First page of pdf is 1"):
        designer.calculate_page_size(doc, 0)


def test_calculate_page_size_swallows_exceptions() -> None:
    designer = PDVisibleSignDesigner()

    class _Broken:
        def get_pages(self) -> list[_FakePage]:
            raise RuntimeError("broken")

    designer.calculate_page_size(_Broken(), 1)
    # Defensive parity stub: dimensions remain at the default zero values.
    assert designer.get_page_width() == 0.0
    assert designer.get_page_height() == 0.0


def test_init_with_document_kwarg_delegates_to_calculate_page_size() -> None:
    doc = _FakeDocument([_FakePage(100.0, 200.0)])
    designer = PDVisibleSignDesigner(document=doc, page=1)
    assert designer.get_page_width() == 100.0
    assert designer.get_page_height() == 200.0


def test_init_with_path_kwarg_uses_file_route(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """``__init__`` with a path delegates to ``calculate_page_size_from_file``
    which itself tries ``pypdfbox.loader.load_pdf``. We stub the loader to
    return our fake doc so the file route is exercised end-to-end without
    needing a real PDF."""
    fake_doc = _FakeDocument([_FakePage(72.0, 144.0)])
    import sys
    import types

    fake_loader = types.ModuleType("pypdfbox.loader")

    def _load_pdf(_source: Any, _password: Any = None) -> _FakeDocument:
        return fake_doc

    fake_loader.load_pdf = _load_pdf  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pypdfbox.loader", fake_loader)

    pdf_path = tmp_path / "fake.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    designer = PDVisibleSignDesigner(document=pdf_path)
    assert designer.get_page_width() == 72.0
    assert designer.get_page_height() == 144.0


def test_calculate_page_size_from_random_access_read_uses_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_doc = _FakeDocument([_FakePage(10.0, 20.0)])
    import sys
    import types

    fake_loader = types.ModuleType("pypdfbox.loader")

    def _load_pdf(_source: Any, _password: Any = None) -> _FakeDocument:
        return fake_doc

    fake_loader.load_pdf = _load_pdf  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pypdfbox.loader", fake_loader)

    designer = PDVisibleSignDesigner()
    designer.calculate_page_size_from_random_access_read(object(), 1)
    assert designer.get_page_width() == 10.0
    assert designer.get_page_height() == 20.0


def test_signature_image_reads_from_path(tmp_path: Path) -> None:
    image_path = tmp_path / "sig.png"
    image_path.write_bytes(b"\x89PNGfake")
    designer = PDVisibleSignDesigner()
    result = designer.signature_image(str(image_path))
    assert result is designer
    assert designer.get_image() == b"\x89PNGfake"


# ---------------------------------------------------------------------------
# parity stubs
# ---------------------------------------------------------------------------
def test_get_signature_text_raises_not_implemented() -> None:
    designer = PDVisibleSignDesigner()
    with pytest.raises(NotImplementedError, match="not supported"):
        designer.get_signature_text()


def test_signature_text_setter_raises_not_implemented() -> None:
    designer = PDVisibleSignDesigner()
    with pytest.raises(NotImplementedError, match="not supported"):
        designer.signature_text("hello")


# ---------------------------------------------------------------------------
# helper class
# ---------------------------------------------------------------------------
def test_identity_affine_transform_defaults() -> None:
    t = _IdentityAffineTransform()
    assert (t.m00, t.m11) == (1.0, 1.0)
    assert (t.m10, t.m01) == (0.0, 0.0)
    assert (t.m02, t.m12) == (0.0, 0.0)
