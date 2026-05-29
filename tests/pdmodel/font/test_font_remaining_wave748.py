from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.pdmodel.font import pd_cid_font_type0 as cid0_module
from pypdfbox.pdmodel.font import pd_type1_font as type1_module
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type3_char_proc import (
    PDType3CharProc,
    _is_numeric_token,
)
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font


class _FakeParsedType1:
    @classmethod
    def from_bytes(cls, data: bytes) -> _FakeParsedType1:
        assert data == b"type1"
        return cls()


class _ZeroWidthType1:
    units_per_em = 1000

    def has_glyph(self, name: str) -> bool:
        return name == "A"

    def get_width(self, _name: str) -> float:
        return 0.0


class _CloseOnlyType1:
    def get_path(self, _name: str) -> list[tuple[str]]:
        return [("closepath",)]


class _FakeCIDCFF(CFFCIDFont):
    def __init__(self, charset: list[str]) -> None:
        super().__init__()
        self._charset = charset
        self.seen_gids: list[int] = []

    def get_charset(self) -> list[str]:
        return self._charset

    def get_type2_char_string(self, cid: int) -> tuple[str, int]:
        # Mirror the real ``CFFCIDFont.getType2CharString(int cid)``: the
        # parameter is a *CID*, resolved CID -> GID internally. The PD layer
        # passes the CID straight through (upstream
        # ``cidFont.getType2CharString(cid)``).
        gid = self.gid_for_cid(cid)
        self.seen_gids.append(gid)
        return ("charstring", gid)


class _FakeParsedCFF:
    def is_cid_font(self) -> bool:
        return True


class _RaisingMatrixCFF:
    @property
    def font_matrix(self) -> list[float]:
        raise RuntimeError("matrix unavailable")


def _char_proc(body: bytes) -> PDType3CharProc:
    stream = COSStream()
    stream.set_raw_data(body)
    return PDType3CharProc(PDType3Font(), stream)


def test_type3_char_proc_handles_parser_edge_cases() -> None:
    d1_proc = _char_proc(b"")
    d1_proc._first_metric_operator = lambda: (  # type: ignore[method-assign]
        b"d1",
        [b"500", b"0", b"bad", b"0", b"10", b"20"],
    )
    assert d1_proc.get_glyph_bbox() is None

    d0_proc = _char_proc(b"")
    d0_proc._first_metric_operator = lambda: (b"d0", [b"bad"])  # type: ignore[method-assign]
    assert d0_proc.get_width() == 0.0

    numeric_only = _char_proc(b"12 34 ")
    assert numeric_only._first_metric_operator() == (None, [b"12", b"34"])
    assert _is_numeric_token(b"") is False


def test_type1_font_parses_font_file_when_parser_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(type1_module, "Type1Font", _FakeParsedType1)

    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"type1")
    descriptor.set_font_file(stream)
    font = PDType1Font()
    font.set_font_descriptor(descriptor)

    assert isinstance(font.get_font_program(), _FakeParsedType1)


@pytest.mark.parametrize(
    ("base_font", "code"),
    [
        (PDType1Font.SYMBOL, 65),
        (PDType1Font.ZAPF_DINGBATS, 33),
    ],
)
def test_type1_font_standard14_symbolic_default_encodings(
    base_font: str,
    code: int,
) -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("BaseFont"), base_font)
    font = PDType1Font(raw)

    assert font.get_glyph_width(code) > 0.0


def test_type1_font_program_zero_width_and_empty_height_edges() -> None:
    font = PDType1Font()
    font._get_type1_font = lambda: _ZeroWidthType1()  # type: ignore[method-assign]
    font._code_to_glyph_name = lambda _code: "A"  # type: ignore[method-assign]

    assert font._program_width(65) is None

    no_program = PDType1Font()
    assert no_program.get_height(65) == 0.0

    close_only = PDType1Font()
    close_only._get_type1_font = lambda: _CloseOnlyType1()  # type: ignore[method-assign]
    close_only._code_to_glyph_name = lambda _code: "A"  # type: ignore[method-assign]
    assert close_only.get_height(65) == 0.0


def test_cid_type0_cid_keyed_empty_charset_uses_gid_zero() -> None:
    program = _FakeCIDCFF([])
    font = PDCIDFontType0()
    font.set_cff_font(program)

    assert font.code_to_gid(12) == 0
    assert font.get_type2_char_string(12) == ("charstring", 0)
    assert program.seen_gids == [0]


def test_cid_type0_parse_specializes_cid_cff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parsed = _FakeCIDCFF([".notdef"])

    monkeypatch.setattr(
        cid0_module.CFFFont,
        "from_bytes",
        classmethod(lambda cls, data: _FakeParsedCFF()),
    )
    monkeypatch.setattr(
        cid0_module.CFFCIDFont,
        "from_cff_font",
        classmethod(lambda cls, base: parsed),
    )

    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"cff")
    descriptor.set_font_file3(stream)
    font = PDCIDFontType0()
    font.set_font_descriptor(descriptor)

    assert font.get_cff_font() is parsed


def test_cid_type0_bad_matrix_property_and_bad_bbox_are_ignored() -> None:
    font = PDCIDFontType0()
    font.get_cff_font = lambda: _RaisingMatrixCFF()  # type: ignore[method-assign]

    assert font.get_font_matrix() == (0.001, 0.0, 0.0, 0.001, 0.0, 0.0)
    assert PDCIDFontType0._coerce_bbox([0, object(), 10, 20]) is None
