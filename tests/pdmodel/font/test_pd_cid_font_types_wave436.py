from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor


class _FakeCFF:
    units_per_em = 2000
    font_matrix = [0.002, 0, 0, 0.002, 0, 0]

    def __init__(self) -> None:
        self._paths = {
            "cid00001": [
                ("moveto", 0, -100),
                ("curveto", 10, 20, 30, 40, 50, 900),
                ("closepath",),
            ],
            "cid00002": [],
        }

    def has_glyph(self, name: str) -> bool:
        return name in {".notdef", "cid00001", "cid00002"}

    def get_width(self, name: str) -> float:
        return {".notdef": 0.0, "cid00001": 1000.0, "cid00002": 0.0}[name]

    def get_default_width_x(self) -> float:
        return 1200.0

    def get_path(self, name: str) -> list[tuple[Any, ...]]:
        return self._paths.get(name, [])

    def get_property(self, name: str) -> object:
        if name == "FontBBox":
            return [-10, -20, 1000, 900]
        raise KeyError(name)

    def get_type2_char_string(self, gid: int) -> tuple[str, int]:
        return ("charstring", gid)


class _FakeGlyph:
    def __init__(self, commands: list[tuple[str, tuple[float, float] | None]]) -> None:
        self._commands = commands

    def draw(self, pen: Any) -> None:
        for op, point in self._commands:
            if op == "moveTo":
                pen.moveTo(point)
            elif op == "lineTo":
                pen.lineTo(point)
            elif op == "closePath":
                pen.closePath()
            elif op == "raise":
                raise ValueError("cannot draw")


class _FakeTTInner:
    def __init__(
        self,
        glyph_order: list[str],
        glyphs: dict[str, Any],
        *,
        include_glyf: bool = True,
        include_head: bool = True,
    ) -> None:
        self._glyph_order = glyph_order
        self._glyphs = glyphs
        self._tables: dict[str, Any] = {}
        if include_glyf:
            self._tables["glyf"] = glyphs
        if include_head:
            self._tables["head"] = SimpleNamespace(
                xMin=-5,
                yMin=-10,
                xMax=900,
                yMax=700,
            )

    def __contains__(self, key: str) -> bool:
        return key in self._tables

    def __getitem__(self, key: str) -> Any:
        return self._tables[key]

    def getGlyphOrder(self) -> list[str]:  # noqa: N802
        return self._glyph_order

    def getGlyphName(self, gid: int) -> str:  # noqa: N802
        return self._glyph_order[gid]

    def getGlyphSet(self) -> dict[str, _FakeGlyph]:  # noqa: N802
        return self._glyphs


class _FakeTTF:
    def __init__(
        self,
        *,
        units_per_em: int = 2000,
        advance_widths: list[int] | None = None,
        inner: _FakeTTInner | None = None,
        post_script: bool = False,
    ) -> None:
        self._units_per_em = units_per_em
        self._advance_widths = advance_widths if advance_widths is not None else [0, 1000]
        self._tt = inner if inner is not None else _FakeTTInner([".notdef", "A"], {})
        self._post_script = post_script

    def get_units_per_em(self) -> int:
        return self._units_per_em

    def get_advance_width(self, gid: int) -> int:
        return self._advance_widths[gid]

    @property
    def advance_widths(self) -> list[int]:
        return self._advance_widths

    def is_post_script(self) -> bool:
        return self._post_script


def _type0_with_program(program: _FakeCFF | None) -> PDCIDFontType0:
    font = PDCIDFontType0()
    font.get_cff_font = lambda: program  # type: ignore[method-assign]
    return font


def _type2_with_program(program: _FakeTTF | None) -> PDCIDFontType2:
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: program  # type: ignore[method-assign]
    return font


def test_type0_glyph_width_prefers_w_then_cff_then_default_width() -> None:
    font = _type0_with_program(_FakeCFF())
    font.set_dw(777)
    font.set_w(COSArray([COSInteger.get(1), COSArray([COSInteger.get(333)])]))

    assert font.get_glyph_width(1) == 333.0
    assert font.get_glyph_width(2) == 777.0
    assert font.get_width_from_font(1) == 500.0
    assert font.get_width_from_font(2) == 0.0


def test_type0_program_metrics_matrix_bbox_paths_and_charstrings() -> None:
    font = _type0_with_program(_FakeCFF())

    assert font.get_average_font_width() == 600.0
    assert font.get_font_matrix() == (0.002, 0.0, 0.0, 0.002, 0.0, 0.0)
    bbox = font.get_bounding_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == -10.0
    assert bbox.get_upper_right_y() == 900.0
    assert font.get_height(1) == 1000.0
    assert font.get_height(1) == 1000.0
    assert font.get_glyph_path(1) == font.get_normalized_path(1)
    assert font.get_type2_char_string(4) == ("charstring", 4)


