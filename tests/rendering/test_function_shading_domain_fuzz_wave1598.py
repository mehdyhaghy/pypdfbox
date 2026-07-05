"""Fuzz / parity battery for Type 1 (function-based) shading out-of-domain
semantics, wave 1598 agent C.

``archive/tests/rendering/oracle/test_function_shading_oracle.py`` pins the
happy-path /Domain + /Matrix coordinate mapping (16x16 luminance MAD gate).
This battery hammers everything AROUND the happy path in
``PDFRenderer._paint_function_shading``, pinned against Apache PDFBox 3.0.7
``org.apache.pdfbox.pdmodel.graphics.shading.Type1ShadingContext.getRaster``
(+ constructor) and ``PDShading.evalFunction``, live-diffed pixel-by-pixel
via ``archive/oracle/probes/ShadingPixelProbe.java``:

* **out-of-domain, no /Background** — upstream's bare ``continue`` leaves the
  raster transparent, so the destination shows through untouched. (pypdfbox
  painted such pixels WHITE before this wave.)
* **out-of-domain, /Background present** — the ``useBackground`` branch paints
  the /Background components, converted through the shading colour space.
  (pypdfbox ignored /Background for Type 1 entirely.)
* **singular /Matrix** — upstream catches the ``NoninvertibleTransform-
  Exception`` from building ``rat`` and falls back to the IDENTITY transform:
  raw device pixel coordinates are then checked against /Domain (so with the
  default unit domain only the top-left device corner is in-domain and the
  rest gets /Background / stays untouched). (pypdfbox skipped the whole fill.)
* **degenerate /Domain (xmin == xmax)** — no upstream early-out: every pixel
  off the exact boundary line fails the domain check and gets /Background /
  stays untouched; a pixel EXACTLY on the boundary still evaluates the
  function (the check is strict ``<`` / ``>``). (pypdfbox skipped the fill.)
* **function-array channel failure** — upstream ``PDShading.evalFunction``
  evaluates one 1-output function per colour component and lets ANY entry's
  IOException propagate, so ``getRaster`` skips the pixel; no zero-filled
  channels. (pypdfbox substituted 0.0 for failing channels.)
* **out-of-range function output** — ``PDShading.evalFunction`` clamps every
  output component to [0, 1] ("adjusted to the nearest valid value") BEFORE
  colour-space conversion.

Known, retained divergences (documented, not bugs):

* colour quantisation rounds (``_clamp_byte``: ``round(v * 255)``) where Java
  truncates (``(int) (v * 255)``) — a global pypdfbox renderer convention, so
  gradient interiors may differ by 1/255 per channel (oracle tolerance 2);
* a broken Type 4 function program makes upstream THROW out of
  ``renderImage`` (the probe exits non-zero); pypdfbox stays permissive and
  leaves the destination untouched (pixel-skip), matching its documented
  permissive-render contract;
* a short (2-element) Type 1 /Domain crashes upstream with an
  ``ArrayIndexOutOfBoundsException`` at raster time; pypdfbox falls back to
  the spec default ``[0 1 0 1]``;
* DeviceCMYK function output converts through the naive ``(1-c)(1-k)``
  formula, not upstream's ISO-coated ICC profile (long-standing pypdfbox
  device-CMYK convention) — pinned py-only here.

Each fixture is a 100x100 page (1:1 device pixels at 72 DPI) filled solid red
first (so "destination untouched" is observable), then one ``/Sh0 sh``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_PAGE = 100.0
# Per-channel tolerance for the live differential: 1 for the global
# round-vs-truncate residual, +1 headroom for the domain-grid colour cache.
# Every divergence this battery guards against is a full-channel miss
# (255-ish), so the gate discriminates sharply.
_CHANNEL_TOL = 2

_RED = (255, 0, 0)  # the base fill — "destination untouched" marker
_CM_100 = b"q 100 0 0 100 0 0 cm /Sh0 sh Q\n"
_NO_CM = b"q /Sh0 sh Q\n"


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------


def _arr(*vals: float) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(float(v)))
    return a


def _calc_fn(body: bytes, n_out: int) -> COSStream:
    """A Type 4 (PostScript calculator) 2-in / n-out function stream."""
    fn = COSStream()
    fn.set_int(COSName.get_pdf_name("FunctionType"), 4)
    fn.set_item(COSName.get_pdf_name("Domain"), _arr(0.0, 1.0, 0.0, 1.0))
    rng = COSArray()
    for _ in range(n_out):
        rng.add(COSFloat(0.0))
        rng.add(COSFloat(1.0))
    fn.set_item(COSName.get_pdf_name("Range"), rng)
    with fn.create_output_stream() as body_out:
        body_out.write(body)
    return fn


def _build(
    out: Path,
    *,
    color_space: str = "DeviceRGB",
    domain: tuple[float, ...] | None = None,
    matrix: tuple[float, ...] | None = None,
    background: tuple[float, ...] | None = None,
    function: COSStream | COSArray | None = None,
    shading_ops: bytes = _CM_100,
) -> Path:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)

    sh = COSDictionary()
    sh.set_int(COSName.get_pdf_name("ShadingType"), 1)
    sh.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name(color_space)
    )
    if domain is not None:
        sh.set_item(COSName.get_pdf_name("Domain"), _arr(*domain))
    if matrix is not None:
        sh.set_item(COSName.get_pdf_name("Matrix"), _arr(*matrix))
    if background is not None:
        sh.set_item(COSName.get_pdf_name("Background"), _arr(*background))
    if function is None:
        # f(x, y) = (x, y, 0): the operands stay on the stack, one 0.0 pushed.
        function = _calc_fn(b"{ 0.0 }", 3)
    sh.set_item(COSName.get_pdf_name("Function"), function)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(COSName.get_pdf_name("Shading"), COSName.get_pdf_name("Sh0"), sh)

    content = COSStream()
    content.set_raw_data(b"1 0 0 rg 0 0 100 100 re f\n" + shading_ops)
    page.get_cos_object().set_item(COSName.CONTENTS, content)
    doc.save(str(out))
    doc.close()
    return out


def _fn_array_rgb() -> COSArray:
    """Per-channel 2-in/1-out calculator array: R = x, G = y, B = 0."""
    arr = COSArray()
    arr.add(_calc_fn(b"{ pop }", 1))  # x y -> x
    arr.add(_calc_fn(b"{ exch pop }", 1))  # x y -> y
    arr.add(_calc_fn(b"{ pop pop 0.0 }", 1))  # x y -> 0
    return arr


def _fn_array_broken_channel() -> COSArray:
    """R = x, G = <parse error>, B = 0 — any failing channel skips the pixel."""
    arr = COSArray()
    arr.add(_calc_fn(b"{ pop }", 1))
    arr.add(_calc_fn(b"{ bogus_operator }", 1))
    arr.add(_calc_fn(b"{ pop pop 0.0 }", 1))
    return arr


# ---------------------------------------------------------------------------
# case table
# ---------------------------------------------------------------------------
# name -> (builder kwargs, [(x, y, expected pypdfbox RGB)], oracle_eligible)
#
# Page geometry: content ``cm 100`` (or /Matrix) maps the unit domain onto the
# page; a device pixel (px, py) has user coords (px, 100 - py), so for the
# cm-mapped fixtures dx = px/100 and dy = (100 - py)/100.

_CASES: dict[str, dict] = {
    # -- restricted domain: in-domain gradient, out-of-domain destination --
    "restricted_domain_no_bg": {
        "build": {"domain": (0.0, 0.5, 0.0, 0.5)},
        "points": [
            (25, 75, (64, 64, 0)),  # dx=dy=0.25 in-domain
            (75, 25, _RED),  # dx=0.75 out -> destination untouched
            (75, 75, _RED),
            (25, 25, _RED),  # dy=0.75 out
        ],
        "oracle": True,
    },
    "restricted_domain_bg_rgb": {
        "build": {
            "domain": (0.0, 0.5, 0.0, 0.5),
            "background": (1.0, 1.0, 0.0),
        },
        "points": [
            (25, 75, (64, 64, 0)),  # in-domain: function wins over /Background
            (75, 25, (255, 255, 0)),  # out -> /Background yellow
            (75, 75, (255, 255, 0)),
            (25, 25, (255, 255, 0)),
        ],
        "oracle": True,
    },
    "restricted_domain_bg_gray": {
        # DeviceGray: 1-output function g = x; /Background converted through
        # the shading colour space (0.2 -> 51 gray).
        "build": {
            "color_space": "DeviceGray",
            "domain": (0.0, 0.5, 0.0, 0.5),
            "background": (0.2,),
            "function": _calc_fn(b"{ pop }", 1),
        },
        "points": [
            (25, 75, (64, 64, 64)),  # in-domain gray 0.25
            (75, 25, (51, 51, 51)),  # out -> gray background
            (25, 25, (51, 51, 51)),
        ],
        "oracle": True,
    },
    # -- singular /Matrix: upstream identity-rat fallback --
    "singular_matrix_bg": {
        # rat == identity -> RAW DEVICE coords vs default domain [0 1 0 1]:
        # only the top-left corner pixels are in-domain.
        "build": {"matrix": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
                  "background": (1.0, 1.0, 0.0)},
        "points": [
            (0, 0, (0, 0, 0)),  # device (0,0) -> f(0,0) = black
            (50, 50, (255, 255, 0)),  # out -> background
            (99, 99, (255, 255, 0)),
        ],
        "oracle": True,
    },
    "singular_matrix_no_bg": {
        "build": {"matrix": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)},
        "points": [
            (0, 0, (0, 0, 0)),  # still painted via the identity fallback
            (50, 50, _RED),  # out, no background -> destination untouched
            (99, 99, _RED),
        ],
        "oracle": True,
    },
    "singular_matrix_rank1_bg": {
        # Rank-1 (det == 0 but nonzero entries) singular matrix — same
        # identity fallback as the all-zeros case.
        "build": {"matrix": (1.0, 2.0, 2.0, 4.0, 0.0, 0.0),
                  "background": (0.0, 0.0, 1.0)},
        "points": [
            (0, 0, (0, 0, 0)),
            (50, 50, (0, 0, 255)),
            (99, 5, (0, 0, 255)),
        ],
        "oracle": True,
    },
    # -- degenerate /Domain: no early-out --
    "degenerate_domain_bg": {
        # xmin == xmax == 0.5: everything off the dx == 0.5 line is
        # out-of-domain -> background; the exact boundary column still
        # evaluates the function (strict < / > check).
        "build": {"domain": (0.5, 0.5, 0.0, 1.0),
                  "background": (0.0, 1.0, 0.0)},
        "points": [
            (25, 50, (0, 255, 0)),
            (75, 50, (0, 255, 0)),
            (50, 25, (128, 191, 0)),  # dx == 0.5 exactly: f(0.5, 0.75)
        ],
        "oracle": True,
    },
    "degenerate_domain_no_bg": {
        "build": {"domain": (0.5, 0.5, 0.0, 1.0)},
        "points": [
            (25, 50, _RED),
            (75, 50, _RED),
            (50, 25, (128, 191, 0)),
        ],
        "oracle": True,
    },
    # -- /Matrix mapping (invertible) + domain interplay --
    "matrix_box_no_bg": {
        # /Matrix [50 0 0 50 25 25] maps the unit domain onto the centre
        # box [25,75]^2 (user space); no cm.
        "build": {"matrix": (50.0, 0.0, 0.0, 50.0, 25.0, 25.0),
                  "shading_ops": _NO_CM},
        "points": [
            (50, 50, (128, 128, 0)),  # centre: dx=dy=0.5
            (30, 70, (25, 25, 0)),  # dx=dy=0.1 (inverse-matrix fp -> 25.499...)
            (10, 10, _RED),  # outside the box -> untouched
            (90, 90, _RED),
        ],
        "oracle": True,
    },
    "matrix_rotated": {
        # /Matrix [0 100 -100 0 100 0] — 90-degree rotation; the unit domain
        # still covers the page but the axes swap: dx = (100-py)/100 image-y,
        # dy = (100-px)/100.
        "build": {"matrix": (0.0, 100.0, -100.0, 0.0, 100.0, 0.0),
                  "shading_ops": _NO_CM},
        "points": [
            (75, 25, (191, 64, 0)),  # dx=0.75, dy=0.25
            (25, 75, (64, 191, 0)),
        ],
        "oracle": True,
    },
    # -- function array (one 1-output function per channel) --
    "function_array_rgb": {
        "build": {"domain": (0.0, 0.5, 0.0, 0.5),
                  "function": _fn_array_rgb()},
        "points": [
            (25, 75, (64, 64, 0)),
            (75, 25, _RED),
        ],
        "oracle": True,
    },
    # -- output clamping (PDShading.evalFunction) --
    "clamped_output": {
        "build": {"function": _calc_fn(b"{ pop pop 2.0 -1.0 0.5 }", 3)},
        "points": [
            (25, 75, (255, 0, 128)),  # 2.0 -> 1, -1.0 -> 0, 0.5 kept
            (75, 25, (255, 0, 128)),
        ],
        "oracle": True,
    },
    # -- full-domain gradient sanity --
    "full_domain_gradient": {
        "build": {},
        "points": [
            (25, 75, (64, 64, 0)),
            (75, 25, (191, 191, 0)),
            (50, 50, (128, 128, 0)),
        ],
        "oracle": True,
    },
    # -- permissive-divergence pins (py-only; upstream throws) --
    "broken_function_program": {
        # Type 4 parse error: upstream propagates the IOException out of
        # renderImage (probe exits non-zero); pypdfbox skips every pixel.
        "build": {"function": _calc_fn(b"{ bogus_operator }", 3)},
        "points": [
            (25, 75, _RED),
            (75, 25, _RED),
        ],
        "oracle": False,
    },
    "broken_channel_in_array": {
        # One failing channel function aborts the whole per-pixel eval
        # (upstream PDShading.evalFunction propagates); with a parse error in
        # EVERY pixel, nothing is painted. Upstream also throws out of
        # renderImage here, so py-only.
        "build": {"function": _fn_array_broken_channel()},
        "points": [
            (25, 75, _RED),
            (75, 25, _RED),
        ],
        "oracle": False,
    },
    "short_domain_array": {
        # 2-element /Domain: upstream AIOOBEs at raster time; pypdfbox falls
        # back to the spec default [0 1 0 1] and paints the full gradient.
        "build": {"domain": (0.0, 1.0)},
        "points": [
            (25, 75, (64, 64, 0)),
            (75, 25, (191, 191, 0)),
        ],
        "oracle": False,
    },
    "cmyk_output_naive": {
        # DeviceCMYK constant output through the naive (1-c)(1-k) formula —
        # long-standing pypdfbox convention (upstream uses an ICC profile).
        "build": {"color_space": "DeviceCMYK",
                  "function": _calc_fn(b"{ pop pop 0.1 0.2 0.3 0.4 }", 4)},
        "points": [
            (25, 75, (138, 122, 107)),
            (75, 25, (138, 122, 107)),
        ],
        "oracle": False,
    },
}


# ---------------------------------------------------------------------------
# shared fixture-PDF construction (one build per module run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fixture_pdfs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("t1_shading_wave1598")
    return {
        name: _build(root / f"{name}.pdf", **spec["build"])
        for name, spec in _CASES.items()
    }


def _render(pdf: Path):
    doc = PDDocument.load(str(pdf))
    try:
        return PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# pinned pypdfbox behaviour (runs everywhere, no Java needed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(_CASES), ids=sorted(_CASES))
def test_pinned_pixels(name: str, fixture_pdfs: dict[str, Path]) -> None:
    img = _render(fixture_pdfs[name])
    assert img.size == (100, 100)
    for x, y, expected in _CASES[name]["points"]:
        got = img.getpixel((x, y))[:3]
        assert got == expected, (
            f"{name} pixel ({x},{y}): got {got}, want {expected}"
        )


# ---------------------------------------------------------------------------
# live differential against Apache PDFBox 3.0.7
# ---------------------------------------------------------------------------

_ORACLE_CASES = sorted(n for n, spec in _CASES.items() if spec["oracle"])


@requires_oracle
@pytest.mark.parametrize("name", _ORACLE_CASES, ids=_ORACLE_CASES)
def test_matches_pdfbox(name: str, fixture_pdfs: dict[str, Path]) -> None:
    pdf = fixture_pdfs[name]
    points = [(x, y) for x, y, _ in _CASES[name]["points"]]
    args = [str(pdf), "0"]
    for x, y in points:
        args += [str(x), str(y)]
    lines = run_probe_text("ShadingPixelProbe", *args).strip().splitlines()
    assert lines[0].split() == ["100", "100"]

    img = _render(pdf)
    for idx, (x, y) in enumerate(points):
        java = tuple(int(v) for v in lines[1 + idx].split())
        py = img.getpixel((x, y))[:3]
        for channel, (jv, pv) in enumerate(zip(java, py, strict=True)):
            assert abs(jv - pv) <= _CHANNEL_TOL, (
                f"{name} pixel ({x},{y}) channel {channel}: "
                f"java={java} py={py}"
            )
