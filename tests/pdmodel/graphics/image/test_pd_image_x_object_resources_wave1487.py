"""Wave 1487 — pin the ``resources`` linkage on ``PDImageXObject``.

Upstream ``PDXObject.createXObject`` threads its ``PDResources`` argument into
``new PDImageXObject(new PDStream(stream), resources)``. The image keeps that
reference so ``getColorSpace()`` can (a) resolve a *named* ``/ColorSpace``
against the page's ``/Resources/ColorSpace`` subdictionary (PDF 32000-1
§8.9.5.2) and (b) consult/populate the document-level ResourceCache for an
indirect colour-space reference. pypdfbox's constructor dropped the parameter
(a deferred follow-up); these tests pin the restored behaviour.

Also pins the per-instance decoded-image cache (upstream
``SoftReference<BufferedImage> cachedImage`` + ``cachedImageSubsampling``):
full-region renders are cached preferring the lowest subsampling seen, and
``set_color_space`` invalidates the cache (upstream has no ``setImage`` —
invalidation happens via ``setColorSpace``, Java line 950).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache
from pypdfbox.pdmodel.pd_resources import PDResources


def _device_rgb_image_stream() -> COSStream:
    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))  # type: ignore[attr-defined]
    stream.set_int(COSName.get_pdf_name("Width"), 1)
    stream.set_int(COSName.get_pdf_name("Height"), 1)
    return stream


# ---------- resources=None backward-compatible path ----------


def test_resources_default_none_constructor():
    image = PDImageXObject(COSStream())
    assert image._resources is None


def test_named_colorspace_unresolvable_without_resources():
    # A bare-name /ColorSpace that only exists in /Resources/ColorSpace
    # cannot resolve when no resources are threaded — matches upstream's
    # resources==null constructors returning a name that PDColorSpace.create
    # cannot resolve.
    stream = _device_rgb_image_stream()
    stream.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("CS0"))
    image = PDImageXObject(stream)  # no resources
    assert image.get_color_space() is None


# ---------- named colourspace resolves through resources ----------


def test_named_colorspace_resolves_through_resources():
    resources = PDResources()
    # Register /Resources/ColorSpace/CS0 -> DeviceRGB array form.
    cs_array = COSArray()
    cs_array.add(COSName.get_pdf_name("DeviceRGB"))
    resources.put(
        COSName.get_pdf_name("ColorSpace"),
        COSName.get_pdf_name("CS0"),
        cs_array,
    )
    stream = _device_rgb_image_stream()
    stream.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("CS0"))

    image = PDImageXObject(stream, resources)
    cs = image.get_color_space()
    assert cs is PDDeviceRGB.INSTANCE


def test_create_x_object_threads_resources_into_image():
    resources = PDResources()
    cs_array = COSArray()
    cs_array.add(COSName.get_pdf_name("DeviceRGB"))
    resources.put(
        COSName.get_pdf_name("ColorSpace"),
        COSName.get_pdf_name("CS0"),
        cs_array,
    )
    stream = _device_rgb_image_stream()
    stream.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("CS0"))

    xobj = PDXObject.create_x_object(stream, resources)
    assert isinstance(xobj, PDImageXObject)
    assert xobj._resources is resources
    assert xobj.get_color_space() is PDDeviceRGB.INSTANCE


def test_get_x_object_threads_resources_into_image():
    resources = PDResources()
    cs_array = COSArray()
    cs_array.add(COSName.get_pdf_name("DeviceRGB"))
    resources.put(
        COSName.get_pdf_name("ColorSpace"),
        COSName.get_pdf_name("CS0"),
        cs_array,
    )
    stream = _device_rgb_image_stream()
    stream.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("CS0"))
    img_name = resources.add_x_object(PDImageXObject(stream))

    fetched = resources.get_x_object(img_name)
    assert isinstance(fetched, PDImageXObject)
    assert fetched._resources is resources
    assert fetched.get_color_space() is PDDeviceRGB.INSTANCE


# ---------- indirect /ColorSpace hits the resource cache ----------


def test_indirect_colorspace_caches_via_resource_cache():
    from pypdfbox.cos.cos_object import COSObject

    cache = DefaultResourceCache()
    resources = PDResources(resource_cache=cache)

    # An indirect ICCBased colour space referenced by the image's /ColorSpace.
    icc_stream = COSStream()
    icc_stream.set_int(COSName.get_pdf_name("N"), 3)
    cs_array = COSArray()
    cs_array.add(COSName.get_pdf_name("ICCBased"))
    cs_array.add(icc_stream)
    indirect = COSObject(7, 0, resolved=cs_array)

    stream = _device_rgb_image_stream()
    stream.set_item(COSName.get_pdf_name("ColorSpace"), indirect)

    image = PDImageXObject(stream, resources)
    first = image.get_color_space()
    assert isinstance(first, PDICCBased)
    # Second call must return the *same* cached wrapper instance — proving the
    # ResourceCache get/put linkage threaded through resources works.
    second = image.get_color_space()
    assert second is first
    # And the cache actually holds it under the indirect ref.
    assert cache.get_color_space(indirect) is first


# ---------- per-instance decoded-image cache (cachedImage) ----------


def test_get_image_caches_decoded_raster():
    # 1x1 DeviceRGB raster, one red pixel.
    stream = _device_rgb_image_stream()
    stream.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB"))
    stream.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    with stream.create_output_stream() as out:
        out.write(b"\xff\x00\x00")
    image = PDImageXObject(stream)

    first = image.get_image()
    assert first is not None
    second = image.get_image()
    # Cache hit: same object returned, not re-decoded.
    assert second is first


def test_set_color_space_invalidates_image_cache():
    # Upstream has no setImage; the decoded-image cache is invalidated by
    # setColorSpace (``colorSpace = null; cachedImage = null;``, Java 945-951).
    stream = _device_rgb_image_stream()
    stream.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB"))
    stream.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    with stream.create_output_stream() as out:
        out.write(b"\xff\x00\x00")
    image = PDImageXObject(stream)

    first = image.get_image()
    assert first is not None
    cs_first = image.get_color_space()
    assert cs_first is PDDeviceRGB.INSTANCE

    image.set_color_space(PDDeviceRGB.INSTANCE)
    # Both per-instance caches reset: a fresh decode and a fresh wrapper.
    fresh = image.get_image()
    assert fresh is not None
    assert fresh is not first


def test_subsampled_full_region_render_is_cached():
    # Upstream caches full-region renders at ANY subsampling level,
    # preferring the lowest level seen (cachedImageSubsampling, Java 514-519).
    stream = _device_rgb_image_stream()
    stream.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB"))
    stream.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    with stream.create_output_stream() as out:
        out.write(b"\xff\x00\x00")
    image = PDImageXObject(stream)

    sub2_first = image.get_image(subsampling=2)
    assert sub2_first is not None
    # Same level again → cache hit.
    assert image.get_image(subsampling=2) is sub2_first

    # A lower (higher-quality) level replaces the cache ...
    full = image.get_image()
    assert full is not None
    assert full is not sub2_first
    assert image.get_image() is full
    # ... and a higher level neither hits nor replaces it.
    sub2_again = image.get_image(subsampling=2)
    assert sub2_again is not sub2_first
    assert image.get_image() is full


def test_region_render_never_cached():
    stream = _device_rgb_image_stream()
    stream.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB"))
    stream.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    with stream.create_output_stream() as out:
        out.write(b"\xff\x00\x00")
    image = PDImageXObject(stream)

    image.get_image(region=(0, 0, 1, 1))
    assert image._cached_image is None
