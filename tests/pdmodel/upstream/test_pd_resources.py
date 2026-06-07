"""Port of resource-dictionary patterns from PDFBox 3.0 upstream tests.

There is no dedicated ``PDResourcesTest.java`` in PDFBox 3.0 — the class is
exercised indirectly. This file ports the resource interactions found in:

- ``pdfbox/src/test/java/org/apache/pdfbox/pdfwriter/COSWriterTest.java``
  (default-resources font registration, ``put(COSName, PDFont)``)
- ``pdfbox/src/test/java/org/apache/pdfbox/multipdf/TestLayerUtility.java``
  (empty-resources construction)
- ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/
  optionalcontent/TestOptionalContentGroups.java``
  (property-list registration via ``add(PDPropertyList)``)

Translation conventions follow CLAUDE.md "Test Porting Conventions".
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDResources
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)


def test_construct_empty_resources() -> None:
    """``new PDResources()`` — TestLayerUtility line 123 / 174.

    The empty-arg constructor must produce a usable PDResources whose
    backing dictionary is empty."""
    resources = PDResources()
    assert resources.get_cos_object() is not None
    assert len(resources.get_font_names()) == 0
    assert len(resources.get_xobject_names()) == 0


def test_put_font_under_named_key() -> None:
    """``resources.put(COSName.getPDFName("Helv"), font1)`` —
    COSWriterTest line 123. Putting a font under an explicit COSName must
    register it under ``/Font`` keyed by that name."""
    resources = PDResources()
    helv = COSDictionary()
    helv.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    helv.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]

    resources.put(PDResources.FONT, COSName.get_pdf_name("Helv"), helv)

    assert resources.has_font(COSName.get_pdf_name("Helv"))
    assert [n.get_name() for n in resources.get_font_names()] == ["Helv"]


def test_add_form_xobject_uses_form_prefix() -> None:
    """Mirrors upstream ``PDResources.add(PDFormXObject)`` which routes
    through ``add(COSName.XOBJECT, "Form", form)`` (line 689)."""
    resources = PDResources()
    form = PDFormXObject(COSStream())

    name = resources.add(form)

    assert name.get_name().startswith("Form")
    assert resources.has_x_object(name)


def test_add_image_xobject_uses_im_prefix() -> None:
    """Mirrors upstream ``PDResources.add(PDImageXObject)`` which routes
    through ``add(COSName.XOBJECT, "Im", image)`` (line 677)."""
    resources = PDResources()
    image = PDImageXObject(COSStream())

    name = resources.add(image)

    assert name.get_name().startswith("Im")


def test_add_optional_content_group_uses_oc_prefix() -> None:
    """Mirrors upstream ``PDResources.add(PDPropertyList)`` (line 656) —
    OCG instances must be keyed ``oc<n>``, plain property lists ``Prop<n>``.
    Echoes the ``resources.add(ocg)`` pattern in TestOptionalContentGroups."""
    resources = PDResources()
    ocg = PDOptionalContentGroup("Layer 1")

    name = resources.add(ocg)

    assert name.get_name().startswith("oc")


def test_get_indirect_returns_none_for_missing_subdict() -> None:
    """Upstream ``getIndirect`` (line 485) returns ``null`` when the
    category sub-dictionary is missing."""
    resources = PDResources()
    assert resources.get_indirect(PDResources.FONT, COSName.get_pdf_name("F0")) is None


def test_get_indirect_returns_none_for_direct_entry() -> None:
    """Upstream ``getIndirect`` returns ``null`` when the entry exists but
    is a direct (inline) value, not an indirect ``COSObject`` reference."""
    resources = PDResources()
    resources.put(PDResources.FONT, COSName.get_pdf_name("F0"), COSDictionary())

    assert resources.get_indirect(PDResources.FONT, COSName.get_pdf_name("F0")) is None


def test_get_returns_resolved_entry() -> None:
    """Upstream ``get`` (line 504) returns the dereferenced COS value."""
    resources = PDResources()
    font = COSDictionary()
    resources.put(PDResources.FONT, COSName.get_pdf_name("F0"), font)

    assert resources.get(PDResources.FONT, COSName.get_pdf_name("F0")) is font


def test_get_returns_none_for_missing() -> None:
    """``get`` returns ``null`` for a missing entry."""
    resources = PDResources()
    assert resources.get(PDResources.FONT, COSName.get_pdf_name("Missing")) is None


def test_create_key_returns_unique_name() -> None:
    """Upstream ``createKey`` (line 740) seeds the counter to
    ``keySet().size()`` and pre-increments, so it is 1-based: the first key on
    an empty category is ``F1`` and the next is ``F2``."""
    resources = PDResources()
    first = resources.create_key(PDResources.FONT, "F")
    resources.put(PDResources.FONT, first, COSDictionary())
    second = resources.create_key(PDResources.FONT, "F")

    assert first.get_name() == "F1"
    assert second.get_name() == "F2"


def test_is_allowed_cache_for_form_xobject_is_true() -> None:
    """Upstream ``isAllowedCache`` (line 453) only inspects image XObjects;
    form XObjects always pass through unconditionally."""
    resources = PDResources()
    form = PDFormXObject(COSStream())

    assert resources.is_allowed_cache(form) is True


def test_is_allowed_cache_blocked_by_default_rgb_override() -> None:
    """When the resources have a ``DefaultRGB`` colour space and the image
    is tagged ``DeviceRGB``, ``isAllowedCache`` must return ``False``
    (PDFBOX-2370)."""
    resources = PDResources()
    # Register a DefaultRGB so the image's DeviceRGB inherits it.
    resources.put(
        PDResources.COLOR_SPACE,
        COSName.get_pdf_name("DefaultRGB"),
        COSDictionary(),
    )
    image_stream = COSStream()
    image_stream.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]
    image_stream.set_name(COSName.get_pdf_name("ColorSpace"), "DeviceRGB")  # type: ignore[attr-defined]
    image = PDImageXObject(image_stream)

    assert resources.is_allowed_cache(image) is False


def test_get_names_dispatches_by_kind() -> None:
    """Mirrors the upstream ``getNames(COSName)`` private helper that
    underpins all the public ``get*Names()`` accessors."""
    resources = PDResources()
    resources.put(PDResources.FONT, COSName.get_pdf_name("F0"), COSDictionary())

    assert [n.get_name() for n in resources.get_names(PDResources.FONT)] == ["F0"]
    assert resources.get_names(PDResources.XOBJECT) == []
