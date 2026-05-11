"""Smoke test for :class:`ConnectedInputStream`."""

from __future__ import annotations

import io

from pypdfbox.examples.util.connected_input_stream import ConnectedInputStream


class _FakeConnection:
    def __init__(self) -> None:
        self.disconnected = False

    def disconnect(self) -> None:
        self.disconnected = True


def test_close_disconnects_connection() -> None:
    payload = io.BytesIO(b"hello world")
    con = _FakeConnection()
    with ConnectedInputStream(con, payload):
        pass
    assert con.disconnected is True


def test_read_delegates() -> None:
    payload = io.BytesIO(b"abc")
    cis = ConnectedInputStream(_FakeConnection(), payload)
    buf = bytearray(3)
    n = cis.read(buf)
    assert n == 3
    assert buf == b"abc"
    cis.close()


def test_mark_supported_for_seekable() -> None:
    cis = ConnectedInputStream(_FakeConnection(), io.BytesIO(b"x"))
    assert cis.mark_supported() is True
    cis.close()
