"""Live PDFBox differential parity for content-stream tokenization.

Compares pypdfbox's ``PDFStreamParser`` token sequence against Apache
PDFBox's ``PDFStreamParser.parse()`` on the same page, via the
``TokenizeProbe`` Java oracle. Each operand/operator is reduced to one
canonical line so the two languages can be compared byte-for-byte without
tripping over float-rendering or locale differences.

Canonical token grammar (must match ``oracle/probes/TokenizeProbe.java``)::

    OP:<name>            operator keyword
    INT:<n>              COSInteger
    REAL:<canon>         COSFloat (canonicalized, locale-independent)
    NAME:/<n>            COSName
    STR:<hexbytes>       COSString (raw bytes, lower-hex)
    BOOL:true|false      COSBoolean
    NULL                 COSNull
    ARRAY:<n>            COSArray header, then n element tokens
    DICT:<n>             COSDictionary header, then n key/value token pairs
    IMGDATA:<len>:<sha>  inline-image bytes carried by the ID operator
"""

from __future__ import annotations

import hashlib
import struct
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

import pytest

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
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# (relative fixture path, page index) — varied content: text, vector
# graphics, clipping, images, form XObjects, rotated pages, AcroForm.
_CASES = [
    ("text/BidiSample.pdf", 0),
    ("text/input/eu-001.pdf", 0),
    ("multipdf/rot0.pdf", 0),
    ("multipdf/rot90.pdf", 0),
    ("multipdf/PDFBOX-4417-001031.pdf", 0),
    ("pdfwriter/unencrypted.pdf", 0),
    ("pdfwriter/PDFBOX-3110-poems-beads.pdf", 0),
    ("pdmodel/interactive/form/AcroFormsBasicFields.pdf", 0),
    ("pdmodel/interactive/annotation/AnnotationTypes.pdf", 0),
    ("multipdf/PDFA3A.pdf", 0),
]


def _float32_shortest(value: float) -> str:
    """Shortest decimal string that round-trips through IEEE-754 single
    precision — the Python equivalent of Java's ``Float.toString(float)``.

    pypdfbox stores a COSFloat's value as the float64 widening of the
    parsed float32 (e.g. ``595.32`` parses to ``595.3200073242188``).
    Java's ``Float.toString`` instead emits the shortest decimal for the
    float32 (``595.32``). Feeding the widened double straight into the
    canonicalizer would round to a spurious ``595.32001``. So we first
    recover the shortest round-tripping decimal, matching Java's source
    string for the canonical-rounding step below.
    """
    target = struct.unpack("f", struct.pack("f", value))[0]
    for prec in range(1, 18):
        candidate = f"{value:.{prec}g}"
        if struct.unpack("f", struct.pack("f", float(candidate)))[0] == target:
            return candidate
    return repr(value)


def _canon_float(value: float) -> str:
    """Locale-independent canonical float rendering — mirror of
    ``TokenizeProbe.canonFloat``: take the shortest float32 string, round
    to 5 decimals (half-even), strip trailing zeros, normalize ``-0`` to
    ``0``."""
    if value != value:  # NaN
        return "nan"
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    # Build the Decimal from the float32's shortest string so the rounding
    # input matches Java's ``Float.toString(f)`` source exactly.
    bd = Decimal(_float32_shortest(value)).quantize(
        Decimal("0.00001"), rounding=ROUND_HALF_EVEN
    ).normalize()
    s = format(bd, "f")
    if s == "-0":
        s = "0"
    return s


def _hex(data: bytes) -> str:
    return data.hex()


def _emit_base(out: list[str], b: COSBase) -> None:
    if isinstance(b, COSInteger):
        out.append(f"INT:{b.long_value()}")
    elif isinstance(b, COSFloat):
        out.append(f"REAL:{_canon_float(b.float_value())}")
    elif isinstance(b, COSName):
        out.append(f"NAME:/{b.get_name()}")
    elif isinstance(b, COSString):
        out.append(f"STR:{_hex(b.get_bytes())}")
    elif isinstance(b, COSBoolean):
        out.append(f"BOOL:{'true' if b.get_value() else 'false'}")
    elif isinstance(b, COSNull):
        out.append("NULL")
    elif isinstance(b, COSArray):
        out.append(f"ARRAY:{b.size()}")
        for i in range(b.size()):
            _emit_base(out, b.get(i))
    elif isinstance(b, COSDictionary):
        out.append(f"DICT:{b.size()}")
        for key in b.key_set():
            out.append(f"NAME:/{key.get_name()}")
            _emit_base(out, b.get_dictionary_object(key))
    else:
        out.append(f"COS:{type(b).__name__}")


def _emit(out: list[str], tok: object) -> None:
    if isinstance(tok, Operator):
        out.append(f"OP:{tok.get_name()}")
        data = tok.get_image_data()
        if data is not None:
            sha = hashlib.sha1(data).hexdigest()  # noqa: S324 - parity hash, not security
            out.append(f"IMGDATA:{len(data)}:{sha}")
    elif isinstance(tok, COSBase):
        _emit_base(out, tok)
    else:
        out.append(f"UNKNOWN:{type(tok).__name__}")


def _render(tokens: list[object]) -> str:
    out: list[str] = []
    for tok in tokens:
        _emit(out, tok)
    # Probe uses ``out.print(sb)``; every token line already ends in '\n'.
    return "".join(line + "\n" for line in out)


def _pypdfbox_tokens(path: Path, page_index: int) -> str:
    doc = PDDocument.load(path)
    try:
        page = doc.get_page(page_index)
        parser = PDFStreamParser(page.get_contents_for_stream_parsing())
        return _render(parser.parse())
    finally:
        doc.close()


def _pypdfbox_tokens_raw(path: Path) -> str:
    return _render(PDFStreamParser.from_bytes(path.read_bytes()).parse())


@requires_oracle
@pytest.mark.parametrize(
    ("rel", "page"),
    _CASES,
    ids=[f"{rel.replace('/', '_')}_p{page}" for rel, page in _CASES],
)
def test_tokenize_matches_pdfbox(rel: str, page: int) -> None:
    fixture = _FIXTURES / rel
    assert fixture.is_file(), f"missing fixture: {fixture}"
    java = run_probe_text("TokenizeProbe", str(fixture), str(page))
    py = _pypdfbox_tokens(fixture, page)
    assert py == java


# Raw content-stream cases (``.cs`` files tokenized via the parser's
# byte-buffer constructor). These exist mainly to exercise the inline-image
# (BI/ID/EI) path — the classic tokenizer divergence point — without
# needing a binary PDF fixture. PDFBox's ``parse()`` folds the ID/EI bytes
# into the BI operator's image data (no standalone ID/EI tokens emitted),
# and we assert pypdfbox does the same byte-for-byte (image-data SHA-1).
_RAW_CASES = [
    "contentstream/inline_image_basic.cs",
    # Embedded ``EI`` byte pair inside the image data: exercises the
    # ``hasNoFollowingBinData`` / lookahead heuristic that stops a literal
    # ``EI`` in binary data from terminating the segment prematurely.
    "contentstream/inline_image_embedded_ei.cs",
]


@requires_oracle
@pytest.mark.parametrize(
    "rel", _RAW_CASES, ids=[r.replace("/", "_") for r in _RAW_CASES]
)
def test_tokenize_raw_matches_pdfbox(rel: str) -> None:
    fixture = _FIXTURES / rel
    assert fixture.is_file(), f"missing fixture: {fixture}"
    java = run_probe_text("TokenizeProbe", str(fixture), "--raw")
    py = _pypdfbox_tokens_raw(fixture)
    assert py == java
