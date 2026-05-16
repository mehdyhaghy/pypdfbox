from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

if TYPE_CHECKING:
    from pypdfbox.io.random_access_read import RandomAccessRead
    from pypdfbox.pdmodel.pd_document import PDDocument


class PDAppearanceStream(PDFormXObject):
    """
    An appearance stream is a Form XObject — a self-contained content
    stream rendered inside the annotation rectangle. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream``.

    Extends :class:`PDFormXObject` (matching upstream's
    ``class PDAppearanceStream extends PDFormXObject``), so all of the
    Form-XObject typed accessors — ``/BBox``, ``/Matrix``, ``/Resources``,
    ``/Group``, ``/Type``, ``/Subtype``, ``/FormType``, ``/StructParents``,
    ``/PieceInfo``, ``/LastModified``, ``/Name``, ``/OC``, ``/Ref``,
    ``/OPI``, ``/Metadata`` — are inherited.

    Two constructor shapes match upstream:

    - ``PDAppearanceStream(cos_stream)`` — wrap an existing form-XObject
      stream for reading.
    - ``PDAppearanceStream(document)`` — create a fresh, empty
      form-XObject stream owned by ``document`` for writing.

    Compatibility note: :meth:`get_stream`, :meth:`get_cos_object`, and
    :meth:`get_content_stream` return the raw :class:`COSStream` (not
    the :class:`PDStream` wrapper that upstream/:class:`PDFormXObject`
    returns from ``getStream()``). The flat ``COSStream`` form is what
    the existing pypdfbox call sites — including
    :class:`PDAppearanceContentStream` and a long tail of tests — were
    built against; preserving it here is the cheap-and-correct path
    rather than churning every caller. Use :meth:`get_pd_stream` when
    the typed :class:`PDStream` wrapper is needed.
    """

    def __init__(self, stream: COSStream | PDStream | PDDocument) -> None:
        # Match the previous lite port's strict input contract: only a
        # ``COSStream`` (read path), a ``PDStream`` wrapper, or a
        # ``PDDocument`` (write-new path) are valid. Anything else — most
        # importantly a bare ``COSDictionary`` — is rejected up front so
        # callers don't silently end up with a half-initialised form
        # XObject. ``PDDocument`` is imported lazily to avoid a cycle
        # (PDDocument → PDPage → PDResources → …).
        from pypdfbox.pdmodel.pd_document import PDDocument  # noqa: PLC0415

        if not isinstance(stream, (COSStream, PDStream, PDDocument)):
            raise TypeError(
                "PDAppearanceStream requires a COSStream, PDStream, or "
                f"PDDocument; got {type(stream).__name__}"
            )
        super().__init__(stream)

    # ------------------------------------------------------------------
    # Stream accessors — overridden to expose the raw ``COSStream``
    # rather than the ``PDStream`` wrapper that
    # :meth:`PDXObject.get_stream` returns. Existing call sites — most
    # notably :class:`PDAppearanceContentStream`, the appearance
    # generator helpers, and the appearance-tail/content tests — treat
    # ``appearance.get_stream()`` as a ``COSStream``; the override keeps
    # that shape stable while the full upstream PDStream-returning shape
    # is available via :meth:`get_pd_stream`.
    # ------------------------------------------------------------------

    def get_stream(self) -> COSStream:  # type: ignore[override]
        """Return the underlying ``COSStream`` body.

        Upstream ``PDFormXObject.getStream()`` returns the ``PDStream``
        wrapper; pypdfbox exposes the raw ``COSStream`` here for
        backward compatibility with the lite appearance API. Callers
        that want the typed wrapper should use :meth:`get_pd_stream`.
        """
        return self._stream.get_cos_object()

    def get_pd_stream(self) -> PDStream:
        """Return the underlying :class:`PDStream` wrapper.

        Matches upstream ``PDFormXObject.getStream()`` semantics for
        callers that need the typed wrapper rather than the raw
        ``COSStream`` returned by the BC-preserving :meth:`get_stream`.
        """
        return self._stream

    def get_content_stream(self) -> COSStream:  # type: ignore[override]
        """Return the underlying content stream as a raw ``COSStream``.

        Upstream ``PDFormXObject.getContentStream()`` (the
        ``PDContentStream`` interface implementation) returns the
        ``PDStream`` wrapper. We override to return the raw
        ``COSStream`` for the same backward-compatibility reason as
        :meth:`get_stream` — the appearance content-stream writer and
        the existing tests treat this as a ``COSStream``.
        """
        return self._stream.get_cos_object()

    # ``get_contents`` / ``get_contents_for_random_access`` /
    # ``get_contents_for_stream_parsing`` are inherited from
    # :class:`PDFormXObject`. The inherited implementations call
    # ``self.get_stream().create_input_stream()`` which now flows
    # through our ``COSStream``-returning override — both ``COSStream``
    # and ``PDStream`` expose ``create_input_stream`` with the same
    # signature, so the inherited behaviour is preserved.

    def get_contents(self) -> BinaryIO:  # type: ignore[override]
        """Decoded appearance content bytes as a readable stream.

        Overrides the inherited :meth:`PDFormXObject.get_contents`
        because ``COSStream.create_input_stream`` raises ``OSError``
        when the body is empty (fresh appearance streams legitimately
        start out empty), whereas the upstream form-XObject contract is
        to hand back an empty stream in that case. Returns a
        ``BytesIO`` for the empty-body path, otherwise delegates to
        ``COSStream.create_input_stream``.
        """
        cos = self._stream.get_cos_object()
        if not cos.has_data():
            import io as _io  # noqa: PLC0415

            return _io.BytesIO(b"")
        return cos.create_input_stream()

    def get_contents_for_random_access(self) -> RandomAccessRead:  # type: ignore[override]
        """Random-access view of the decoded appearance content bytes.

        Overrides the inherited :meth:`PDFormXObject.get_contents_for_random_access`
        for the empty-body case (see :meth:`get_contents`)."""
        from pypdfbox.io.random_access_read_buffer import (  # noqa: PLC0415
            RandomAccessReadBuffer,
        )

        cos = self._stream.get_cos_object()
        if not cos.has_data():
            return RandomAccessReadBuffer.from_bytes(b"")
        with cos.create_input_stream() as src:
            data = src.read()
        return RandomAccessReadBuffer.from_bytes(data)


__all__ = ["PDAppearanceStream"]
