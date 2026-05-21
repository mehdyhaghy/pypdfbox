"""``Loader._coerce_source`` parity across every accepted source shape
(wave 1366, agent E).

Verifies ``Loader.load_pdf`` accepts:

* ``str`` paths
* ``pathlib.Path``
* ``os.PathLike`` (custom adapter)
* ``bytes``
* ``bytearray``
* ``memoryview``
* binary streams (``BinaryIO`` — ``io.BytesIO`` and a duck-typed shim)
* ``RandomAccessRead`` (passed through without ownership transfer)

Plus rejection of:

* ``int``, ``None``, lists — non-coercible shapes raise ``TypeError`` at
  the boundary.

No upstream JUnit counterpart — pypdfbox's coercion helper is a Python-
side addition since Java overload resolution handles the equivalent.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.loader import Loader


def _make_pdf_bytes() -> bytes:
    sink = io.BytesIO()
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(sink)
    return sink.getvalue()


def test_load_from_str_path(tmp_path: Path) -> None:
    """``Loader.load_pdf(str)`` resolves through ``RandomAccessReadBufferedFile``."""
    p = tmp_path / "from_str.pdf"
    p.write_bytes(_make_pdf_bytes())
    cos = Loader.load_pdf(str(p))
    try:
        assert cos.get_trailer() is not None
    finally:
        cos.close()


def test_load_from_pathlib_path(tmp_path: Path) -> None:
    """``Loader.load_pdf(Path)`` succeeds — same path as ``str`` via PathLike."""
    p = tmp_path / "from_path.pdf"
    p.write_bytes(_make_pdf_bytes())
    cos = Loader.load_pdf(p)
    try:
        assert cos.get_trailer() is not None
    finally:
        cos.close()


def test_load_from_custom_pathlike(tmp_path: Path) -> None:
    """A custom object exposing ``__fspath__`` is accepted (mirrors Java's
    ``File`` polymorphism via the os.PathLike protocol)."""

    class _FakePath:
        def __init__(self, p: Path) -> None:
            self._p = p

        def __fspath__(self) -> str:
            return str(self._p)

    p = tmp_path / "from_fspath.pdf"
    p.write_bytes(_make_pdf_bytes())
    cos = Loader.load_pdf(_FakePath(p))
    try:
        assert cos.get_trailer() is not None
    finally:
        cos.close()


def test_load_from_bytes() -> None:
    """Raw ``bytes`` route through ``RandomAccessReadBuffer``."""
    cos = Loader.load_pdf(_make_pdf_bytes())
    try:
        assert cos.get_trailer() is not None
    finally:
        cos.close()


def test_load_from_bytearray() -> None:
    """``bytearray`` is accepted same as ``bytes``."""
    cos = Loader.load_pdf(bytearray(_make_pdf_bytes()))
    try:
        assert cos.get_trailer() is not None
    finally:
        cos.close()


def test_load_from_memoryview() -> None:
    """``memoryview`` is accepted same as ``bytes``."""
    cos = Loader.load_pdf(memoryview(_make_pdf_bytes()))
    try:
        assert cos.get_trailer() is not None
    finally:
        cos.close()


def test_load_from_bytesio() -> None:
    """``io.BytesIO`` (a ``BinaryIO``) is drained via
    ``create_buffer_from_stream``."""
    cos = Loader.load_pdf(io.BytesIO(_make_pdf_bytes()))
    try:
        assert cos.get_trailer() is not None
    finally:
        cos.close()


def test_load_from_duck_typed_stream() -> None:
    """Any object exposing a ``read`` method is treated as a binary stream."""

    class _ReadShim:
        def __init__(self, data: bytes) -> None:
            self._buf = io.BytesIO(data)

        def read(self, n: int | None = -1) -> bytes:
            return self._buf.read(n if n is not None else -1)

    cos = Loader.load_pdf(_ReadShim(_make_pdf_bytes()))
    try:
        assert cos.get_trailer() is not None
    finally:
        cos.close()


def test_load_from_random_access_read_no_ownership_transfer() -> None:
    """When passed a ``RandomAccessRead`` directly the Loader does NOT
    take ownership — caller must close it explicitly."""
    rar = RandomAccessReadBuffer(_make_pdf_bytes())
    cos = Loader.load_pdf(rar)
    try:
        assert cos.get_trailer() is not None
    finally:
        cos.close()
        # Caller-owned RAR — close it now that the doc is closed.
        rar.close()


@pytest.mark.parametrize(
    "bad",
    [None, 42, 3.14, [], {}, (b"PDF",)],
    ids=["none", "int", "float", "list", "dict", "tuple"],
)
def test_load_rejects_non_source(bad: object) -> None:
    """Non-coercible source shapes raise ``TypeError`` from
    ``_coerce_source`` at the Loader boundary."""
    with pytest.raises(TypeError):
        Loader.load_pdf(bad)


def test_load_pdf_from_bytes_rejects_non_bytes() -> None:
    """``Loader.load_pdf_from_bytes`` explicitly rejects non-bytes-like
    input with a clear message (eager validation)."""
    with pytest.raises(TypeError, match="bytes"):
        Loader.load_pdf_from_bytes("a string")  # type: ignore[arg-type]


def test_load_pdf_from_file_rejects_non_path() -> None:
    """``Loader.load_pdf_from_file`` explicitly rejects non-path input."""
    with pytest.raises(TypeError, match="str or PathLike"):
        Loader.load_pdf_from_file(b"raw bytes")  # type: ignore[arg-type]


def test_load_pdf_from_bytes_succeeds_with_bytes() -> None:
    """Happy path through the eager-validation entry."""
    cos = Loader.load_pdf_from_bytes(_make_pdf_bytes())
    try:
        assert cos.get_trailer() is not None
    finally:
        cos.close()


def test_load_pdf_from_file_succeeds_with_path(tmp_path: Path) -> None:
    """Happy path through the eager-validation entry."""
    p = tmp_path / "from_file.pdf"
    p.write_bytes(_make_pdf_bytes())
    cos = Loader.load_pdf_from_file(p)
    try:
        assert cos.get_trailer() is not None
    finally:
        cos.close()


def test_load_pdf_from_file_accepts_os_pathlike(tmp_path: Path) -> None:
    """``os.PathLike`` instance (not just ``str``/``Path``) is accepted."""
    p = tmp_path / "from_file_pl.pdf"
    p.write_bytes(_make_pdf_bytes())

    class _OsPath:
        def __init__(self, p: Path) -> None:
            self._p = p

        def __fspath__(self) -> str:
            return os.fspath(self._p)

    cos = Loader.load_pdf_from_file(_OsPath(p))
    try:
        assert cos.get_trailer() is not None
    finally:
        cos.close()
