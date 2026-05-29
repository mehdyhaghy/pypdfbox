from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_CID_TO_GID_MAP = COSName.get_pdf_name("CIDToGIDMap")
_DIFFERENCES = COSName.get_pdf_name("Differences")
_ENCODING = COSName.get_pdf_name("Encoding")


class _FakeCFF:
    def __init__(
        self,
        *,
        units_per_em: int = 1000,
        width: float = 500.0,
        default_width: float = 0.0,
        charset: list[str] | None = None,
        glyphs: set[str] | None = None,
        path: list[tuple[Any, ...]] | None = None,
    ) -> None:
        self.units_per_em = units_per_em
        self._width = width
        self._default_width = default_width
        self._charset = charset if charset is not None else [".notdef", "A"]
        self._glyphs = glyphs if glyphs is not None else {"A"}
        self._path = path if path is not None else [("moveto", 0, 0), ("lineto", 0, 700)]

    def has_glyph(self, name: str) -> bool:
        return name in self._glyphs

    def get_width(self, _name: str) -> float:
        return self._width

    def get_path(self, _name: str) -> list[tuple[Any, ...]]:
        return self._path

    def get_charset(self) -> list[str]:
        return self._charset

    def get_default_width_x(self) -> float:
        return self._default_width


class _FakeCIDCFF(CFFCIDFont):
    def __init__(self, charset: list[str]) -> None:
        super().__init__()
        self._charset = charset
        self.seen_gids: list[int] = []

    def get_charset(self) -> list[str]:
        return self._charset

    def get_type2_char_string(self, cid: int) -> object:
        # Mirror the real ``CFFCIDFont.getType2CharString(int cid)``: the
        # parameter is a *CID*, resolved CID -> GID internally. The PD layer
        # passes the CID straight through (upstream
        # ``cidFont.getType2CharString(cid)``).
        self.seen_gids.append(self.gid_for_cid(cid))
        return object()


class _RaisingMatrixCFF:
    @property
    def font_matrix(self) -> list[float]:
        raise RuntimeError("matrix unavailable")


class _ZeroUnitsTTF:
    def get_units_per_em(self) -> int:
        return 0


class _ZeroAdvanceTTF:
    advance_widths = [0, 0, 0]

    def get_units_per_em(self) -> int:
        return 1000


class _MissingGlyphNameTable:
    def getGlyphName(self, _gid: int) -> str:  # noqa: N802 - fontTools API
        raise KeyError("missing")


class _MissingGlyphTTF:
    _tt = _MissingGlyphNameTable()


def _winansi_type1c_font() -> PDType1CFont:
    raw = COSDictionary()
    raw.set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))
    return PDType1CFont(raw)


def test_type1c_program_width_rejects_missing_glyph_bad_units_and_zero_width() -> None:
    font = _winansi_type1c_font()

    font._get_cff_font = lambda: _FakeCFF(glyphs=set())  # type: ignore[method-assign]
    assert font._program_width(65) is None

    font._get_cff_font = lambda: _FakeCFF(units_per_em=0)  # type: ignore[method-assign]
    assert font._program_width(65) is None

    font._get_cff_font = lambda: _FakeCFF(width=0.0)  # type: ignore[method-assign]
    assert font._program_width(65) is None


def test_type1c_glyph_absent_from_charset_returns_empty_path_height_and_gid() -> None:
    # Wave-1434: a no-/Encoding PDType1CFont now resolves StandardEncoding via
    # read_encoding_from_font() (upstream PDSimpleFont.readEncoding), so code 65
    # -> "A" (matching PDFBox). The empty-charset case checked here is therefore
    # "glyph name not present in the embedded CFF": model it consistently
    # (empty charset -> no glyphs, no path) so code 65 -> "A" -> GID 0 -> empty
    # path/height. Pre-wave-1434 the encoding was wrongly None so code 65
    # produced no glyph name at all (the blank-render bug).
    font = PDType1CFont()
    font._get_cff_font = lambda: _FakeCFF(  # type: ignore[method-assign]
        charset=[], glyphs=set(), path=[]
    )

    assert font.code_to_name(65) == "A"
    assert font.get_glyph_path(65) == []
    assert font.get_height(65) == 0.0
    assert font.code_to_gid(65) == 0


def test_type1c_average_width_uses_cff_default_width_when_scaled() -> None:
    font = _winansi_type1c_font()
    font._get_cff_font = lambda: _FakeCFF(  # type: ignore[method-assign]
        units_per_em=500,
        default_width=250,
    )

    assert font.get_average_font_width() == 500.0


