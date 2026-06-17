"""Live PDFBox differential parity for the COSStream WIRE FORMAT on write.

Strict **byte-equality** check of the exact bytes ``COSWriter.visit_from_stream``
emits for a stream object (PDF 32000-1 §7.3.8):

* dictionary framing first (``<< ... >>``);
* the literal ``stream`` keyword followed by a **CR-LF** pair (PDFBox uses
  ``writeCRLF`` here, not a bare LF);
* the raw (already filter-encoded) body bytes verbatim;
* a **CR-LF** pair, then ``endstream``, then a single LF (``writeEOL``);
* ``/Length`` written as a DIRECT integer in the dict (never an indirect ref),
  equal to the encoded body length;
* NO ``/DL`` (decoded-length) entry — that is an ObjStm-only artifact of the
  compressed writer, never emitted for a plain stream.

The Java oracle is ``oracle/probes/StreamWireFormatProbe.java``, which drives
PDFBox's own ``COSWriter.visitFromStream`` straight into a ``ByteArrayOutputStream``
(no document / header / xref) and prints ``<label>: <hex>`` for the full byte
image plus ``<label>_length`` and ``<label>_has_dl``.

To keep this test scoped to the **wire framing** (and not to FlateDecode
compression-byte parity, which Java's ``Deflater`` and Python's ``zlib`` do not
guarantee identical and which is pinned by separate filter oracles), the Python
side does NOT re-encode the payload. It takes the *exact* raw body bytes PDFBox
emitted between the ``stream\\r\\n`` and ``\\r\\nendstream`` markers, stores them
verbatim in a pypdfbox ``COSStream`` along with the matching ``/Filter`` entry,
then drives ``COSWriter.visit_from_stream`` and asserts the full byte image is
identical. The framing, ``/Length`` form, and ``/DL`` absence are thereby
compared apples-to-apples regardless of which deflate implementation produced
the body.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdfwriter.cos_writer import COSWriter
from tests.oracle.harness import requires_oracle, run_probe

# Wire-format markers PDFBox emits around the body.
_STREAM_PREFIX = b"stream\r\n"
_BODY_SUFFIX = b"\r\nendstream"

# /Filter chains keyed by probe label — must match StreamWireFormatProbe.
_FILTERS: dict[str, list[str] | None] = {
    "empty": None,
    "raw": None,
    "flate": ["FlateDecode"],
    "chain": ["ASCII85Decode", "FlateDecode"],
    "onebyte": None,
}


def _parse_probe() -> dict[str, dict[str, object]]:
    """Run the probe and return ``{label: {"image": bytes, "length": int,
    "has_dl": bool}}`` parsed from its ``<key>: <value>`` lines."""
    raw = run_probe("StreamWireFormatProbe")
    cases: dict[str, dict[str, object]] = {}
    for line in raw.split(b"\n"):
        if not line.strip():
            continue
        key, _, value = line.partition(b": ")
        key_s = key.decode("ascii")
        val_s = value.decode("ascii")
        if key_s.endswith("_length"):
            cases.setdefault(key_s[: -len("_length")], {})["length"] = int(val_s)
        elif key_s.endswith("_has_dl"):
            cases.setdefault(key_s[: -len("_has_dl")], {})["has_dl"] = (
                val_s == "true"
            )
        else:
            cases.setdefault(key_s, {})["image"] = bytes.fromhex(val_s)
    return cases


def _extract_body(image: bytes) -> bytes:
    """Return the raw body bytes PDFBox wrote between the framing markers."""
    start = image.index(_STREAM_PREFIX) + len(_STREAM_PREFIX)
    end = image.rindex(_BODY_SUFFIX)
    return image[start:end]


def _emit_pypdfbox(body: bytes, filters: list[str] | None) -> bytes:
    """Build a COSStream holding ``body`` verbatim (+ matching /Filter) and
    serialise it through ``COSWriter.visit_from_stream``."""
    stream = COSStream()
    if body:
        with stream.create_raw_output_stream() as out:
            out.write(body)
    if filters is not None:
        if len(filters) == 1:
            stream.set_item(COSName.FILTER, COSName.get_pdf_name(filters[0]))
        else:
            arr = COSArray([COSName.get_pdf_name(f) for f in filters])
            stream.set_item(COSName.FILTER, arr)
    sink = io.BytesIO()
    writer = COSWriter(sink)
    writer.visit_from_stream(stream)
    stream.close()
    return sink.getvalue()


@requires_oracle
@pytest.mark.parametrize("label", ["empty", "raw", "flate", "chain", "onebyte"])
def test_stream_wire_format_matches_pdfbox(label: str) -> None:
    cases = _parse_probe()
    case = cases[label]
    image = case["image"]
    assert isinstance(image, bytes)

    # PDFBox never emits a /DL entry for a plain stream.
    assert case["has_dl"] is False

    body = _extract_body(image)
    py_image = _emit_pypdfbox(body, _FILTERS[label])

    # Byte-identical full image: dict framing + stream/CRLF + body + CRLF +
    # endstream + LF, with /Length a direct integer equal to the body length.
    assert py_image == image


@requires_oracle
@pytest.mark.parametrize("label", ["empty", "raw", "flate", "chain", "onebyte"])
def test_stream_length_is_direct_body_length(label: str) -> None:
    """The /Length dict entry PDFBox writes equals the encoded body length and
    is a direct integer (so it appears literally inside the ``<< ... >>``)."""
    cases = _parse_probe()
    case = cases[label]
    image = case["image"]
    assert isinstance(image, bytes)
    body = _extract_body(image)

    assert case["length"] == len(body)
    # The literal ``/Length <n>`` token must appear inside the dict (proving a
    # direct integer, not an indirect ``/Length n 0 R`` reference).
    assert b"/Length " + str(len(body)).encode("ascii") in image
    assert b"/Length %d 0 R" % len(body) not in image


@requires_oracle
def test_stream_keyword_eol_is_crlf() -> None:
    """The EOL after the ``stream`` keyword and before ``endstream`` is a
    CR-LF pair, per PDFBox's ``writeCRLF`` calls (PDF 32000-1 §7.3.8 allows
    either CRLF or a single LF after ``stream``; PDFBox picks CRLF)."""
    cases = _parse_probe()
    for label, case in cases.items():
        if "image" not in case:
            continue
        image = case["image"]
        assert isinstance(image, bytes)
        assert _STREAM_PREFIX in image, label
        # endstream is preceded by CR-LF and followed by a single LF.
        assert _BODY_SUFFIX + b"\n" in image, label
        # The keyword EOL is CRLF, never a bare LF: there is no ``stream\n``
        # that is not part of ``stream\r\n``.
        idx = image.index(b"stream")
        assert image[idx : idx + len(_STREAM_PREFIX)] == _STREAM_PREFIX, label
