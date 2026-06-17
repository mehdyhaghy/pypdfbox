"""Live PDFBox differential parity for object-header / endobj leniency.

Real-world PDFs often carry malformations around the
``N G obj ... endobj`` envelope that Apache PDFBox's lenient parser
tolerates: extra whitespace between the header and the object body, a
``%``-comment inserted inside an object, a missing ``endobj`` (next
``N G obj`` marker arrives directly), and extra garbage bytes between
``endobj`` and the next object.

This module hand-builds a valid 6-object, 1-page PDF (real Helvetica
text) and then MALFORMS object 5 (the font dict) four different ways —
each still recoverable. Object 5 is downstream of the page graph that
``PDFTextStripper`` walks, so a recovery failure on object 5 won't
torpedo text extraction; we still pin the OUTCOME (page count, object
count, /Root /Info presence, extracted text) against the
:class:`ObjHeaderLenientProbe` Java oracle to confirm pypdfbox's lenient
behaviour matches PDFBox's bit-for-bit.

Because every mutation shifts the byte offset of object 6 (the info
dict), the xref subsection entries past object 5 become stale. Both
engines must fall through to brute-force ``N G obj`` recovery — that's
the high-value lenience marker exercised here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pypdfbox.cos.cos_name import COSName
from pypdfbox.loader import Loader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# ---- baseline: a well-formed minimal 1-page PDF ----

_BODY = b"BT /F1 24 Tf 72 700 Td (Hello) Tj ET"


def _build_pdf() -> bytes:
    """Assemble a well-formed 6-object, 1-page PDF with a traditional
    xref table + trailer + ``startxref``."""
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: b"<< /Length %d >>\nstream\n%s\nendstream" % (len(_BODY), _BODY),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        6: b"<< /Producer (pypdfbox-test) /Title (Header Lenient Fixture) >>",
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


# ---- the four header-malformation modes ----


def _mutate_extra_ws(data: bytes) -> bytes:
    """(a) Insert extra whitespace (spaces + EOL) between the
    ``5 0 obj`` header and the dictionary body."""
    return data.replace(b"5 0 obj\n<<", b"5 0 obj\n     \n  <<")


def _mutate_comment_in_obj(data: bytes) -> bytes:
    """(b) Insert a ``%``-comment between the ``5 0 obj`` header and
    the dictionary body — comments are syntactically whitespace per
    ISO 32000-1 §7.2.4 so a lenient parser must accept them anywhere a
    whitespace skipper is invoked."""
    return data.replace(
        b"5 0 obj\n<<", b"5 0 obj\n%a comment in the middle\n<<"
    )


def _mutate_missing_endobj(data: bytes) -> bytes:
    """(c) Strip the ``endobj`` keyword between object 5 and object 6
    so the next ``N G obj`` marker arrives directly. PDFBox treats the
    next object header as an implicit ``endobj``."""
    pattern = re.compile(rb"(5 0 obj\n[^\n]*\n)endobj\n(6 0 obj)", re.DOTALL)
    out = pattern.sub(rb"\1\2", data)
    assert out != data, "missing-endobj mutation did not apply"
    return out


def _mutate_extra_bytes(data: bytes) -> bytes:
    """(d) Insert garbage bytes (and a CRLF) between object 5's
    ``endobj`` and object 6's header. PDFBox's brute-force scan skips
    past anything that isn't a valid ``N G obj`` header."""
    return data.replace(
        b"endobj\n6 0 obj", b"endobj\r\nXYZ_garbage_bytes\n6 0 obj"
    )


_CLEAN = _build_pdf()
_CASES: dict[str, bytes] = {
    "clean": _CLEAN,
    "extra_ws": _mutate_extra_ws(_CLEAN),
    "comment_in_obj": _mutate_comment_in_obj(_CLEAN),
    "missing_endobj": _mutate_missing_endobj(_CLEAN),
    "extra_bytes": _mutate_extra_bytes(_CLEAN),
}


# ---- pypdfbox-side fingerprint (mirrors ObjHeaderLenientProbe's output) ----


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")


def _pypdfbox_dump(path: str) -> str:
    """Produce the same canonical fingerprint the Java
    ``ObjHeaderLenientProbe`` emits, loading ``path`` via the lenient
    (default) ``Loader.load_pdf``. Returns ``PARSE_FAIL\\n`` on any throw."""
    try:
        cos = Loader.load_pdf(path)
    except Exception:
        return "PARSE_FAIL\n"
    try:
        pd = PDDocument(cos)
        pages = pd.get_number_of_pages()
        objects = len(cos.get_xref_table())
        trailer = cos.get_trailer()
        root = (
            trailer is not None
            and trailer.get_dictionary_object(COSName.ROOT) is not None
        )
        info = (
            trailer is not None
            and trailer.get_dictionary_object(COSName.get_pdf_name("Info"))
            is not None
        )
        text = PDFTextStripper().get_text(pd)
        return (
            f"pages={pages}\n"
            f"objects={objects}\n"
            f"root={'present' if root else 'absent'}\n"
            f"info={'present' if info else 'absent'}\n"
            f"text={_escape(text)}\n"
        )
    except Exception:
        return "PARSE_FAIL\n"
    finally:
        cos.close()


@requires_oracle
@pytest.mark.parametrize("name", list(_CASES), ids=list(_CASES))
def test_obj_header_lenient_matches_pdfbox(name: str, tmp_path: Path) -> None:
    """pypdfbox must recover the same page count, object count, /Root
    /Info presence, and extracted text as PDFBox 3.0.7 for every
    object-header malformation."""
    pdf_path = tmp_path / f"{name}.pdf"
    pdf_path.write_bytes(_CASES[name])
    java = run_probe_text("ObjHeaderLenientProbe", str(pdf_path))
    py = _pypdfbox_dump(str(pdf_path))
    assert py == java
    # Guard against a "both fail identically" green: the lenience target
    # is a real recovery, not a shared PARSE_FAIL.
    assert java.startswith("pages="), f"expected recovery, got: {java!r}"
