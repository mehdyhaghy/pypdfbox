from __future__ import annotations

from types import SimpleNamespace

import pytest

from pypdfbox.pdmodel.font import pd_type0_font as type0_module
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


class _Descendant:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def get_glyph_width(self, cid: int) -> float:
        self.calls.append(cid)
        return cid + 500.0

    def get_height(self, cid: int) -> float:
        self.calls.append(cid)
        return cid + 700.0

    def get_position_vector(self, cid: int) -> tuple[float, float]:
        self.calls.append(cid)
        return (cid + 10.0, cid + 20.0)

    def get_average_font_width(self) -> float:
        return 612.5

    def get_bounding_box(self) -> str:
        return "bbox"

    def has_glyph(self, cid: int) -> bool:
        self.calls.append(cid)
        return cid == 42

    def get_width_from_font(self, cid: int) -> float:
        self.calls.append(cid)
        return cid + 300.0

    def encode_glyph_id(self, glyph_id: int) -> bytes:
        return b"gid:" + bytes([glyph_id])


def test_metric_delegators_resolve_code_to_cid_wave458(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    descendant = _Descendant()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code + 1)

    assert font.has_glyph(41) is True
    assert font.get_width_from_font(4) == 305.0
    assert font.get_height(6) == 707.0
    assert font.get_average_font_width() == 612.5
    assert font.get_bounding_box() == "bbox"
    assert descendant.calls == [42, 5, 7]


def test_displacement_uses_horizontal_width_or_vertical_height_wave458(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    descendant = _Descendant()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code + 10)
    monkeypatch.setattr(font, "is_vertical", lambda: False)

    assert font.get_displacement(2) == (0.512, 0.0)

    monkeypatch.setattr(font, "is_vertical", lambda: True)

    assert font.get_displacement(2) == (0.0, 0.712)


def test_position_vector_scales_and_negates_descendant_vector_wave458(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    descendant = _Descendant()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: 30)

    assert font.get_position_vector(5) == (-0.04, -0.05)


def test_no_descendant_fallbacks_for_metric_helpers_wave458() -> None:
    font = PDType0Font()

    assert font.get_displacement(9) == (0.0, 0.0)
    assert font.get_position_vector(9) == (0.0, 0.0)
    assert font.has_glyph(9) is False
    assert font.get_width_from_font(9) == 0.0
    assert font.get_height(9) == 0.0
    assert font.get_average_font_width() == 0.0
    assert font.get_bounding_box() is None


def test_encode_glyph_id_delegates_or_falls_back_to_big_endian_wave458(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: _Descendant())

    assert font.encode_glyph_id(7) == b"gid:\x07"

    monkeypatch.setattr(font, "get_descendant_font", lambda: None)

    assert font.encode_glyph_id(0x12345) == b"\x23\x45"


def test_width_alias_font_matrix_and_string_width_wave458(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(font, "encode", lambda text: b"abcdef")
    reads = [(10, 2), (20, 1), (30, 3)]
    monkeypatch.setattr(font, "read_code", lambda _data, _offset: reads.pop(0))
    monkeypatch.setattr(font, "get_glyph_width", lambda code: float(code))

    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    assert font.get_width(12) == 12.0
    assert font.get_string_width("abc") == 60.0


def test_string_width_stops_when_read_code_consumes_no_bytes_wave458(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(font, "encode", lambda text: b"abc")
    monkeypatch.setattr(font, "read_code", lambda _data, _offset: (99, 0))
    monkeypatch.setattr(font, "get_glyph_width", lambda code: float(code))

    assert font.get_string_width("abc") == 0.0


def test_collect_subset_codepoints_merges_staged_text_and_used_chars_wave458() -> None:
    font = PDType0Font()
    font.add_to_subset(ord("A"))
    font.add_text_to_subset("BC")

    assert font._collect_subset_codepoints("CD", [ord("E")]) == {
        ord("A"),
        ord("B"),
        ord("C"),
        ord("D"),
        ord("E"),
    }
    assert font._collect_subset_codepoints([70, "71"], None) == {
        ord("A"),
        ord("B"),
        ord("C"),
        70,
        71,
    }


def test_subset_rejects_missing_or_unsupported_descendant_wave458(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()

    with pytest.raises(ValueError, match="no descendant CIDFont"):
        font.subset()

    monkeypatch.setattr(font, "get_descendant_font", lambda: object())

    with pytest.raises(ValueError, match="CIDFontType2"):
        font.subset()


def test_load_ttf_and_otf_read_source_and_delegate_wave458(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[bytes, str]] = []

    def fake_build(data: bytes, *, fallback_name: str) -> PDType0Font:
        calls.append((data, fallback_name))
        return PDType0Font()

    monkeypatch.setattr(type0_module, "_build_type0_from_ttf", fake_build)

    assert isinstance(PDType0Font.load_ttf(None, b"ttf"), PDType0Font)
    assert isinstance(PDType0Font.load_otf(None, bytearray(b"otf")), PDType0Font)

    assert calls == [(b"ttf", "EmbeddedTTF"), (b"otf", "EmbeddedOTF")]


def test_ps_name_from_ttf_falls_back_for_missing_or_bad_name_table_wave458() -> None:
    assert type0_module._ps_name_from_ttf(SimpleNamespace(), "Fallback") == "Fallback"

    bad_inner = {"name": SimpleNamespace(getName=lambda *_args: object())}
    ttf = SimpleNamespace(_tt=bad_inner)

    assert type0_module._ps_name_from_ttf(ttf, "Fallback") == "Fallback"
