"""PDFBOX-6185 wiring: ScratchFile backing file via create_protected_temp_file.

Upstream ``ScratchFile.enlarge`` (3.0 branch, post PDFBOX-6185) creates its
backing temp file through ``IOUtils.createProtectedTempFile(dir, "PDFBox",
".tmp")`` so owner-only permissions apply at creation time, and
``ScratchFile.close`` deletes the file after closing the handle. These tests
pin the ported wiring in ``pypdfbox/io/scratch_file.py``.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from pypdfbox.io import MemoryUsageSetting, ScratchFile
from pypdfbox.io import io_utils as io_utils_module


def _backing_path(sf: ScratchFile) -> Path | None:
    return sf._tmp_path  # noqa: SLF001


def test_backing_file_uses_protected_helper_naming_and_dir(tmp_path: Path) -> None:
    setting = MemoryUsageSetting.setup_temp_file_only().set_temp_dir(tmp_path)
    with ScratchFile(setting) as sf:
        path = _backing_path(sf)
        assert path is not None
        assert path.exists()
        assert path.parent == tmp_path
        # Upstream prefix/suffix: "PDFBox" / ".tmp".
        assert path.name.startswith("PDFBox")
        assert path.name.endswith(".tmp")


@pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX file modes not applicable on Windows"
)
def test_backing_file_has_owner_only_permissions(tmp_path: Path) -> None:
    setting = MemoryUsageSetting.setup_temp_file_only().set_temp_dir(tmp_path)
    with ScratchFile(setting) as sf:
        path = _backing_path(sf)
        assert path is not None
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == stat.S_IRUSR | stat.S_IWUSR  # 0o600


def test_backing_file_unlinked_on_close(tmp_path: Path) -> None:
    setting = MemoryUsageSetting.setup_temp_file_only().set_temp_dir(tmp_path)
    sf = ScratchFile(setting)
    idx = sf.get_new_page()
    sf.write_page(idx, b"\xab" * sf.page_size)
    path = _backing_path(sf)
    assert path is not None and path.exists()
    sf.close()
    assert not path.exists()
    assert _backing_path(sf) is None
    # Close stays idempotent.
    sf.close()


def test_backing_file_registered_for_shutdown_deletion(tmp_path: Path) -> None:
    setting = MemoryUsageSetting.setup_temp_file_only().set_temp_dir(tmp_path)
    with ScratchFile(setting) as sf:
        path = _backing_path(sf)
        assert path in io_utils_module._TEMP_DIRS_TO_DELETE  # noqa: SLF001


def test_mixed_mode_spill_creates_protected_backing_file(tmp_path: Path) -> None:
    setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=32).set_temp_dir(
        tmp_path
    )
    with ScratchFile(setting, page_size=16) as sf:
        # Two pages fit in RAM; no backing file yet.
        ids = [sf.get_new_page() for _ in range(2)]
        assert _backing_path(sf) is None
        # Third page spills to disk through the protected helper.
        ids.append(sf.get_new_page())
        path = _backing_path(sf)
        assert path is not None
        assert path.parent == tmp_path
        if sys.platform != "win32":
            assert stat.S_IMODE(path.stat().st_mode) == stat.S_IRUSR | stat.S_IWUSR
        for i, idx in enumerate(ids):
            sf.write_page(idx, bytes([i]) * 16)
        for i, idx in enumerate(ids):
            out = bytearray(16)
            sf.read_page(idx, out)
            assert bytes(out) == bytes([i]) * 16
    assert not path.exists()


def test_temp_file_only_round_trip_survives_wiring(tmp_path: Path) -> None:
    setting = MemoryUsageSetting.setup_temp_file_only().set_temp_dir(tmp_path)
    with ScratchFile(setting, page_size=64) as sf:
        idx = sf.get_new_page()
        payload = b"\xde\xad\xbe\xef" * 16
        sf.write_page(idx, payload)
        out = bytearray(64)
        sf.read_page(idx, out)
        assert bytes(out) == payload


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod-based open failure is POSIX-only"
)
@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permissions")
def test_open_failure_deletes_fresh_backing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Upstream deletes the temp file when RandomAccessFile creation fails."""
    created: list[Path] = []
    real_create = io_utils_module.create_protected_temp_file

    def failing_create(
        directory: object, prefix: str | None, suffix: str | None
    ) -> Path:
        path = real_create(directory, prefix, suffix)
        created.append(path)
        os.chmod(path, 0)  # make the subsequent open("r+b") fail
        return path

    monkeypatch.setattr(
        "pypdfbox.io.scratch_file.create_protected_temp_file", failing_create
    )
    setting = MemoryUsageSetting.setup_temp_file_only().set_temp_dir(tmp_path)
    with pytest.raises(OSError):
        ScratchFile(setting)
    assert len(created) == 1
    assert not created[0].exists()
