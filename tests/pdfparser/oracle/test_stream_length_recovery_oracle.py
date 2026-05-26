"""Live PDFBox differential parity for stream-length / ``endstream`` recovery.

Real-world PDFs frequently carry a stream ``/Length`` that is *wrong* (too
short, too long, zero), *missing*, or an *indirect reference* (which may itself
resolve to a wrong value). A conforming lenient parser must, in those cases,
recover the true body by scanning forward to the next ``endstream`` keyword —
exactly what Apache PDFBox's ``COSParser.parseCOSStream`` does via
``validateStreamLength`` + ``readUntilEndStream`` (and then rewrites ``/Length``
with the recovered value).

This module hand-crafts a family of tiny PDFs whose single content stream has a
deliberately tricky ``/Length`` and asserts that pypdfbox recovers the *same*
body bytes (SHA-256 + length) and the *same* resolved ``/Length`` as PDFBox
3.0.7 — via the ``StreamLenRecoverProbe`` Java oracle. The probe reads each
stream's raw (encoded) body straight off ``createRawInputStream`` so the
comparison is filter-independent: it is purely a length-recovery fidelity check.

Canonical line (one per stream object, sorted by ``(objNum, genNum)``)::

    <objNum> <genNum>: rawlen=<n> sha=<hex> length=<resolved-/Length-or-none>
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_number import COSNumber
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_parser import PDFParser
from tests.oracle.harness import requires_oracle, run_probe_text

# A real (parseable) content-stream body so PDFBox is happy to load the page.
_BODY = b"BT /F1 12 Tf 50 100 Td (Hi) Tj ET"
_REAL_LEN = len(_BODY)


def _build_pdf(
    length_value: int,
    *,
    indirect_length: bool = False,
    omit_length: bool = False,
) -> bytes:
    """Hand-build a minimal 1-page PDF whose content stream (object 4) has a
    ``/Length`` of ``length_value`` (direct, indirect, or omitted)."""
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 200 200] /Contents 4 0 R >>"
        ),
    }
    if omit_length:
        len_entry = b""
    elif indirect_length:
        len_entry = b" /Length 5 0 R"
    else:
        len_entry = b" /Length %d" % length_value
    objs[4] = b"<<" + len_entry + b" >>\nstream\n" + _BODY + b"\nendstream"
    if indirect_length:
        objs[5] = b"%d" % length_value

    out = bytearray(b"%PDF-1.7\n")
    offsets: dict[int, int] = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"
    xref_off = len(out)
    n_objs = max(objs) + 1
    out += b"xref\n0 %d\n" % n_objs
    out += b"0000000000 65535 f \n"
    for n in range(1, n_objs):
        if n in offsets:
            out += b"%010d 00000 n \n" % offsets[n]
        else:
            out += b"0000000000 65535 f \n"
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % n_objs
    out += b"startxref\n%d\n%%%%EOF" % xref_off
    return bytes(out)


# (name, raw bytes) — each name doubles as the parametrize id.
_CASES: dict[str, bytes] = {
    "correct_length": _build_pdf(_REAL_LEN),
    "wrong_length_short": _build_pdf(_REAL_LEN - 5),
    "wrong_length_long": _build_pdf(_REAL_LEN + 10),
    "wrong_length_zero": _build_pdf(0),
    "missing_length": _build_pdf(_REAL_LEN, omit_length=True),
    "indirect_length": _build_pdf(_REAL_LEN, indirect_length=True),
    "indirect_wrong_length": _build_pdf(_REAL_LEN - 3, indirect_length=True),
}


def _pypdfbox_dump(data: bytes) -> str:
    """Produce the same canonical stream-recovery fingerprint the Java
    ``StreamLenRecoverProbe`` emits, parsing ``data`` via :class:`PDFParser`."""
    parser = PDFParser(RandomAccessReadBuffer(data))
    doc = parser.parse()
    try:
        keys = sorted(
            doc.get_xref_table().keys(),
            key=lambda k: (k.get_number(), k.get_generation()),
        )
        lines: list[str] = []
        for key in keys:
            obj = doc.get_object_from_pool(key)
            try:
                resolved = obj.get_object()
            except Exception:
                continue
            if not isinstance(resolved, COSStream):
                continue
            raw = resolved.get_raw_data()
            sha = hashlib.sha256(raw).hexdigest()
            len_item = resolved.get_dictionary_object(COSName.LENGTH)
            len_str = (
                str(len_item.long_value())
                if isinstance(len_item, COSNumber)
                else "none"
            )
            lines.append(
                f"{key.get_number()} {key.get_generation()}: "
                f"rawlen={len(raw)} sha={sha} length={len_str}"
            )
        return "".join(line + "\n" for line in lines)
    finally:
        doc.close()


@requires_oracle
@pytest.mark.parametrize("name", list(_CASES), ids=list(_CASES))
def test_stream_length_recovery_matches_pdfbox(
    name: str, tmp_path: Path
) -> None:
    data = _CASES[name]
    pdf_path = tmp_path / f"{name}.pdf"
    pdf_path.write_bytes(data)
    java = run_probe_text("StreamLenRecoverProbe", str(pdf_path))
    py = _pypdfbox_dump(data)
    assert py == java
