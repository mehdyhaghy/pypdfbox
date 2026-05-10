"""Wave 1275 parity test for COSWriter.set_output / set_standard_output."""

from __future__ import annotations

import io

from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream
from pypdfbox.pdfwriter.cos_writer import COSWriter


def test_set_output_replaces_raw_sink() -> None:
    sink_a = io.BytesIO()
    sink_b = io.BytesIO()
    writer = COSWriter(sink_a)
    try:
        assert writer.get_output() is sink_a
        writer.set_output(sink_b)
        assert writer.get_output() is sink_b
    finally:
        writer.close()


def test_set_standard_output_replaces_framing_layer() -> None:
    sink = io.BytesIO()
    writer = COSWriter(sink)
    try:
        original = writer.get_standard_output()
        # Build a replacement standard output that wraps the same adapter
        # so we can confirm the setter swap actually changes the reference.
        replacement = COSStandardOutputStream(writer._adapter, position=42)
        writer.set_standard_output(replacement)
        assert writer.get_standard_output() is replacement
        assert writer.get_standard_output() is not original
    finally:
        writer.close()
