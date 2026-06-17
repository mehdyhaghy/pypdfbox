"""Live PDFBox differential parity for the image-XObject ``/SMask`` (a separate
grayscale image giving per-pixel alpha for the base image, PDF 32000-1
§8.9.5.4) as exposed by ``PDImageXObject.getImage()``.

This is the *image* ``/SMask`` — DISTINCT from the ExtGState ``/SMask`` (waves
1455/1458) and from the explicit ``/Mask`` stencil (covered at the render level
by ``tests/rendering/oracle/test_image_mask_oracle.py`` and at the dims level by
``test_mask_mismatched_dims_oracle.py``). Apache PDFBox's
``PDImageXObject.getImage()`` returns an ARGB ``BufferedImage`` with the
``/SMask`` composited as the alpha channel; pypdfbox's ``get_image()`` must
return an RGBA image whose alpha plane agrees.

The cases pin the two behaviours singled out by the wave brief that the
existing oracles do NOT cover at the ``getImage()`` ARGB level:

* **smask_gradient_same_dims** — control: a 64×64 base RGB with a 64×64
  grayscale ``/SMask`` left→right alpha gradient. Alpha must fade across the
  image; colour stays solid.
* **smask_scaled_up** — a 64×64 base RGB with a SMALLER 8×8 ``/SMask`` whose
  samples form a left-opaque / right-transparent split. The mask is upscaled
  to the base's 64×64 (per spec the SMask maps across the base's unit square);
  a renderer that applied the 8×8 mask 1:1 at the top-left would mask only an
  8×8 corner and diverge grossly on the alpha plane.
* **smask_decode_inverted** — a 64×64 base RGB with a 64×64 ``/SMask`` carrying
  ``/Decode [1 0]``, which inverts the grayscale samples → the alpha is the
  complement of the raw mask samples. A renderer that ignored the SMask's own
  ``/Decode`` produces the un-inverted alpha and diverges.

We compare ``PDImageXObject.getImage()`` directly (NO page render), emitting a
16×16 per-channel (R,G,B,A) average grid via ``oracle/probes/ImageSoftMaskProbe.java``.
Pixel-exact parity is impossible (Pillow vs Java2D resample), so we gate the
fingerprint at ``MAD < 6`` / ``MAXDIFF < 60`` per channel — the established
image-oracle tolerance. Guard tests prove the gate detects an ignored-SMask /
un-scaled-SMask / ignored-/Decode regression.

Fixtures are tiny one-page PDFs synthesised in-memory (no committed binaries).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60
_BASE = 64  # base image side, px


def _channel_grid(img: Image.Image, channel: int) -> list[int]:
    """16×16 average of one channel (0=R,1=G,2=B,3=A) over an RGBA image —
    identical integer-division cell mapping to ``ImageSoftMaskProbe.java``."""
    rgba = img.convert("RGBA")
    width, height = rgba.size
    px = rgba.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            total[idx] += px[x, y][channel]
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 0 for i in range(_GRID * _GRID)
    ]


def _oracle_channels(fixture: Path) -> dict[str, list[int]]:
    """Run ImageSoftMaskProbe on the first image XObject; parse the four
    16×16 channel grids (r,g,b,a) plus the exact (w, h)."""
    line = next(
        ln
        for ln in run_probe_text("ImageSoftMaskProbe", str(fixture)).splitlines()
        if ln.startswith("smask ")
    )
    tokens = line.split()
    fields: dict[str, str] = {}
    i = 1
    keys_single = {"page", "name", "w", "h"}
    while i < len(tokens):
        key = tokens[i]
        if key in ("r", "g", "b", "a") or key in keys_single:
            fields[key] = tokens[i + 1]
            i += 2
        else:
            i += 2
    out: dict[str, list[int]] = {"_w": [int(fields["w"])], "_h": [int(fields["h"])]}
    for ch in ("r", "g", "b", "a"):
        grid = [int(v) for v in fields[ch].split(",")]
        assert len(grid) == _GRID * _GRID
        out[ch] = grid
    return out


def _attach_smask(
    doc: PDDocument,
    base: PDImageXObject,
    mask_img: Image.Image,
    decode: list[float] | None = None,
) -> None:
    """Build an 8-bit DeviceGray ``/SMask`` Image XObject from ``mask_img``
    (mode "L") and attach it to ``base`` via ``set_soft_mask``. ``decode``,
    when given, is written as the SMask's own ``/Decode`` array."""
    smask = LosslessFactory.create_from_image(doc, mask_img.convert("L"))
    if decode is not None:
        smask.set_decode(decode)
    base.set_soft_mask(smask)
    assert base.has_soft_mask()


