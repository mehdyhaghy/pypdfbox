"""Coverage-boost tests for :mod:`pypdfbox.pdmodel.font.file_system_font_provider`.

Exercises per-platform default font directories, cache file plumbing
(`get_disk_cache_file`, `is_bad_path`, `save_disk_cache`,
`write_font_info`), the parse-success / parse-failure branches of
`_add_true_type_font` / `_add_type1_font` / `_add_true_type_collection`,
the hashing helper, the `create_fs_ignored` recovery path, and the
public spellings of the private scan helpers.

Uses the bundled Liberation TTFs from ``pypdfbox/resources/ttf/`` as
real on-disk font fixtures so we never depend on the host OS's actual
font directories.
"""

from __future__ import annotations

import io
import pathlib
import shutil
import sys
from typing import Any

import pytest

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.pdmodel.font import file_system_font_provider as mod
from pypdfbox.pdmodel.font.file_system_font_provider import FileSystemFontProvider

# ---------- shared helpers ----------

_LIBERATION_DIR = (
    pathlib.Path(__file__).resolve().parents[3]
    / "pypdfbox"
    / "resources"
    / "ttf"
)


def _copy_liberation(tmp_path: pathlib.Path, name: str) -> pathlib.Path:
    src = _LIBERATION_DIR / name
    dst = tmp_path / name
    shutil.copy2(src, dst)
    return dst


# ---------- platform-dispatch (_default_font_dirs) ----------


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "monkeypatching sys.platform does not change pathlib's path-flavour "
        "dispatch — Path('/System/Library/Fonts') stays a WindowsPath under "
        "the running interpreter and stringifies with backslashes, breaking "
        "the POSIX-style substring assertions."
    ),
)
def test_default_font_dirs_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod.sys, "platform", "darwin")
    dirs = mod._default_font_dirs()
    paths = [str(p) for p in dirs]
    assert any("/System/Library/Fonts" in p for p in paths)
    assert any("/Library/Fonts" in p for p in paths)
    assert any("Library/Fonts" in p for p in paths)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "monkeypatching sys.platform does not change pathlib's path-flavour "
        "dispatch — Path('/usr/share/fonts') stays a WindowsPath under the "
        "running interpreter and stringifies with backslashes, breaking the "
        "POSIX-style substring assertions."
    ),
)
def test_default_font_dirs_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod.sys, "platform", "linux")
    dirs = mod._default_font_dirs()
    paths = [str(p) for p in dirs]
    assert any("/usr/share/fonts" in p for p in paths)
    assert any("/usr/local/share/fonts" in p for p in paths)
    assert any(".fonts" in p for p in paths)
    assert any(".local/share/fonts" in p for p in paths)


def test_default_font_dirs_win32_with_localappdata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mod.sys, "platform", "win32")
    monkeypatch.setenv("WINDIR", "C:\\Windows")
    monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\dev\\AppData\\Local")
    dirs = mod._default_font_dirs()
    paths = [str(p) for p in dirs]
    assert any("Fonts" in p for p in paths)
    assert any("Microsoft" in p for p in paths)


def test_default_font_dirs_win32_without_localappdata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mod.sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("WINDIR", raising=False)
    dirs = mod._default_font_dirs()
    # Without WINDIR we still get the C:\Windows\Fonts fallback.
    assert any("Fonts" in str(p) for p in dirs)


def test_default_font_dirs_unknown_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mod.sys, "platform", "freebsd")
    dirs = mod._default_font_dirs()
    assert dirs == []


# ---------- _collect_font_files ----------


def test_collect_font_files_finds_supported_suffixes(
    tmp_path: pathlib.Path,
) -> None:
    (tmp_path / "a.ttf").write_bytes(b"")
    (tmp_path / "b.otf").write_bytes(b"")
    (tmp_path / "c.ttc").write_bytes(b"")
    (tmp_path / "d.otc").write_bytes(b"")
    (tmp_path / "e.pfb").write_bytes(b"")
    (tmp_path / "f.txt").write_text("nope", encoding="utf-8")
    files = FileSystemFontProvider._collect_font_files([tmp_path])
    suffixes = sorted(p.suffix.lower() for p in files)
    assert suffixes == [".otc", ".otf", ".pfb", ".ttc", ".ttf"]


