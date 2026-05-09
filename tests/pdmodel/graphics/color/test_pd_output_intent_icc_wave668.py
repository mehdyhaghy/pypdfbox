from __future__ import annotations

import io

import pytest
from PIL import Image, ImageCms

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.color import PDOutputIntent
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.pd_document import PDDocument


def _icc_with_signature(colorspace: bytes = b"RGB ") -> bytes:
    return b"\x00" * 16 + colorspace + b"\x00" * 16 + b"acsp" + b"\x00" * 8


def test_wave668_dictionary_profile_requires_document() -> None:
    with pytest.raises(TypeError, match="requires document"):
        PDOutputIntent(COSDictionary(), _icc_with_signature())


def test_wave668_dictionary_profile_accepts_file_like_with_document() -> None:
    doc = PDDocument()
    raw = COSDictionary()
    intent = PDOutputIntent(
        raw,
        io.BytesIO(_icc_with_signature(b"CMYK")),
        document=doc,
    )

    assert intent.get_cos_object() is raw
    assert intent.get_n_for_profile() == 4


def test_wave668_set_dest_output_profile_accepts_pdstream() -> None:
    intent = PDOutputIntent()
    stream = PDStream(COSStream())

    intent.set_dest_output_profile(stream)

    assert intent.get_dest_output_profile_cos() is stream.get_cos_object()


def test_wave668_set_dest_output_profile_rejects_invalid_type() -> None:
    intent = PDOutputIntent()

    with pytest.raises(TypeError, match="expected PDStream, COSStream, or None"):
        intent.set_dest_output_profile(COSName.get_pdf_name("Bad"))  # type: ignore[arg-type]


def test_wave668_dest_profile_getters_reject_wrong_cos_shapes() -> None:
    intent = PDOutputIntent()
    intent.get_cos_object().set_item(
        COSName.get_pdf_name("DestOutputProfile"), COSName.get_pdf_name("Bad")
    )

    with pytest.raises(TypeError, match="DestOutputProfile type"):
        intent.get_dest_output_profile()
    with pytest.raises(TypeError, match="DestOutputProfile type"):
        intent.get_dest_output_profile_cos()

    intent.get_cos_object().set_item(
        COSName.get_pdf_name("DestOutputProfileRef"), COSName.get_pdf_name("Bad")
    )
    with pytest.raises(TypeError, match="DestOutputProfileRef type"):
        intent.get_dest_output_profile_ref()


def test_wave668_get_n_for_profile_returns_none_when_decode_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intent = PDOutputIntent()
    intent.set_dest_output_profile(COSStream())

    def fail_to_byte_array(self: PDStream) -> bytes:
        raise ValueError("bad stream")

    monkeypatch.setattr(PDStream, "to_byte_array", fail_to_byte_array)

    assert intent.get_n_for_profile() is None


def test_wave668_set_data_reuses_existing_profile_stream() -> None:
    intent = PDOutputIntent()
    stream = COSStream()
    intent.set_dest_output_profile(stream)

    intent.set_data(_icc_with_signature(), num_components=3)

    assert intent.get_dest_output_profile_cos() is stream
    assert stream.get_int(COSName.get_pdf_name("N")) == 3


def test_wave668_icc_range_component_can_be_overwritten() -> None:
    cs = PDICCBased()
    cs.set_n(1)
    cs.set_range_for_component(0, -0.25, 1.25)
    cs.set_range_for_component(0, 0.1, 0.9)

    assert cs.get_range_for_component(0) == (
        pytest.approx(0.1),
        pytest.approx(0.9),
    )


class _FakeProfile:
    pass


class _FakeTransform:
    pass


class _FakeImage:
    def __init__(self, pixel):
        self._pixel = pixel

    def getpixel(self, xy):
        assert xy == (0, 0)
        return self._pixel


