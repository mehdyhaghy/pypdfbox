"""Wave 1352 coverage-boost tests for
:mod:`pypdfbox.pdmodel.pd_resources`.

Closes the remaining uncovered branches:

* line 163 — :meth:`PDResources.get_indirect` happy path returning a
  ``COSObject`` reference.
* line 862 — :meth:`PDResources.is_allowed_cache` early-out when the
  image's ``get_cos_object()`` payload doesn't expose a callable
  ``get_name``.
* line 865 — early-out when the image's ColorSpace is missing
  (``get_name`` returned ``None``).
* line 870 — DeviceCMYK + DefaultCMYK override path.
* lines 875-879 — DeviceGray + DefaultGray override path, plus the
  final ``return not has_color_space(cs_name)`` for an unrecognised
  colour-space name.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSObject, COSStream
from pypdfbox.pdmodel import PDResources

# ---------- line 163: get_indirect with an indirect entry ----------


def test_get_indirect_returns_indirect_cos_object_reference() -> None:
    """When the resource entry is wrapped in a ``COSObject``, ``get_indirect``
    returns the wrapper unchanged — hits the ``return raw`` branch at line
    163."""
    resources = PDResources()
    real_font = COSDictionary()
    indirect = COSObject(7, 0, resolved=real_font)
    # Put through the underlying sub-dict directly so the indirect wrapper
    # survives — ``put()`` would unwrap it.
    sub = resources.get_cos_object()
    font_sub = COSDictionary()
    font_sub.set_item(COSName.get_pdf_name("F0"), indirect)
    sub.set_item(PDResources.FONT, font_sub)

    out = resources.get_indirect(PDResources.FONT, COSName.get_pdf_name("F0"))
    assert out is indirect


# ---------- line 862: image XObject with non-callable get_name ----------


def test_is_allowed_cache_payload_without_get_name_passes() -> None:
    """An image XObject whose underlying COS payload doesn't expose a
    callable ``get_name`` cannot have its colour space inspected; the
    method conservatively returns ``True`` (line 862)."""
    # Local import so the heavy graphics-image stack only loads when
    # the test actually runs.
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
        PDImageXObject,
    )

    image_stream = COSStream()
    image_stream.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]

    class _ShimImage(PDImageXObject):
        def get_cos_object(self) -> object:  # type: ignore[override]
            # Plain object — no get_name attribute at all.
            return object()

    image = _ShimImage(image_stream)
    resources = PDResources()
    assert resources.is_allowed_cache(image) is True


# ---------- line 865: cs_name_str is None ----------


def test_is_allowed_cache_image_with_no_colour_space_passes() -> None:
    """Image XObject without a ``/ColorSpace`` entry — ``get_name`` on
    the stream returns ``None``, hitting line 864-865."""
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
        PDImageXObject,
    )

    image_stream = COSStream()
    image_stream.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]
    # Deliberately no /ColorSpace set.
    image = PDImageXObject(image_stream)
    resources = PDResources()
    assert resources.is_allowed_cache(image) is True


# ---------- line 870: DeviceCMYK + DefaultCMYK ----------


def test_is_allowed_cache_blocked_by_default_cmyk_override() -> None:
    """A page that defines ``DefaultCMYK`` shadows the image's
    ``DeviceCMYK`` colour space — caching is forbidden (line 870)."""
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
        PDImageXObject,
    )

    resources = PDResources()
    resources.put(
        PDResources.COLOR_SPACE,
        COSName.get_pdf_name("DefaultCMYK"),
        COSDictionary(),
    )
    image_stream = COSStream()
    image_stream.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]
    image_stream.set_name(COSName.get_pdf_name("ColorSpace"), "DeviceCMYK")  # type: ignore[attr-defined]
    image = PDImageXObject(image_stream)
    assert resources.is_allowed_cache(image) is False


# ---------- lines 875-878: DeviceGray + DefaultGray ----------


def test_is_allowed_cache_blocked_by_default_gray_override() -> None:
    """DefaultGray override shadows DeviceGray on the image — line 878
    returns False."""
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
        PDImageXObject,
    )

    resources = PDResources()
    resources.put(
        PDResources.COLOR_SPACE,
        COSName.get_pdf_name("DefaultGray"),
        COSDictionary(),
    )
    image_stream = COSStream()
    image_stream.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]
    image_stream.set_name(COSName.get_pdf_name("ColorSpace"), "DeviceGray")  # type: ignore[attr-defined]
    image = PDImageXObject(image_stream)
    assert resources.is_allowed_cache(image) is False


# ---------- line 879: unknown colour-space name falls through ----------


def test_is_allowed_cache_falls_through_for_named_resource_colour_space() -> None:
    """An image referencing a custom colour-space name (not Device*)
    — caching is allowed iff the resources sub-dictionary does NOT
    already advertise that colour space (line 879).

    Two assertions:
      * resource has the name → cache forbidden (returns False);
      * resource lacks the name → cache allowed (returns True).
    """
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
        PDImageXObject,
    )

    image_stream = COSStream()
    image_stream.set_name(COSName.SUBTYPE, "Image")  # type: ignore[attr-defined]
    image_stream.set_name(COSName.get_pdf_name("ColorSpace"), "CustomCS")  # type: ignore[attr-defined]
    image = PDImageXObject(image_stream)

    resources_with = PDResources()
    resources_with.put(
        PDResources.COLOR_SPACE,
        COSName.get_pdf_name("CustomCS"),
        COSDictionary(),
    )
    assert resources_with.is_allowed_cache(image) is False

    resources_without = PDResources()
    assert resources_without.is_allowed_cache(image) is True
