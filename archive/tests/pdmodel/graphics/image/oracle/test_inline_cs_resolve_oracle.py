"""Live PDFBox differential parity for inline-image (BI/ID/EI) COLOUR-SPACE
resolution — the abbreviated-key + abbreviated-colour-space + named-resource
resolution surface, isolated from the raster pixel path.

``InlineImgProbe`` / ``test_inline_image_oracle.py`` already gate the decoded
raster (a 16x16 luminance grid) and the resolved colour-space *name*. They do
*not* assert the resolved :class:`PDColorSpace` **class** or its component
count, and they always go through ``getImage()`` — so a colour space that
resolves to the wrong *class* (e.g. ``DeviceRGB`` vs an Indexed whose base is
``DeviceRGB``) but happens to paint a similar grid would slip through, and a
colour space whose raster path is unsupported can't be checked at all.

This module drives Apache PDFBox's ``PDInlineImage.getColorSpace()`` directly
(``oracle/probes/InlineCsResolveProbe.java``) and asserts, per inline image, an
exact tuple of:

* ``getWidth()`` / ``getHeight()`` / ``getBitsPerComponent()``
* ``isStencil()``
* resolved colour-space **name** *and* **class simple-name**
* ``getNumberOfComponents()``
* for ``Indexed``: the **base** colour-space name + component count

across the full abbreviation matrix the PDF spec §8.9.7 allows:
abbreviated keys (``/W /H /BPC /CS /F /IM /D /I``) and full keys, abbreviated
colour-space names (``/G /RGB /CMYK``), the ``[/I ...]`` indexed abbreviation,
and a ``/CS`` that *names* a colour space defined in the page
``/Resources /ColorSpace`` (both a plain device name and a Separation array).

PDFBox's ``PDColorSpace`` subclass simple-names (``PDDeviceGray``,
``PDDeviceRGB``, ``PDDeviceCMYK``, ``PDIndexed``, ``PDSeparation``) match
pypdfbox's class ``__name__`` one-for-one, so the class assertion is a direct
string comparison.
"""

from __future__ import annotations

import pytest

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text


# --------------------------------------------------------------------------
# Fixture synthesis — a one-page PDF whose content stream embeds the given
# inline-image blocks, with an optional page ``/Resources /ColorSpace`` dict
# and optional extra indirect objects (e.g. a Separation tint transform).
# --------------------------------------------------------------------------
def _build_pdf(
    inline_blocks: list[bytes],
    color_space_dict: bytes = b"",
    extra_objs: list[bytes] | None = None,
) -> bytes:
    body = bytearray(b"q 100 0 0 100 50 50 cm\n")
    for block in inline_blocks:
        body += block
    body += b"Q\n"
    content = bytes(body)

    def obj(num: int, data: bytes) -> bytes:
        return f"{num} 0 obj\n".encode() + data + b"\nendobj\n"

    stream_obj = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)
    if color_space_dict:
        resources = b"<< /ColorSpace << " + color_space_dict + b" >> >>"
    else:
        resources = b"<< >>"
    parts = [
        obj(1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        obj(
            3,
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
            b"/Contents 4 0 R /Resources " + resources + b" >>",
        ),
        obj(4, stream_obj),
    ]
    parts += extra_objs or []
    count = len(parts) + 1
    pdf = bytearray(b"%PDF-1.7\n")
    offsets: list[int] = []
    for part in parts:
        offsets.append(len(pdf))
        pdf += part
    xref_off = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % count
    for off in offsets:
        pdf += b"%010d 00000 n \n" % off
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        count,
        xref_off,
    )
    return bytes(pdf)


def _inline(params: bytes, data: bytes) -> bytes:
    return b"BI " + params + b" ID\n" + data + b"\nEI\n"


def _ahx(data: bytes) -> bytes:
    return data.hex().upper().encode() + b">"


# --------------------------------------------------------------------------
# Cases — (label, [inline blocks], color_space_dict, extra_objs).
# Each case is engineered so the resolved colour-space identity is the point
# under test (the raster bytes are arbitrary but valid for the declared dims).
# --------------------------------------------------------------------------
def _gray_abbrev() -> bytes:
    # /CS /G abbreviation -> DeviceGray, 1 component.
    return _inline(b"/W 2 /H 2 /BPC 8 /CS /G /F /AHx", _ahx(bytes([0, 64, 128, 255])))


def _rgb_abbrev() -> bytes:
    # /CS /RGB abbreviation -> DeviceRGB, 3 components.
    rgb = bytes([200, 30, 30, 30, 200, 30, 30, 30, 200, 200, 200, 30])
    return _inline(b"/W 2 /H 2 /BPC 8 /CS /RGB /F /AHx", _ahx(rgb))