def _patch_icc_success(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pixel=(64, 128, 255),
    applied_none: bool = False,
) -> list[tuple[str, object]]:
    samples: list[tuple[str, object]] = []
    monkeypatch.setattr(ImageCms, "ImageCmsProfile", lambda src: _FakeProfile())
    monkeypatch.setattr(ImageCms, "createProfile", lambda name: _FakeProfile())
    monkeypatch.setattr(
        ImageCms,
        "buildTransform",
        lambda in_profile, out_profile, in_mode, out_mode: _FakeTransform(),
    )

    def fake_new(mode, size, sample):
        assert size == (1, 1)
        samples.append((mode, sample))
        return _FakeImage(sample)

    def fake_apply_transform(src, transform):
        assert isinstance(transform, _FakeTransform)
        if applied_none:
            return None
        return _FakeImage(pixel)

    monkeypatch.setattr(Image, "new", fake_new)
    monkeypatch.setattr(ImageCms, "applyTransform", fake_apply_transform)
    return samples


@pytest.mark.parametrize(
    ("n", "components", "expected_sample"),
    [
        (1, [-1.0], 0),
        (4, [0.0, 0.5, 1.0, 2.0], (0, 128, 255, 255)),
    ],
)
def test_wave668_try_icc_to_rgb_builds_samples_for_gray_and_cmyk(
    monkeypatch: pytest.MonkeyPatch,
    n: int,
    components: list[float],
    expected_sample: object,
) -> None:
    cs = PDICCBased()
    monkeypatch.setattr(cs, "get_iccprofile_bytes", lambda: b"profile")
    monkeypatch.setattr(cs, "get_n", lambda: n)
    samples = _patch_icc_success(monkeypatch)

    assert cs._try_icc_to_rgb(components) == (
        pytest.approx(64 / 255),
        pytest.approx(128 / 255),
        pytest.approx(1.0),
    )
    assert samples == [("L" if n == 1 else "CMYK", expected_sample)]


def test_wave668_try_icc_to_rgb_returns_none_when_srgb_profile_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cs = PDICCBased()
    monkeypatch.setattr(cs, "get_iccprofile_bytes", lambda: b"profile")
    monkeypatch.setattr(cs, "get_n", lambda: 3)
    monkeypatch.setattr(ImageCms, "ImageCmsProfile", lambda src: _FakeProfile())
    monkeypatch.setattr(
        ImageCms,
        "createProfile",
        lambda name: (_ for _ in ()).throw(ImageCms.PyCMSError("no srgb")),
    )

    assert cs._try_icc_to_rgb([0.1, 0.2, 0.3]) is None


def test_wave668_try_icc_to_rgb_returns_none_when_transform_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cs = PDICCBased()
    monkeypatch.setattr(cs, "get_iccprofile_bytes", lambda: b"profile")
    monkeypatch.setattr(cs, "get_n", lambda: 3)
    _patch_icc_success(monkeypatch, applied_none=True)

    assert cs._try_icc_to_rgb([0.1, 0.2, 0.3]) is None


def test_wave668_try_icc_to_rgb_returns_none_when_transform_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cs = PDICCBased()
    monkeypatch.setattr(cs, "get_iccprofile_bytes", lambda: b"profile")
    monkeypatch.setattr(cs, "get_n", lambda: 3)
    monkeypatch.setattr(ImageCms, "ImageCmsProfile", lambda src: _FakeProfile())
    monkeypatch.setattr(ImageCms, "createProfile", lambda name: _FakeProfile())
    monkeypatch.setattr(
        ImageCms,
        "buildTransform",
        lambda *args: (_ for _ in ()).throw(ImageCms.PyCMSError("bad transform")),
    )

    assert cs._try_icc_to_rgb([0.1, 0.2, 0.3]) is None


def test_wave668_try_icc_to_rgb_returns_none_for_non_rgb_pixel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cs = PDICCBased()
    monkeypatch.setattr(cs, "get_iccprofile_bytes", lambda: b"profile")
    monkeypatch.setattr(cs, "get_n", lambda: 3)
    _patch_icc_success(monkeypatch, pixel=128)

    assert cs._try_icc_to_rgb([0.1, 0.2, 0.3]) is None
