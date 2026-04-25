from __future__ import annotations

import io
from collections.abc import Iterable
from typing import Any, BinaryIO

from pypdfbox.io import ScratchFile, ScratchFileBuffer

from .cos_array import COSArray
from .cos_base import COSBase
from .cos_dictionary import COSDictionary
from .cos_name import COSName
from .i_cos_visitor import ICOSVisitor


class _CommittingOutputStream(io.BytesIO):
    """``BytesIO`` subclass whose ``close()`` commits the buffered bytes
    back into the owning ``COSStream``."""

    def __init__(self, owner: COSStream) -> None:
        super().__init__()
        self._owner = owner
        self._committed = False

    def close(self) -> None:
        if not self._committed:
            self._committed = True
            self._owner._set_raw_data_internal(self.getvalue())
        super().close()


class COSStream(COSDictionary):
    """
    PDF stream — a dictionary plus a binary content body. Inherits
    ``COSDictionary`` per upstream (``COSStream extends COSDictionary``);
    overrides ``accept`` to dispatch ``visit_from_stream``.

    Body bytes are stored in a ``ScratchFile`` buffer (which spills to
    disk per the document's ``MemoryUsageSetting``). Filter encoding /
    decoding is delegated to the ``filter`` module (PRD §6.4) and is
    out of scope for this class — only **raw** byte access is provided
    here. Decoded helpers will land in cluster ``filter`` cluster #1.
    """

    def __init__(
        self,
        scratch_file: ScratchFile | None = None,
        items: Iterable[tuple[COSName | str, COSBase]] | None = None,
    ) -> None:
        super().__init__(items)
        if scratch_file is None:
            self._scratch = ScratchFile()
            self._owns_scratch = True
        else:
            self._scratch = scratch_file
            self._owns_scratch = False
        self._buffer: ScratchFileBuffer | None = None
        self._closed = False

    # ---------- raw bytes I/O ----------

    def has_data(self) -> bool:
        return self._buffer is not None and self._buffer.length() > 0

    def get_length(self) -> int:
        return self._buffer.length() if self._buffer is not None else 0

    def get_raw_data(self) -> bytes:
        """Snapshot of the current raw (encoded) bytes."""
        if self._buffer is None:
            return b""
        cur = self._buffer.get_position()
        self._buffer.seek(0)
        out = bytearray(self._buffer.length())
        n = self._buffer.read_into(out)
        self._buffer.seek(cur)
        return bytes(out[:n] if n > 0 else b"")

    def set_raw_data(self, data: bytes | bytearray | memoryview) -> None:
        """Replace the raw body with ``data``."""
        self._set_raw_data_internal(bytes(data))

    def _set_raw_data_internal(self, data: bytes) -> None:
        if self._closed:
            raise ValueError("operation on closed COSStream")
        if self._buffer is None:
            self._buffer = self._scratch.create_buffer()
        else:
            self._buffer.clear()
        self._buffer.write_bytes(data)
        self._buffer.seek(0)

    def create_raw_input_stream(self) -> BinaryIO:
        """Return a fresh ``BytesIO`` snapshot of the current raw bytes.

        Raises ``OSError`` if the stream has no data (PDFBox parity)."""
        if self._buffer is None:
            raise OSError("stream has no data")
        return io.BytesIO(self.get_raw_data())

    def create_raw_output_stream(self) -> BinaryIO:
        """Return a writable stream; on ``close()`` its contents replace
        this stream's raw body."""
        if self._closed:
            raise ValueError("operation on closed COSStream")
        return _CommittingOutputStream(self)

    def create_input_stream(self) -> BinaryIO:
        """Return a stream over the **decoded** body. Without ``/Filter`` this
        is equivalent to ``create_raw_input_stream``. Filter decoding lives
        in the ``filter`` module (cluster #1) — calling this on a stream
        with filters set raises ``NotImplementedError`` until then."""
        if self.get_filter_list():
            raise NotImplementedError(
                "COSStream filter decoding lives in pypdfbox.filter (not yet ported)"
            )
        return self.create_raw_input_stream()

    def create_output_stream(self, filters: COSBase | None = None) -> BinaryIO:
        """Return a writable stream that on ``close()`` becomes the body.

        If ``filters`` is supplied (a ``COSName`` or ``COSArray`` of names)
        the stream's ``/Filter`` entry is set, but actual filter encoding is
        deferred to the ``filter`` module — passing filters today raises
        ``NotImplementedError``."""
        if filters is not None:
            raise NotImplementedError(
                "COSStream filter encoding lives in pypdfbox.filter (not yet ported)"
            )
        return self.create_raw_output_stream()

    # ---------- /Filter introspection ----------

    def get_filter_list(self) -> list[COSName]:
        """Return the ``/Filter`` chain as a list of ``COSName``.

        Per PDF spec, ``/Filter`` may be absent, a single name, or an
        array of names. Returns ``[]`` when absent."""
        f = self.get_dictionary_object(COSName.FILTER)  # type: ignore[attr-defined]
        if f is None:
            return []
        if isinstance(f, COSName):
            return [f]
        if isinstance(f, COSArray):
            out: list[COSName] = []
            for entry in f:
                if isinstance(entry, COSName):
                    out.append(entry)
                else:
                    raise TypeError(f"non-name entry in /Filter array: {entry!r}")
            return out
        raise TypeError(f"unexpected /Filter type: {type(f).__name__}")

    # ---------- lifecycle ----------

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._buffer is not None:
            self._buffer.close()
            self._buffer = None
        if self._owns_scratch:
            self._scratch.close()

    def is_closed(self) -> bool:
        return self._closed

    # ---------- visitor ----------

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_stream(self)

    def __enter__(self) -> COSStream:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"COSStream(dict_size={self.size()}, body_len={self.get_length()})"
