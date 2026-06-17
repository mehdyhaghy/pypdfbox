"""Live PDFBox differential parity for ``COSStream`` length + filter write
round-trip.

Drives the ``COSStream`` write API directly (no document, no parser) and pins
the encode-on-write contract against Apache PDFBox 3.0.7 via
``oracle/probes/CosStreamLenProbe.java``:

* ``create_output_stream(FlateDecode)`` then ``get_length()`` must report the
  ENCODED (compressed) length — strictly less than the decoded payload — and
  the ``/Length`` dictionary entry must equal ``get_length()``;
* ``create_raw_input_stream()`` yields the raw encoded bytes (length ==
  ``get_length()``); ``create_input_stream()`` yields the decoded bytes equal
  to the original payload (the round-trip invariant);
* ``/Filter`` is recorded as a single bare ``COSName`` for a one-element chain
  and as a ``COSArray`` for a two-filter chain;
* a no-filter ``create_output_stream()`` stores the payload verbatim (raw len
  == decoded len == payload len, no ``/Filter``).

The probe fixes the decoded payload internally; the Python side reconstructs
the identical payload so both engines operate on the same input bytes. The
FlateDecode and ASCII85 encoders are deterministic here (both sides wrap the
same zlib level and a faithful ASCII85OutputStream port), so even the encoded
lengths coincide exactly — asserted alongside the structural invariants.
"""

from __future__ import annotations

import json

from pypdfbox.cos import COSName, COSStream
from pypdfbox.cos.cos_array import COSArray
from tests.oracle.harness import requires_oracle, run_probe_text

# Must match the payload CosStreamLenProbe builds internally.
_PAYLOAD = b"BT /F1 12 Tf 100 700 Td (Hello COSStream Length) Tj ET\n" * 64


def _probe_facts() -> dict[str, object]:
    return json.loads(run_probe_text("CosStreamLenProbe"))


@requires_oracle
def test_flate_write_updates_length_to_encoded_and_round_trips() -> None:
    """The core surface: ``create_output_stream(FlateDecode)`` → ``get_length``
    is the ENCODED length, ``/Length`` matches it, raw bytes == that length,
    decoded bytes == payload."""
    java = _probe_facts()

    stream = COSStream()
    with stream.create_output_stream(filters=COSName.FLATE_DECODE) as out:
        out.write(_PAYLOAD)

    encoded_len = stream.get_length()
    length_entry = stream.get_long(COSName.LENGTH)
    raw = stream.create_raw_input_stream().read()
    decoded = stream.create_input_stream().read()
    shape = type(stream.get_filters()).__name__

    # /Length tracks the encoded body, not the decoded payload.
    assert encoded_len == length_entry == len(raw)
    assert encoded_len < len(_PAYLOAD)
    assert decoded == _PAYLOAD
    assert isinstance(stream.get_filters(), COSName)

    # Byte/behaviour parity against PDFBox.
    assert encoded_len == java["flate_length"]
    assert length_entry == java["flate_length_entry"]
    assert len(raw) == java["flate_raw_len"]
    assert len(decoded) == java["flate_decoded_len"]
    assert java["flate_decoded_equals_payload"] is True
    assert java["flate_encoded_lt_decoded"] is True
    assert java["flate_filter_shape"] == "name" == _shape_token(shape)
    assert java["flate_filter_list"] == "FlateDecode"
    assert len(_PAYLOAD) == java["payload_len"]

    stream.close()


@requires_oracle
def test_two_filter_chain_records_array_and_round_trips() -> None:
    """A ``[/ASCII85Decode /FlateDecode]`` chain records the array shape and
    decodes back to the payload, byte-identical length to PDFBox."""
    java = _probe_facts()

    stream = COSStream()
    with stream.create_output_stream(
        filters=[COSName.get_pdf_name("ASCII85Decode"), COSName.FLATE_DECODE]
    ) as out:
        out.write(_PAYLOAD)

    chain_len = stream.get_length()
    decoded = stream.create_input_stream().read()

    assert isinstance(stream.get_filters(), COSArray)
    assert decoded == _PAYLOAD
    assert chain_len == java["chain_length"]
    assert java["chain_decoded_equals_payload"] is True
    assert java["chain_filter_shape"] == "array"
    assert java["chain_filter_list"] == "ASCII85Decode,FlateDecode"
    assert [n.name for n in stream.get_filter_list()] == [
        "ASCII85Decode",
        "FlateDecode",
    ]

    stream.close()


@requires_oracle
def test_no_filter_write_stores_verbatim() -> None:
    """``create_output_stream()`` with no filter stores the payload verbatim:
    raw length == decoded length == payload length, no ``/Filter``."""
    java = _probe_facts()

    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(_PAYLOAD)

    raw_len = stream.get_length()
    raw = stream.create_raw_input_stream().read()
    decoded = stream.create_input_stream().read()

    assert raw_len == len(raw) == len(decoded) == len(_PAYLOAD)
    assert raw == decoded == _PAYLOAD
    assert stream.get_filters() is None

    assert raw_len == java["raw_length"]
    assert len(raw) == java["raw_raw_len"]
    assert len(decoded) == java["raw_decoded_len"]
    assert java["raw_filter_shape"] == "none"

    stream.close()


def _shape_token(class_name: str) -> str:
    return {"COSName": "name", "COSArray": "array", "NoneType": "none"}.get(
        class_name, "other"
    )


# ---------------------------------------------------------------------------
# pypdfbox-side regression pins (no oracle, fast) — guard the encoded-length
# contract even when the live oracle is unavailable.
# ---------------------------------------------------------------------------


def test_get_length_reports_encoded_not_decoded_length() -> None:
    stream = COSStream()
    with stream.create_output_stream(filters=COSName.FLATE_DECODE) as out:
        out.write(_PAYLOAD)
    assert stream.get_length() < len(_PAYLOAD)
    assert stream.get_long(COSName.LENGTH) == stream.get_length()
    assert stream.create_input_stream().read() == _PAYLOAD
    stream.close()


def test_raw_vs_decoded_input_streams_differ_under_filter() -> None:
    stream = COSStream()
    with stream.create_output_stream(filters=COSName.FLATE_DECODE) as out:
        out.write(_PAYLOAD)
    raw = stream.create_raw_input_stream().read()
    decoded = stream.create_input_stream().read()
    assert raw != decoded
    assert len(raw) == stream.get_length()
    assert decoded == _PAYLOAD
    stream.close()
