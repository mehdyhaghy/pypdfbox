from __future__ import annotations

from pypdfbox.pdfwriter.compress.compress_parameters import CompressParameters
from pypdfbox.pdfwriter.compress.cos_object_pool import COSObjectPool
from pypdfbox.pdfwriter.compress.cos_writer_compression_pool import (
    COSWriterCompressionPool,
)
from pypdfbox.pdfwriter.compress.cos_writer_object_stream import COSWriterObjectStream
from pypdfbox.pdfwriter.compress.direct_access_byte_array_output_stream import (
    DirectAccessByteArrayOutputStream,
)

__all__ = [
    "COSObjectPool",
    "COSWriterCompressionPool",
    "COSWriterObjectStream",
    "CompressParameters",
    "DirectAccessByteArrayOutputStream",
]
