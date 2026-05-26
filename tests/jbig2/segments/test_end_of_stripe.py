"""Hand-written tests for the JBIG2 EndOfStripe segment (7.4.9)."""

from __future__ import annotations

import struct

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.end_of_stripe import EndOfStripe


def _parse(data: bytes) -> EndOfStripe:
    sis = SubInputStream(ImageInputStream(data), 0, len(data))
    end_of_stripe = EndOfStripe()
    end_of_stripe.init(None, sis)
    return end_of_stripe


def test_line_number():
    end_of_stripe = _parse(struct.pack(">I", 12345))
    assert end_of_stripe.get_line_number() == 12345


def test_line_number_zero():
    end_of_stripe = _parse(struct.pack(">I", 0))
    assert end_of_stripe.get_line_number() == 0


def test_line_number_max_32_bit():
    end_of_stripe = _parse(struct.pack(">I", 0xFFFFFFFF))
    assert end_of_stripe.get_line_number() == 0xFFFFFFFF
