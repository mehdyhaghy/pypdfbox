from __future__ import annotations

from dataclasses import dataclass, field

from pypdfbox.cos import COSDictionary


@dataclass
class DecodeResult:
    """Outcome of a ``Filter.decode()`` call.

    Mirrors `org.apache.pdfbox.filter.DecodeResult`. Some filters
    (notably DCT and JPX) update the stream parameters during decode —
    e.g. populating ``/ColorSpace`` from JPEG markers. ``parameters``
    starts as a copy of the input dictionary and may be mutated.
    """

    parameters: COSDictionary = field(default_factory=COSDictionary)
    bytes_written: int = 0
