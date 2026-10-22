from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .compress import CompressParameters
    from .content_stream_writer import ContentStreamWriter
    from .cos_standard_output_stream import COSStandardOutputStream
    from .cos_writer import COSWriter
    from .cos_writer_xref_entry import COSWriterXRefEntry

__getattr__, __dir__ = _attach(
    __name__,
    {
        "CompressParameters": ".compress",
        "ContentStreamWriter": ".content_stream_writer",
        "COSStandardOutputStream": ".cos_standard_output_stream",
        "COSWriter": ".cos_writer",
        "COSWriterXRefEntry": ".cos_writer_xref_entry",
    },
)

__all__ = [
    "COSStandardOutputStream",
    "COSWriter",
    "COSWriterXRefEntry",
    "CompressParameters",
    "ContentStreamWriter",
]
