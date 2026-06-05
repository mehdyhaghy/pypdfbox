"""Wave 1483 — PDStream encode-on-write constructor parity.

Upstream ``PDStream(PDDocument, InputStream, COSName filter)`` (and the
``COSArray`` multi-filter variant) reads the input stream and writes it through
``stream.createOutputStream(filters)`` — i.e. the supplied bytes are the
*decoded* payload and are ENCODED through the filter chain on the way in, with
``/Filter`` set accordingly. The previous pypdfbox behaviour stored the bytes
verbatim while still tagging ``/Filter``, producing a stream whose body could
not be decoded on round-trip (zlib error).

Oracle-confirmed values from ``PdStreamEncodeProbe`` against
``pdfbox-app-3.0.7.jar`` for the 600-byte payload ``b"hello world " * 50``:

    decoded 600 f7ed3bcaa429dfc9288fc96a9f32747f88fffc9cdba9f3326910f5dda7a98b20
    FlateDecode          -> raw 27 bytes,  /Length 27
    ASCII85Decode,Flate  -> raw 37 bytes
    NONE                 -> raw 600 bytes, no /Filter

These tests pass WITHOUT the oracle (values are pinned); the optional
``@requires_oracle`` test re-derives them live.
"""

from __future__ import annotations

import hashlib
import io

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.common import PDStream
from pypdfbox.pdmodel.pd_document import PDDocument

_PAYLOAD = b"hello world " * 50
_DECODED_SHA = "f7ed3bcaa429dfc9288fc96a9f32747f88fffc9cdba9f3326910f5dda7a98b20"
# Oracle-confirmed compressed body for the single-filter FlateDecode case:
# Apache PDFBox 3.0.7 and CPython zlib emit byte-identical deflate output
# for this payload (raw 27 bytes, sha below). Pinned so a future change to
# the embed encoder is caught even without the live oracle.
_FLATE_RAW_LEN = 27
_FLATE_RAW_SHA = "6d2637a3fb9e0cabeff49c7bdc23a8e792f83bb7dd42e082f72ec0b0035ef0bd"


def test_single_filter_constructor_encodes_and_round_trips() -> None:
    doc = PDDocument()
    try:
        stream = PDStream(doc, io.BytesIO(_PAYLOAD), COSName.FLATE_DECODE)  # type: ignore[attr-defined]
        # Full decode recovers the original payload byte-for-byte.
        decoded = stream.create_input_stream().read()
        assert decoded == _PAYLOAD
        assert hashlib.sha256(decoded).hexdigest() == _DECODED_SHA
        # Raw body is the compressed form (oracle: 27 bytes, byte-identical
        # to PDFBox's Deflater output for this payload).
        raw = stream.create_raw_input_stream().read()
        assert raw != _PAYLOAD
        assert len(raw) == _FLATE_RAW_LEN
        assert hashlib.sha256(raw).hexdigest() == _FLATE_RAW_SHA
        # /Filter records the single FlateDecode entry.
        assert [n.name for n in stream.get_filters()] == ["FlateDecode"]
        # /Length reflects the encoded body (oracle: 27).
        assert stream.get_length() == len(raw)
    finally:
        doc.close()


def test_multi_filter_constructor_encodes_full_chain() -> None:
    doc = PDDocument()
    try:
        chain = COSArray([COSName.ASCII85_DECODE, COSName.FLATE_DECODE])  # type: ignore[attr-defined]
        stream = PDStream(doc, io.BytesIO(_PAYLOAD), chain)
        decoded = stream.create_input_stream().read()
        assert decoded == _PAYLOAD
        assert hashlib.sha256(decoded).hexdigest() == _DECODED_SHA
        # Filter chain recorded in order (decode order).
        assert [n.name for n in stream.get_filters()] == [
            "ASCII85Decode",
            "FlateDecode",
        ]
        raw = stream.create_raw_input_stream().read()
        assert raw != _PAYLOAD
    finally:
        doc.close()


def test_no_filter_constructor_stores_verbatim() -> None:
    doc = PDDocument()
    try:
        stream = PDStream(doc, io.BytesIO(_PAYLOAD))
        # No filter -> body stored verbatim, no /Filter entry.
        assert stream.create_raw_input_stream().read() == _PAYLOAD
        assert stream.create_input_stream().read() == _PAYLOAD
        assert stream.get_filters() == []
        assert stream.get_length() == len(_PAYLOAD)
    finally:
        doc.close()


def test_bytes_input_data_keyword_encodes() -> None:
    # The keyword-arg form (no document) takes the same encode-on-write path.
    stream = PDStream(input_data=_PAYLOAD, filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    assert stream.create_input_stream().read() == _PAYLOAD
    raw = stream.create_raw_input_stream().read()
    assert raw != _PAYLOAD


def test_binary_input_stream_is_closed_after_embed() -> None:
    src = io.BytesIO(_PAYLOAD)
    PDStream(input_data=src, filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    assert src.closed


def test_empty_payload_with_filter_round_trips_to_empty() -> None:
    stream = PDStream(input_data=b"", filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    # An empty COSStream returns an empty decoded read.
    assert stream.create_input_stream().read() == b""


def test_cos_stream_overload_still_rejects_input_data() -> None:
    with pytest.raises(TypeError):
        PDStream(COSStream(), b"data")


# ---------- live differential ----------

try:  # optional oracle differential
    from tests.oracle.harness import requires_oracle, run_probe_text

    _HAVE_HARNESS = True
except Exception:  # pragma: no cover - harness optional
    _HAVE_HARNESS = False


if _HAVE_HARNESS:

    @requires_oracle
    def test_encode_ctor_matches_pdfbox_oracle(tmp_path) -> None:
        payload_file = tmp_path / "payload.bin"
        payload_file.write_bytes(_PAYLOAD)

        for spec, expected_filters in (
            ("FlateDecode", ["FlateDecode"]),
            ("ASCII85Decode,FlateDecode", ["ASCII85Decode", "FlateDecode"]),
            ("NONE", []),
        ):
            out = run_probe_text("PdStreamEncodeProbe", str(payload_file), spec)
            lines = out.strip().splitlines()
            assert lines[0].startswith("decoded ")
            j_decoded_len, j_decoded_sha = lines[0].split()[1:3]

            doc = PDDocument()
            try:
                if spec == "NONE":
                    stream = PDStream(doc, io.BytesIO(_PAYLOAD))
                elif "," in spec:
                    names = [COSName.get_pdf_name(n) for n in spec.split(",")]
                    stream = PDStream(doc, io.BytesIO(_PAYLOAD), COSArray(names))
                else:
                    stream = PDStream(
                        doc, io.BytesIO(_PAYLOAD), COSName.get_pdf_name(spec)
                    )
                decoded = stream.create_input_stream().read()
                assert len(decoded) == int(j_decoded_len)
                assert hashlib.sha256(decoded).hexdigest() == j_decoded_sha
                assert [n.name for n in stream.get_filters()] == expected_filters
            finally:
                doc.close()
