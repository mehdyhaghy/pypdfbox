from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger
from pypdfbox.pdmodel.interactive.digitalsignature.cos_filter_input_stream import (
    COSFilterInputStream,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_prop_build_data_dict import (
    PDPropBuildDataDict,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value_certificate import (
    PDSeedValueCertificate,
)


class _ShortNonSeekable:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._data) - self._offset
        start = self._offset
        self._offset = min(len(self._data), self._offset + size)
        return self._data[start : self._offset]

    def close(self) -> None:
        self._offset = len(self._data)


def test_wave828_non_seekable_skip_breaks_when_source_ends_before_range() -> None:
    stream = COSFilterInputStream(_ShortNonSeekable(b"abc"), [10, 2])

    assert stream.read_all() == b""


def test_wave828_prop_build_summary_includes_date_only() -> None:
    data = PDPropBuildDataDict()

    data.set_date("2026-05-09")

    assert str(data) == "PDPropBuildDataDict(date=2026-05-09)"


def test_wave828_certificate_subject_dn_non_string_value_becomes_empty() -> None:
    cert = PDSeedValueCertificate()
    subject_dn = COSDictionary()
    subject_dn.set_item("CN", COSInteger.get(7))
    subject_dns = COSArray([subject_dn])
    cert.get_cos_object().set_item("SubjectDN", subject_dns)

    assert cert.get_subject_dn() == [{"CN": ""}]
