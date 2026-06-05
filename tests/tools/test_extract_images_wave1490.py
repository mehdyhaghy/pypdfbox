"""``ExtractImages.write2file`` branch round-out (wave 1490).

Wave 1489 ported the full ``write2file`` dispatch (passthrough / raw /
bitonal). Wave 1490 exercises the branches the wave-1489 oracle fixture did
not reach so the module hits 100% line coverage:

* the helper exception / ``None`` fall-throughs (``_num_data_elements``,
  ``_color_space_name``, ``_is_device_gray``),
* the ``-noColorConvert`` raw path's ``get_raw_image`` AttributeError →
  ``None`` arm and the > 3-channel CMYK → ``tiff`` arm,
* the ``jpg`` CMYK decode-and-re-encode arm (non-RGB/Gray, no direct flag),
* the ``jp2`` JPX *passthrough* arm and the ``jp2`` CMYK decode →
  ``jpeg2000`` arm,
* the ``tiff`` + DeviceGray bitonal (G4) conversion arm.

Branches whose *output* is upstream-observable (the JPEG passthrough, the
flate PNG, the masked PNG) are pinned against live PDFBox in
``tests/tools/oracle/test_extract_images_write2file_oracle.py``. The arms
here are either not reachable from the oracle's four-image fixture (JPX
passthrough, CMYK re-encode, G4 bitonal) or are pure helper plumbing, so
they are driven with real factory images plus small stubs that mirror the
exact ``PDImage`` surface ``write2file`` touches.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image

from pypdfbox.pdmodel.graphics.image.jpeg_factory import JPEGFactory
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.tools import extract_images


def _engine() -> extract_images.ImageGraphicsEngine:
    outer = extract_images.ExtractImages()
    return extract_images.ImageGraphicsEngine(page=None, outer=outer)


# --------------------------------------------------------------------------
# helper exception / None fall-throughs
# --------------------------------------------------------------------------
def test_num_data_elements_getbands_raises_falls_back_to_one() -> None:
    class _Bad:
        def getbands(self) -> tuple:
            raise TypeError("boom")

    assert extract_images._num_data_elements(_Bad()) == 1


def test_num_data_elements_no_getbands_returns_one() -> None:
    assert extract_images._num_data_elements(object()) == 1


def test_color_space_name_get_color_space_raises_returns_none() -> None:
    class _Img:
        def get_color_space(self) -> Any:
            raise NotImplementedError

    assert extract_images._color_space_name(_Img()) is None


def test_color_space_name_get_name_raises_returns_none() -> None:
    class _CS:
        def get_name(self) -> str:
            raise AttributeError

    class _Img:
        def get_color_space(self) -> Any:
            return _CS()

    assert extract_images._color_space_name(_Img()) is None


def test_is_device_gray_true_for_devicegray() -> None:
    class _CS:
        def get_name(self) -> str:
            return "DeviceGray"

    class _Img:
        def get_color_space(self) -> Any:
            return _CS()

    assert extract_images._is_device_gray(_Img()) is True


# --------------------------------------------------------------------------
# stub image scaffolding for the synthetic write2file arms
# --------------------------------------------------------------------------
class _StubImage:
    """Minimal ``PDImage`` surface used by ``write2file``. Not a
    ``PDImageXObject`` so ``has_masks`` short-circuits to False (the masked
    path is covered by the oracle)."""

    def __init__(
        self,
        *,
        suffix: str,
        color_space: str | None,
        image: Image.Image | None = None,
        raw_image: Any = "__unset__",
        passthrough: bytes = b"",
    ) -> None:
        self._suffix = suffix
        self._color_space = color_space
        self._image = image
        self._raw_image = raw_image
        self._passthrough = passthrough

    def get_suffix(self) -> str | None:
        return self._suffix

    def get_color_space(self) -> Any:
        if self._color_space is None:
            return None

        class _CS:
            def __init__(self, name: str) -> None:
                self._name = name

            def get_name(self) -> str:
                return self._name

        return _CS(self._color_space)

    def get_image(self) -> Image.Image | None:
        return self._image

    def get_raw_image(self) -> Any:
        if self._raw_image == "__unset__":
            raise AttributeError("no raw image")
        return self._raw_image

    def create_input_stream(self, _stop_filters: Any = None) -> io.BytesIO:
        return io.BytesIO(self._passthrough)


# --------------------------------------------------------------------------
# -noColorConvert: get_raw_image AttributeError → falls through to suffix path
# --------------------------------------------------------------------------
def test_no_color_convert_raw_image_unavailable_falls_through(tmp_path: Path) -> None:
    stub = _StubImage(
        suffix="png",
        color_space="DeviceRGB",
        image=Image.new("RGB", (4, 3), (10, 20, 30)),
        # raw_image unset → get_raw_image raises AttributeError → image is None
    )
    prefix = str(tmp_path / "img")
    _engine().write2file(stub, prefix, direct_jpeg=False, no_color_convert=True)
    # Falls through to the normal decode path → png from get_image().
    png = tmp_path / "img.png"
    assert png.exists() and png.stat().st_size > 0


# --------------------------------------------------------------------------
# -noColorConvert: > 3 channels (CMYK) → tiff
# --------------------------------------------------------------------------
def test_no_color_convert_cmyk_raw_writes_tiff(tmp_path: Path) -> None:
    cmyk = Image.new("CMYK", (5, 4), (1, 2, 3, 4))
    stub = _StubImage(suffix="png", color_space="DeviceCMYK", raw_image=cmyk)
    prefix = str(tmp_path / "img")
    _engine().write2file(stub, prefix, direct_jpeg=False, no_color_convert=True)
    tiff = tmp_path / "img.tiff"
    assert tiff.exists() and tiff.stat().st_size > 0
    with Image.open(tiff) as reopened:
        assert reopened.size == (5, 4)


def test_no_color_convert_three_channel_raw_writes_png(tmp_path: Path) -> None:
    rgb = Image.new("RGB", (6, 2), (9, 9, 9))
    stub = _StubImage(suffix="jpg", color_space="DeviceRGB", raw_image=rgb)
    prefix = str(tmp_path / "img")
    _engine().write2file(stub, prefix, direct_jpeg=False, no_color_convert=True)
    assert (tmp_path / "img.png").exists()
    assert not (tmp_path / "img.tiff").exists()


# --------------------------------------------------------------------------
# jpg CMYK: not RGB/Gray, no direct flag → decode + re-encode
# --------------------------------------------------------------------------
def test_jpg_cmyk_decode_and_reencode(tmp_path: Path) -> None:
    doc = PDDocument()
    try:
        cmyk = Image.new("CMYK", (12, 9), (10, 20, 30, 40))
        pd_image = JPEGFactory.create_from_image(doc, cmyk)
        assert pd_image.get_suffix() == "jpg"
        assert pd_image.get_color_space().get_name() == "DeviceCMYK"
        prefix = str(tmp_path / "img")
        _engine().write2file(pd_image, prefix, direct_jpeg=False, no_color_convert=False)
    finally:
        doc.close()
    jpg = tmp_path / "img.jpg"
    assert jpg.exists() and jpg.stat().st_size > 0
    with Image.open(jpg) as reopened:
        assert reopened.size == (12, 9)


def test_jpg_cmyk_decode_returns_none_writes_empty(tmp_path: Path) -> None:
    """CMYK jpg whose get_image() yields None → file opened, nothing written."""
    stub = _StubImage(suffix="jpg", color_space="DeviceCMYK", image=None)
    prefix = str(tmp_path / "img")
    _engine().write2file(stub, prefix, direct_jpeg=False, no_color_convert=False)
    jpg = tmp_path / "img.jpg"
    assert jpg.exists() and jpg.stat().st_size == 0


# --------------------------------------------------------------------------
# jp2 (JPX) passthrough: DeviceRGB → raw JPX bytes copied verbatim
# --------------------------------------------------------------------------
def test_jp2_rgb_passthrough_copies_raw_stream(tmp_path: Path) -> None:
    raw = b"\x00\x00\x00\x0cjP  \r\n\x87\nFAKE-JPX-PAYLOAD"
    stub = _StubImage(suffix="jpx", color_space="DeviceRGB", passthrough=raw)
    prefix = str(tmp_path / "img")
    _engine().write2file(stub, prefix, direct_jpeg=False, no_color_convert=False)
    jp2 = tmp_path / "img.jp2"
    assert jp2.exists()
    assert jp2.read_bytes() == raw


def test_jp2_direct_flag_forces_passthrough(tmp_path: Path) -> None:
    raw = b"JPX-RAW"
    stub = _StubImage(suffix="jpx", color_space="DeviceCMYK", passthrough=raw)
    prefix = str(tmp_path / "img")
    _engine().write2file(stub, prefix, direct_jpeg=True, no_color_convert=False)
    assert (tmp_path / "img.jp2").read_bytes() == raw


# --------------------------------------------------------------------------
# jp2 CMYK (not direct, not RGB/Gray) → decode + write jpeg2000
# --------------------------------------------------------------------------
def test_jp2_cmyk_decode_to_jpeg2000(tmp_path: Path) -> None:
    rgb = Image.new("RGB", (8, 6), (7, 8, 9))
    stub = _StubImage(suffix="jpx", color_space="DeviceCMYK", image=rgb)
    prefix = str(tmp_path / "img")
    _engine().write2file(stub, prefix, direct_jpeg=False, no_color_convert=False)
    jp2 = tmp_path / "img.jp2"
    assert jp2.exists() and jp2.stat().st_size > 0
    with Image.open(jp2) as reopened:
        assert reopened.size == (8, 6)


def test_jp2_cmyk_decode_returns_none_writes_empty(tmp_path: Path) -> None:
    stub = _StubImage(suffix="jpx", color_space="DeviceCMYK", image=None)
    prefix = str(tmp_path / "img")
    _engine().write2file(stub, prefix, direct_jpeg=False, no_color_convert=False)
    jp2 = tmp_path / "img.jp2"
    assert jp2.exists() and jp2.stat().st_size == 0


# --------------------------------------------------------------------------
# tiff + DeviceGray → bitonal (G4) conversion
# --------------------------------------------------------------------------
def test_tiff_devicegray_converts_to_bitonal(tmp_path: Path) -> None:
    gray = Image.new("L", (10, 8), 200)
    stub = _StubImage(suffix="tiff", color_space="DeviceGray", image=gray)
    prefix = str(tmp_path / "img")
    _engine().write2file(stub, prefix, direct_jpeg=False, no_color_convert=False)
    tiff = tmp_path / "img.tiff"
    assert tiff.exists() and tiff.stat().st_size > 0
    with Image.open(tiff) as reopened:
        # 1-bit bitonal image written.
        assert reopened.mode == "1"
        assert reopened.size == (10, 8)


def test_tiff_devicegray_decode_none_returns_early(tmp_path: Path) -> None:
    stub = _StubImage(suffix="tiff", color_space="DeviceGray", image=None)
    prefix = str(tmp_path / "img")
    _engine().write2file(stub, prefix, direct_jpeg=False, no_color_convert=False)
    # get_image() → None → early return after opening the file (empty).
    tiff = tmp_path / "img.tiff"
    assert tiff.exists() and tiff.stat().st_size == 0


# --------------------------------------------------------------------------
# tiff + non-DeviceGray → falls to the generic else decode arm
# --------------------------------------------------------------------------
def test_tiff_non_devicegray_uses_generic_decode(tmp_path: Path) -> None:
    rgb = Image.new("RGB", (7, 5), (1, 2, 3))
    stub = _StubImage(suffix="tiff", color_space="DeviceRGB", image=rgb)
    prefix = str(tmp_path / "img")
    _engine().write2file(stub, prefix, direct_jpeg=False, no_color_convert=False)
    tiff = tmp_path / "img.tiff"
    assert tiff.exists() and tiff.stat().st_size > 0
    with Image.open(tiff) as reopened:
        assert reopened.size == (7, 5)
