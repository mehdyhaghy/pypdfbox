"""Hand-written tests for
:class:`pypdfbox.pdmodel.graphics.color.pd_pattern.PDPattern`.

These exercise the API as pypdfbox uses it (lazy-resource attachment,
soft-resolution, snake-case ``to_string`` alias, structural predicates
unique to pypdfbox). The line-for-line port of the upstream surface
lives in ``upstream/test_pd_pattern.py``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.pd_resources import PDResources

# ---------- to_string alias ----------


def test_to_string_returns_literal_pattern() -> None:
    """``to_string`` is the snake_case alias for upstream
    ``toString()``. PDPattern.java line 141 returns the literal
    ``"Pattern"``; the alias must agree with ``__str__``."""
    cs = PDPattern()
    assert cs.to_string() == "Pattern"
    assert cs.to_string() == str(cs)


def test_to_string_returns_literal_for_uncolored_form() -> None:
    """Same literal regardless of construction form — upstream
    ``toString()`` ignores the underlying CS."""
    cs = PDPattern(PDDeviceRGB.INSTANCE)
    assert cs.to_string() == "Pattern"
    assert cs.to_string() == str(cs)


def test_to_string_does_not_delegate_to_get_name() -> None:
    """``toString`` and ``getName`` happen to coincide for Pattern;
    confirm both routes return the same literal independently."""
    cs = PDPattern()
    assert cs.to_string() == cs.get_name() == "Pattern"


# ---------- COS round-trip ----------


def test_cos_object_is_name_for_bare_form() -> None:
    """For the *colored* (bare-name) form, pypdfbox surfaces the
    plain ``/Pattern`` name as the COS object — matching the way
    PDF parsers see the pattern color space written as a name in
    a content stream / resource dict (PDF 32000-1 §8.6.6.2)."""
    cos = PDPattern().get_cos_object()
    assert cos == COSName.get_pdf_name("Pattern")


def test_cos_object_is_two_element_array_for_uncolored_form() -> None:
    """Array form ``[/Pattern <underlying CS>]`` — PDPattern.java line
    63-65."""
    cos = PDPattern(PDDeviceCMYK.INSTANCE).get_cos_object()
    assert isinstance(cos, COSArray)
    assert cos.size() == 2
    assert cos.get_object(0) == COSName.get_pdf_name("Pattern")


# ---------- structural predicates (pypdfbox enrichment) ----------


def test_is_colored_and_is_uncolored_are_inverses() -> None:
    colored = PDPattern()
    uncolored = PDPattern(PDDeviceRGB.INSTANCE)
    assert colored.is_colored() is not colored.is_uncolored()
    assert uncolored.is_colored() is not uncolored.is_uncolored()


def test_has_underlying_color_space_matches_is_uncolored() -> None:
    """Both predicates are structural proxies for the array-form
    construction. They must agree."""
    for cs in (
        PDPattern(),
        PDPattern(PDDeviceRGB.INSTANCE),
        PDPattern(PDDeviceGray.INSTANCE),
        PDPattern(PDDeviceCMYK.INSTANCE),
    ):
        assert cs.has_underlying_color_space() is cs.is_uncolored()


# ---------- resource lazy-attachment (pypdfbox enrichment) ----------


def test_set_resources_replaces_existing() -> None:
    res_a = PDResources()
    res_b = PDResources()
    cs = PDPattern(resources=res_a)
    assert cs.get_resources() is res_a
    cs.set_resources(res_b)
    assert cs.get_resources() is res_b


def test_clear_resources_detaches() -> None:
    cs = PDPattern(resources=PDResources())
    assert cs.has_resources()
    cs.clear_resources()
    assert not cs.has_resources()
    assert cs.get_resources() is None


def test_has_resources_reflects_attachment() -> None:
    cs = PDPattern()
    assert not cs.has_resources()
    cs.set_resources(PDResources())
    assert cs.has_resources()


# ---------- get_pattern error surface ----------


def test_get_pattern_raises_when_no_resources() -> None:
    """pypdfbox-specific guard — upstream constructor always sets
    resources eagerly; we accept lazy attachment so we have to
    detect the no-resources case explicitly."""
    cs = PDPattern()
    color = PDColor([], cs, COSName.get_pdf_name("P0"))
    with pytest.raises(OSError, match="resources"):
        cs.get_pattern(color)


def test_get_pattern_raises_when_color_lacks_pattern_name() -> None:
    cs = PDPattern(resources=PDResources())
    color = PDColor([0.5], cs)  # no pattern-name component
    with pytest.raises(OSError, match="no pattern name"):
        cs.get_pattern(color)


# ---------- get_pattern_or_none short-circuits ----------


def test_get_pattern_or_none_no_resources() -> None:
    cs = PDPattern()
    color = PDColor([], cs, COSName.get_pdf_name("P0"))
    assert cs.get_pattern_or_none(color) is None


def test_get_pattern_or_none_no_pattern_name() -> None:
    cs = PDPattern(resources=PDResources())
    color = PDColor([0.5], cs)
    assert cs.get_pattern_or_none(color) is None


def test_get_pattern_or_none_missing_name() -> None:
    cs = PDPattern(resources=PDResources())
    color = PDColor([], cs, COSName.get_pdf_name("Missing"))
    assert cs.get_pattern_or_none(color) is None


# ---------- to_rgb fall-through ----------


def test_to_rgb_uncolored_with_gray_underlying() -> None:
    rgb = PDPattern(PDDeviceGray.INSTANCE).to_rgb([0.5])
    assert rgb == pytest.approx((0.5, 0.5, 0.5), abs=1e-6)


def test_to_rgb_uncolored_with_cmyk_underlying() -> None:
    rgb = PDPattern(PDDeviceCMYK.INSTANCE).to_rgb([0.0, 0.0, 0.0, 0.0])
    assert rgb is not None
    assert len(rgb) == 3


def test_to_rgb_colored_returns_none_for_any_components() -> None:
    """Colored / shading patterns can't be resolved without rendering;
    upstream throws — we return ``None`` regardless of components."""
    cs = PDPattern()
    assert cs.to_rgb([]) is None
    assert cs.to_rgb([0.5, 0.5]) is None


# ---------- initial color singleton-ish ----------


def test_initial_color_is_empty_pattern_with_null_color_space() -> None:
    """Upstream ``EMPTY_PATTERN = new PDColor(new float[]{}, null)`` — a
    null colour space and no components. Closed in wave 1595 (was
    previously ``cs=self``)."""
    cs = PDPattern()
    initial = cs.get_initial_color()
    assert initial.get_color_space() is None
    assert initial.get_components() == []
