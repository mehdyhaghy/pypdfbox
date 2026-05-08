"""Hand-written tests for ``EndstreamFilterStream``.

The class is a tiny state machine that decides how many bytes a PDF
stream body would have once a spurious final CR LF / LF is stripped
(while preserving a final lone CR). The upstream parity tests live in
``tests/pdfparser/upstream/test_endstream_filter_stream.py``; these
exercise edge cases that aren't covered by the upstream JUnit suite.
"""

from __future__ import annotations

from pypdfbox.pdfparser import EndstreamFilterStream


def _drive(*chunks: bytes) -> int:
    feos = EndstreamFilterStream()
    for chunk in chunks:
        feos.filter(chunk, 0, len(chunk))
    return feos.calculate_length()


def test_empty_stream_has_zero_length() -> None:
    assert _drive() == 0


def test_short_buffer_skips_ascii_probe_and_filters() -> None:
    # Length 10 or less skips the PDFBOX-2120 ASCII-detection short-
    # circuit; we always filter. A trailing LF is dropped.
    assert _drive(b"abc\n") == 3


def test_ascii_probe_disables_filtering_when_leading_text() -> None:
    # 11 bytes of ASCII text triggers the PDFBOX-2120 path: filtering
    # is disabled so the trailing LF is preserved.
    assert _drive(b"hello world\n") == len(b"hello world\n")


def test_binary_leading_bytes_keep_filtering_active() -> None:
    # A control byte in the probe window forces filtering even though
    # the buffer is long.
    payload = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x20, 0x20, 0x20]) + b"\n"
    assert _drive(payload) == len(payload) - 1


def test_lone_trailing_cr_is_preserved() -> None:
    # PDFBox keeps a final CR (it might be meaningful in ASCII text).
    assert _drive(b"\x01\x02\r") == 3


def test_trailing_crlf_is_dropped() -> None:
    assert _drive(b"\x01\x02\r\n") == 2


def test_trailing_lf_alone_is_dropped() -> None:
    assert _drive(b"\x01\x02\n") == 2


def test_crlf_split_across_buffers_is_dropped() -> None:
    # CR ends one buffer, LF begins the next — the pair is recognised
    # and dropped.
    assert _drive(b"\x01\x02\r", b"\n") == 2


def test_isolated_cr_buffer_followed_by_more_data() -> None:
    # A buffer ending in CR followed by a non-LF buffer counts the CR.
    assert _drive(b"\x01\x02\r", b"\x03") == 4


def test_calculate_length_is_idempotent_after_reset() -> None:
    feos = EndstreamFilterStream()
    feos.filter(b"\x01\x02\r\n", 0, 4)
    assert feos.calculate_length() == 2
    # After calculate_length, internal CR/LF flags are cleared, so a
    # second call doesn't double-count anything.
    assert feos.calculate_length() == 2


def test_offset_argument_skips_leading_bytes() -> None:
    feos = EndstreamFilterStream()
    feos.filter(b"\xff\xff\x01\x02\x03", 2, 3)
    assert feos.calculate_length() == 3


def test_consecutive_lf_buffers_keep_only_final_drop() -> None:
    # Each '\n' in mid-stream is recorded; only the last is held back.
    feos = EndstreamFilterStream()
    feos.filter(b"\x01\n", 0, 2)
    feos.filter(b"\x02\n", 0, 2)
    assert feos.calculate_length() == 3  # 0x01, 0x0A, 0x02


def test_cr_then_buffer_starting_with_lf_only_drops_pair() -> None:
    # A held-back CR followed by a one-byte LF buffer drops both.
    feos = EndstreamFilterStream()
    feos.filter(b"\x01\r", 0, 2)
    feos.filter(b"\n", 0, 1)
    assert feos.calculate_length() == 1


def test_crlf_split_across_single_lf_buffer_is_kept_when_more_data_arrives() -> None:
    # A one-byte LF chunk can complete the final CR LF, but only
    # calculate_length() knows whether it was truly final.
    assert _drive(b"\x01\r", b"\n", b"\x02") == 4


def test_initial_crlf_split_across_single_lf_buffer_keeps_filtering_state() -> None:
    # If the held pair is at the start, a later long ASCII chunk must not
    # re-run the ASCII probe and drop the earlier CR LF.
    payload = b"hello world\n"
    assert _drive(b"\r", b"\n", payload) == len(b"\r\nhello world")
