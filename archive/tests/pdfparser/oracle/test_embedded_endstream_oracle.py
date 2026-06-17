"""Live PDFBox differential parity for the EMBEDDED-``endstream`` recovery facet.

A stream whose *body bytes* contain the literal token ``endstream`` is the
worst case for length recovery. PDFBox's ``endstream``-scan workaround
(``COSParser.readUntilEndStream``) is a byte-substring search, so it would
truncate the body at the first embedded occurrence — *unless* the declared
``/Length`` is trusted first. ``COSParser.parseCOSStream`` only runs the scan
when ``validateStreamLength`` fails, so:

* **correct length** — the scan is short-circuited; the embedded token is
  harmless and the FULL body survives (``/Length`` unchanged).
* **wrong (short / long) length** and **missing length** — ``validateStreamLength``
  fails, the scan runs, the body is truncated at the embedded ``endstream``,
  and ``/Length`` is rewritten to the truncated count.

In the wrong/missing cases the recovery leaves the source cursor *mid-body*
(after the false terminator). ``COSParser.parseFileObject`` then reads a
trailing keyword that is NOT ``endobj`` and, in lenient mode, only *warns* —
it must keep the recovered stream rather than discard the object (Java lines
682-695). pypdfbox previously raised here, dropping the stream entirely; this
module pins the fix to PDFBox 3.0.7 byte-for-byte.

The :class:`EmbeddedEndstreamProbe` Java oracle emits, one line per stream
object sorted by ``(objNum, genNum)``::

    <objNum> <genNum>: rawlen=<n> sha=<hex> length=<resolved-/Length-or-none>

reading each body off ``createRawInputStream`` so the check is purely a
length-recovery fidelity comparison.
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

# A real content-stream body whose bytes embed the literal token
# ``endstream`` (inside a drawn-text literal). A naive forward scan would
# stop at that token; a trusted /Length must read past it.
_BODY = b"BT /F1 12 Tf 50 100 Td (the endstream word) Tj ET"
_REAL_LEN = len(_BODY)


def _build_pdf(length_value: int, *, omit_length: bool = False) -> bytes:
    """Hand-build a minimal 1-page PDF whose content stream (object 4) embeds
    the literal token ``endstream`` in its body, with a ``/Length`` of
    ``length_value`` (or omitted when ``omit_length``)."""
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 200 200] /Contents 4 0 R >>"
        ),
    }
    len_entry = b"" if omit_length else b" /Length %d" % length_value
    objs[4] = b"<<" + len_entry + b" >>\nstream\n" + _BODY + b"\nendstream"

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
    # Correct /Length: scan short-circuited, embedded token harmless,
    # full body preserved unchanged.
    "embed_correct_length": _build_pdf(_REAL_LEN),
    # Wrong (short / long) /Length: scan runs, truncates at the embedded
    # token, /Length rewritten to the truncated count.
    "embed_wrong_short": _build_pdf(_REAL_LEN - 10),
    "embed_wrong_long": _build_pdf(_REAL_LEN + 15),
    # Missing /Length: fallback readUntilEnd, same truncation + rewrite.
    "embed_missing_length": _build_pdf(0, omit_length=True),
}


def _pypdfbox_dump(data: bytes) -> str:
    """Produce the same canonical stream-recovery fingerprint the Java
    :class:`EmbeddedEndstreamProbe` emits, parsing ``data`` via
    :class:`PDFParser`."""
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
def test_embedded_endstream_recovery_matches_pdfbox(
    name: str, tmp_path: Path
) -> None:
    """pypdfbox must recover the SAME body bytes (SHA-256 + length) and the
    SAME rewritten ``/Length`` as PDFBox 3.0.7 for a stream whose body embeds
    the literal ``endstream`` token — preserving the full body when ``/Length``
    is correct and truncating at the embedded token (without discarding the
    stream) when it is wrong or missing."""
    data = _CASES[name]
    pdf_path = tmp_path / f"{name}.pdf"
    pdf_path.write_bytes(data)
    java = run_probe_text("EmbeddedEndstreamProbe", str(pdf_path))
    py = _pypdfbox_dump(data)
    assert py == java
    # Guard against a "both emit nothing" green: every case must surface the
    # one content-stream object (object 4).
    assert java.startswith("4 0: rawlen=")