def test_simple_font_standard14_with_dictionary_encoding_no_base() -> None:
    # A non-symbolic Helvetica with a /Differences-only encoding (no
    # /BaseEncoding) resolves its base to StandardEncoding, matching upstream
    # PDFBox (verified against the PDFBox 3.0.7 oracle: base == StandardEncoding,
    # isStandard14() == true). Because the single difference [65 /A] merely
    # restates StandardEncoding's own mapping for code 65, the overlay is
    # trivial and the font remains a Standard-14 font. (Wave 1417: previously
    # get_encoding_typed lost the symbolic flag and left base == None, which
    # disqualified the font — a divergence from upstream now fixed.)
    encoding = COSDictionary()
    encoding.set_item(
        _DIFFERENCES,
        COSArray([COSInteger.get(65), COSName.get_pdf_name("A")]),
    )
    raw = COSDictionary()
    raw.set_name(_BASE_FONT, "Helvetica")
    raw.set_item(_ENCODING, encoding)
    font = PDSimpleFont(raw)

    assert font.is_standard_14() is True

    # A non-trivial difference (remapping a code to a glyph other than the
    # base encoding's) still disqualifies the font, per PDFBOX-2372.
    encoding2 = COSDictionary()
    encoding2.set_item(
        _DIFFERENCES,
        COSArray([COSInteger.get(65), COSName.get_pdf_name("bullet")]),
    )
    raw2 = COSDictionary()
    raw2.set_name(_BASE_FONT, "Helvetica")
    raw2.set_item(_ENCODING, encoding2)
    assert PDSimpleFont(raw2).is_standard_14() is False


def test_simple_font_encode_skips_unmapped_names_and_falls_back_to_question() -> None:
    encoding = COSDictionary()
    encoding.set_item(
        _DIFFERENCES,
        COSArray([COSInteger.get(65), COSName.get_pdf_name("DefinitelyNotAGlyph")]),
    )
    raw = COSDictionary()
    raw.set_item(_ENCODING, encoding)
    font = PDSimpleFont(raw)

    assert font.encode("A") == b"?"


def test_cid_type2_identity_string_and_unknown_map_shape_are_safe() -> None:
    font = PDCIDFontType2()
    font.get_cos_object().set_item(_CID_TO_GID_MAP, "Identity")  # type: ignore[arg-type]

    assert font.is_identity_cid_to_gid_map() is True

    font.get_cos_object().set_item(_CID_TO_GID_MAP, COSInteger.get(7))
    font.clear_cid_to_gid_map_cache()

    assert font.cid_to_gid(12) == 12


def test_cid_type2_metric_and_path_fallback_edges() -> None:
    font = PDCIDFontType2()
    font.cid_to_gid = lambda _cid: 1  # type: ignore[method-assign]
    font.get_true_type_font = lambda: _ZeroUnitsTTF()  # type: ignore[method-assign]

    assert font.get_height(5) == 0.0

    font.get_true_type_font = lambda: _ZeroAdvanceTTF()  # type: ignore[method-assign]
    assert font.get_average_font_width() == font.get_default_width()

    font.get_true_type_font = lambda: _MissingGlyphTTF()  # type: ignore[method-assign]
    assert font.get_glyph_path(5) == []

    def raise_gid(_cid: int) -> int:
        raise RuntimeError("cid map unavailable")

    font.cid_to_gid = raise_gid  # type: ignore[method-assign]
    assert font.get_normalized_path(5) == []


def test_cid_type0_cid_keyed_empty_charset_falls_back_to_gid_zero() -> None:
    font = PDCIDFontType0()
    program = _FakeCIDCFF([])
    font.get_cff_font = lambda: program  # type: ignore[method-assign]

    assert font.code_to_gid(12) == 0
    assert font.get_type2_char_string(12) is not None
    assert program.seen_gids == [0]


def test_cid_type0_bad_font_matrix_and_bad_bbox_are_ignored() -> None:
    font = PDCIDFontType0()
    font.get_cff_font = lambda: _RaisingMatrixCFF()  # type: ignore[method-assign]

    assert font.get_font_matrix() == (0.001, 0.0, 0.0, 0.001, 0.0, 0.0)
    assert PDCIDFontType0._coerce_bbox([0, "bad", 10, 20]) is None
