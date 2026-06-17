"""Live PDFBox differential parity for a **Separation** Image XObject carrying
an explicit ``/Decode`` array — proves pypdfbox applies ``/Decode`` (including
an inverted ``[1 0]``) to the raw tint samples BEFORE running the Separation
tint transform, exactly as Apache PDFBox does.

PDFBox's ``SampledImageReader`` maps every raw sample through
``decode[0] + sample/maxVal * (decode[1] - decode[0])`` into the colour space's
component range *before* ``PDSeparation.toRGBImage`` evaluates the tint
transform (PDF 32000-1 §8.9.5.2). So for a single-component Separation:

* **default ``[0 1]``** — the tint ramp is left dark → right light (raw 0 →
  tint 0.0, raw 255 → tint 1.0); the tint transform here maps tint t → an
  RGB gray ``(t, t, t)``.
* **inverted ``[1 0]``** — the ramp reverses (raw 0 → tint 1.0): left light →
  right dark.

Before wave 1455 pypdfbox's ``_decode_devicen_to_rgb`` ignored ``/Decode``
entirely, so both decode forms produced the *same* ramp — a real divergence
from PDFBox (regression pin below: default must differ from inverted, and both
must match PDFBox).

Signal: ``oracle/probes/SeparationDecodeImageProbe.java`` emits every pixel of
the decoded raster's middle scanline as ``r,g,b`` triples. Java2D vs Pillow
sub-pixel rounding is tiny on a flat synthetic ramp, so we gate per-channel
with a small tolerance; the default-vs-inverted *reversal* is asserted
structurally (it is gross, not a rounding artefact).

Fixtures are tiny one-page PDFs synthesised in-memory (no committed binaries).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_W, _H = 32, 8
_MB = 200  # media-box side, pt
# Flat synthetic ramp — only codec rounding differs between Java2D and Pillow.
_CHANNEL_TOLERANCE = 4


def _tint_transform_func() -> COSDictionary:
    """Type-2 exponential tint transform: single tint t → DeviceRGB (t, t, t)
    (C0 = [0 0 0], C1 = [1 1 1], N = 1) — a linear tint → gray ramp."""
    d = COSDictionary()
    d.set_item("FunctionType", COSInteger.get(2))
    dom = COSArray()
    dom.add(COSFloat(0.0))
    dom.add(COSFloat(1.0))
    d.set_item("Domain", dom)
    c0 = COSArray()
    for _ in range(3):
        c0.add(COSFloat(0.0))
    d.set_item("C0", c0)
    c1 = COSArray()
    for _ in range(3):
        c1.add(COSFloat(1.0))
    d.set_item("C1", c1)
    d.set_item("N", COSFloat(1.0))
    return d


def _separation_cs() -> COSArray:
    """``[/Separation /MyColor /DeviceRGB <tint transform>]``."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("MyColor"))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    arr.add(_tint_transform_func())
    return arr


def _separation_image(decode: list[float]) -> PDImageXObject:
    """8-bpc single-component Separation image: left→right tint ramp 0..255,
    carrying the given ``/Decode`` array."""
    stream = COSStream()
    stream.set_raw_data(
        bytes(min(255, x * 256 // _W) for _y in range(_H) for x in range(_W))
    )
    image = PDImageXObject(stream)
    image.set_width(_W)
    image.set_height(_H)
    image.set_bits_per_component(8)
    stream.set_item("ColorSpace", _separation_cs())
    arr = COSArray()
    for v in decode:
        arr.add(COSFloat(v))
    stream.set_item("Decode", arr)
    return image


def _save(path: Path, decode: list[float]) -> None:
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    cs = PDPageContentStream(doc, page)
    cs.draw_image(_separation_image(decode), 40, 60, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _oracle_row(fixture: Path) -> list[tuple[int, int, int]]:
    """Run SeparationDecodeImageProbe and parse the single image line's middle
    scanline into a list of (r, g, b) triples."""
    lines = [
        ln
        for ln in run_probe_text(
            "SeparationDecodeImageProbe", str(fixture)
        ).splitlines()
        if ln
    ]
    assert len(lines) == 1, f"expected one image, probe emitted: {lines!r}"
    tokens = lines[0].split()
    row_at = tokens.index("row") + 1
    triples = []
    for tok in tokens[row_at:]:
        r, g, b = (int(v) for v in tok.split(","))
        triples.append((r, g, b))
    return triples


def _py_row(fixture: Path) -> list[tuple[int, int, int]]:
    """pypdfbox decode → middle scanline as (r, g, b) triples."""
    with PDDocument.load(fixture) as doc:
        res = doc.get_page(0).get_resources()
        names = list(res.get_x_object_names())
        assert len(names) == 1
        img = res.get_x_object(names[0]).get_image()
    assert img is not None, "pypdfbox get_image() returned None"
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    mid = h // 2
    return [px[x, mid] for x in range(w)]


@requires_oracle
@pytest.mark.parametrize(
    "decode", [[0.0, 1.0], [1.0, 0.0]], ids=["default_0_1", "inverted_1_0"]
)
def test_separation_decode_matches_pdfbox(
    decode: list[float], tmp_path: Path
) -> None:
    """For both the default ``[0 1]`` and inverted ``[1 0]`` decode, pypdfbox's
    decoded Separation raster must match Apache PDFBox per-channel within a
    small codec-rounding tolerance."""
    fixture = tmp_path / f"sep_{int(decode[0])}_{int(decode[1])}.pdf"
    _save(fixture, decode)

    java = _oracle_row(fixture)
    py = _py_row(fixture)
    assert len(py) == len(java), (
        f"row length diverges: pypdfbox={len(py)} java={len(java)}"
    )
    for x, (jt, pt) in enumerate(zip(java, py, strict=True)):
        for ch, (jc, pc) in enumerate(zip(jt, pt, strict=True)):
            assert abs(jc - pc) <= _CHANNEL_TOLERANCE, (
                f"decode {decode} px {x} ch {ch}: pypdfbox={pc} java={jc} "
                f"(diff {abs(jc - pc)} > {_CHANNEL_TOLERANCE})"
            )


@requires_oracle
def test_inverted_decode_reverses_ramp(tmp_path: Path) -> None:
    """Direct proof ``/Decode [1 0]`` is applied before the tint transform:
    the default ramp goes dark→light, the inverted ramp light→dark. A decoder
    that ignores ``/Decode`` on a Separation image (the pre-wave-1455 bug)
    produces the *same* ramp for both, failing this reversal check."""
    default_pdf = tmp_path / "sep_default.pdf"
    inverted_pdf = tmp_path / "sep_inverted.pdf"
    _save(default_pdf, [0.0, 1.0])
    _save(inverted_pdf, [1.0, 0.0])

    default = [sum(t) / 3 for t in _py_row(default_pdf)]
    inverted = [sum(t) / 3 for t in _py_row(inverted_pdf)]

    # Default: left dark, right light.
    assert default[-1] - default[0] > 100, (
        f"default ramp not dark→light (l={default[0]:.0f} r={default[-1]:.0f})"
    )
    # Inverted: left light, right dark — the reversal.
    assert inverted[0] - inverted[-1] > 100, (
        f"/Decode [1 0] not applied to Separation image "
        f"(l={inverted[0]:.0f} r={inverted[-1]:.0f})"
    )
    # And the two ramps must NOT be identical (the pre-fix failure mode).
    assert default != inverted, (
        "default and inverted /Decode produced identical rasters — "
        "/Decode ignored for Separation images"
    )
