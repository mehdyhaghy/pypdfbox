"""Wave 1275 parity tests: XPacket aliases + lazy TypeMapping."""

from __future__ import annotations

from pypdfbox.xmpbox.type.type_mapping import TypeMapping
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


def test_get_end_x_packet_alias_matches_existing() -> None:
    meta = XMPMetadata()
    assert meta.get_end_x_packet() == meta.get_end_xpacket()


def test_set_end_x_packet_alias_propagates() -> None:
    meta = XMPMetadata()
    meta.set_end_x_packet("r")
    assert meta.get_end_xpacket() == "r"
    assert meta.is_read_only() is True


def test_get_type_mapping_returns_lazy_singleton() -> None:
    meta = XMPMetadata()
    tm1 = meta.get_type_mapping()
    tm2 = meta.get_type_mapping()
    assert isinstance(tm1, TypeMapping)
    assert tm1 is tm2  # cached after first call
