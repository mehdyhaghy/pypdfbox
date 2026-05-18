from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox import Loader
from pypdfbox.cos import COSDictionary, COSDocument
from pypdfbox.io import RandomAccessRead, RandomAccessReadBuffer


def _build_pdf(objects: list[bytes], trailer: bytes, version: bytes = b"1.4") -> bytes:
    """Assemble a tiny but spec-compliant PDF.

    Mirrors the helper in ``tests/pdfparser/test_pdf_parser.py``; copied
    here to keep this test module self-contained (no cross-package
    relative import).
    """
    out = bytearray()
    out += b"%PDF-" + version + b"\n"
    offsets: list[int] = [0]
    for body in objects:
        offsets.append(len(out))
        out += body
        if not body.endswith(b"\n"):
            out += b"\n"
    xref_offset = len(out)
    out += b"xref\n"
    out += f"0 {len(offsets)}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n"
    out += trailer + b"\n"
    out += b"startxref\n"
    out += f"{xref_offset}\n".encode("ascii")
    out += b"%%EOF"
    return bytes(out)


def _minimal_pdf() -> bytes:
    return _build_pdf(
        [b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
         b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj"],
        b"<< /Size 3 /Root 1 0 R >>",
        version=b"1.7",
    )


def _assert_minimal_document(doc: COSDocument) -> None:
    assert isinstance(doc, COSDocument)
    assert doc.get_version() == 1.7
    catalog = doc.get_catalog()
    assert isinstance(catalog, COSDictionary)
    assert catalog.get_name("Type") == "Catalog"


# ---------- source-form coverage ----------


def test_load_pdf_from_bytes() -> None:
    doc = Loader.load_pdf(_minimal_pdf())
    try:
        _assert_minimal_document(doc)
    finally:
        doc.close()


def test_load_pdf_from_bytearray() -> None:
    doc = Loader.load_pdf(bytearray(_minimal_pdf()))
    try:
        _assert_minimal_document(doc)
    finally:
        doc.close()


def test_load_pdf_from_memoryview() -> None:
    raw = _minimal_pdf()
    doc = Loader.load_pdf(memoryview(raw))
    try:
        _assert_minimal_document(doc)
    finally:
        doc.close()


def test_load_pdf_from_path(tmp_path: Path) -> None:
    pdf_path = tmp_path / "tiny.pdf"
    pdf_path.write_bytes(_minimal_pdf())
    doc = Loader.load_pdf(pdf_path)
    try:
        _assert_minimal_document(doc)
    finally:
        doc.close()


def test_load_pdf_from_str_path(tmp_path: Path) -> None:
    pdf_path = tmp_path / "tiny.pdf"
    pdf_path.write_bytes(_minimal_pdf())
    doc = Loader.load_pdf(str(pdf_path))
    try:
        _assert_minimal_document(doc)
    finally:
        doc.close()


def test_load_pdf_from_binary_io() -> None:
    doc = Loader.load_pdf(io.BytesIO(_minimal_pdf()))
    try:
        _assert_minimal_document(doc)
    finally:
        doc.close()


def test_load_pdf_from_random_access_read() -> None:
    src = RandomAccessReadBuffer(_minimal_pdf())
    doc = Loader.load_pdf(src)
    try:
        _assert_minimal_document(doc)
    finally:
        doc.close()


# ---------- error path ----------


def test_load_pdf_rejects_int() -> None:
    with pytest.raises(TypeError, match="Loader.load_pdf"):
        Loader.load_pdf(123)  # type: ignore[arg-type]


def test_load_pdf_rejects_none() -> None:
    with pytest.raises(TypeError):
        Loader.load_pdf(None)  # type: ignore[arg-type]


# ---------- lifecycle ----------


def test_doc_close_releases_loader_owned_source(tmp_path: Path) -> None:
    """When Loader created the RandomAccessRead, ``doc.close()`` must
    close it too — otherwise callers that only see the document leak the
    file handle."""
    pdf_path = tmp_path / "tiny.pdf"
    pdf_path.write_bytes(_minimal_pdf())
    doc = Loader.load_pdf(pdf_path)
    inner: RandomAccessRead = doc._source  # type: ignore[assignment]
    assert inner is not None
    assert not inner.is_closed()
    doc.close()
    assert inner.is_closed()


def test_doc_close_does_not_touch_caller_owned_source() -> None:
    """When the caller passes a RandomAccessRead in, ownership stays
    with them — closing the document leaves the source open."""
    src = RandomAccessReadBuffer(_minimal_pdf())
    doc = Loader.load_pdf(src)
    doc.close()
    assert not src.is_closed()
    src.close()


# ---------- MemoryUsageSetting plumbing ----------


def test_load_pdf_default_memory_usage_setting_uses_default_scratch() -> None:
    """No-setting path keeps the existing heap-backed default — the
    document's scratch file should be the one COSDocument allocates
    lazily (i.e. not the loader-supplied instance)."""
    from pypdfbox.io import StorageMode  # noqa: PLC0415

    doc = Loader.load_pdf(_minimal_pdf())
    try:
        # Default heap-backed scratch.
        assert doc.scratch_file.setting.mode is StorageMode.MAIN_MEMORY_ONLY
    finally:
        doc.close()


def test_load_pdf_threads_memory_usage_setting_to_scratch_file(
    tmp_path: Path,
) -> None:
    """Caller-supplied :class:`MemoryUsageSetting` should be honoured —
    the resulting document's ``ScratchFile`` carries the same policy."""
    from pypdfbox.io import MemoryUsageSetting, StorageMode  # noqa: PLC0415

    setting = MemoryUsageSetting.setup_temp_file_only().set_temp_dir(tmp_path)
    doc = Loader.load_pdf(_minimal_pdf(), None, setting)
    try:
        assert doc.scratch_file.setting is setting
        assert doc.scratch_file.setting.mode is StorageMode.TEMP_FILE_ONLY
    finally:
        doc.close()


def test_load_pdf_mixed_memory_usage_setting() -> None:
    """The mixed mode setup is also threaded through — the scratch file
    keeps the supplied memory cap and storage cap."""
    from pypdfbox.io import MemoryUsageSetting, StorageMode  # noqa: PLC0415

    setting = MemoryUsageSetting.setup_mixed(
        max_main_memory_bytes=64 * 1024,
        max_storage_bytes=1024 * 1024,
    )
    doc = Loader.load_pdf(_minimal_pdf(), None, setting)
    try:
        assert doc.scratch_file.setting.mode is StorageMode.MIXED
        assert doc.scratch_file.setting.max_main_memory_bytes == 64 * 1024
        assert doc.scratch_file.setting.max_storage_bytes == 1024 * 1024
    finally:
        doc.close()


def test_load_pdf_closes_loader_owned_scratch_on_doc_close() -> None:
    """Loader-allocated scratch files are owned by the document so
    ``doc.close()`` releases them."""
    from pypdfbox.io import MemoryUsageSetting  # noqa: PLC0415

    setting = MemoryUsageSetting.setup_temp_file_only()
    doc = Loader.load_pdf(_minimal_pdf(), None, setting)
    scratch = doc.scratch_file
    assert not scratch.is_closed()
    doc.close()
    assert scratch.is_closed()


def test_load_pdf_from_file_threads_memory_usage_setting(
    tmp_path: Path,
) -> None:
    """The path-shaped entry point forwards the setting too."""
    from pypdfbox.io import MemoryUsageSetting, StorageMode  # noqa: PLC0415

    path = tmp_path / "tiny.pdf"
    path.write_bytes(_minimal_pdf())
    setting = MemoryUsageSetting.setup_main_memory_only(
        max_main_memory_bytes=128 * 1024
    )
    doc = Loader.load_pdf_from_file(path, None, setting)
    try:
        assert doc.scratch_file.setting.mode is StorageMode.MAIN_MEMORY_ONLY
        assert doc.scratch_file.setting.max_main_memory_bytes == 128 * 1024
    finally:
        doc.close()


def test_load_pdf_from_bytes_threads_memory_usage_setting() -> None:
    """The bytes-shaped entry point forwards the setting too."""
    from pypdfbox.io import MemoryUsageSetting, StorageMode  # noqa: PLC0415

    setting = MemoryUsageSetting.setup_temp_file_only()
    doc = Loader.load_pdf_from_bytes(_minimal_pdf(), None, setting)
    try:
        assert doc.scratch_file.setting.mode is StorageMode.TEMP_FILE_ONLY
    finally:
        doc.close()


def test_load_alias_threads_memory_usage_setting() -> None:
    """The ``Loader.load`` upstream-style alias also forwards."""
    from pypdfbox.io import MemoryUsageSetting, StorageMode  # noqa: PLC0415

    setting = MemoryUsageSetting.setup_main_memory_only(max_main_memory_bytes=32768)
    doc = Loader.load(_minimal_pdf(), None, setting)
    try:
        assert doc.scratch_file.setting.mode is StorageMode.MAIN_MEMORY_ONLY
        assert doc.scratch_file.setting.max_main_memory_bytes == 32768
    finally:
        doc.close()
