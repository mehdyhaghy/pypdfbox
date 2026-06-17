"""Live PDFBox differential parity for inline-image (BI/ID/EI) FILTER-
ABBREVIATION decode (PDF 32000-1 §8.9.7 Table 93).

``InlineImgProbe`` gates the decoded *raster* of an inline image and
``InlineCsResolveProbe`` (wave 1467) gates colour-space resolution. Neither
isolates the **filter abbreviation** facet: that ``getFilters()`` returns the
abbreviation *verbatim* (PDFBox does NOT expand ``/AHx`` -> ``ASCIIHexDecode``
in ``getFilters()`` — the expansion happens inside
``FilterFactory.getFilter()``), and that the abbreviated ``/F`` resolves to the
right decoder so ``getData()`` produces byte-identical decoded bytes.

This module drives Apache PDFBox's ``PDInlineImage.getFilters()`` +
``getData()`` directly (``oracle/probes/InlineFilterAbbrevProbe.java``) and
asserts, per inline image:

* the verbatim filter-name list matches (abbreviation kept as stored),
* the **byte-exact** decoded payload (``getData()`` hex) matches — the
  strongest possible parity signal for the lossless abbreviations
  ``/AHx`` ``/A85`` ``/LZW`` ``/Fl`` ``/RL`` (and their full-name forms,
  plus a two-filter chain ``[/A85 /Fl]``).

Lossy/codec abbreviations (``/DCT`` / ``/CCF``) are deliberately out of scope
here — byte-exact decode across Java2D vs Pillow is impossible and they are
already covered by the raster-grid probes; this facet is the lossless
abbreviation-expansion correctness path.
"""

from __future__ import annotations

import zlib

import pytest

from pypdfbox.filter.filter_factory import FilterFactory
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text


# --------------------------------------------------------------------------
# Encoders for the raw raster payloads — produced with stdlib / pypdfbox's own
# filter encoders, then embedded *verbatim* (binary) between ID and EI.
# --------------------------------------------------------------------------
def _enc_ahx(data: bytes) -> bytes:
    return data.hex().upper().encode("ascii") + b">"


def _enc_a85(data: bytes) -> bytes:
    import base64

    return base64.a85encode(data) + b"~>"


def _enc_flate(data: bytes) -> bytes:
    return zlib.compress(data)


def _enc_lzw(data: bytes) -> bytes:
    import io

    dst = io.BytesIO()
    FilterFactory.INSTANCE.get_filter("LZWDecode").encode(io.BytesIO(data), dst)
    return dst.getvalue()


def _enc_rl(data: bytes) -> bytes:
    import io

    dst = io.BytesIO()
    FilterFactory.INSTANCE.get_filter("RunLengthDecode").encode(io.BytesIO(data), dst)
    return dst.getvalue()


# A deterministic 4x4 / 8 bpc DeviceGray raster (16 bytes) used as the decoded
# target for every lossless case so the byte-exact assertion has a fixed goal.
_RASTER = bytes([0, 16, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 192, 208, 224, 240])


def _inline(params: bytes, data: bytes) -> bytes:
    # A leading whitespace after ID and a trailing whitespace before EI per the
    # spec; the binary payload is embedded verbatim.
    return b"BI " + params + b" ID " + data + b" EI\n"


# --------------------------------------------------------------------------
# Cases — (label, params, encoded-data) each decoding back to _RASTER.
# --------------------------------------------------------------------------
def _cases() -> list[tuple[str, bytes, bytes]]:
    cases: list[tuple[str, bytes, bytes]] = []
    base = b"/W 4 /H 4 /BPC 8 /CS /G "
    # Abbreviated single-filter forms.
    cases.append(("ahx", base + b"/F /AHx", _enc_ahx(_RASTER)))
    cases.append(("a85", base + b"/F /A85", _enc_a85(_RASTER)))
    cases.append(("lzw", base + b"/F /LZW", _enc_lzw(_RASTER)))
    cases.append(("fl", base + b"/F /Fl", _enc_flate(_RASTER)))
    cases.append(("rl", base + b"/F /RL", _enc_rl(_RASTER)))
    # Full-name forms (also accepted by inline images).
    cases.append(("flate_full", base + b"/F /FlateDecode", _enc_flate(_RASTER)))
    cases.append(
        ("ascii85_full", base + b"/F /ASCII85Decode", _enc_a85(_RASTER))
    )
    # Filter *chain*: A85 (outer, ASCII) wraps Flate (inner). Decode order is
    # left-to-right per the array, so encode inner-first.
    chain = _enc_a85(_enc_flate(_RASTER))
    cases.append(("a85_then_fl", base + b"/F [/A85 /Fl]", chain))
    return cases


