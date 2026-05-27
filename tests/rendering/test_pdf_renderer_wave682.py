from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(
    width: float = 4.0,
    height: float = 4.0,
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(
    size: tuple[int, int] = (4, 4),
) -> tuple[PDDocument, PDFRenderer]:
    doc, _page = _make_doc(float(size[0]), float(size[1]))
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", size, (255, 255, 255))  # noqa: SLF001
    renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
    renderer._draw.setantialias(True)  # noqa: SLF001
    renderer._gs_stack = [_GState()]  # noqa: SLF001
    renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
    return doc, renderer


def _finish(renderer: PDFRenderer) -> None:
    draw = renderer._draw  # noqa: SLF001
    if draw is not None:
        draw.flush()


def test_resolve_font_caches_direct_resource_font_and_handles_failures() -> None:
    class _Resources:
        def __init__(self) -> None:
            self.calls = 0
            self.font = object()

        def get_font(self, _name: COSName) -> object:
            self.calls += 1
            return self.font

    class _RaisingResources:
        def get_font(self, _name: COSName) -> object:
            raise RuntimeError("font unavailable")

    doc, renderer = _prepared_renderer()
    try:
        name = COSName.get_pdf_name("F1")
        assert renderer._resolve_font(name) is None  # noqa: SLF001

        renderer._resources = _RaisingResources()  # noqa: SLF001
        assert renderer._resolve_font(name) is None  # noqa: SLF001

        resources = _Resources()
        renderer._resources = resources  # noqa: SLF001
        assert renderer._resolve_font(name) is resources.font  # noqa: SLF001
        assert renderer._resolve_font(name) is resources.font  # noqa: SLF001
        assert resources.calls == 1
    finally:
        _finish(renderer)
        doc.close()


def test_text_operator_guards_and_read_code_fallback(monkeypatch: Any) -> None:
    class _BadReaderFont:
        def __init__(self) -> None:
            self.calls = 0

        def read_code(self, _data: bytes, _offset: int) -> tuple[int, int]:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("bad code")
            return (99, 0)

    doc, renderer = _prepared_renderer()
    try:
        renderer._op_set_font(None, [])  # noqa: SLF001
        renderer._op_set_font(None, [object(), object()])  # noqa: SLF001
        assert renderer._gs.text_font is None  # noqa: SLF001

        renderer._show_string(b"abc")  # noqa: SLF001
        renderer._gs.text_font = _BadReaderFont()  # noqa: SLF001
        renderer._gs.text_font_size = 10.0  # noqa: SLF001

        seen_codes: list[int] = []
        monkeypatch.setattr(renderer, "_get_ttf_glyph_set", lambda _font: (None, None))
        monkeypatch.setattr(
            PDFRenderer,
            "_get_type1_units_per_em",
            staticmethod(lambda _font: None),
        )
        monkeypatch.setattr(
            renderer,
            "_draw_glyph",
            lambda _font, code, *_args, **_kwargs: seen_codes.append(code)
            or 100.0,
        )

        renderer._show_string(b"AZ")  # noqa: SLF001

        assert seen_codes == [65, 99]
        assert renderer._gs.text_matrix[4] == 2.0  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_get_ttf_glyph_set_type0_parse_and_glyphset_failures(
    monkeypatch: Any,
) -> None:
    import pypdfbox.fontbox.ttf as ttf_module
    import pypdfbox.pdmodel.font.pd_type0_font as type0_module

    class _FontFile:
        def to_byte_array(self) -> bytes:
            return b"not-a-ttf"

    class _Descriptor:
        def get_font_file2(self) -> _FontFile:
            return _FontFile()

    class _Descendant:
        def get_font_descriptor(self) -> _Descriptor:
            return _Descriptor()

    class _Type0Font:
        def get_descendant_font(self) -> _Descendant:
            return _Descendant()

    class _TTF:
        _tt = object()

    class _BadGlyphSetTTF:
        class _TT:
            def getGlyphSet(self) -> Any:  # noqa: N802
                raise RuntimeError("no glyphs")

        _tt = _TT()

    doc, renderer = _prepared_renderer()
    try:
        monkeypatch.setattr(type0_module, "PDType0Font", _Type0Font)
        monkeypatch.setattr(
            ttf_module.TrueTypeFont,
            "from_bytes",
            staticmethod(lambda _data: (_ for _ in ()).throw(RuntimeError("bad ttf"))),
        )
        assert renderer._get_ttf_glyph_set(_Type0Font()) == (None, None)  # noqa: SLF001

        monkeypatch.setattr(
            ttf_module.TrueTypeFont,
            "from_bytes",
            staticmethod(lambda _data: _BadGlyphSetTTF()),
        )
        ttf, glyph_set = renderer._get_ttf_glyph_set(_Type0Font())  # noqa: SLF001
        assert isinstance(ttf, _BadGlyphSetTTF)
        assert glyph_set is None

        monkeypatch.setattr(
            ttf_module.TrueTypeFont,
            "from_bytes",
            staticmethod(lambda _data: _TTF()),
        )
        assert renderer._get_ttf_glyph_set(object()) == (None, None)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_type1c_units_and_resolve_font_program_cache(
    monkeypatch: Any,
) -> None:
    import pypdfbox.fontbox.font_mappers as mapper_module
    import pypdfbox.pdmodel.font.pd_type1c_font as type1c_module

    class _CFFProgram:
        units_per_em = 2048

    class _Type1CFont:
        def __init__(self, program: _CFFProgram | None) -> None:
            self._program = program

        def _get_cff_font(self) -> _CFFProgram | None:
            return self._program

    class _Mapping:
        def get_font(self) -> str:
            return "fallback"

    class _Mapper:
        calls = 0

        def get_font_box_font(self, _name: str, _descriptor: object | None) -> _Mapping:
            self.calls += 1
            return _Mapping()

    doc, renderer = _prepared_renderer()
    try:
        monkeypatch.setattr(type1c_module, "PDType1CFont", _Type1CFont)
        assert PDFRenderer._get_type1_units_per_em(_Type1CFont(None)) is None  # noqa: SLF001
        assert PDFRenderer._get_type1_units_per_em(_Type1CFont(_CFFProgram())) == 2048  # noqa: E501, SLF001

        renderer._get_ttf_glyph_set = lambda _font: (None, None)  # type: ignore[method-assign] # noqa: SLF001, E501
        program_font = _Type1CFont(_CFFProgram())
        assert renderer._resolve_font_program(program_font) is program_font._program  # noqa: SLF001
        assert renderer._resolve_font_program(program_font) is program_font._program  # noqa: SLF001

        mapper = _Mapper()
        monkeypatch.setattr(
            mapper_module.FontMappers,
            "instance",
            staticmethod(lambda: mapper),
        )
        plain_font = object()
        assert renderer._resolve_font_program(plain_font) == "fallback"  # noqa: SLF001
        assert renderer._resolve_font_program(plain_font) == "fallback"  # noqa: SLF001
        assert mapper.calls == 1
    finally:
        _finish(renderer)
        doc.close()


def test_draw_glyph_ttf_and_type1_failures_fall_back_cleanly(
    monkeypatch: Any,
) -> None:
    class _BadTTF:
        class _TT:
            def getGlyphName(self, _gid: int) -> str:  # noqa: N802
                raise RuntimeError("name failed")

        _tt = _TT()

        def get_units_per_em(self) -> int:
            return 1000

    class _Type1Font:
        def get_glyph_path(self, _code: int) -> list[tuple[str, float, float]]:
            raise RuntimeError("path failed")

        def get_glyph_width(self, _code: int) -> float:
            return 333.0

    class _PlaceholderFont:
        pass

    doc, renderer = _prepared_renderer()
    try:
        monkeypatch.setattr(
            PDFRenderer,
            "_code_to_gid",
            staticmethod(lambda _font, _code, _ttf: 7),
        )
        monkeypatch.setattr(
            renderer,
            "_resolve_font_program",
            lambda _font: None,
        )
        monkeypatch.setattr(renderer, "_maybe_warn_standard14", lambda _font: None)
        monkeypatch.setattr(renderer, "_draw_placeholder_box", lambda *_args: None)

        assert renderer._draw_glyph(  # noqa: SLF001
            _PlaceholderFont(),
            65,
            _BadTTF(),
            {},
        ) == 500.0

        assert renderer._draw_glyph(  # noqa: SLF001
            _Type1Font(),
            65,
            None,
            None,
            type1_units_per_em=1000,
        ) == 333.0
    finally:
        _finish(renderer)
        doc.close()