def _one_image_pdf(path: Path, build) -> None:
    """One-page PDF whose only image XObject is produced by ``build(doc)``."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    image = build(doc)
    resources = PDResources()
    name = resources.add_x_object(image)
    page.set_resources(resources)
    cos_doc = doc.get_document()
    content = f"q 100 0 0 100 10 10 cm /{name.get_name()} Do Q".encode("ascii")
    stream = COSStream(cos_doc.scratch_file)
    with stream.create_output_stream() as out:
        out.write(content)
    page.get_cos_object().set_item(COSName.get_pdf_name("Contents"), stream)
    doc.save(str(path))
    doc.close()


def _build_gradient_same_dims(path: Path) -> None:
    def build(doc: PDDocument) -> PDImageXObject:
        base = Image.new("RGB", (_BASE, _BASE), (220, 40, 40))
        alpha = Image.new("L", (_BASE, _BASE))
        apx = alpha.load()
        for x in range(_BASE):
            col = round(x * 255 / (_BASE - 1))
            for y in range(_BASE):
                apx[x, y] = col
        image = LosslessFactory.create_from_image(doc, base)
        _attach_smask(doc, image, alpha)
        return image

    _one_image_pdf(path, build)


def _build_scaled_up(path: Path) -> None:
    def build(doc: PDDocument) -> PDImageXObject:
        base = Image.new("RGB", (_BASE, _BASE), (40, 80, 220))
        # 8×8 SMask: left half opaque (255), right half transparent (0).
        small = Image.new("L", (8, 8), 0)
        spx = small.load()
        for x in range(8):
            for y in range(8):
                spx[x, y] = 255 if x < 4 else 0
        image = LosslessFactory.create_from_image(doc, base)
        _attach_smask(doc, image, small)
        return image

    _one_image_pdf(path, build)


def _build_decode_inverted(path: Path) -> None:
    def build(doc: PDDocument) -> PDImageXObject:
        base = Image.new("RGB", (_BASE, _BASE), (60, 200, 90))
        # Raw mask samples: left opaque (255), right transparent (0). With
        # /Decode [1 0] the samples invert → left transparent, right opaque.
        raw = Image.new("L", (_BASE, _BASE), 0)
        rpx = raw.load()
        for x in range(_BASE):
            for y in range(_BASE):
                rpx[x, y] = 255 if x < _BASE // 2 else 0
        image = LosslessFactory.create_from_image(doc, base)
        _attach_smask(doc, image, raw, decode=[1.0, 0.0])
        return image

    _one_image_pdf(path, build)


_BUILDERS = {
    "smask_gradient_same_dims": _build_gradient_same_dims,
    "smask_scaled_up": _build_scaled_up,
    "smask_decode_inverted": _build_decode_inverted,
}


def _pypdfbox_image(fixture: Path) -> Image.Image:
    """Reload ``fixture`` and return ``getImage()`` of its single image XObject."""
    with PDDocument.load(fixture) as doc:
        resources = doc.get_page(0).get_resources()
        name = next(iter(resources.get_x_object_names()))
        image = resources.get_x_object(name)
        out = image.get_image()
    assert out is not None
    return out.convert("RGBA")


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_image_smask_get_image_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """``PDImageXObject.getImage()`` must agree with Apache PDFBox's ARGB
    decode of the same image-``/SMask`` fixture across all four channels."""
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)

    java = _oracle_channels(fixture)
    py_img = _pypdfbox_image(fixture)

    # Exact decoded dimensions — a mismatch is a real bug, not resample noise.
    assert (py_img.width, py_img.height) == (java["_w"][0], java["_h"][0]), (
        f"{label}: getImage() dims diverge from PDFBox: "
        f"pypdfbox={py_img.size} java=({java['_w'][0]},{java['_h'][0]})"
    )

    for ch_idx, ch in enumerate(("r", "g", "b", "a")):
        py_grid = _channel_grid(py_img, ch_idx)
        diffs = [abs(a - b) for a, b in zip(java[ch], py_grid, strict=True)]
        mad = sum(diffs) / len(diffs)
        maxdiff = max(diffs)
        assert mad < _MAD_TOLERANCE, (
            f"{label}: channel {ch!r} mean abs cell diff {mad:.2f} >= "
            f"{_MAD_TOLERANCE} (maxdiff={maxdiff}) — SMask mis-applied, not resample"
        )
        assert maxdiff < _MAXDIFF_TOLERANCE, (
            f"{label}: channel {ch!r} worst cell diff {maxdiff} >= "
            f"{_MAXDIFF_TOLERANCE} (mad={mad:.2f}) — a region diverges far beyond resample"
        )


@requires_oracle
def test_scaled_smask_fades_left_to_right(tmp_path: Path) -> None:
    """Direct proof the 8×8 SMask is upscaled across the whole 64×64 base
    (not applied 1:1 at the top-left): the alpha plane must be opaque on the
    left half and transparent on the right half of the decoded image."""
    fixture = tmp_path / "smask_scaled_up.pdf"
    _build_scaled_up(fixture)
    img = _pypdfbox_image(fixture)
    apx = img.load()
    y = _BASE // 2
    assert apx[8, y][3] > 200, "scaled SMask left half not opaque — applied 1:1?"
    assert apx[_BASE - 8, y][3] < 60, "scaled SMask right half not transparent"


@requires_oracle
def test_inverted_decode_flips_alpha(tmp_path: Path) -> None:
    """Direct proof the SMask's ``/Decode [1 0]`` is applied: raw samples are
    left-opaque/right-transparent, so with the inverting decode the alpha must
    be transparent on the LEFT and opaque on the RIGHT. A renderer ignoring the
    SMask /Decode would leave the raw (un-inverted) alpha."""
    fixture = tmp_path / "smask_decode_inverted.pdf"
    _build_decode_inverted(fixture)
    img = _pypdfbox_image(fixture)
    apx = img.load()
    y = _BASE // 2
    assert apx[8, y][3] < 60, "decode-inverted SMask left not transparent — /Decode ignored"
    assert apx[_BASE - 8, y][3] > 200, "decode-inverted SMask right not opaque"


@requires_oracle
def test_ignored_smask_would_fail_alpha_gate(tmp_path: Path) -> None:
    """Guard the gate: an image with a ``/SMask`` whose alpha is IGNORED
    (opaque raster, alpha 255 everywhere) must land outside tolerance on the
    alpha channel against PDFBox's correct ARGB decode — proving the gate
    detects a dropped SMask rather than passing both."""
    fixture = tmp_path / "smask_gradient_same_dims.pdf"
    _build_gradient_same_dims(fixture)
    java = _oracle_channels(fixture)

    # Reconstruct the opaque (alpha-255) raster the old stub returned.
    with PDDocument.load(fixture) as doc:
        resources = doc.get_page(0).get_resources()
        name = next(iter(resources.get_x_object_names()))
        image = resources.get_x_object(name)
        opaque = image.to_pil_image().convert("RGBA")
    py_alpha = _channel_grid(opaque, 3)

    diffs = [abs(a - b) for a, b in zip(java["a"], py_alpha, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: an ignored image /SMask passes the alpha MAD gate "
        f"(observed mad={mad:.2f})"
    )
