from __future__ import annotations

import pytest

from tests.fontbox.ttf import test_true_type_font as true_type_mod
from tests.fontbox.ttf import test_ttf_data_stream as data_stream_mod


def test_wave865_intermittent_eof_stream_reads_and_reports_eof() -> None:
    stream = data_stream_mod._IntermittentEOFStream([0x41])  # noqa: SLF001

    assert stream.read() == 0x41
    assert stream.read() == -1


def test_wave865_intermittent_eof_stream_abstract_slots_raise() -> None:
    stream = data_stream_mod._IntermittentEOFStream([])  # noqa: SLF001

    with pytest.raises(NotImplementedError):
        stream.read_long()

    with pytest.raises(NotImplementedError):
        stream.read_into(bytearray(1), 0, 1)


def test_wave865_intermittent_eof_stream_position_and_original_data() -> None:
    stream = data_stream_mod._IntermittentEOFStream([1, 2, 3])  # noqa: SLF001

    stream.seek(2)

    assert stream.get_current_position() == 2
    assert stream.get_original_data() == b""
    assert stream.get_original_data_size() == 0
    assert stream.close() is None


def test_wave865_fake_fonttools_ttf_rejects_non_cmap_tag() -> None:
    fake = true_type_mod._FakeFontToolsTTFont(  # noqa: SLF001
        true_type_mod._FakeFontToolsCmapTable([]),  # noqa: SLF001
        [".notdef"],
    )

    with pytest.raises(KeyError, match="name"):
        fake["name"]
