from __future__ import annotations

from tests.pdmodel.test_pdfua_flavour import _xmp_packet


def test_wave1103_xmp_packet_includes_optional_conformance() -> None:
    packet = _xmp_packet(2, conformance="B")

    assert b'pdfuaid:part="2"' in packet
    assert b'pdfuaid:conformance="B"' in packet

