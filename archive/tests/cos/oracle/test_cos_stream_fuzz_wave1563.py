"""Live PDFBox differential-fuzz for ``COSStream`` filtered / unfiltered access
and the lazy decode lifecycle (wave 1563).

Complementary to ``test_cos_stream_len_oracle.py`` (encode-on-write contract +
filter shape) and the wire-format / embedded-endstream probes: this file targets
the READ side and stream lifecycle facets NOT covered there, pinned against
Apache PDFBox 3.0.7 via ``oracle/probes/CosStreamFuzzProbe.java``:

* verbatim raw bytes with NO filter — ``create_raw_input_stream()`` and
  ``create_input_stream()`` yield byte-identical output (the no-filter shortcut);
* raw FlateDecode-encoded bytes + ``/Filter`` set directly — raw differs from
  decoded, decoded == payload, and a SECOND ``create_input_stream()`` reproduces
  the same bytes (non-destructive re-decode from the raw buffer);
* ``get_filters()`` shape across none / single-name / two-element array;
* a stale ``/Length`` planted on the dict — ``get_length()`` returns the DICT
  entry (upstream ``getInt(/Length, 0)`` semantics), not the live body length;
* an empty (never-written) stream — ``get_length()==0``, ``get_filters()`` None,
  ``has_data()`` False, both input-stream factories raise, and
  ``to_text_string()`` swallows to ``""``;
* a ``[/ASCII85Decode /FlateDecode]`` chain decodes back to the payload;
* ``to_text_string()`` on a UTF-16BE-BOM body returns the decoded text.

REAL BUG FIXED THIS WAVE: ``COSStream.get_length()`` previously returned the
live body-buffer length; PDFBox returns ``getInt(/Length, 0)`` (the dictionary
entry). Case C below pins the corrected behavior on both sides — a planted
``/Length`` of 999999 is what ``get_length()`` now reports.

The probe fixes the decoded payload internally; the Python side rebuilds the
identical payload so both engines compare on the same input bytes. The
FlateDecode encoder is fed PDFBox-produced encoded bytes for the decode cases
(the probe pre-encodes through its own ``createOutputStream``), so the decode
path is exercised on bytes PDFBox itself wrote.
"""

from __future__ import annotations

import json

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_integer import COSInteger
from tests.oracle.harness import requires_oracle, run_probe_text

# Must match the payload CosStreamFuzzProbe builds internally.
_PAYLOAD = b"q 1 0 0 1 0 0 cm (decode lifecycle fuzz) Tj Q\n" * 40

_FLATE = COSName.get_pdf_name("FlateDecode")
_ASCII85 = COSName.get_pdf_name("ASCII85Decode")
_LENGTH = COSName.get_pdf_name("Length")
_FILTER = COSName.get_pdf_name("Filter")


def _probe_facts() -> dict[str, object]:
    return json.loads(run_probe_text("CosStreamFuzzProbe"))


def _flate_encoded() -> bytes:
    """A FlateDecode-encoded copy of ``_PAYLOAD``, produced by our own encoder.

    The probe pre-encodes with PDFBox; both encoders wrap zlib so the encoded
    bytes are interchangeable for decode purposes (decode is exact either way).
    """
    enc = COSStream()
    with enc.create_output_stream(filters=_FLATE) as out:
        out.write(_PAYLOAD)
    raw = enc.create_raw_input_stream().read()
    enc.close()
    return raw


def _chain_encoded() -> bytes:
    enc = COSStream()
    with enc.create_output_stream(filters=[_ASCII85, _FLATE]) as out:
        out.write(_PAYLOAD)
    raw = enc.create_raw_input_stream().read()
    enc.close()
    return raw


# ---------------------------------------------------------------------------
# Live-oracle differential tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_no_filter_raw_equals_decoded() -> None:
    """Case A: verbatim raw write, no /Filter — raw == decoded == payload."""
    java = _probe_facts()

    s = COSStream()
    with s.create_raw_output_stream() as out:
        out.write(_PAYLOAD)
    raw = s.create_raw_input_stream().read()
    decoded = s.create_input_stream().read()

    assert raw == decoded == _PAYLOAD
    assert s.has_data() is True
    assert s.get_filters() is None
    # get_length now reads the /Length the raw-write close synced.
    assert s.get_length() == len(_PAYLOAD)

    assert java["a_length"] == len(_PAYLOAD)
    assert java["a_has_data"] is True
    assert java["a_raw_equals_decoded"] is True
    assert java["a_raw_equals_payload"] is True
    assert java["a_filter_shape"] == "none"
    assert java["payload_len"] == len(_PAYLOAD)
    s.close()


@requires_oracle
def test_raw_encoded_plus_filter_decodes_and_double_decode_stable() -> None:
    """Case B: raw FlateDecode bytes + /Filter set directly — raw differs from
    decoded, decoded == payload, and a second decode is stable."""
    java = _probe_facts()

    s = COSStream()
    with s.create_raw_output_stream() as out:
        out.write(_flate_encoded())
    s.set_item(_FILTER, _FLATE)

    raw = s.create_raw_input_stream().read()
    decoded1 = s.create_input_stream().read()
    decoded2 = s.create_input_stream().read()

    assert raw != decoded1
    assert decoded1 == _PAYLOAD
    assert decoded1 == decoded2  # non-destructive re-decode
    assert isinstance(s.get_filters(), COSName)

    assert java["b_raw_differs_decoded"] is True
    assert java["b_decoded_equals_payload"] is True
    assert java["b_double_decode_stable"] is True
    assert java["b_filter_shape"] == "name"
    s.close()


