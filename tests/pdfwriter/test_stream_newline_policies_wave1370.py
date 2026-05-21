"""Wave 1370 — stream / endstream newline policies.

PDF 32000-1 §7.3.8.1 pins the newline policy around the ``stream`` and
``endstream`` keywords:

* the ``stream`` keyword shall be followed by CRLF or LF only (never
  bare CR — readers can't tell a payload byte from a delimiter), and
* the ``endstream`` keyword shall be preceded by CRLF or LF (the
  reader strips up to two trailing EOL bytes when computing /Length).

pypdfbox uses CRLF on both sides for byte-for-byte parity with upstream
PDFBox, and the ``COSStandardOutputStream`` ``write_eol`` collapses to
LF when the previous byte already was an EOL — avoiding accidental
``\\r\\n\\n`` triples.
"""

from __future__ import annotations

import io
import re

from pypdfbox.cos import (
    COSDictionary,
    COSDocument,
    COSName,
    COSObject,
    COSStream,
)
from pypdfbox.loader import Loader
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream


def _make_stream_doc(raw: bytes) -> bytes:
    stream = COSStream()
    stream.set_raw_data(raw)
    stream.set_int(COSName.LENGTH, len(raw))  # type: ignore[attr-defined]

    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    catalog.set_item(
        COSName.get_pdf_name("Body"), COSObject(2, 0, resolved=stream)
    )
    cat_obj = COSObject(1, 0, resolved=catalog)
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, cat_obj)  # type: ignore[attr-defined]
    doc = COSDocument()
    doc.set_version(1.4)
    doc.set_trailer(trailer)
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(doc)
    return sink.getvalue()


# ---------- stream-keyword newline policy ---------------------------------


def test_stream_keyword_followed_by_crlf() -> None:
    """``stream`` MUST be followed by CRLF — readers consume exactly
    two bytes after the keyword."""
    raw = b"abcdef"
    out = _make_stream_doc(raw)
    stream_idx = out.index(b"stream")
    # The two bytes after "stream" must be CR LF.
    assert out[stream_idx + 6:stream_idx + 8] == b"\r\n"


def test_endstream_preceded_by_crlf() -> None:
    """The bytes immediately before ``endstream`` must be CRLF."""
    raw = b"ghijkl"
    out = _make_stream_doc(raw)
    end_idx = out.index(b"endstream")
    assert out[end_idx - 2:end_idx] == b"\r\n"


def test_endstream_followed_by_eol() -> None:
    """``endstream`` itself must be terminated by an EOL byte so the
    next ``endobj`` keyword starts on a fresh line."""
    raw = b"mnopqr"
    out = _make_stream_doc(raw)
    end_idx = out.index(b"endstream")
    tail = out[end_idx + len(b"endstream")]
    assert tail in (0x0A, 0x0D), f"unexpected endstream tail byte 0x{tail:02x}"


# ---------- /Length matches payload length exactly ------------------------


def test_length_matches_emitted_payload_bytes() -> None:
    """/Length must equal the count of bytes between the post-stream EOL
    and the pre-endstream EOL (exclusive). Specifically pypdfbox writes
    ``stream\\r\\n<payload>\\r\\nendstream`` so /Length == len(payload)."""
    raw = b"this is the payload - 32 bytes!!"  # exactly 32 bytes
    out = _make_stream_doc(raw)
    # Find the /Length entry in the stream dict.
    lengths = re.findall(rb"/Length (\d+)", out)
    # First /Length should be the stream's.
    assert int(lengths[0]) == len(raw)


def test_payload_round_trips_through_loader_after_crlf_framing() -> None:
    """Best end-to-end: the writer-side framing must let the parser
    pick the payload back up byte-for-byte."""
    raw = b"the round trip payload - kept intact"
    out = _make_stream_doc(raw)
    parsed = Loader.load_pdf(out)
    try:
        cat = parsed.get_catalog()
        assert cat is not None
        body = cat.get_dictionary_object(COSName.get_pdf_name("Body"))
        assert isinstance(body, COSStream)
        assert body.get_raw_data() == raw
    finally:
        parsed.close()


# ---------- raw COSStandardOutputStream EOL helpers -----------------------


def test_write_crlf_emits_literal_cr_lf_pair() -> None:
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)
    out.write_crlf()
    assert sink.getvalue() == b"\r\n"


def test_write_lf_emits_single_lf() -> None:
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)
    out.write_lf()
    assert sink.getvalue() == b"\n"


def test_consecutive_write_eol_calls_collapse_to_single_eol() -> None:
    """After the first ``write_eol`` the on-new-line flag flips to True,
    so a second ``write_eol`` is a no-op — prevents stacked blank lines
    after the ``endstream`` / ``endobj`` pair."""
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)
    out.write(b"hi")
    out.write_eol()  # flips on-new-line True.
    out.write_eol()  # already on newline -> no-op.
    out.write_eol()  # still no-op.
    out.write(b"x")
    # Expect exactly one EOL byte between "hi" and "x".
    val = sink.getvalue()
    assert val.startswith(b"hi")
    assert val.endswith(b"x")
    body = val[2:-1]
    # All bytes in body must be EOL bytes, and only one of them.
    assert len(body) == 1
    assert body in (b"\n", b"\r")


def test_write_eol_emits_eol_when_not_on_newline() -> None:
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)
    out.write(b"abc")
    out.write_eol()
    # The exact EOL byte depends on the EOL constant; just verify the
    # buffer now ends with one EOL byte.
    val = sink.getvalue()
    assert val.startswith(b"abc")
    assert val[-1] in (0x0A, 0x0D)


def test_empty_stream_still_frames_with_crlf_pair() -> None:
    """A zero-byte stream payload must still emit ``stream\\r\\n\\r\\nendstream``
    — never collapse to ``stream\\r\\nendstream`` (that would change
    /Length semantics on round-trip)."""
    raw = b""
    out = _make_stream_doc(raw)
    stream_idx = out.index(b"stream")
    end_idx = out.index(b"endstream")
    # Between ``stream`` + CRLF and ``endstream``'s preceding CRLF the
    # body length is 0 — confirm by slicing.
    body_start = stream_idx + len(b"stream") + 2
    body_end = end_idx - 2
    assert body_end - body_start == 0
    # And both CRLFs are present in their canonical positions.
    assert out[stream_idx + 6:stream_idx + 8] == b"\r\n"
    assert out[end_idx - 2:end_idx] == b"\r\n"
