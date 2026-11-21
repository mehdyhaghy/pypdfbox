"""PDFBOX-6334 forward-port: malformed ``<?xpacket end ...?>`` handling.

Upstream 3.0.8 read ``charAt(5)`` of the end PI data without a length check,
so ``<?xpacket end=?>`` raised ``StringIndexOutOfBoundsException``. 3.0.9
reports ``XpacketBadEnd`` instead. pypdfbox previously treated an end PI it
could not match as absent and accepted the packet.
"""

import pytest

from pypdfbox.xmpbox import DomXmpParser, XmpParsingException

_BAD_VALUE = "Expected xpacket 'end' attribute with value 'r' or 'w'"
_NOT_FIRST = "Expected xpacket 'end' attribute (must be present and placed in first)"

_HEAD = (
    "<?xpacket begin=\"﻿\" id=\"W5M0MpCehiHzreSzNTczkc9d\"?>\n"
    "<x:xmpmeta xmlns:x=\"adobe:ns:meta/\">\n"
    "\t<rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"/>\n"
    "</x:xmpmeta>"
)


@pytest.mark.parametrize(
    "data",
    ["end=", "end=r", "end='", "end=\"", "end='r", "end=\"w"],
    ids=["bare", "unquoted", "sq", "dq", "sq_r", "dq_w"],
)
def test_parse_end_packet_short_data_is_bad_end(data: str) -> None:
    with pytest.raises(XmpParsingException) as info:
        DomXmpParser().parse_end_packet(data)
    assert str(info.value) == _BAD_VALUE
    assert (
        info.value.get_error_type()
        is XmpParsingException.ErrorType.XPACKET_BAD_END
    )


@pytest.mark.parametrize("data", ["end='r'", "end=\"w\"", "end='w' extra='1'"])
def test_parse_end_packet_valid(data: str) -> None:
    assert DomXmpParser().parse_end_packet(data) == data[5]


@pytest.mark.parametrize(
    ("tail", "message"),
    [
        ("<?xpacket end=?>", _BAD_VALUE),
        ("<?xpacket end=r?>", _BAD_VALUE),
        ("<?xpacket end=\"\"?>", _BAD_VALUE),
        ("<?xpacket end='k'?>", _BAD_VALUE),
        ("<?xpacket end?>", _NOT_FIRST),
    ],
    ids=["bare", "unquoted", "empty", "bad_value", "no_equals"],
)
def test_parse_rejects_malformed_end_pi(tail: str, message: str) -> None:
    with pytest.raises(XmpParsingException) as info:
        DomXmpParser().parse((_HEAD + tail).encode("utf-8"))
    assert str(info.value) == message


@pytest.mark.parametrize(
    ("tail", "expected"),
    [
        ("<?xpacket end=\"r\"?>", "r"),
        ("<?xpacket end='w'?>", "w"),
        ("<?xpacket end='r' extra='1'?>", "r"),
    ],
    ids=["r", "w", "trailing_attr"],
)
def test_parse_accepts_valid_end_pi(tail: str, expected: str) -> None:
    metadata = DomXmpParser().parse((_HEAD + tail).encode("utf-8"))
    assert metadata.get_end_x_packet() == expected


def test_parse_missing_end_pi_still_tolerated() -> None:
    metadata = DomXmpParser().parse(_HEAD.encode("utf-8"))
    assert metadata.get_end_x_packet() == "w"
