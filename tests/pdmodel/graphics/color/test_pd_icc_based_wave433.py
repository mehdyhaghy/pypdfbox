from __future__ import annotations

import sys

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream, COSString
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased


def _malformed_icc_based() -> PDICCBased:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(COSName.get_pdf_name("NotAStream"))
    return PDICCBased(arr)


def test_malformed_array_without_stream_is_lenient() -> None:
    cs = _malformed_icc_based()

    assert cs.get_pdstream() is None
    assert cs.get_pd_stream() is None
    assert cs.get_n() == 0
    assert cs.get_number_of_components() == 0
    assert cs.get_initial_color().get_components() == []
    assert cs.get_default_decode(8) == []
    assert cs.get_iccprofile_bytes() == b""


def test_malformed_array_mutators_are_noops() -> None:
    cs = _malformed_icc_based()
    metadata = PDMetadata(b"<x:xmpmeta/>")

    cs.set_n(4)
    cs.set_alternate(PDDeviceRGB.INSTANCE)
    cs.set_range(COSArray())
    cs.set_range_for_component(0, -1.0, 1.0)
    cs.set_metadata(metadata)
    cs.clear_alternate()
    cs.clear_range()
    cs.clear_metadata()

    assert cs.get_n() == 0
    assert cs.get_alternate() is None
    assert cs.get_range() is None
    assert cs.get_metadata() is None


def test_optional_entries_ignore_wrong_cos_shape() -> None:
    cs = PDICCBased()
    stream = cs.get_pdstream()
    assert stream is not None

    stream.set_item("Alternate", COSString("DeviceRGB"))
    stream.set_item("Range", COSName.get_pdf_name("NotAnArray"))
    stream.set_item("Metadata", COSName.get_pdf_name("NotAStream"))

    assert cs.get_alternate() is None
    assert cs.has_alternate() is False
    assert cs.get_range() is None
    assert cs.has_range() is False
    assert cs.get_metadata() is None
    assert cs.has_metadata() is False


def test_set_alternate_rejects_color_space_without_cos_form() -> None:
    class NoCosColorSpace:
        def get_cos_object(self) -> None:
            return None

    cs = PDICCBased()
    with pytest.raises(TypeError, match="requires a color space with a COS form"):
        cs.set_alternate(NoCosColorSpace())  # type: ignore[arg-type]


def test_set_metadata_accepts_raw_stream_and_none_clears() -> None:
    cs = PDICCBased()
    raw = COSStream()

    cs.set_metadata(raw)
    metadata = cs.get_metadata()
    assert isinstance(metadata, PDMetadata)
    assert metadata.get_cos_object() is raw
    assert cs.has_metadata() is True

    cs.set_metadata(None)
    assert cs.get_metadata() is None
    assert cs.has_metadata() is False


def test_try_icc_to_rgb_returns_none_for_unsupported_n_before_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cs = PDICCBased()
    monkeypatch.setattr(cs, "get_iccprofile_bytes", lambda: b"not parsed")
    monkeypatch.setattr(cs, "get_n", lambda: 5)

    assert cs._try_icc_to_rgb([0.1, 0.2, 0.3, 0.4, 0.5]) is None


def test_try_icc_to_rgb_returns_none_when_components_are_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cs = PDICCBased()
    monkeypatch.setattr(cs, "get_iccprofile_bytes", lambda: b"not parsed")
    monkeypatch.setattr(cs, "get_n", lambda: 3)

    assert cs._try_icc_to_rgb([0.1, 0.2]) is None


def test_try_icc_to_rgb_returns_none_when_pillow_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cs = PDICCBased()
    monkeypatch.setitem(sys.modules, "PIL", None)

    assert cs._try_icc_to_rgb([0.0, 0.0, 0.0]) is None
