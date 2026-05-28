"""Live PDFBox differential parity for exponential-notation real numbers in
content streams.

PDF 32000-1 §7.3.3 defines real numbers as ``[+-]?(\\d+|\\d*\\.\\d+|\\d+\\.\\d*)`` —
exponential notation (``1e3`` / ``1.5E-2``) is OUT OF SPEC. Real-world PDF
writers nevertheless emit them. PDFBox's two number-parsing entry points
diverge here:

* ``PDFStreamParser.parseNextToken`` (top-level content-stream operand) inlines
  its own number reader that accepts only digits, ``.``, and ``-``. An exp
  marker ``e``/``E`` is NOT consumed; ``1.5e2 12 Tf`` tokenises as ``1.5``
  (COSFloat) + ``e`` (operator) + ``2`` (COSInteger) + ``12`` (COSInteger) +
  ``Tf`` — garbage downstream of the malformed number, but the parser
  tolerates it (no throw).
* ``BaseParser.parseCOSNumber`` (called by ``parseDirectObject`` for numbers
  inside arrays / dictionaries) accepts ``e``/``E`` and an optional exponent
  sign. ``[-1.5e3] TJ`` parses cleanly as ``[COSFloat(-1500.0)] TJ``.

This module hand-builds five PDFs covering both branches plus a clean control.
Each is loaded via PDFBox's ``Loader.loadPDF`` and through pypdfbox's
``Loader.load_pdf``; both must produce the same canonical fingerprint (page
count + extracted text + the canonical token sequence parsed off each page's
content stream).

A bug in pypdfbox before wave 1453 was that ``BaseParser.read_number``
matched only the spec's grammar (no exp marker), so the in-array case raised
``PDFParseError("unexpected byte 0x65 ('e') at start of object")`` and the
``[ ... ] TJ`` array came back EMPTY. The fix extends ``read_number`` to
mirror PDFBox's lenient parseCOSNumber accept set.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSNull, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.loader import Loader
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text


def _build_pdf(stream_body: bytes) -> bytes:
    """Assemble a minimal 1-page PDF whose content stream is ``stream_body``."""
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: b"<< /Length %d >>\nstream\n%s\nendstream" % (
            len(stream_body),
            stream_body,
        ),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        6: b"<< /Producer (pypdfbox-test) /Title (ExpNotation) >>",
    }
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"
    xref_off = len(out)
    n_objs = max(objs) + 1
    out += b"xref\n0 %d\n" % n_objs
    out += b"0000000000 65535 f \n"
    for n in range(1, n_objs):
        out += b"%010d 00000 n \n" % offsets[n]
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info 6 0 R >>\n" % n_objs
    out += b"startxref\n%d\n%%%%EOF" % xref_off
    return bytes(out)


# ---- content-stream cases ----

_CASES: dict[str, bytes] = {
    # Plain control — no exp notation anywhere.
    "clean": b"BT /F1 12 Tf 72 700 Td (Plain) Tj ET",
    # Exp notation as a top-level Tf operand. Both engines split it at ``e``.
    "tf_exp_pos": b"BT /F1 1.5e2 Tf 72 700 Td (HelloPos) Tj ET",
    # Exp notation as a top-level rg operand with a negative exponent.
    "rg_exp_neg": (
        b"BT /F1 12 Tf 72 700 Td (HelloNeg) Tj ET 1.5e-2 0 0 rg"
    ),
    # Exp notation INSIDE a TJ positioning array — exercises parseDirectObject,
    # which is the exp-aware path on both engines. Uses a small negative kern
    # (-50) that does NOT cross PDFBox's word-break heuristic, so text
    # extraction returns ``AB`` (no inserted space) on both engines and the
    # parity check stays on the parser surface.
    "tj_array_exp": (
        b"BT /F1 12 Tf 72 700 Td [(A)-5e1(B)] TJ ET"
    ),
    # Multiple exp-notation reals in a single array — strings concatenate
    # because the small kerns stay below the stripper's word-break gate.
    "array_mixed_exp": (
        b"BT /F1 12 Tf 72 700 Td [(M) 1e1 (N) -2.5E-1 (O)] TJ ET"
    ),
}


# ---- pypdfbox-side fingerprint (mirrors ExpNotationProbe's output) ----


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _java_float_repr(value: float) -> str:
    """Mirror ``Float.toString(float)`` to one decimal place for whole values
    (Java emits ``-1500.0``; Python's ``repr`` emits ``-1500.0`` already, but
    drops to integer style for round numbers). For non-integer or exp-range
    values, fall back to a shortest-round-tripping decimal."""
    # COSFloat coerces to IEEE-754 single precision on construction, so any
    # value we get out is already float32-representable. The probe's canon
    # branch uses ``Float.toString(((COSNumber) o).floatValue())`` — that
    # contract for floats inside ``[1e-3, 1e7)`` produces decimal form with
    # at least one fractional digit (``-1500.0``, ``0.25``). Outside that
    # window Java switches to ``XEY`` (e.g. ``1.0E-4``); none of our test
    # cases hit that window, so emit Java-style decimal form unconditionally.
    if value != value:  # NaN
        return "NaN"
    if value == 0.0:
        return "-0.0" if str(value).startswith("-") else "0.0"
    # Use Python's repr but normalise the ``int`` shape to ``int.0`` and
    # uppercase scientific exponents to ``E``.
    r = repr(value)
    if "e" in r:
        mantissa, exp = r.split("e", 1)
        if "." not in mantissa:
            mantissa += ".0"
        return mantissa + "E" + exp.lstrip("+")
    if "." not in r:
        r += ".0"
    return r


def _canon_token(t: object) -> str:
    if t is None or isinstance(t, COSNull):
        return "null"
    if isinstance(t, COSInteger):
        return f"i{t.long_value()}"
    if isinstance(t, COSFloat):
        return f"f{_java_float_repr(t.float_value())}"
    if isinstance(t, COSName):
        return f"n{t.get_name()}"
    if isinstance(t, COSString):
        return f"s{t.get_string()}"
    if isinstance(t, COSArray):
        inner = ",".join(_canon_token(e) for e in t)
        return f"a[{inner}]"
    if isinstance(t, Operator):
        return f"op:{t.name}"
    return f"?{type(t).__name__}"


def _canon_tokens(toks: list[object]) -> str:
    return ",".join(_canon_token(t) for t in toks)


def _page_content_bytes(pd: PDDocument, page_index: int) -> bytes:
    """Return the concatenated raw bytes of a page's /Contents stream(s).
    ``PDPage.get_contents`` already unwinds the filter chain and joins an
    array form with newlines so the byte buffer hands to ``PDFStreamParser``
    the same operator stream the renderer would walk."""
    return pd.get_page(page_index).get_contents()


def _pypdfbox_dump(path: str) -> str:
    """Produce the same canonical fingerprint the ``ExpNotationProbe`` Java
    oracle emits. Returns ``PARSE_FAIL\\n`` on any load throw."""
    try:
        cos = Loader.load_pdf(path)
    except Exception:
        return "PARSE_FAIL\n"
    try:
        pd = PDDocument(cos)
        pages = pd.get_number_of_pages()
        try:
            text = PDFTextStripper().get_text(pd)
        except Exception:
            text = "<EXTRACT_FAIL>"
        lines = [f"pages={pages}\n", f"text={_escape(text)}\n"]
        for i in range(pages):
            body = _page_content_bytes(pd, i)
            try:
                parser = PDFStreamParser(RandomAccessReadBuffer(body))
                raw = parser.parse()
                canon = _canon_tokens(raw)
            except Exception as exc:
                canon = f"TOKEN_FAIL:{type(exc).__name__}"
            lines.append(f"tokens.page{i}={canon}\n")
        return "".join(lines)
    except Exception:
        return "PARSE_FAIL\n"
    finally:
        cos.close()


@requires_oracle
@pytest.mark.parametrize("name", list(_CASES), ids=list(_CASES))
def test_exp_notation_matches_pdfbox(name: str, tmp_path: Path) -> None:
    """pypdfbox's content-stream + array-direct-object number parsers must
    agree with PDFBox 3.0.7 on tokens, page count, and extracted text for
    every exp-notation case — both the lenient parseDirectObject branch
    (in-array, accepts exp) and the strict top-level branch (rejects exp,
    falls through to an operator-like keyword)."""
    pdf_path = tmp_path / f"{name}.pdf"
    pdf_path.write_bytes(_build_pdf(_CASES[name]))
    java = run_probe_text("ExpNotationProbe", str(pdf_path))
    py = _pypdfbox_dump(str(pdf_path))
    assert py == java, f"mismatch for case {name!r}:\nPY:  {py!r}\nJAVA:{java!r}"
    # Guard against a "both fail identically" green — every case must produce
    # a real fingerprint, not a shared PARSE_FAIL.
    assert java.startswith("pages="), f"expected fingerprint, got: {java!r}"
