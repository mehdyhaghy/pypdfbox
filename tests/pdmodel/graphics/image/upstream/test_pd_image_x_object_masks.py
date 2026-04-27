"""Ported upstream tests from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/PDImageXObjectTest.java``
and the related mask-flow tests in ``TestImageXObject*.java``.

Translated from JUnit 5 to pytest per CLAUDE.md §"Test Porting Conventions".

Scope: typed accessors for ``/SMask``, ``/Mask`` (both stream and color-key
forms), ``/ImageMask`` / stencil aliases, and ``/SMaskInData``. Upstream
PDFBox exercises these accessors as a side-effect of its ``createFromImage``
factories and renderer round-trips; we cover them directly against synthetic
COS dictionaries so the parity tests do not depend on the rendering cluster.

Skipped upstream tests (require rendering-cluster work or factory cluster
that is intentionally out of scope for this change):

- ``testCreateFromBufferedImage`` and friends — depend on
  ``LosslessFactory`` / ``JPEGFactory`` building real image streams plus
  the renderer's Pillow-backed compositing. The factories are ported
  separately; the mask accessors covered here are factory-agnostic.
- ``testCheckSMaskInData`` — relies on parsing a real JPX stream to
  observe the SMaskInData hint round-tripped through the renderer.
  We cover the typed accessor in isolation here.
- Mask compositing tests (e.g. ``testMaskedRender``) — strictly renderer
  territory. PDImageXObject's job is to expose the typed mask handles;
  composing them onto the base image lives in the rendering cluster.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.graphics.image import PDImageXObject


def _make_image() -> PDImageXObject:
    return PDImageXObject(COSStream())


# ---------- /SMask round-trip (mirrors getSoftMask / setSoftMask) ----------


def test_set_and_get_soft_mask() -> None:
    image = _make_image()
    soft = _make_image()
    soft.set_width(32)
    soft.set_height(32)
    image.set_soft_mask(soft)

    fetched = image.get_soft_mask()
    assert fetched is not None
    assert fetched.get_cos_object() is soft.get_cos_object()


def test_get_soft_mask_absent_returns_none() -> None:
    assert _make_image().get_soft_mask() is None


# ---------- /Mask explicit-mask vs color-key parity ----------


def test_get_mask_returns_image_when_stream() -> None:
    image = _make_image()
    mask = _make_image()
    mask.set_image_mask(True)
    image.set_mask(mask)

    assert image.get_mask() is not None
    assert image.get_mask().get_cos_object() is mask.get_cos_object()
    # Upstream: when /Mask is a stream, color-key array accessor returns null.
    assert image.get_color_key_mask() is None


def test_get_color_key_mask_returns_array_when_array() -> None:
    image = _make_image()
    image.set_color_key_mask([0, 255])
    assert image.get_color_key_mask() == [0, 255]
    # Upstream: when /Mask is a color-key array, get_mask() returns null.
    assert image.get_mask() is None


def test_color_key_mask_preserves_pair_count() -> None:
    """Upstream stores n pairs (one per component); accessor must round-trip
    the full flat list, not just the first pair."""
    image = _make_image()
    raw = COSArray()
    for value in (10, 20, 30, 40, 50, 60):
        raw.add(COSInteger.get(value))
    image.get_cos_object().set_item(COSName.get_pdf_name("Mask"), raw)

    assert image.get_color_key_mask() == [10, 20, 30, 40, 50, 60]


# ---------- /ImageMask + stencil aliases ----------


def test_is_image_mask_default_false() -> None:
    assert _make_image().is_image_mask() is False
    assert _make_image().is_stencil() is False


def test_set_image_mask_true_round_trips() -> None:
    image = _make_image()
    image.set_image_mask(True)
    assert image.is_image_mask() is True
    # Stencil alias mirrors /ImageMask per upstream PDImage interface.
    assert image.is_stencil() is True


def test_set_stencil_writes_image_mask_entry() -> None:
    image = _make_image()
    image.set_stencil(True)
    assert (
        image.get_cos_object().get_boolean(
            COSName.get_pdf_name("ImageMask"), False
        )
        is True
    )


# ---------- /SMaskInData (JPXDecode-only hint) ----------


def test_smask_in_data_default_zero() -> None:
    assert _make_image().get_smask_in_data() == 0


@pytest.mark.parametrize("value", [0, 1, 2])
def test_set_smask_in_data_accepts_legal_values(value: int) -> None:
    image = _make_image()
    image.set_smask_in_data(value)
    assert image.get_smask_in_data() == value


def test_set_smask_in_data_rejects_illegal_value() -> None:
    image = _make_image()
    with pytest.raises(ValueError):
        image.set_smask_in_data(3)
