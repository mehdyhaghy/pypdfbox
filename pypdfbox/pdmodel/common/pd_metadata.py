from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

from pypdfbox.cos import COSName, COSStream

from .pd_stream import PDStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]


class PDMetadata(PDStream):
    """
    Document-level metadata stream wrapper. Mirrors
    ``org.apache.pdfbox.pdmodel.common.PDMetadata``.

    A ``PDMetadata`` is a ``PDStream`` whose body holds an XMP packet
    (XML). For document-level metadata streams the dictionary carries
    ``/Type /Metadata`` and ``/Subtype /XML``.

    Upstream ships three constructors:

    - ``PDMetadata(PDDocument)``                  — fresh stream tagged
      ``/Type /Metadata`` ``/Subtype /XML``.
    - ``PDMetadata(PDDocument, InputStream)``     — fresh stream populated
      from the input bytes, also tagged.
    - ``PDMetadata(COSStream)``                   — wrap an existing stream
      *without* setting ``/Type`` / ``/Subtype``.

    Python collapses these into a single dispatch on the first argument:

    - ``None``                       → fresh tagged stream.
    - ``COSStream``                  → wrap as-is (no tagging).
    - ``bytes`` / ``str``            → fresh tagged stream populated with
      the XMP packet (``str`` is encoded as UTF-8).
    - ``PDDocument`` / ``COSDocument`` → fresh tagged stream attached to
      that document. An optional ``input_data`` argument (bytes, str, or
      file-like) is then imported via :meth:`import_xmp_metadata`,
      mirroring upstream's two-argument constructor.

    Filter control is inherited from :class:`PDStream` — call
    :meth:`set_filters` to declare an on-write encoding chain (e.g.
    ``COSName.FLATE_DECODE``).
    """

    def __init__(
        self,
        stream_or_doc: (
            PDDocument | COSStream | bytes | bytearray | memoryview | str | None
        ) = None,
        input_data: bytes | bytearray | memoryview | str | BinaryIO | None = None,
    ) -> None:
        # Local import to avoid circular dependency.
        from pypdfbox.cos import COSDocument  # noqa: PLC0415
        from pypdfbox.pdmodel.pd_document import PDDocument  # noqa: PLC0415

        if isinstance(stream_or_doc, COSStream):
            # Wrap-as-is: do NOT set /Type or /Subtype. Mirrors upstream
            # ``PDMetadata(COSStream)``.
            if input_data is not None:
                raise TypeError(
                    "PDMetadata(COSStream, input_data) is not a valid overload"
                )
            super().__init__(stream_or_doc)
            return

        if isinstance(stream_or_doc, str):
            super().__init__()
            self._tag_metadata()
            self.import_xmp_metadata(stream_or_doc.encode("utf-8"))
            return

        if isinstance(stream_or_doc, (bytes, bytearray, memoryview)):
            super().__init__()
            self._tag_metadata()
            self.import_xmp_metadata(bytes(stream_or_doc))
            return

        if stream_or_doc is None:
            super().__init__()
            self._tag_metadata()
            if input_data is not None:
                self.import_xmp_metadata(input_data)
            return

        if isinstance(stream_or_doc, (PDDocument, COSDocument)):
            # Mirrors upstream ``PDMetadata(PDDocument)`` and
            # ``PDMetadata(PDDocument, InputStream)``.
            super().__init__(stream_or_doc)
            self._tag_metadata()
            if input_data is not None:
                self.import_xmp_metadata(input_data)
            return

        raise TypeError(
            f"PDMetadata expected None, COSStream, bytes, str, PDDocument, or "
            f"COSDocument; got {type(stream_or_doc).__name__}"
        )

    # ---------- internal helpers ----------

    def _tag_metadata(self) -> None:
        """Stamp ``/Type /Metadata`` and ``/Subtype /XML`` on the wrapped
        COSStream — required for document-level XMP metadata streams."""
        cos = self.get_cos_object()
        cos.set_name(_TYPE, "Metadata")
        cos.set_name(_SUBTYPE, "XML")

    # ---------- XMP I/O ----------

    def import_xmp_metadata(
        self, xmp: bytes | bytearray | memoryview | str | BinaryIO
    ) -> None:
        """Replace the stream body with the supplied XMP packet bytes.

        Mirrors upstream ``importXMPMetadata(byte[])``. Accepts:

        - ``bytes`` / ``bytearray`` / ``memoryview`` — written verbatim.
        - ``str`` — encoded as UTF-8 then written.
        - file-like (any object with ``read()``) — fully drained, then
          written verbatim. Matches upstream's ``InputStream`` overload
          shape used by callers that build the XMP packet in memory.
        """
        if isinstance(xmp, str):
            data = xmp.encode("utf-8")
        elif isinstance(xmp, (bytes, bytearray, memoryview)):
            data = bytes(xmp)
        elif hasattr(xmp, "read"):
            chunk = xmp.read()
            if isinstance(chunk, str):
                data = chunk.encode("utf-8")
            else:
                data = bytes(chunk)
        else:
            raise TypeError(
                f"import_xmp_metadata expected bytes, str, or a file-like "
                f"object; got {type(xmp).__name__}"
            )
        with self.create_output_stream() as out:
            out.write(data)

    def export_xmp_metadata(self) -> bytes:
        """Return the (decoded) XMP packet bytes from the stream body.

        Note: upstream returns an ``InputStream`` here; we return the
        materialised ``bytes`` because most call sites read the full
        packet anyway and Python doesn't have a cheap stream type to
        pass around. Use :meth:`create_input_stream` if you need a
        file-like handle. An empty/uninitialised stream yields ``b""``
        rather than raising — matches the natural "no XMP packet" case."""
        cos = self.get_cos_object()
        if not cos.has_data():
            return b""
        with self.create_input_stream() as src:
            return src.read()

    def get_metadata_as_string(self) -> str:
        """Return the XMP packet body decoded as UTF-8. Mirrors upstream
        ``getMetadataAsString()``. Empty stream → empty string."""
        return self.export_xmp_metadata().decode("utf-8")

    # ---------- convenience ----------

    def create_input_stream(self, stop_filters=None) -> BinaryIO:  # type: ignore[override]
        # Provided for symmetry with upstream's ``createInputStream()``.
        # PDStream already supplies the implementation; this override
        # exists purely so the docstring shows up on PDMetadata.
        return super().create_input_stream(stop_filters)