def test_collect_font_files_recurses_into_subdirs(
    tmp_path: pathlib.Path,
) -> None:
    nested = tmp_path / "deep" / "deeper"
    nested.mkdir(parents=True)
    (nested / "nested.ttf").write_bytes(b"")
    files = FileSystemFontProvider._collect_font_files([tmp_path])
    assert len(files) == 1
    assert files[0].name == "nested.ttf"


def test_collect_font_files_handles_oserror(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When `Path.is_dir` raises OSError, the directory is skipped."""

    class Boom(type(tmp_path)):
        def is_dir(self) -> bool:  # type: ignore[override]
            raise OSError("boom")

    boom = Boom(str(tmp_path))
    files = FileSystemFontProvider._collect_font_files([boom])
    assert files == []


def test_collect_font_files_handles_rglob_oserror(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class WalkErr(type(tmp_path)):
        def is_dir(self) -> bool:  # type: ignore[override]
            return True

        def rglob(self, pattern: str) -> Any:  # type: ignore[override]
            raise OSError("permission denied")

    bad = WalkErr(str(tmp_path))
    files = FileSystemFontProvider._collect_font_files([bad])
    assert files == []


# ---------- scan / add real TTFs ----------


def test_scan_loads_real_ttf(tmp_path: pathlib.Path) -> None:
    _copy_liberation(tmp_path, "LiberationSans-Regular.ttf")
    provider = FileSystemFontProvider(directories=[tmp_path])
    infos = list(provider.get_font_info())
    assert len(infos) == 1
    info = infos[0]
    assert info.get_post_script_name() == "LiberationSans"
    assert info.get_format() is FontFormat.TTF
    # OS/2 metadata extracted
    assert info.get_weight_class() > 0


def test_add_true_type_font_public_spelling(tmp_path: pathlib.Path) -> None:
    font = _copy_liberation(tmp_path, "LiberationSerif-Regular.ttf")
    provider = FileSystemFontProvider(directories=[])
    provider.add_true_type_font(font)
    infos = list(provider.get_font_info())
    assert len(infos) == 1
    assert infos[0].get_post_script_name() == "LiberationSerif"


def test_add_true_type_font_swallows_parse_error(
    tmp_path: pathlib.Path,
) -> None:
    bogus = tmp_path / "bogus.ttf"
    bogus.write_bytes(b"\x00\x01garbage")
    provider = FileSystemFontProvider(directories=[])
    # Must not raise; nothing added.
    provider.add_true_type_font(bogus)
    assert list(provider.get_font_info()) == []


def test_add_true_type_collection_swallows_error(
    tmp_path: pathlib.Path,
) -> None:
    bogus = tmp_path / "bogus.ttc"
    bogus.write_bytes(b"\x00\x01\x02\x03")
    provider = FileSystemFontProvider(directories=[])
    # Must not raise.
    provider.add_true_type_collection(bogus)
    assert list(provider.get_font_info()) == []


def test_add_type1_font_swallows_error(tmp_path: pathlib.Path) -> None:
    bogus = tmp_path / "bogus.pfb"
    bogus.write_bytes(b"\x00\x01\x02\x03")
    provider = FileSystemFontProvider(directories=[])
    provider.add_type1_font(bogus)
    assert list(provider.get_font_info()) == []


def test_scan_fonts_public_spelling(tmp_path: pathlib.Path) -> None:
    font = _copy_liberation(tmp_path, "LiberationMono-Regular.ttf")
    provider = FileSystemFontProvider(directories=[])
    provider.scan_fonts([font])
    infos = list(provider.get_font_info())
    assert any(i.get_post_script_name() == "LiberationMono" for i in infos)


def test_scan_dispatches_by_suffix(tmp_path: pathlib.Path) -> None:
    """Each suffix triggers a different add_* path; corrupt files are skipped."""
    (tmp_path / "x.ttf").write_bytes(b"junk")
    (tmp_path / "y.otf").write_bytes(b"junk")
    (tmp_path / "z.ttc").write_bytes(b"junk")
    (tmp_path / "w.pfb").write_bytes(b"junk")
    provider = FileSystemFontProvider(directories=[tmp_path])
    # All four corrupt; provider still constructs cleanly with zero fonts.
    assert list(provider.get_font_info()) == []


# ---------- compute_hash ----------


def test_compute_hash_with_stream() -> None:
    stream = io.BytesIO(b"hello world")
    digest = FileSystemFontProvider.compute_hash(stream)
    # SHA-1 of "hello world"
    assert digest == "2aae6c35c94fcfb415dbe95f408b9ce91ee846ed"


def test_compute_hash_with_bytes() -> None:
    digest = FileSystemFontProvider.compute_hash(b"hello world")
    assert digest == "2aae6c35c94fcfb415dbe95f408b9ce91ee846ed"


def test_compute_hash_with_large_stream() -> None:
    """Forces multiple read() iterations to cover the loop branch."""
    data = b"x" * (65536 * 3 + 17)
    digest_a = FileSystemFontProvider.compute_hash(io.BytesIO(data))
    digest_b = FileSystemFontProvider.compute_hash(data)
    assert digest_a == digest_b


# ---------- create_fs_ignored ----------


def test_create_fs_ignored_with_real_file(tmp_path: pathlib.Path) -> None:
    font = _copy_liberation(tmp_path, "LiberationSans-Italic.ttf")
    provider = FileSystemFontProvider(directories=[])
    info = provider.create_fs_ignored(font, FontFormat.TTF, "IgnoredFont")
    assert info.get_post_script_name() == "IgnoredFont"
    assert info in list(provider.get_font_info())
    assert info.font_hash != ""
    assert info.last_modified > 0


def test_create_fs_ignored_missing_file(tmp_path: pathlib.Path) -> None:
    provider = FileSystemFontProvider(directories=[])
    missing = tmp_path / "absent.ttf"
    info = provider.create_fs_ignored(missing, FontFormat.TTF, "Missing")
    assert info.font_hash == ""
    assert info.last_modified == 0


# ---------- is_bad_path / get_disk_cache_file ----------


def test_is_bad_path_none_or_empty() -> None:
    assert FileSystemFontProvider.is_bad_path(None) is True
    assert FileSystemFontProvider.is_bad_path("") is True


def test_is_bad_path_nonexistent(tmp_path: pathlib.Path) -> None:
    assert (
        FileSystemFontProvider.is_bad_path(str(tmp_path / "no-such-dir"))
        is True
    )


def test_is_bad_path_writable(tmp_path: pathlib.Path) -> None:
    assert FileSystemFontProvider.is_bad_path(str(tmp_path)) is False


def test_get_disk_cache_file_uses_env(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PDFBOX_FONTCACHE", str(tmp_path))
    p = FileSystemFontProvider.get_disk_cache_file()
    assert p == tmp_path / ".pdfbox.cache"


def test_get_disk_cache_file_falls_back_to_home(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PDFBOX_FONTCACHE", raising=False)
    # Pretend HOME points at the writable tmp_path.
    monkeypatch.setattr(mod.Path, "home", staticmethod(lambda: tmp_path))
    p = FileSystemFontProvider.get_disk_cache_file()
    assert p == tmp_path / ".pdfbox.cache"


def test_get_disk_cache_file_falls_back_to_tempdir(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bad env + bad home -> tempfile.gettempdir() / .pdfbox.cache."""
    monkeypatch.setenv("PDFBOX_FONTCACHE", str(tmp_path / "missing"))
    # Home points at a non-existent dir, forcing the tempdir branch.
    monkeypatch.setattr(
        mod.Path, "home", staticmethod(lambda: tmp_path / "no-home")
    )
    p = FileSystemFontProvider.get_disk_cache_file()
    assert p.name == ".pdfbox.cache"


def test_get_disk_cache_file_ignores_bad_env(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A nonexistent PDFBOX_FONTCACHE falls through to home/tempdir."""
    monkeypatch.setenv("PDFBOX_FONTCACHE", str(tmp_path / "nope"))
    monkeypatch.setattr(mod.Path, "home", staticmethod(lambda: tmp_path))
    p = FileSystemFontProvider.get_disk_cache_file()
    assert p == tmp_path / ".pdfbox.cache"


# ---------- save_disk_cache / write_font_info / load_disk_cache ----------


def test_save_and_write_font_info_round_trip(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_liberation(tmp_path, "LiberationSans-Bold.ttf")
    monkeypatch.setenv("PDFBOX_FONTCACHE", str(tmp_path))
    provider = FileSystemFontProvider(directories=[tmp_path])
    assert len(list(provider.get_font_info())) >= 1
    provider.save_disk_cache()
    cache_file = tmp_path / ".pdfbox.cache"
    assert cache_file.is_file()
    text = cache_file.read_text(encoding="utf-8")
    assert "LiberationSans-Bold" in text or "LiberationSans" in text
    # Each record is pipe-separated.
    assert "|" in text


def test_save_disk_cache_handles_oserror(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """If opening the cache file fails, save_disk_cache swallows the error."""
    provider = FileSystemFontProvider(directories=[])
    # Force get_disk_cache_file to return a path that cannot be opened.
    bad = tmp_path / "no" / "such" / "dir" / ".pdfbox.cache"
    monkeypatch.setattr(
        FileSystemFontProvider, "get_disk_cache_file", staticmethod(lambda: bad)
    )
    # Should not raise.
    provider.save_disk_cache()
    assert not bad.exists()


def test_write_font_info_uses_writer_write(
    tmp_path: pathlib.Path,
) -> None:
    font = _copy_liberation(tmp_path, "LiberationSerif-Italic.ttf")
    provider = FileSystemFontProvider(directories=[])
    provider.add_true_type_font(font)
    info = provider.get_font_info()[0]
    buf = io.StringIO()
    provider.write_font_info(buf, info)
    line = buf.getvalue()
    assert line.endswith("\n")
    assert line.count("|") >= 10  # all delimiter fields present
    assert "LiberationSerif" in line


def test_write_font_info_handles_non_writer() -> None:
    """If the writer doesn't expose `.write`, no exception is raised."""
    provider = FileSystemFontProvider(directories=[])
    # Build a minimal FSFontInfo via a real scan.

    class Sink:
        pass

    # Need a font_info to pass in; use create_fs_ignored on a missing file.
    info = provider.create_fs_ignored(
        pathlib.Path("/nonexistent.ttf"), FontFormat.TTF, "Whatever"
    )
    # Should silently no-op.
    provider.write_font_info(Sink(), info)


def test_load_disk_cache_stub_returns_empty(tmp_path: pathlib.Path) -> None:
    provider = FileSystemFontProvider(directories=[])
    assert provider.load_disk_cache([tmp_path / "any.ttf"]) == []


# ---------- add_true_type_font_impl ----------


def test_add_true_type_font_impl_records_hash(
    tmp_path: pathlib.Path,
) -> None:
    from fontTools.ttLib import TTFont

    font = _copy_liberation(tmp_path, "LiberationMono-Bold.ttf")
    provider = FileSystemFontProvider(directories=[])
    ttf = TTFont(str(font), lazy=True)
    try:
        provider.add_true_type_font_impl(ttf, font, "deadbeef")
    finally:
        ttf.close()
    infos = list(provider.get_font_info())
    assert len(infos) == 1
    assert infos[0].font_hash == "deadbeef"


def test_add_true_type_font_impl_skips_missing_name_table(
    tmp_path: pathlib.Path,
) -> None:
    """A ttf-like object missing the 'name' table yields no FSFontInfo."""

    class FakeTTF:
        def __getitem__(self, key: str) -> Any:
            raise KeyError(key)

    provider = FileSystemFontProvider(directories=[])
    provider.add_true_type_font_impl(FakeTTF(), tmp_path / "x.ttf", "h")
    assert list(provider.get_font_info()) == []


# ---------- otf suffix handling for font_format ----------


def test_scan_real_ttf_via_otf_suffix(tmp_path: pathlib.Path) -> None:
    """Copying a TTF under an `.otf` suffix produces FontFormat.OTF info."""
    src = _LIBERATION_DIR / "LiberationSans-Regular.ttf"
    dst = tmp_path / "LiberationSans.otf"
    shutil.copy2(src, dst)
    provider = FileSystemFontProvider(directories=[tmp_path])
    infos = list(provider.get_font_info())
    assert len(infos) == 1
    assert infos[0].get_format() is FontFormat.OTF


# ---------- default-cache-only construction (no directories) ----------


def test_construct_without_directories_uses_platform_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Without `directories=`, the provider falls through to _default_font_dirs."""
    # Force the defaults to one empty tmp dir to avoid host fonts.
    monkeypatch.setattr(mod, "_default_font_dirs", lambda: [tmp_path])
    provider = FileSystemFontProvider()
    assert list(provider.get_font_info()) == []
