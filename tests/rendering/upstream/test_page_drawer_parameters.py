"""Upstream-equivalent parity tests for
``pypdfbox.rendering.PageDrawerParameters``.

Upstream baseline: PDFBox 3.0.x.
Source: ``pdfbox/src/main/java/org/apache/pdfbox/rendering/PageDrawerParameters.java``.

Upstream's class is a final, package-private parameter bundle handed
from ``PDFRenderer`` to ``PageDrawer.__init__`` so subclassed page
drawers (the ``CustomPageDrawer`` example pattern) can fish out the
renderer, page, subsampling flag, destination, AWT rendering hints, and
image-downscaling threshold without breaking the public ``PageDrawer``
ctor signature. Upstream has no dedicated JUnit; we pin the six getters
and the constructor argument round-trip here so any future re-arrange
catches.
"""
from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer, RenderDestination
from pypdfbox.rendering.page_drawer_parameters import PageDrawerParameters


@pytest.fixture
def renderer_and_page() -> tuple[PDFRenderer, PDPage, PDDocument]:
    document = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
    document.add_page(page)
    renderer = PDFRenderer(document)
    try:
        yield renderer, page, document
    finally:
        document.close()


def test_constructor_round_trips_every_field(
    renderer_and_page: tuple[PDFRenderer, PDPage, PDDocument],
) -> None:
    renderer, page, _doc = renderer_and_page
    hints: dict[str, Any] = {"hint_a": 1, "hint_b": "two"}
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=True,
        destination=RenderDestination.PRINT,
        rendering_hints=hints,
        image_downscaling_optimization_threshold=0.75,
    )
    assert params.get_renderer() is renderer
    assert params.get_page() is page
    assert params.is_subsampling_allowed() is True
    assert params.get_destination() is RenderDestination.PRINT
    assert params.get_rendering_hints() is hints
    assert params.get_image_downscaling_optimization_threshold() == pytest.approx(0.75)


def test_subsampling_flag_coerces_truthy_values_to_bool(
    renderer_and_page: tuple[PDFRenderer, PDPage, PDDocument],
) -> None:
    """Upstream stores the field as a Java ``boolean``; the Python port
    coerces via ``bool(...)`` so passing ``1`` or ``"x"`` round-trips
    as ``True``.
    """
    renderer, page, _doc = renderer_and_page
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=1,  # type: ignore[arg-type]
        destination=RenderDestination.VIEW,
        rendering_hints=None,
        image_downscaling_optimization_threshold=0.0,
    )
    assert params.is_subsampling_allowed() is True


def test_subsampling_flag_coerces_falsy_values_to_bool(
    renderer_and_page: tuple[PDFRenderer, PDPage, PDDocument],
) -> None:
    renderer, page, _doc = renderer_and_page
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=0,  # type: ignore[arg-type]
        destination=RenderDestination.VIEW,
        rendering_hints=None,
        image_downscaling_optimization_threshold=0.0,
    )
    assert params.is_subsampling_allowed() is False


def test_threshold_coerces_to_float(
    renderer_and_page: tuple[PDFRenderer, PDPage, PDDocument],
) -> None:
    """Upstream field is a Java ``float`` — passing an ``int`` must
    round-trip through ``float(...)``.
    """
    renderer, page, _doc = renderer_and_page
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=False,
        destination=RenderDestination.VIEW,
        rendering_hints=None,
        image_downscaling_optimization_threshold=2,  # type: ignore[arg-type]
    )
    threshold = params.get_image_downscaling_optimization_threshold()
    assert isinstance(threshold, float)
    assert threshold == 2.0


def test_rendering_hints_pass_through_unchanged(
    renderer_and_page: tuple[PDFRenderer, PDPage, PDDocument],
) -> None:
    """Upstream's ``getRenderingHints()`` returns the same map reference
    passed to the constructor — no defensive copy. Pin that contract.
    """
    renderer, page, _doc = renderer_and_page
    hints: list[Any] = ["a", "b"]
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=False,
        destination=RenderDestination.EXPORT,
        rendering_hints=hints,
        image_downscaling_optimization_threshold=0.0,
    )
    assert params.get_rendering_hints() is hints


def test_destination_field_accepts_every_enum_member(
    renderer_and_page: tuple[PDFRenderer, PDPage, PDDocument],
) -> None:
    renderer, page, _doc = renderer_and_page
    for destination in RenderDestination:
        params = PageDrawerParameters(
            renderer=renderer,
            page=page,
            subsampling_allowed=False,
            destination=destination,
            rendering_hints=None,
            image_downscaling_optimization_threshold=0.0,
        )
        assert params.get_destination() is destination


def test_class_uses_slots_to_match_upstream_final_fields(
    renderer_and_page: tuple[PDFRenderer, PDPage, PDDocument],
) -> None:
    """Upstream marks every field ``private final`` — there is no
    public mutator. pypdfbox enforces immutability via ``__slots__``
    listing all six fields. Pin so a refactor that drops slots gets
    caught.
    """
    renderer, page, _doc = renderer_and_page
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=False,
        destination=RenderDestination.VIEW,
        rendering_hints=None,
        image_downscaling_optimization_threshold=0.0,
    )
    assert not hasattr(params, "__dict__")
    expected_slots = {
        "_renderer",
        "_page",
        "_subsampling_allowed",
        "_destination",
        "_rendering_hints",
        "_image_downscaling_optimization_threshold",
    }
    assert set(PageDrawerParameters.__slots__) == expected_slots
