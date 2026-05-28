"""Live PDFBox differential parity for ``/SMaskInData`` (PDF 32000-1 §8.9.7.5,
Table 89) — the JPX-only optional hint that tells the renderer how to interpret
the JPEG 2000 stream's encoded alpha channel:

* ``0`` (default) — no SMask information embedded in the JPX data.
* ``1`` — the JPX bytes carry premultiplied colour samples + alpha.
* ``2`` — the JPX bytes carry an opacity (matte) channel used as a soft mask.

Apache PDFBox 3.0.7's ``PDImageXObject`` does **not** expose a public
``getSMaskInData()`` accessor (that landed on a later upstream branch); the
3.0.7 build reads the entry inline inside ``getImage()`` to forward via
``DecodeResult.getJPXSMask()``. So the differential here is at the COS-dict
level: ``oracle/probes/SMaskInDataProbe.java`` reads each image XObject's
``getCOSObject().getInt(COSName("SMaskInData"), 0)`` directly, and pypdfbox's
``PDImageXObject.get_smask_in_data()`` (a forward-compat accessor wrapping the
same lookup) must agree bit-for-bit across:

* ``/SMaskInData`` absent → both report ``0`` (the spec default).
* ``/SMaskInData 0`` explicit → both report ``0`` (and round-trip the entry).
* ``/SMaskInData 1`` (premultiplied) → both report ``1``.
* ``/SMaskInData 2`` (matte) → both report ``2``.

Each fixture is a one-page PDF whose only image XObject is a real JPEG-2000
stream (Pillow / OpenJPEG-encoded) under ``/Filter /JPXDecode``, with the
``/SMaskInData`` integer set on the image dict at fixture-build time. Render
parity is NOT covered here — the pinned ``pdfbox-app-3.0.7.jar`` registers no
JPEG 2000 ImageReader (see ``test_jpx_decode_oracle.py``), so there is no Java
raster to differential against, and the JPX SMaskInData modes 1/2 require a
decoder that understands embedded alpha which neither side ships. The
*accessor + dict-level parity* this module pins is the meaningful behavioural
contract: the accessor matches PDFBox's COS read, and the entry survives
save/load round-trip — which is what every downstream consumer relies on.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text


def _gradient_rgb(width: int, height: int) -> Image.Image:
    """Deterministic RGB gradient — wavelet-friendly so JPEG 2000 reproduces it
    with little loss. Content doesn't matter for the accessor parity test, but
    a real raster keeps the JPX stream syntactically valid for both sides."""
    img = Image.new("RGB", (width, height))
    for y in range(height):
        for x in range(width):
            img.putpixel(
                (x, y),
                ((x * 7) % 256, (y * 9) % 256, ((x + y) * 5) % 256),
            )
    return img


def _build_jpx_pdf(
    path: Path,
    width: int,
    height: int,
    smask_in_data: int | None,
) -> None:
    """One-page PDF whose only image is a JPEG-2000 raster carrying the given
    ``/SMaskInData`` (or no entry at all when ``smask_in_data is None``)."""
    raster = _gradient_rgb(width, height)
    buf = io.BytesIO()
    raster.save(buf, format="JPEG2000")
    jp2 = buf.getvalue()

    document = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    document.add_page(page)
    cos_doc = document.get_document()

    stream = COSStream(cos_doc.scratch_file)
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Image"))
    stream.set_int(COSName.get_pdf_name("Width"), width)
    stream.set_int(COSName.get_pdf_name("Height"), height)
    stream.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    stream.set_item(COSName.FILTER, COSName.get_pdf_name("JPXDecode"))
    stream.set_int(COSName.get_pdf_name("Length"), len(jp2))
    stream.set_raw_data(jp2)

    image = PDImageXObject(stream)
    if smask_in_data is not None:
        # Set via the public accessor so the round-trip exercises set→save→load.
        image.set_smask_in_data(smask_in_data)
    resources = PDResources()
    name = resources.add_x_object(image)
    page.set_resources(resources)

    content = (f"q {width} 0 0 {height} 10 10 cm /{name.get_name()} Do Q").encode(
        "ascii"
    )
    content_stream = COSStream(cos_doc.scratch_file)
    with content_stream.create_output_stream() as out:
        out.write(content)
    page.get_cos_object().set_item(COSName.get_pdf_name("Contents"), content_stream)

    with path.open("wb") as fh:
        document.save(fh)
    document.close()


def _parse_probe(line: str) -> dict[str, str]:
    """Parse a single probe stdout line into a key→value dict.

    The line shape is ``smid page <p> name <n> w <w> h <h> bpc <bpc>
    accessor <a> raw <r> filter <f> grid <none-or-256-ints>``. Every key in the
    list above keys to its immediate next token; the only multi-token tail is
    ``grid``, captured as a single space-joined string.
    """
    tokens = line.strip().split()
    assert tokens and tokens[0] == "smid", f"unexpected probe line: {line!r}"
    keys_single = {"page", "name", "w", "h", "bpc", "accessor", "raw", "filter"}
    fields: dict[str, str] = {}
    i = 1
    while i < len(tokens):
        key = tokens[i]
        if key == "grid":
            fields["grid"] = " ".join(tokens[i + 1 :])
            break
        if key in keys_single:
            fields[key] = tokens[i + 1]
            i += 2
            continue
        # Unknown key — skip its value defensively.
        i += 2
    return fields


def _pypdfbox_read(pdf_bytes: bytes) -> tuple[int, int, int, int, str]:
    """Reload ``pdf_bytes`` and return ``(w, h, bpc, smask_in_data, filter)``
    for its single image XObject."""
    document = PDDocument.load(pdf_bytes)
    try:
        resources = document.get_page(0).get_resources()
        names = list(resources.get_x_object_names())
        assert names, "fixture PDF has no image XObject"
        image = resources.get_x_object(names[0])
        cos = image.get_cos_object()
        filter_value = cos.get_dictionary_object(COSName.FILTER)
        if isinstance(filter_value, COSName):
            filter_name = filter_value.get_name()
        else:
            filter_name = str(filter_value)
        return (
            image.get_width(),
            image.get_height(),
            image.get_bits_per_component(),
            image.get_smask_in_data(),
            filter_name,
        )
    finally:
        document.close()


# (label, smask_in_data, expected_dict_value)
# expected_dict_value matches what BOTH sides must read out of the saved dict.
# For the "absent" case the saved dict won't contain /SMaskInData at all and
# both sides default to 0.
_CASES = [
    ("absent", None, 0),
    ("zero", 0, 0),
    ("premultiplied", 1, 1),
    ("matte", 2, 2),
]


@requires_oracle
@pytest.mark.parametrize(
    ("label", "smask_in_data", "expected"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_smask_in_data_dict_parity_matches_pdfbox(
    tmp_path: Path, label: str, smask_in_data: int | None, expected: int
) -> None:
    """The ``/SMaskInData`` integer that PDFBox 3.0.7 reads off a JPX image
    XObject's COS dict must equal what pypdfbox's
    ``PDImageXObject.get_smask_in_data()`` returns on the *same* saved PDF.
    Covers absent (spec default 0), explicit 0, premultiplied (1), and matte
    (2) — every legal value per PDF 32000-1 Table 89."""
    fixture = tmp_path / f"smask_in_data_{label}.pdf"
    _build_jpx_pdf(fixture, width=32, height=24, smask_in_data=smask_in_data)
    pdf_bytes = fixture.read_bytes()

    # PDFBox side.
    out = run_probe_text("SMaskInDataProbe", str(fixture)).strip()
    lines = [ln for ln in out.splitlines() if ln.startswith("smid ")]
    assert len(lines) == 1, f"expected exactly one image, probe emitted: {out!r}"
    java = _parse_probe(lines[0])

    # pypdfbox side.
    py_w, py_h, py_bpc, py_accessor, py_filter = _pypdfbox_read(pdf_bytes)

    # Dim / filter parity sanity (proves we're looking at the same image).
    assert int(java["w"]) == py_w == 32
    assert int(java["h"]) == py_h == 24
    assert int(java["bpc"]) == py_bpc == 8
    assert java["filter"] == py_filter == "JPXDecode"

    # /SMaskInData accessor parity — the actual assertion this test exists for.
    assert int(java["accessor"]) == expected, (
        f"PDFBox 3.0.7 reads /SMaskInData={java['accessor']!r}, "
        f"expected {expected} for case {label!r}"
    )
    assert int(java["raw"]) == expected
    assert py_accessor == expected, (
        f"pypdfbox PDImageXObject.get_smask_in_data() returned {py_accessor}, "
        f"expected {expected} (PDFBox reports {java['accessor']}) for case {label!r}"
    )
    assert py_accessor == int(java["accessor"]), (
        "accessor diverges from Apache PDFBox 3.0.7's raw COS read: "
        f"pypdfbox={py_accessor} java={java['accessor']}"
    )


@requires_oracle
def test_smask_in_data_round_trips_explicit_zero(tmp_path: Path) -> None:
    """Setting ``/SMaskInData 0`` explicitly is observably distinct from
    omitting the entry (the dict carries an integer the writer wrote) — but
    the accessor must collapse both to the spec default ``0`` per PDF 32000-1
    Table 89, on both sides of the oracle."""
    fixture = tmp_path / "smask_in_data_explicit_zero.pdf"
    _build_jpx_pdf(fixture, width=32, height=24, smask_in_data=0)
    pdf_bytes = fixture.read_bytes()

    out = run_probe_text("SMaskInDataProbe", str(fixture)).strip()
    java = _parse_probe(out.splitlines()[0])
    assert int(java["accessor"]) == 0
    assert int(java["raw"]) == 0

    document = PDDocument.load(pdf_bytes)
    try:
        resources = document.get_page(0).get_resources()
        name = next(iter(resources.get_x_object_names()))
        image = resources.get_x_object(name)
        # Accessor reports the spec default.
        assert image.get_smask_in_data() == 0
        # And the underlying dict actually carries the explicit 0 (proving the
        # writer round-tripped the entry, not silently dropped it). This is
        # the load-bearing distinction: a future "drop default 0 on write"
        # optimisation must not regress this assertion silently.
        raw = image.get_cos_object().get_int(
            COSName.get_pdf_name("SMaskInData"), -1
        )
        assert raw == 0, (
            "/SMaskInData 0 was dropped from the saved dict — accessor still "
            "reads 0 by default, but the entry's presence is observable and "
            "must survive save/load."
        )
    finally:
        document.close()
