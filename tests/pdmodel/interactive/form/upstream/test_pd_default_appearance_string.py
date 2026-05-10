"""Ported from upstream ``PDDefaultAppearanceStringTest.java``.

Translation conventions follow ``CLAUDE.md``:

- ``@BeforeEach setUp()`` → module-scoped pytest fixture.
- ``assertEquals(expected, actual, delta)`` → ``actual == pytest.approx(expected, abs=delta)``.
- ``assertThrows(IOException.class, ...)`` → ``with pytest.raises(OSError): ...``.
- ``COSString::new`` → ``COSString(value)``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSString
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.form.pd_default_appearance_string import (
    PDDefaultAppearanceString,
)
from pypdfbox.pdmodel.pd_resources import PDResources


@pytest.fixture
def fixture() -> tuple[PDResources, COSName, PDType1Font]:
    """Equivalent of upstream ``@BeforeEach setUp()`` (Java lines 40-48).

    Builds a fresh ``PDResources`` and registers a ``PDType1Font``
    spelling Helvetica; the resource name allocated by
    :meth:`PDResources.add` is captured for use in the /DA strings below.
    """
    resources = PDResources()
    helvetica = PDType1Font()
    helvetica.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), PDType1Font.HELVETICA
    )
    helvetica.get_cos_object().set_name(COSName.get_pdf_name("Subtype"), "Type1")
    font_resource_name = resources.add(helvetica)
    return resources, font_resource_name, helvetica


def test_parse_da_string(
    fixture: tuple[PDResources, COSName, PDType1Font],
) -> None:
    """Ports upstream ``testParseDAString`` (Java lines 51-63).

    Parses ``/<resourceName> 12 Tf 0.019 0.305 0.627 rg`` and asserts
    the resolved font / size / colour matches.
    """
    resources, font_resource_name, helvetica = fixture
    sample_string = COSString(
        "/" + font_resource_name.get_name() + " 12 Tf 0.019 0.305 0.627 rg"
    )

    default_appearance_string = PDDefaultAppearanceString(sample_string, resources)

    assert default_appearance_string.get_font_size() == pytest.approx(12, abs=0.001)
    # Upstream asserts ``assertEquals(helvetica, ...)`` via Java's
    # ``equals``; pypdfbox doesn't define ``__eq__`` on ``PDFont``, so
    # we resolve through the font's BaseFont name (which uniquely
    # identifies Helvetica via the Standard14 table).
    resolved_font = default_appearance_string.get_font()
    assert resolved_font is not None
    assert resolved_font.get_name() == helvetica.get_name()

    font_color = default_appearance_string.get_font_color()
    assert font_color is not None
    assert font_color.get_color_space() is PDDeviceRGB.INSTANCE
    components = font_color.get_components()
    assert components[0] == pytest.approx(0.019, abs=0.0001)
    assert components[1] == pytest.approx(0.305, abs=0.0001)
    assert components[2] == pytest.approx(0.627, abs=0.0001)


def test_font_resource_unavailable(
    fixture: tuple[PDResources, COSName, PDType1Font],
) -> None:
    """Ports upstream ``testFontResourceUnavailable`` (Java lines 66-72).

    A /DA referencing ``/Helvetica`` when /DR has no such resource must
    raise (upstream ``IOException``; pypdfbox ``OSError`` per
    ``CLAUDE.md`` mapping).
    """
    resources, _, _ = fixture
    sample_string = COSString("/Helvetica 12 Tf 0.019 0.305 0.627 rg")
    with pytest.raises(OSError):
        PDDefaultAppearanceString(sample_string, resources)


def test_wrong_number_of_color_arguments(
    fixture: tuple[PDResources, COSName, PDType1Font],
) -> None:
    """Ports upstream ``testWrongNumberOfColorArguments`` (Java lines 75-81).

    Two-component ``rg`` is invalid; constructor must raise.
    """
    resources, _, _ = fixture
    sample_string = COSString("/Helvetica 12 Tf 0.305 0.627 rg")
    with pytest.raises(OSError):
        PDDefaultAppearanceString(sample_string, resources)
