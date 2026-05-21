"""Wave 1341 coverage boost for
``pypdfbox.io.non_seekable_random_access_read_input_stream``.

Pre-wave the module sat at 92.9 %. Remaining uncovered surface:

* ``_available_on_underlying`` fallback — exercised against a plain
  ``io.BytesIO``; wave 1363 taught the fallback to interrogate
  ``getbuffer().nbytes - tell()`` so ``length()`` / ``available()`` now
  reflect the underlying byte count for in-memory streams (matches the
  upstream contract for ``ByteArrayInputStream``).
* ``_fetch`` salvage branch (lines 281-286) — triggered when the
  underlying stream EOFs mid-buffer after a full LAST buffer, and the
  caller drives one more fetch attempt.
* ``_fetch`` OSError propagation (lines 295-298) — the underlying
  ``readinto`` raises ``OSError``; the helper logs, marks EOF, and
  re-raises.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.io.non_seekable_random_access_read_input_stream import (
    _BUFFER_SIZE,
    NonSeekableRandomAccessReadInputStream,
)


# ---------------------------------------------------------------------------
# ``_available_on_underlying`` fallback on a BytesIO (wave 1363 parity fix)
# ---------------------------------------------------------------------------
def test_length_on_bytesio_returns_buffered_size_only() -> None:
    """``io.BytesIO`` exposes no ``available()`` callable; wave 1363 made
    the fallback consult ``getbuffer().nbytes - tell()`` so ``length()``
    mirrors upstream Java's ``ByteArrayInputStream.available`` parity."""
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abcdef"))
    # Nothing buffered yet — fallback reports the full underlying size.
    assert raw.length() == 6
    # After a single ``read()`` the helper buffers a full chunk;
    # length stays >= 1.
    raw.read()
    assert raw.length() >= 1


def test_available_on_bytesio_reports_buffered_remainder() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abc"))
    # Fresh stream — underlying reports 3 bytes available via the
    # ``getbuffer()`` fallback.
    assert raw.available() == 3
    raw.read()
    # One byte consumed from a 3-byte buffer → 2 left.
    assert raw.available() == 2


# ---------------------------------------------------------------------------
# ``_fetch`` salvage branch (lines 281-286)
# ---------------------------------------------------------------------------
def test_fetch_salvage_branch_triggers_when_eof_during_mid_buffer() -> None:
    """Force a ``_fetch`` while LAST is full and CURRENT is mid-buffer:
    the salvage path preserves the tail of LAST and head of CURRENT into
    LAST so subsequent rewinds can still consult historical bytes."""
    # Stream = 1 full buffer + half a buffer. Read past the second buffer
    # so the third ``_fetch`` enters the salvage branch when the
    # underlying returns 0 bytes.
    payload = b"A" * _BUFFER_SIZE + b"B" * (_BUFFER_SIZE // 2)
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(payload))
    # Read the entire stream plus a bit to drive the third fetch.
    out = bytearray(_BUFFER_SIZE + _BUFFER_SIZE // 2 + 100)
    n = raw.read_into(out)
    # Read should return exactly the total payload size (EOF caps it).
    assert n == _BUFFER_SIZE + _BUFFER_SIZE // 2
    # LAST should have been salvaged: rewind 50 bytes — well within the
    # preserved tail — still works.
    raw.rewind(50)
    out2 = bytearray(50)
    raw.read_into(out2)
    # The salvaged tail holds the last 50 bytes of the payload.
    assert bytes(out2) == payload[-50:]


# ---------------------------------------------------------------------------
# ``_fetch`` OSError propagation (lines 295-298)
# ---------------------------------------------------------------------------
class _RaisingStream:
    """File-like stream whose ``readinto`` raises ``OSError`` on demand."""

    def __init__(self, message: str = "underlying stream broken") -> None:
        self._message = message
        self._closed = False

    def readinto(self, buf: bytearray) -> int:  # noqa: ARG002
        raise OSError(self._message)

    def close(self) -> None:
        self._closed = True


def test_fetch_propagates_underlying_oserror() -> None:
    raw = NonSeekableRandomAccessReadInputStream(_RaisingStream())
    with pytest.raises(OSError, match="underlying stream broken"):
        raw.read()
    # The helper sets ``_eof`` before re-raising so subsequent
    # ``is_eof()`` queries return True.
    assert raw._eof is True  # type: ignore[attr-defined]


def test_fetch_oserror_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    raw = NonSeekableRandomAccessReadInputStream(_RaisingStream("disk pop"))
    with caplog.at_level("WARNING"), pytest.raises(OSError):
        raw.read()
    # Warning text quotes the upstream message verbatim.
    assert any("disk pop" in rec.getMessage() for rec in caplog.records)
