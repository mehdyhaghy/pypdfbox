"""Live PDFBox differential parity for ``PDPageContentStream.drawImage``.

Does pypdfbox's :meth:`PDPageContentStream.draw_image` emit the same
content-stream tokens as Apache PDFBox for each of the three upstream
``drawImage`` overloads, and register the image XObject in
``/Resources /XObject`` the same way?

The Java side is ``oracle/probes/DrawImageProbe.java``: for each overload
it builds a one-page PDF, draws a fixed deterministic 4x3 image, saves,
re-parses the page content with ``PDFStreamParser`` and emits a canonical
token stream plus a ``RES:/<name>=Subtype:.. Width:.. Height:..`` line for
the resource registration. The three blocks are separated by ``===form===``
markers.

Each overload must emit ``q`` / ``<a b c d e f> cm`` / ``/Name Do`` / ``Q``:

- ``draw_image(image, x, y)`` → ``cm = [W 0 0 H x y]`` (W/H = image px size).
- ``draw_image(image, x, y, w, h)`` → ``cm = [w 0 0 h x y]``.
- ``draw_image(image, (a, b, c, d, e, f))`` → ``cm`` is the matrix verbatim.

Normalisation (legitimate, format-only differences — NOT bugs):

- **Numeric int-vs-real** is collapsed (``NUM:<canon>``) exactly as the
  content-generation oracle does: PDFBox round-trips ``2 cm`` through a
  COSInteger while pypdfbox may format a whole-valued float as a bare int;
  only the value matters.
- **The resource-slot index** of the auto-allocated XObject name differs by
  a known codebase-wide divergence (pypdfbox 0-based ``/Im0`` vs upstream
  1-based ``/Im1``). The trailing digits of an ``/<word><digits>`` token are
  canonicalised on both sides so the slot number is not counted as this
  wave's bug (tracked separately).
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_EVEN, Decimal

from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from tests.oracle.harness import requires_oracle, run_probe_text


def _canon_float(value: float) -> str:
    d = (
        Decimal(repr(float(value)))
        .quantize(Decimal("0.00001"), rounding=ROUND_HALF_EVEN)
        .normalize()
    )
    s = format(d, "f")
    if s == "-0":
        s = "0"
    return s


def _fixed_image() -> Image.Image:
    """Deterministic 4x3 RGBA image matching DrawImageProbe.fixedImage()."""
    img = Image.new("RGBA", (4, 3))
    px = img.load()
    for y in range(3):
        for x in range(4):
            px[x, y] = (x * 40, y * 60, 0x33, 0xFF)
    return img


def _emit_base(lines: list[str], b: object) -> None:
    if isinstance(b, COSInteger):
        lines.append(f"INT:{b.long_value()}")
    elif isinstance(b, COSFloat):
        lines.append(f"REAL:{_canon_float(b.float_value())}")
    elif isinstance(b, COSName):
        lines.append(f"NAME:/{b.get_name()}")
    elif isinstance(b, COSString):
        lines.append(f"STR:{b.get_bytes().hex()}")
    elif isinstance(b, COSBoolean):
        lines.append(f"BOOL:{'true' if b.get_value() else 'false'}")
    elif isinstance(b, COSNull):
        lines.append("NULL")
    elif isinstance(b, COSArray):
        lines.append(f"ARRAY:{len(b)}")
        for el in b:
            _emit_base(lines, el)
    elif isinstance(b, COSDictionary):
        keys = list(b.key_set())
        lines.append(f"DICT:{len(keys)}")
        for key in keys:
            lines.append(f"NAME:/{key.get_name()}")
            _emit_base(lines, b.get_dictionary_object(key))
    else:
        lines.append(f"COS:{type(b).__name__}")


def _tokenize_py(data: bytes) -> list[str]:
    lines: list[str] = []
    parser = PDFStreamParser.from_bytes(data)
    try:
        for tok in parser.parse():
            if isinstance(tok, Operator):
                lines.append(f"OP:{tok.get_name()}")
            else:
                _emit_base(lines, tok)
    finally:
        parser.close()
    return lines


_NUM_RE = re.compile(r"^(INT|REAL):(.+)$")
# A NAME or RES token carrying an auto-allocated resource slot: /Im1, /Im0, etc.
_SLOT_RE = re.compile(r"/([A-Za-z]+)\d+")


def _normalize(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        m = _NUM_RE.match(line)
        if m:
            out.append(f"NUM:{_canon_float(float(m.group(2)))}")
        else:
            # Canonicalise the auto-allocated XObject slot index (known
            # 0-based vs 1-based divergence) in both NAME:/Imn and RES:/Imn.
            out.append(_SLOT_RE.sub(r"/\1#", line))
    return out


def _py_block(doc_pdf, draw) -> list[str]:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 300.0, 400.0))
        doc.add_page(page)
        img = LosslessFactory.create_from_image(doc, _fixed_image())
        with PDPageContentStream(doc, page) as cs:
            draw(cs, img)
        body = page.get_contents()
        res = page.get_resources()
        lines = _tokenize_py(body)
        for name in res.get_x_object_names():
            sub = res.get_cos_object().get_dictionary_object(
                COSName.get_pdf_name("XObject")
            )
            raw = sub.get_dictionary_object(name)
            subtype = raw.get_name_as_string(COSName.get_pdf_name("Subtype"))
            width = raw.get_int(COSName.get_pdf_name("Width"))
            height = raw.get_int(COSName.get_pdf_name("Height"))
            lines.append(
                f"RES:/{name.get_name()}=Subtype:{subtype} "
                f"Width:{width} Height:{height}"
            )
        return _normalize(lines)
    finally:
        doc.close()


def _split_blocks(raw: str) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    cur: str | None = None
    for line in raw.splitlines():
        if line.startswith("===") and line.endswith("==="):
            cur = line.strip("=")
            blocks[cur] = []
        elif cur is not None and line:
            blocks[cur].append(line)
    return {k: _normalize(v) for k, v in blocks.items()}


@requires_oracle
def test_draw_image_overloads_match_pdfbox(tmp_path) -> None:
    out_pdf = tmp_path / "draw_image.pdf"
    java = _split_blocks(run_probe_text("DrawImageProbe", str(out_pdf)))

    py = {
        "xy": _py_block(out_pdf, lambda cs, img: cs.draw_image(img, 10.0, 20.0)),
        "xywh": _py_block(
            out_pdf, lambda cs, img: cs.draw_image(img, 30.0, 40.0, 100.0, 50.0)
        ),
        "matrix": _py_block(
            out_pdf,
            lambda cs, img: cs.draw_image(img, (2.0, 0.5, 0.25, 3.0, 7.0, 11.0)),
        ),
    }

    for form in ("xy", "xywh", "matrix"):
        assert py[form] == java[form], (
            f"draw_image({form}) token/resource stream diverges from PDFBox.\n"
            f"--- pypdfbox ---\n{chr(10).join(py[form])}\n"
            f"--- java ---\n{chr(10).join(java[form])}"
        )
