"""Live PDFBox differential parity for indirect-``/Length`` stream resolution.

PDF 1.7 §7.3.8 explicitly permits a stream dictionary's ``/Length`` to be an
indirect reference rather than an inline integer — writers commonly emit
``/Length 5 0 R`` *before* the stream body, then back-patch the value into the
referenced object once the final byte count is known. A conforming parser must
read past ``stream\\n…\\nendstream`` *without* prior knowledge of the length,
then resolve the indirect reference (or, for a *forward* reference whose target
hasn't been parsed yet, defer + resolve once the full xref pool is available).

This module hand-builds three byte-identical-shape PDFs whose single
content-stream object 4 declares ``/Length 5 0 R`` — the target object 5 lives
at three different positions relative to the stream:

* ``forward`` — object 5 comes *after* object 4. Parser cannot resolve ``5 0 R``
  inline; it must read past ``endstream`` and look up the length later. This is
  the high-value case (it exercises the deferred resolution path).
* ``backward`` — object 5 comes *before* object 4. The xref entry for 5 is
  already known when 4 is parsed; resolution is immediate.
* ``wrong_indirect`` — object 5 says the wrong length. Parser must fall back to
  the ``endstream`` scan + rewrite ``/Length`` (PDFBox's
  ``validateStreamLength`` workaround).

For each case the :class:`IndirectLengthProbe` Java oracle emits::

    pages=<n>
    length=<resolved-/Length>
    text=<escaped extracted text>

and pypdfbox must produce the same canonical fingerprint. ``length`` is read
off the stream dictionary *after* parsing — PDFBox rewrites the entry with the
true byte count whenever the declared value disagreed with the recovered body.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_number import COSNumber
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.loader import Loader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# A real (parseable + extractable) content stream so PDFBox can show text.
_BODY = b"BT /F1 24 Tf 72 700 Td (Hello Indirect) Tj ET"
_REAL_LEN = len(_BODY)


def _build_pdf(*, length_value: int, length_obj_first: bool) -> bytes:
    """Hand-build a minimal 1-page PDF whose content stream (object 4) has
    ``/Length 5 0 R`` and where object 5 (the integer length) lives either
    BEFORE object 4 (``length_obj_first=True``) or AFTER it (``False``).

    ``length_value`` is the integer the length-object reports. Pass the real
    body length for a correct-but-indirect case; pass any other value to
    force ``validateStreamLength`` to fall back to the ``endstream`` scan and
    rewrite ``/Length`` with the recovered count.
    """
    body_obj = (
        b"<< /Length 5 0 R >>\nstream\n" + _BODY + b"\nendstream"
    )
    length_obj = b"%d" % length_value
    fixed_objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 6 0 R >> >> /Contents 4 0 R >>"
        ),
        6: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    # Emit shared objects first, then either object 5 -> 4 (backward) or
    # 4 -> 5 (forward).  PDFBox + pypdfbox both build the xref off the
    # ``N G obj`` offsets we record here, so emission order is what
    # decides whether the length lookup is a forward or backward jump.
    emission_order = (
        [1, 2, 3, 5, 4, 6] if length_obj_first else [1, 2, 3, 4, 5, 6]
    )
    bodies: dict[int, bytes] = dict(fixed_objs)
    bodies[4] = body_obj
    bodies[5] = length_obj
    for n in emission_order:
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + bodies[n] + b"\nendobj\n"
    xref_off = len(out)
    n_objs = max(bodies) + 1
    out += b"xref\n0 %d\n" % n_objs
    out += b"0000000000 65535 f \n"
    for n in range(1, n_objs):
        out += b"%010d 00000 n \n" % offsets[n]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % n_objs
    out += b"startxref\n%d\n%%%%EOF" % xref_off
    return bytes(out)


_CASES: dict[str, bytes] = {
    # The high-value case: ``/Length 5 0 R`` and object 5 hasn't been
    # parsed yet when object 4 is reached. Parser must read past
    # ``endstream`` without prior length knowledge and resolve later.
    "forward": _build_pdf(length_value=_REAL_LEN, length_obj_first=False),
    # Easier path: object 5 (the length) comes before object 4 (the stream),
    # so its xref entry is already known when ``5 0 R`` is resolved.
    "backward": _build_pdf(length_value=_REAL_LEN, length_obj_first=True),
    # Indirect /Length reports the WRONG byte count — parser must fall back
    # to the ``endstream`` scan + rewrite ``/Length`` with the recovered
    # length. Exercises PDFBox's ``validateStreamLength`` workaround.
    "wrong_indirect": _build_pdf(
        length_value=_REAL_LEN - 7, length_obj_first=False
    ),
}


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")


def _pypdfbox_dump(path: str) -> str:
    """Produce the same canonical indirect-length fingerprint the Java
    :class:`IndirectLengthProbe` emits, loading ``path`` via
    :meth:`Loader.load_pdf`. Returns ``PARSE_FAIL\\n`` on any throw."""
    try:
        cos = Loader.load_pdf(path)
    except Exception:
        return "PARSE_FAIL\n"
    try:
        pd = PDDocument(cos)
        pages = pd.get_number_of_pages()
        contents = pd.get_page(0).get_cos_object().get_dictionary_object(
            COSName.CONTENTS
        )
        resolved_len = -1
        if isinstance(contents, COSStream):
            len_item = contents.get_dictionary_object(COSName.LENGTH)
            if isinstance(len_item, COSNumber):
                resolved_len = len_item.long_value()
        text = PDFTextStripper().get_text(pd)
        return (
            f"pages={pages}\n"
            f"length={resolved_len}\n"
            f"text={_escape(text)}\n"
        )
    except Exception:
        return "PARSE_FAIL\n"
    finally:
        cos.close()


@requires_oracle
@pytest.mark.parametrize("name", list(_CASES), ids=list(_CASES))
def test_indirect_length_matches_pdfbox(name: str, tmp_path: Path) -> None:
    """pypdfbox must resolve indirect ``/Length`` (forward + backward) and
    fall back to ``endstream`` recovery for a wrong indirect ``/Length``
    with the SAME page count, resolved length, and extracted text as
    PDFBox 3.0.7."""
    pdf_path = tmp_path / f"{name}.pdf"
    pdf_path.write_bytes(_CASES[name])
    java = run_probe_text("IndirectLengthProbe", str(pdf_path))
    py = _pypdfbox_dump(str(pdf_path))
    assert py == java
    # Guard against a "both fail identically" green: the indirect-length
    # target is an actual successful load, not a shared PARSE_FAIL.
    assert java.startswith("pages=")
