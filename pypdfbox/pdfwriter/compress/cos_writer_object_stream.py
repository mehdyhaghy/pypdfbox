"""Compressed object stream emitter.

Mirrors ``org.apache.pdfbox.pdfwriter.compress.COSWriterObjectStream``
(PDFBox 3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/compress/
COSWriterObjectStream.java``).

The class collects ``(COSObjectKey, COSBase)`` pairs via
:meth:`prepare_stream_object` and then writes them into a single deflated
``/ObjStm`` stream when :meth:`write_objects_to_stream` is invoked.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING, BinaryIO

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdfwriter.compress.direct_access_byte_array_output_stream import (
    DirectAccessByteArrayOutputStream,
)

if TYPE_CHECKING:
    from pypdfbox.pdfwriter.compress.cos_writer_compression_pool import (
        COSWriterCompressionPool,
    )

_LOG = logging.getLogger(__name__)
_SPACE = b" "


def _write_pdf(base: COSBase, output: BinaryIO) -> None:
    """Delegate to the value's ``write_pdf`` (snake_case mirror)."""
    # COSFloat, COSInteger, COSBoolean and COSName all expose write_pdf.
    method = getattr(base, "write_pdf", None)
    if method is None:
        raise OSError(f"No write_pdf for {type(base).__name__}")
    method(output)