def _cmyk_abbrev() -> bytes:
    # /CS /CMYK abbreviation -> DeviceCMYK, 4 components.
    cmyk = bytes([0, 0, 0, 0, 255, 0, 0, 0, 0, 255, 0, 0, 0, 0, 0, 255])
    return _inline(b"/W 2 /H 2 /BPC 8 /CS /CMYK /F /AHx", _ahx(cmyk))


def _gray_fullkeys() -> bytes:
    # Full key names + full colour-space name -> identical resolution.
    params = (
        b"/Width 2 /Height 2 /BitsPerComponent 8 "
        b"/ColorSpace /DeviceGray /Filter /ASCIIHexDecode"
    )
    return _inline(params, _ahx(bytes([0, 64, 128, 255])))


def _indexed_abbrev_i_rgb() -> bytes:
    # [/I /RGB 3 <palette>] inline abbreviation -> PDIndexed, base DeviceRGB.
    lookup = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255])
    rows = bytes(
        [
            (0 << 6) | (1 << 4) | (2 << 2) | 3,
            (3 << 6) | (2 << 4) | (1 << 2) | 0,
            0,
            (3 << 6) | (3 << 4) | (3 << 2) | 3,
        ]
    )
    params = (
        b"/W 4 /H 4 /BPC 2 /CS [/I /RGB 3 <"
        + lookup.hex().upper().encode()
        + b">] /F /AHx"
    )
    return _inline(params, _ahx(rows))


def _indexed_abbrev_i_g() -> bytes:
    # [/I /G 1 <palette>] -> PDIndexed, base DeviceGray (abbrev base name).
    lookup = bytes([0, 128])
    rows = bytes([(0 << 6) | (1 << 4), (1 << 6) | (0 << 4)])
    params = (
        b"/W 2 /H 2 /BPC 2 /CS [/Indexed /G 1 <"
        + lookup.hex().upper().encode()
        + b">]"
    )
    return _inline(params, rows)


def _stencil_mask() -> bytes:
    # /IM true stencil with no /CS -> getColorSpace() falls back to DeviceGray,
    # getBitsPerComponent() is forced to 1.
    stencil = bytes([0b10101010, 0b11110000])
    return _inline(b"/W 8 /H 2 /IM true", stencil)


_SELF_CONTAINED_CASES: list[tuple[str, list[bytes]]] = [
    ("gray_abbrev", [_gray_abbrev()]),
    ("rgb_abbrev", [_rgb_abbrev()]),
    ("cmyk_abbrev", [_cmyk_abbrev()]),
    ("gray_fullkeys", [_gray_fullkeys()]),
    ("indexed_i_rgb", [_indexed_abbrev_i_rgb()]),
    ("indexed_indexed_g", [_indexed_abbrev_i_g()]),
    ("stencil_mask", [_stencil_mask()]),
    (
        "multi_mixed",
        [_gray_abbrev(), _rgb_abbrev(), _indexed_abbrev_i_rgb(), _stencil_mask()],
    ),
]


# Named-CS-from-resources cases: /CS names an entry in /Resources /ColorSpace.
def _named_device_rgb() -> tuple[list[bytes], bytes, list[bytes]]:
    # /CS /CS0 where /CS0 = /DeviceRGB (a name alias in resources).
    rgb = bytes([200, 30, 30, 30, 200, 30, 30, 30, 200, 200, 200, 30])
    block = _inline(b"/W 2 /H 2 /BPC 8 /CS /CS0 /F /AHx", _ahx(rgb))
    return [block], b"/CS0 /DeviceRGB", []


def _named_separation() -> tuple[list[bytes], bytes, list[bytes]]:
    # /CS /Spot0 where /Spot0 = [/Separation /Spot /DeviceRGB 5 0 R].
    tint_fn = (
        b"5 0 obj\n"
        b"<< /FunctionType 2 /Domain [0 1] /C0 [1 1 1] /C1 [1 0 0] /N 1 >>"
        b"\nendobj\n"
    )
    samples = bytes([0, 255, 128, 255])
    block = _inline(b"/W 2 /H 2 /BPC 8 /CS /Spot0", samples)
    return [block], b"/Spot0 [/Separation /Spot /DeviceRGB 5 0 R]", [tint_fn]


_NAMED_CASES: list[tuple[str, list[bytes], bytes, list[bytes]]] = []
for _label, _builder in (
    ("named_device_rgb", _named_device_rgb),
    ("named_separation", _named_separation),
):
    _blocks, _csdict, _extras = _builder()
    _NAMED_CASES.append((_label, _blocks, _csdict, _extras))


