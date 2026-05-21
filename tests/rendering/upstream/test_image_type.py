"""Upstream-equivalent parity tests for ``pypdfbox.rendering.ImageType``.

Upstream baseline: PDFBox 3.0.x.
Source: ``pdfbox/src/main/java/org/apache/pdfbox/rendering/ImageType.java``.

Upstream models five Java BufferedImage flavours (BINARY / GRAY / RGB /
ARGB / BGR) as an enum where each value implements
``toBufferedImageType()`` returning the matching ``BufferedImage.TYPE_*``
int constant. Upstream does NOT ship a JUnit for this enum directly; we
pin the member set, the int mapping, and the Pillow-mode bridge so a
re-sync that adds a new image type (or renames a constant) trips a test
failure.
"""
from __future__ import annotations

import pytest

from pypdfbox.rendering import ImageType
from pypdfbox.rendering.image_type import (
    TYPE_3BYTE_BGR,
    TYPE_BYTE_BINARY,
    TYPE_BYTE_GRAY,
    TYPE_INT_ARGB,
    TYPE_INT_RGB,
)


def test_enum_has_exactly_five_members_in_upstream_order() -> None:
    names = [member.name for member in ImageType]
    assert names == ["BINARY", "GRAY", "RGB", "ARGB", "BGR"]


def test_member_count_matches_upstream() -> None:
    assert len(list(ImageType)) == 5


@pytest.mark.parametrize(
    "member, expected_awt_type",
    [
        (ImageType.BINARY, TYPE_BYTE_BINARY),
        (ImageType.GRAY, TYPE_BYTE_GRAY),
        (ImageType.RGB, TYPE_INT_RGB),
        (ImageType.ARGB, TYPE_INT_ARGB),
        (ImageType.BGR, TYPE_3BYTE_BGR),
    ],
)
def test_to_buffered_image_type_returns_awt_constant(
    member: ImageType, expected_awt_type: int
) -> None:
    assert member.to_buffered_image_type() == expected_awt_type


def test_awt_constants_match_java_buffered_image_values() -> None:
    """The AWT BufferedImage int constants are part of the public Java
    contract — pin them so they don't drift if a future maintenance
    pass re-numbers the module-level ints.
    """
    assert TYPE_INT_RGB == 1
    assert TYPE_INT_ARGB == 2
    assert TYPE_3BYTE_BGR == 5
    assert TYPE_BYTE_GRAY == 10
    assert TYPE_BYTE_BINARY == 12


@pytest.mark.parametrize(
    "member, expected_pil_mode",
    [
        (ImageType.BINARY, "1"),
        (ImageType.GRAY, "L"),
        (ImageType.RGB, "RGB"),
        (ImageType.ARGB, "RGBA"),
        (ImageType.BGR, "RGB"),
    ],
)
def test_pil_mode_property_maps_to_pillow_mode_string(
    member: ImageType, expected_pil_mode: str
) -> None:
    """pypdfbox-only addition for the Pillow bridge. BGR collapses to
    RGB because Pillow has no packed BGR mode; callers that need real
    BGR pixel order swap channels at the boundary.
    """
    assert member.pil_mode == expected_pil_mode


def test_members_are_distinct_singletons() -> None:
    a, b, c, d, e = (
        ImageType.BINARY,
        ImageType.GRAY,
        ImageType.RGB,
        ImageType.ARGB,
        ImageType.BGR,
    )
    assert len({a, b, c, d, e}) == 5


@pytest.mark.parametrize(
    "member",
    list(ImageType),
    ids=[m.name for m in ImageType],
)
def test_value_round_trips_via_index(member: ImageType) -> None:
    """``ImageType[name]`` mirrors Java ``ImageType.valueOf(name)``."""
    assert ImageType[member.name] is member


def test_pillow_can_open_mode_string_for_every_member() -> None:
    """The ``pil_mode`` string must round-trip through ``Image.new``
    — i.e. it must be a real Pillow mode, not a typo. This is the
    Python equivalent of upstream's implicit guarantee that the
    BufferedImage.TYPE_* constants are accepted by
    ``new BufferedImage(w, h, type)``.
    """
    from PIL import Image

    for member in ImageType:
        img = Image.new(member.pil_mode, (1, 1))
        assert img.mode == member.pil_mode