def test_type0_handles_malformed_program_values_and_unsupported_encoding() -> None:
    program = _FakeCFF()
    program.units_per_em = 0
    program.font_matrix = [1, 2, 3]
    program.get_property = lambda name: ["bad"]  # type: ignore[method-assign]
    font = _type0_with_program(program)
    font.set_dw(444)

    assert font.get_width_from_font(1) == 0.0
    assert font.get_average_font_width() == 444.0
    assert font.get_font_matrix() == (0.001, 0.0, 0.0, 0.001, 0.0, 0.0)
    assert font.get_bounding_box() is None
    assert font.get_height(2) == 0.0
    assert font.get_glyph_path(99) == []
    with pytest.raises(NotImplementedError):
        font.encode_glyph_id(1)


def test_type0_strict_cff_embedding_predicate_accepts_only_expected_subtypes() -> None:
    font = PDCIDFontType0()
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "OpenType")  # type: ignore[attr-defined]
    descriptor.set_font_file3(stream)
    font.set_font_descriptor(descriptor)
    assert font.is_cff_embedded() is True

    stream.set_name(COSName.SUBTYPE, "Type1C")  # type: ignore[attr-defined]
    assert font.is_cff_embedded() is False


def test_type2_cid_to_gid_negative_raw_bytes_and_identity_name() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    stream.set_data(b"\x00\x05\x00\x09")
    font.set_cid_to_gid_map(stream)

    assert font.cid_to_gid(-1) == 0
    assert font.get_cid_to_gid_map_bytes() == b"\x00\x05\x00\x09"
    assert font.is_identity_cid_to_gid_map() is False
    assert font.code_to_cid(12) == 12
    assert font.code_to_gid(1) == 9

    font.set_cid_to_gid_map("Identity")
    assert font.get_cid_to_gid_map_bytes() is None
    assert font.is_identity_cid_to_gid_map() is True


def test_type2_no_program_parse_is_cached_as_not_damaged() -> None:
    font = PDCIDFontType2()

    assert font.get_true_type_font() is None
    assert font.get_true_type_font() is None
    assert font._ttf is False  # noqa: SLF001
    assert font.is_embedded() is False
    assert font.is_damaged() is False


def test_type2_font_metrics_fallbacks_and_exception_paths() -> None:
    font = _type2_with_program(_FakeTTF(units_per_em=0, advance_widths=[0, 0]))
    font.set_dw(321)

    assert font.get_width_from_font(1) == 0.0
    assert font.get_average_font_width() == 321.0
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

    no_glyf = _type2_with_program(
        _FakeTTF(inner=_FakeTTInner([".notdef", "A"], {}, include_glyf=False))
    )
    assert no_glyf.get_height(1) == 0.0

    missing_glyph = _type2_with_program(
        _FakeTTF(inner=_FakeTTInner([".notdef", "A"], {}, include_glyf=True))
    )
    assert missing_glyph.get_height(1) == 0.0


def test_type2_paths_are_drawn_and_normalized_by_units_per_em() -> None:
    glyph = _FakeGlyph(
        [
            ("moveTo", (0, 0)),
            ("lineTo", (1000, 500)),
            ("closePath", None),
        ]
    )
    inner = _FakeTTInner([".notdef", "A"], {"A": glyph})
    font = _type2_with_program(_FakeTTF(units_per_em=2000, inner=inner))

    assert font.get_glyph_path(1) == [
        ("moveto", 0.0, 0.0),
        ("lineto", 1000.0, 500.0),
        ("closepath",),
    ]
    assert font.get_normalized_path(1) == [
        ("moveto", 0.0, 0.0),
        ("lineto", 500.0, 250.0),
        ("closepath",),
    ]


def test_type2_path_and_postscript_predicate_failure_paths() -> None:
    raising = _FakeGlyph([("raise", None)])
    inner = _FakeTTInner([".notdef", "A"], {"A": raising})
    font = _type2_with_program(_FakeTTF(inner=inner, post_script=True))
    assert font.get_glyph_path(1) == []
    assert font.get_normalized_path(1) == []
    assert font.is_open_type_post_script() is True

    class _BadPredicateTTF(_FakeTTF):
        def is_post_script(self) -> bool:
            raise ValueError("bad predicate")

    assert _type2_with_program(_BadPredicateTTF()).is_open_type_post_script() is False
