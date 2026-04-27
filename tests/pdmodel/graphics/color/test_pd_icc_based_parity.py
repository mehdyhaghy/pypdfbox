from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased


_RANGE: COSName = COSName.get_pdf_name("Range")
_METADATA: COSName = COSName.get_pdf_name("Metadata")


# ---------- get_n / set_n round-trip ----------


def test_pd_icc_based_get_n_default_is_three() -> None:
    # Constructor stamps /N = 3 on the fresh stream.
    assert PDICCBased().get_n() == 3


def test_pd_icc_based_get_n_round_trip() -> None:
    cs = PDICCBased()
    cs.set_n(4)
    assert cs.get_n() == 4
    cs.set_n(1)
    assert cs.get_n() == 1


# ---------- get_pd_stream ----------


def test_pd_icc_based_get_pd_stream_wraps_underlying_stream() -> None:
    cs = PDICCBased()
    pd_stream = cs.get_pd_stream()
    assert isinstance(pd_stream, PDStream)
    # Wrapped stream identity must match the underlying COSStream.
    assert pd_stream.get_cos_object() is cs.get_pdstream()


# ---------- get_range_for_component ----------


def test_pd_icc_based_get_range_for_component_default_is_zero_one() -> None:
    # No /Range entry → default per PDF 32000-1 §8.6.5.5 is (0.0, 1.0).
    cs = PDICCBased()
    assert cs.get_range_for_component(0) == (0.0, 1.0)
    assert cs.get_range_for_component(2) == (0.0, 1.0)


def test_pd_icc_based_get_range_for_component_returns_pair_when_present() -> None:
    cs = PDICCBased()
    cs.set_n(3)
    rng = COSArray()
    for v in (-2.0, 2.0, -3.0, 3.0, -4.0, 4.0):
        rng.add(COSFloat(v))
    cs.set_range(rng)
    assert cs.get_range_for_component(0) == (-2.0, 2.0)
    assert cs.get_range_for_component(1) == (-3.0, 3.0)
    assert cs.get_range_for_component(2) == (-4.0, 4.0)


# ---------- set_range_for_component round-trip ----------


def test_pd_icc_based_set_range_for_component_round_trip() -> None:
    cs = PDICCBased()
    cs.set_n(3)
    cs.set_range_for_component(0, -1.5, 1.5)
    cs.set_range_for_component(1, -2.5, 2.5)
    cs.set_range_for_component(2, -3.5, 3.5)
    assert cs.get_range_for_component(0) == (-1.5, 1.5)
    assert cs.get_range_for_component(1) == (-2.5, 2.5)
    assert cs.get_range_for_component(2) == (-3.5, 3.5)


def test_pd_icc_based_set_range_for_component_pads_intermediate_slots() -> None:
    # Setting component 2 first must leave components 0 and 1 at the
    # default (0.0, 1.0) pair, not at junk.
    cs = PDICCBased()
    cs.set_n(3)
    cs.set_range_for_component(2, -5.0, 5.0)
    assert cs.get_range_for_component(0) == (0.0, 1.0)
    assert cs.get_range_for_component(1) == (0.0, 1.0)
    assert cs.get_range_for_component(2) == (-5.0, 5.0)


# ---------- get_iccprofile_bytes ----------


def test_pd_icc_based_get_iccprofile_bytes_returns_decoded_body() -> None:
    cs = PDICCBased()
    payload = b"\x00\x01\x02fake-icc-profile-bytes\xff"
    underlying = cs.get_pdstream()
    assert isinstance(underlying, COSStream)
    underlying.set_raw_data(payload)
    assert cs.get_iccprofile_bytes() == payload


def test_pd_icc_based_get_iccprofile_bytes_empty_when_no_body() -> None:
    # Fresh PDICCBased has no ICC body yet.
    assert PDICCBased().get_iccprofile_bytes() == b""


# ---------- get_metadata / set_metadata ----------


def test_pd_icc_based_get_metadata_returns_pdmetadata_when_present() -> None:
    cs = PDICCBased()
    underlying = cs.get_pdstream()
    assert isinstance(underlying, COSStream)
    meta_stream = COSStream()
    meta_stream.set_raw_data(b"<x:xmpmeta/>")
    underlying.set_item(_METADATA, meta_stream)
    metadata = cs.get_metadata()
    assert isinstance(metadata, PDMetadata)
    assert metadata.get_cos_object() is meta_stream


def test_pd_icc_based_get_metadata_none_when_absent() -> None:
    assert PDICCBased().get_metadata() is None


def test_pd_icc_based_set_metadata_round_trip() -> None:
    cs = PDICCBased()
    meta = PDMetadata(b"<x:xmpmeta/>")
    cs.set_metadata(meta)
    fetched = cs.get_metadata()
    assert isinstance(fetched, PDMetadata)
    assert fetched.get_cos_object() is meta.get_cos_object()


# ---------- get_alternate_color_space alias ----------


def test_pd_icc_based_alternate_color_space_alias_round_trip() -> None:
    from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK

    cs = PDICCBased()
    cs.set_alternate_color_space(PDDeviceCMYK.INSTANCE)
    fetched = cs.get_alternate_color_space()
    assert fetched is not None
    assert fetched.get_name() == "DeviceCMYK"
