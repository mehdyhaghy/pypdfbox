"""Port of ``org.apache.pdfbox.benchmark``.

The upstream module is a JMH harness; the port wraps its workloads in
stdlib ``time.perf_counter`` helpers so they can be driven from
``pytest-benchmark`` or a plain CLI. The Blackhole pattern is replaced
with assignment-to-attribute consume sinks that prevent dead-code
elimination without pulling in JMH.
"""

from pypdfbox.benchmark.load_and_save import LoadAndSave
from pypdfbox.benchmark.null_output_stream import NullOutputStream
from pypdfbox.benchmark.rendering import Rendering
from pypdfbox.benchmark.text_extraction import TextExtraction

__all__ = [
    "LoadAndSave",
    "NullOutputStream",
    "Rendering",
    "TextExtraction",
]