class COSWriterObjectStream:
    """Streams a batch of compressible COS objects into one ``/ObjStm``."""

    def __init__(self, compression_pool: COSWriterCompressionPool) -> None:
        self._compression_pool = compression_pool
        self._prepared_keys: list[COSObjectKey] = []
        self._prepared_objects: list[COSBase] = []

    def prepare_stream_object(
        self, key: COSObjectKey | None, obj: COSBase | None
    ) -> None:
        """Stage ``obj`` (under ``key``) for the next stream write."""
        if key is None or obj is None:
            return
        self._prepared_keys.append(key)
        self._prepared_objects.append(
            obj.get_object() if isinstance(obj, COSObject) and obj.get_object() is not None else obj
        )

    def get_prepared_keys(self) -> list[COSObjectKey]:
        """Return an immutable view of the staged keys."""
        return list(self._prepared_keys)

    def write_objects_to_stream(self, stream: COSStream) -> COSStream:
        """Write all staged objects into ``stream`` using ``/FlateDecode``."""
        object_count = len(self._prepared_keys)
        stream.set_item(COSName.TYPE, COSName.OBJ_STM)
        stream.set_int(COSName.N, object_count)

        object_numbers: list[int] = []
        objects_buffer: list[DirectAccessByteArrayOutputStream] = []
        for i in range(object_count):
            partial_output = DirectAccessByteArrayOutputStream()
            object_numbers.append(self._prepared_keys[i].get_number())
            self.write_object(partial_output, self._prepared_objects[i], top_level=True)
            objects_buffer.append(partial_output)

        # Build the (objNum, offset) header.
        offsets_buf = BytesIO()
        next_object_offset = 0
        for i, n in enumerate(object_numbers):
            offsets_buf.write(str(n).encode("iso-8859-1"))
            offsets_buf.write(_SPACE)
            offsets_buf.write(str(next_object_offset).encode("iso-8859-1"))
            offsets_buf.write(_SPACE)
            next_object_offset += objects_buffer[i].size()
        offsets_map_buffer = offsets_buf.getvalue()

        with stream.create_output_stream(COSName.FLATE_DECODE) as output:
            output.write(offsets_map_buffer)
            stream.set_int(COSName.FIRST, len(offsets_map_buffer))
            for raw_object in objects_buffer:
                output.write(raw_object.get_raw_data())
        return stream

    # ------------------------------------------------------------------
    # Internal writers (mirror the private writeCOSX methods upstream)
    # ------------------------------------------------------------------
    def write_object(self, output: BinaryIO, obj: COSBase | None, top_level: bool) -> None:
        """Mirrors upstream ``writeObject`` (private). Dispatches on the
        concrete COS type and recurses into containers."""
        if obj is None:
            return
        base: COSBase
        if isinstance(obj, COSObject):
            if not top_level:
                actual_key = obj.get_key()
                if actual_key is not None:
                    self.write_object_reference(output, actual_key)
                    return
            inner = obj.get_object()
            if inner is None:
                _LOG.debug("Can't dereference indirect object, writing COSNull instead %s", obj)
                self.write_cos_null(output)
                return
            base = inner
        else:
            base = obj

        if not top_level and self._compression_pool.contains(base):
            key = self._compression_pool.get_key(base)
            if key is None:
                raise OSError(
                    f"Error: Adding unknown object reference to object stream:{obj}"
                )
            self.write_object_reference(output, key)
            return

        if isinstance(base, COSString):
            self.write_cos_string(output, base)
        elif isinstance(base, COSFloat):
            self.write_cos_float(output, base)
        elif isinstance(base, COSInteger):
            self.write_cos_integer(output, base)
        elif isinstance(base, COSBoolean):
            self.write_cos_boolean(output, base)
        elif isinstance(base, COSName):
            self.write_cos_name(output, base)
        elif isinstance(base, COSArray):
            self.write_cos_array(output, base)
        elif isinstance(base, COSDictionary):
            self.write_cos_dictionary(output, base)
        elif isinstance(base, COSNull):
            self.write_cos_null(output)
        else:
            raise OSError(f"Error: Unknown type in object stream:{obj}")

    # Back-compat alias for callers using the leading-underscore spelling.
    _write_object = write_object

    def write_cos_string(self, output: BinaryIO, cos_string: COSString) -> None:
        """Emit a ``COSString`` token. Mirrors upstream ``writeCOSString``."""
        from pypdfbox.pdfwriter.cos_writer import COSWriter as _Writer

        _Writer.write_string(cos_string, output)
        output.write(_SPACE)

    _write_cos_string = write_cos_string

    def write_cos_float(self, output: BinaryIO, cos_float: COSFloat) -> None:
        """Emit a ``COSFloat`` token. Mirrors upstream ``writeCOSFloat``."""
        _write_pdf(cos_float, output)
        output.write(_SPACE)

    _write_cos_float = write_cos_float

    def write_cos_integer(self, output: BinaryIO, cos_integer: COSInteger) -> None:
        """Emit a ``COSInteger`` token. Mirrors upstream ``writeCOSInteger``."""
        _write_pdf(cos_integer, output)
        output.write(_SPACE)

    _write_cos_integer = write_cos_integer

    def write_cos_boolean(self, output: BinaryIO, cos_boolean: COSBoolean) -> None:
        """Emit a ``COSBoolean`` token. Mirrors upstream ``writeCOSBoolean``."""
        _write_pdf(cos_boolean, output)
        output.write(_SPACE)

    _write_cos_boolean = write_cos_boolean

    def write_cos_name(self, output: BinaryIO, cos_name: COSName) -> None:
        """Emit a ``COSName`` token. Mirrors upstream ``writeCOSName``."""
        _write_pdf(cos_name, output)
        output.write(_SPACE)

    _write_cos_name = write_cos_name

    def write_cos_array(self, output: BinaryIO, cos_array: COSArray) -> None:
        """Emit a ``COSArray`` token. Mirrors upstream ``writeCOSArray``."""
        output.write(b"[")
        for value in cos_array:
            if value is None:
                self.write_cos_null(output)
            else:
                self.write_object(output, value, top_level=False)
        output.write(b"]")
        output.write(_SPACE)

    _write_cos_array = write_cos_array

    def write_cos_dictionary(self, output: BinaryIO, cos_dict: COSDictionary) -> None:
        """Emit a ``COSDictionary`` token. Mirrors upstream ``writeCOSDictionary``."""
        output.write(b"<<")
        for key, value in cos_dict.entry_set():
            if value is None:
                continue
            # PDFBOX-5927: keys are written as top-level to avoid an indirect rewrite.
            self.write_object(output, key, top_level=True)
            self.write_object(output, value, top_level=False)
        output.write(b">>")
        output.write(_SPACE)

    _write_cos_dictionary = write_cos_dictionary

    def write_object_reference(self, output: BinaryIO, ref: COSObjectKey) -> None:
        """Emit an indirect-object reference (``N G R``). Mirrors upstream
        ``writeObjectReference``."""
        output.write(str(ref.get_number()).encode("iso-8859-1"))
        output.write(_SPACE)
        output.write(str(ref.get_generation()).encode("iso-8859-1"))
        output.write(_SPACE)
        output.write(b"R")
        output.write(_SPACE)

    _write_object_reference = write_object_reference

    def write_cos_null(self, output: BinaryIO) -> None:
        """Emit a ``null`` token. Mirrors upstream ``writeCOSNull``."""
        output.write(b"null")
        output.write(_SPACE)

    _write_cos_null = write_cos_null


__all__ = ["COSWriterObjectStream"]
