from __future__ import annotations

import argparse
import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel.encryption import PDInvalidPasswordException
from pypdfbox.tools import imagetopdf, info


class _DocWithCatalog:
    def __init__(self, catalog: object) -> None:
        self._catalog = catalog

    def get_document_catalog(self) -> object:
        return self._catalog


class _Catalog:
    def __init__(self, metadata: object) -> None:
        self._metadata = metadata

    def get_metadata(self) -> object:
        return self._metadata


class _RaisingCatalog:
    def get_metadata(self) -> object:
        raise RuntimeError("bad catalog")


class _StringMetadata:
    def __init__(self, value: object) -> None:
        self._value = value

    def get_metadata_as_string(self) -> object:
        return self._value


class _BrokenFallbackMetadata:
    def get_metadata_as_string(self) -> str:
        raise RuntimeError("no decoded string")

    def create_input_stream(self) -> io.BytesIO:
        raise OSError("no raw stream")


def _color_space_name(path: Path) -> str:
    image = imagetopdf.create_image_xobject(path)
    color_space = image.get_color_space_cos_object()
    assert color_space is not None
    return color_space.get_name()  # type: ignore[attr-defined]


def test_info_read_xmp_defensive_metadata_shapes() -> None:
    assert info._read_xmp(_DocWithCatalog(_RaisingCatalog())) is None  # noqa: SLF001
    assert info._read_xmp(_DocWithCatalog(_Catalog(None))) is None  # noqa: SLF001
    assert info._read_xmp(_DocWithCatalog(_Catalog(_StringMetadata(None)))) is None  # noqa: SLF001
    assert info._read_xmp(_DocWithCatalog(_Catalog(_StringMetadata(42)))) == "42"  # noqa: SLF001
    assert info._read_xmp(_DocWithCatalog(_Catalog(_BrokenFallbackMetadata()))) is None  # noqa: SLF001


def test_info_txt_prints_non_numeric_versions(capsys: pytest.CaptureFixture[str]) -> None:
    info._print_txt(  # noqa: SLF001
        {
            "file": "odd.pdf",
            "header_version": "not-a-float",
            "catalog_version": None,
            "effective_version": "effective",
            "pages": 0,
            "encrypted": False,
            "info": {},
            "custom": {},
        },
        None,
    )

    out = capsys.readouterr().out
    assert "PDF version (header): not-a-float" in out
    assert "Effective version: effective" in out


def test_info_run_returns_one_for_invalid_password(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "locked.pdf"
    src.write_bytes(b"%PDF-1.7\n")

    def raise_bad_password(path: Path, *, password: str = "") -> object:
        assert path == src
        assert password == "secret"
        raise PDInvalidPasswordException("bad password")

    monkeypatch.setattr(info.PDDocument, "load", raise_bad_password)
    args = argparse.Namespace(
        input=str(src),
        password="secret",
        metadata=False,
        output="txt",
    )

    assert info.run(args) == 1
    assert "bad password" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("filename", "mode", "fmt", "want_color_space"),
    [
        ("cmyk.jpg", "CMYK", "JPEG", "DeviceCMYK"),
        ("palette.png", "P", "PNG", "DeviceRGB"),
        ("gray.png", "L", "PNG", "DeviceGray"),
        ("bitmap.png", "1", "PNG", "DeviceGray"),
        ("cmyk.tif", "CMYK", "TIFF", "DeviceCMYK"),
    ],
)
def test_imagetopdf_embeds_less_common_pillow_modes(
    tmp_path: Path,
    filename: str,
    mode: str,
    fmt: str,
    want_color_space: str,
) -> None:
    path = tmp_path / filename
    image = Image.new(mode, (3, 2))
    if mode == "P":
        image.putpalette([0, 0, 0, 255, 0, 0] + [0, 0, 0] * 254)
    image.save(path, format=fmt)

    assert _color_space_name(path) == want_color_space


def test_imagetopdf_parse_orientation_reports_argparse_error() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="orientation must be one of"):
        imagetopdf._parse_orientation("sideways")  # noqa: SLF001