_CASES = _cases()


# Expected verbatim filter names per case (what getFilters() should return).
_EXPECTED_FILTERS = {
    "ahx": ["AHx"],
    "a85": ["A85"],
    "lzw": ["LZW"],
    "fl": ["Fl"],
    "rl": ["RL"],
    "flate_full": ["FlateDecode"],
    "ascii85_full": ["ASCII85Decode"],
    "a85_then_fl": ["A85", "Fl"],
}


def _build_pdf(inline_block: bytes) -> bytes:
    body = bytearray(b"q 100 0 0 100 50 50 cm\n")
    body += inline_block
    body += b"Q\n"
    content = bytes(body)

    def obj(num: int, data: bytes) -> bytes:
        return f"{num} 0 obj\n".encode("ascii") + data + b"\nendobj\n"

    stream_obj = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)
    parts = [
        obj(1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        obj(
            3,
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
            b"/Contents 4 0 R /Resources << >> >>",
        ),
        obj(4, stream_obj),
    ]
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


def _pypdfbox_block(pdf_bytes: bytes) -> tuple[list[str], str]:
    """Return (filter-name list, lowercase-hex of get_data()) for the single
    inline image in ``pdf_bytes``."""
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
                return image.get_filters(), image.get_data().hex()
    raise AssertionError("no inline image parsed by pypdfbox")


def _oracle_block(tmp_path, pdf_bytes: bytes) -> tuple[list[str], str]:
    fixture = tmp_path / "inline_filter.pdf"
    fixture.write_bytes(pdf_bytes)
    try:
        text = run_probe_text("InlineFilterAbbrevProbe", str(fixture), "0")
    finally:
        fixture.unlink(missing_ok=True)
    lines = [ln for ln in text.splitlines() if ln != ""]
    # line 0 = filter names, line 1 = "LEN n HEX ...".
    names = [] if lines[0] == "-" else lines[0].split()
    parts = lines[1].split()
    # parts == ["LEN", n, "HEX", hex] — hex may be empty.
    hex_str = parts[3] if len(parts) > 3 else ""
    return names, hex_str


@requires_oracle
@pytest.mark.parametrize(
    ("label", "params", "data"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_inline_filter_abbrev_decode_matches_pdfbox(
    tmp_path, label: str, params: bytes, data: bytes
) -> None:
    """Inline-image filter abbreviation (``/AHx`` ``/A85`` ``/LZW`` ``/Fl``
    ``/RL`` + full forms + a chain) returns the same verbatim ``getFilters()``
    list and the same byte-exact ``getData()`` as Apache PDFBox."""
    pdf_bytes = _build_pdf(_inline(params, data))
    java_names, java_hex = _oracle_block(tmp_path, pdf_bytes)
    py_names, py_hex = _pypdfbox_block(pdf_bytes)

    assert py_names == java_names, (
        f"{label}: getFilters() diverges:\n  pypdfbox={py_names}\n  java    ={java_names}"
    )
    assert py_names == _EXPECTED_FILTERS[label], (
        f"{label}: getFilters() not the expected verbatim form: {py_names}"
    )
    assert py_hex == java_hex, (
        f"{label}: decoded getData() diverges from PDFBox:\n"
        f"  pypdfbox={py_hex}\n  java    ={java_hex}"
    )
    # And both must decode back to the original raster.
    assert py_hex == _RASTER.hex(), (
        f"{label}: pypdfbox decoded payload != source raster"
    )
