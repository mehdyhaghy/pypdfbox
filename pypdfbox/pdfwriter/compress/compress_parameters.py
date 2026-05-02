from __future__ import annotations

from typing import ClassVar


class CompressParameters:
    """Configuration for PDF compression (object-stream packing).

    Mirrors ``org.apache.pdfbox.pdfwriter.compress.CompressParameters``.

    A ``CompressParameters`` instance carries a single tunable: the
    maximum number of objects that may be packed into one compressed
    object stream (``ObjStm``). Higher values reduce overhead but slow
    down readers that must materialize the full stream to access any
    member. A value of ``0`` disables compression entirely.
    """

    DEFAULT_OBJECT_STREAM_SIZE: ClassVar[int] = 200

    # ``DEFAULT_COMPRESSION`` and ``NO_COMPRESSION`` are populated below
    # the class body — they need ``CompressParameters`` itself to exist.
    DEFAULT_COMPRESSION: ClassVar["CompressParameters"]
    NO_COMPRESSION: ClassVar["CompressParameters"]

    def __init__(self, object_stream_size: int | None = None) -> None:
        if object_stream_size is None:
            object_stream_size = self.DEFAULT_OBJECT_STREAM_SIZE
        if object_stream_size < 0:
            raise ValueError("Object stream size can't be a negative value")
        self._object_stream_size: int = int(object_stream_size)

    def get_object_stream_size(self) -> int:
        """Return the number of objects that may be packed into one
        compressed object stream."""
        return self._object_stream_size

    def is_compress(self) -> bool:
        """Return ``True`` if compression (object-stream packing) is
        enabled — i.e. when :py:meth:`get_object_stream_size` is positive."""
        return self._object_stream_size > 0


CompressParameters.DEFAULT_COMPRESSION = CompressParameters()
CompressParameters.NO_COMPRESSION = CompressParameters(0)
