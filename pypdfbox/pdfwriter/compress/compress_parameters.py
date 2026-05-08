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
    DEFAULT_COMPRESSION: ClassVar[CompressParameters]
    NO_COMPRESSION: ClassVar[CompressParameters]

    def __init__(self, object_stream_size: int | None = None) -> None:
        if object_stream_size is None:
            object_stream_size = self.DEFAULT_OBJECT_STREAM_SIZE
        # ``bool`` is an ``int`` subclass in Python — accept it (Java's
        # ``int`` parameter accepts widened ``boolean``? no, but treating
        # ``True``/``False`` as ``1``/``0`` is the principle-of-least-
        # surprise behavior for a numeric tunable). Anything else that
        # isn't an integer is a programming error and should fail loud.
        if not isinstance(object_stream_size, int):
            raise TypeError(
                "object_stream_size must be an int, "
                f"got {type(object_stream_size).__name__}"
            )
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

    def is_disabled(self) -> bool:
        """Return ``True`` when compression is disabled (object-stream
        size is ``0``). Convenience inverse of :py:meth:`is_compress` —
        no upstream counterpart, but matches the predicate-pair pattern
        used elsewhere in the writer cluster (e.g. ``is_free`` /
        ``with_free`` on :class:`COSWriterXRefEntry`)."""
        return self._object_stream_size == 0

    def with_object_stream_size(
        self, object_stream_size: int
    ) -> CompressParameters:
        """Return a new :class:`CompressParameters` carrying the given
        ``object_stream_size``. The current instance is left unchanged
        (the value type is conceptually immutable — upstream's field is
        ``final``).

        Returns ``self`` when the requested size matches the current one
        (no allocation churn).
        """
        updated = CompressParameters(object_stream_size)
        if updated._object_stream_size == self._object_stream_size:
            return self
        return updated

    # ---------- value-type semantics ----------
    #
    # Upstream relies on Java identity (no ``equals``/``hashCode``
    # overrides). pypdfbox treats ``CompressParameters`` as an immutable
    # value object — two instances configured with the same object-stream
    # size are interchangeable, so we override ``__eq__`` / ``__hash__``
    # to make set/dict membership work the obvious way. Note in
    # CHANGES.md: this is an additive Pythonic affordance, no upstream
    # behavior is altered.

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CompressParameters):
            return NotImplemented
        return self._object_stream_size == other._object_stream_size

    def __hash__(self) -> int:
        return hash(("CompressParameters", self._object_stream_size))

    def __repr__(self) -> str:
        return (
            f"CompressParameters(object_stream_size={self._object_stream_size})"
        )


CompressParameters.DEFAULT_COMPRESSION = CompressParameters()
CompressParameters.NO_COMPRESSION = CompressParameters(0)
