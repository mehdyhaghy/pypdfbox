"""Wave 1396 branch-coverage tests for ``COSWriter`` helpers.

Closes:
* 170->exit — ``_RawSinkAdapter.close`` skips when sink has no callable
  close.
* (also covers 165->exit for ``flush()``).
* 632->634 — ``_existing_key_for`` returns None when COSObject's
  resolved actual is None.
"""

from __future__ import annotations

from io import BytesIO

from pypdfbox.cos import COSObject
from pypdfbox.pdfwriter.cos_writer import COSWriter, _RawSinkAdapter


def test_raw_sink_adapter_close_when_sink_lacks_close() -> None:
    """Sink without callable close() short-circuits cleanly.

    Closes False arm of ``callable(close)`` at line 170.
    """
    class SinkNoClose:
        def write(self, data: bytes) -> int:
            return len(data)

    adapter = _RawSinkAdapter(SinkNoClose())
    adapter.close()  # must not raise


def test_raw_sink_adapter_flush_when_sink_lacks_flush() -> None:
    """Sink without callable flush() short-circuits cleanly.

    Closes False arm of ``callable(flush)`` at line 165.
    """
    class SinkNoFlush:
        def write(self, data: bytes) -> int:
            return len(data)

    adapter = _RawSinkAdapter(SinkNoFlush())
    adapter.flush()  # must not raise


def test_existing_key_for_returns_none_when_cos_object_actual_is_none() -> None:
    """``_existing_key_for`` returns None for a COSObject whose actual
    has not been resolved.

    Closes False arm at line 632 (``actual is not None``).
    """
    # A COSObject placeholder where get_object() returns None.
    obj = COSObject(object_number=999, generation_number=0)
    sink = BytesIO()
    writer = COSWriter(sink)
    # Not registered → existing lookup returns None; the COSObject
    # branch enters but ``actual is None``, so we fall through.
    assert writer._lookup_existing_key(obj) is None  # noqa: SLF001