def _pypdfbox_descriptions(pdf_bytes: bytes) -> list[tuple]:
    """Resolve each inline image's colour space with pypdfbox; return per-image
    tuple matching ``InlineCsResolveProbe`` output, in stream order."""
    out: list[tuple] = []
    with PDDocument.load(pdf_bytes) as doc:
        page = doc.get_page(0)
        resources = page.get_resources()
        parser = PDFStreamParser(RandomAccessReadBuffer(page.get_contents()))
        for token in parser.tokens():
            if isinstance(token, Operator) and token.get_name() == "BI":
                image = PDInlineImage(
                    token.get_image_parameters(),
                    token.get_image_data(),
                    resources,
                )
                cs_name = "?"
                cs_class = "?"
                n_comp = -1
                base_name = "-"
                base_comp = -1
                try:
                    cs = image.get_color_space()
                    cs_name = cs.get_name()
                    cs_class = type(cs).__name__
                    n_comp = cs.get_number_of_components()
                    base = getattr(cs, "get_base_color_space", None)
                    if base is not None:
                        base_cs = base()
                        if base_cs is not None:
                            base_name = base_cs.get_name()
                            base_comp = base_cs.get_number_of_components()
                except Exception:  # noqa: BLE001 — mirror probe's catch-all
                    cs_name = "?"
                out.append(
                    (
                        image.get_width(),
                        image.get_height(),
                        image.get_bits_per_component(),
                        "1" if image.is_stencil() else "0",
                        cs_name,
                        cs_class,
                        n_comp,
                        base_name,
                        base_comp,
                    )
                )
    return out


def _oracle_descriptions(tmp_path, pdf_bytes: bytes) -> list[tuple]:
    fixture = tmp_path / "inline_cs.pdf"
    fixture.write_bytes(pdf_bytes)
    try:
        text = run_probe_text("InlineCsResolveProbe", str(fixture), "0")
    finally:
        fixture.unlink(missing_ok=True)
    out: list[tuple] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        out.append(
            (
                int(parts[0]),
                int(parts[1]),
                int(parts[2]),
                parts[3],
                parts[4],
                parts[5],
                int(parts[6]),
                parts[7],
                int(parts[8]),
            )
        )
    return out


@requires_oracle
@pytest.mark.parametrize(
    ("label", "blocks"),
    _SELF_CONTAINED_CASES,
    ids=[c[0] for c in _SELF_CONTAINED_CASES],
)
def test_inline_cs_resolution_matches_pdfbox(
    tmp_path, label: str, blocks: list[bytes]
) -> None:
    """Inline-image colour-space resolution (abbreviated + full keys,
    abbreviated colour-space names, ``[/I ...]`` indexed, stencil fallback)
    resolves to the same class / components / dims as Apache PDFBox."""
    pdf_bytes = _build_pdf(blocks)
    java = _oracle_descriptions(tmp_path, pdf_bytes)
    py = _pypdfbox_descriptions(pdf_bytes)

    assert len(py) == len(java), (
        f"{label}: pypdfbox found {len(py)} inline images, PDFBox found {len(java)}"
    )
    for idx, (py_row, java_row) in enumerate(zip(py, java, strict=True)):
        assert py_row == java_row, (
            f"{label}[{idx}]: inline colour-space resolution diverges from "
            f"PDFBox:\n  pypdfbox={py_row}\n  java    ={java_row}"
        )


@requires_oracle
@pytest.mark.parametrize(
    ("label", "blocks", "cs_dict", "extras"),
    _NAMED_CASES,
    ids=[c[0] for c in _NAMED_CASES],
)
def test_inline_named_cs_resolution_matches_pdfbox(
    tmp_path, label: str, blocks: list[bytes], cs_dict: bytes, extras: list[bytes]
) -> None:
    """An inline ``/CS`` that *names* a colour space in the page
    ``/Resources /ColorSpace`` resolves to the same class / components as
    Apache PDFBox (device-name alias + Separation array)."""
    pdf_bytes = _build_pdf(blocks, cs_dict, extras)
    java = _oracle_descriptions(tmp_path, pdf_bytes)
    py = _pypdfbox_descriptions(pdf_bytes)

    assert len(py) == len(java) == 1, (
        f"{label}: expected 1 inline image, py={len(py)} java={len(java)}"
    )
    assert py[0] == java[0], (
        f"{label}: named-CS resolution diverges from PDFBox:\n"
        f"  pypdfbox={py[0]}\n  java    ={java[0]}"
    )