@requires_oracle
def test_get_length_reads_dictionary_entry_not_body() -> None:
    """Case C (the wave-1563 bug fix): a stale /Length that disagrees with the
    body — get_length() returns the DICT entry (PDFBox ``getInt(/Length,0)``
    semantics), NOT the real body length."""
    java = _probe_facts()

    s = COSStream()
    with s.create_raw_output_stream() as out:
        out.write(_PAYLOAD)
    # Plant a bogus /Length the body does not match.
    s.set_item(_LENGTH, COSInteger.get(999999))

    assert s.get_length() == 999999
    assert s.get_int(_LENGTH) == 999999
    assert s.get_length() != len(_PAYLOAD)
    # The true body length is still recoverable via the raw bytes.
    assert len(s.create_raw_input_stream().read()) == len(_PAYLOAD)

    assert java["c_get_length"] == 999999
    assert java["c_length_entry"] == 999999
    assert java["c_get_length_equals_body"] is False
    s.close()


@requires_oracle
def test_empty_stream_factories_and_text() -> None:
    """Case D: an empty (never-written) stream — length 0, no filters, no data,
    both input-stream factories raise, and to_text_string() swallows to ""."""
    java = _probe_facts()

    s = COSStream()
    assert s.get_length() == 0
    assert s.has_data() is False
    assert s.get_filters() is None
    with pytest.raises(OSError):
        s.create_raw_input_stream()
    with pytest.raises(OSError):
        s.create_input_stream()
    assert s.to_text_string() == ""

    assert java["d_length"] == 0
    assert java["d_has_data"] is False
    assert java["d_filter_shape"] == "none"
    # PDFBox raises java.io.IOException; pypdfbox maps to OSError.
    assert java["d_raw_input_exc"] == "java.io.IOException"
    assert java["d_input_exc"] == "java.io.IOException"
    assert java["d_to_text"] == ""
    s.close()


@requires_oracle
def test_two_filter_chain_decodes_to_payload() -> None:
    """Case E: [/ASCII85Decode /FlateDecode] on raw bytes decodes to payload."""
    java = _probe_facts()

    s = COSStream()
    with s.create_raw_output_stream() as out:
        out.write(_chain_encoded())
    chain = COSArray([_ASCII85, _FLATE])
    s.set_item(_FILTER, chain)

    decoded = s.create_input_stream().read()
    assert decoded == _PAYLOAD
    assert isinstance(s.get_filters(), COSArray)
    assert [n.name for n in s.get_filter_list()] == ["ASCII85Decode", "FlateDecode"]

    assert java["e_decoded_equals_payload"] is True
    assert java["e_filter_shape"] == "array"
    assert java["e_filter_list"] == "ASCII85Decode,FlateDecode"
    s.close()


@requires_oracle
def test_to_text_string_utf16be_bom() -> None:
    """Case F: to_text_string() on a UTF-16BE-BOM body returns decoded text."""
    java = _probe_facts()

    s = COSStream()
    with s.create_raw_output_stream() as out:
        out.write(b"\xfe\xff\x00H\x00i\x00!")
    assert s.to_text_string() == "Hi!"
    assert java["f_to_text"] == "Hi!"
    s.close()


# ---------------------------------------------------------------------------
# pypdfbox-side regression pins (no oracle, fast) — guard the corrected
# get_length contract and the decode lifecycle even when the oracle is absent.
# ---------------------------------------------------------------------------


def test_get_length_uses_length_entry_regression() -> None:
    s = COSStream()
    with s.create_raw_output_stream() as out:
        out.write(_PAYLOAD)
    assert s.get_length() == len(_PAYLOAD)
    s.set_item(_LENGTH, COSInteger.get(999999))
    assert s.get_length() == 999999  # dict entry wins, body unchanged
    assert len(s.create_raw_input_stream().read()) == len(_PAYLOAD)
    s.close()


def test_set_raw_data_syncs_length_regression() -> None:
    s = COSStream()
    s.set_raw_data(b"hello world")
    assert s.contains_key(_LENGTH)
    assert s.get_int(_LENGTH) == 11
    assert s.get_length() == 11
    s.close()


def test_double_decode_non_destructive_regression() -> None:
    s = COSStream()
    with s.create_raw_output_stream() as out:
        out.write(_flate_encoded())
    s.set_item(_FILTER, _FLATE)
    assert s.create_input_stream().read() == _PAYLOAD
    assert s.create_input_stream().read() == _PAYLOAD
    s.close()


def test_empty_stream_raises_regression() -> None:
    s = COSStream()
    assert s.get_length() == 0
    with pytest.raises(OSError):
        s.create_input_stream()
    with pytest.raises(OSError):
        s.create_raw_input_stream()
    assert s.to_text_string() == ""
    s.close()
