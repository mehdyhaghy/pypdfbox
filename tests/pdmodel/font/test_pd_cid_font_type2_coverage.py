"""Wave 1323: coverage-boost tests for :class:`PDCIDFontType2`.

Closes gaps in:

* :meth:`get_open_type_font` — OpenType program with / without supported
  outlines, plus exception handling on ``is_supported_otf``.
* :meth:`get_cmap_lookup` — exception path on the lookup call.
* :meth:`generate_bounding_box` — TTF ``get_font_bbox`` raising.
* :meth:`get_path` / :meth:`get_path_from_outlines` — OpenType-CFF
  outline branch, including the ``get_path_from_outlines`` None
  fallback used by :meth:`get_path`.
* :meth:`encode` — embedded Identity-H/V path, embedded predefined CMap
  path, ``/ToUnicode`` fallback, non-embedded direct-cmap path, and the
  ``ValueError`` raised when no glyph can be located.
* :meth:`find_font_or_substitute` — FontMappers registry overridden with
  a stub mapper, mapper missing ``get_cid_font``, and exception swallow.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from pypdfbox.fontbox.cid_font_mapping import CIDFontMapping
from pypdfbox.fontbox.font_mapper import FontMapper
from pypdfbox.fontbox.font_mappers import FontMappers
from pypdfbox.fontbox.ttf.open_type_font import OpenTypeFont
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

# ---------- stub helpers --------------------------------------------------


class _StubGlyphSet:
    """Minimal fontTools-shaped glyph set — yields a duck-typed glyph
    whose ``draw`` callable forwards to ``pen.moveTo`` / ``lineTo`` /
    ``closePath`` so :func:`_make_path_pen` sees real commands."""

    def __init__(self, draw_callable: Any) -> None:
        self._draw = draw_callable

    def __getitem__(self, name: str) -> Any:
        return SimpleNamespace(draw=self._draw)


class _StubInnerTT:
    def __init__(self, draw_callable: Any) -> None:
        self._glyph_set = _StubGlyphSet(draw_callable)
        self._glyph_order = [".notdef", "A", "B"]

    def getGlyphName(self, gid: int) -> str:  # noqa: N802 — fontTools name
        if 0 <= gid < len(self._glyph_order):
            return self._glyph_order[gid]
        return ".notdef"

    def getGlyphSet(self) -> Any:  # noqa: N802 — fontTools name
        return self._glyph_set

    def __contains__(self, _key: str) -> bool:
        return False


class _StubOTFFont(OpenTypeFont):
    """Stand-in for an :class:`OpenTypeFont`-typed parsed program. We
    subclass the real :class:`OpenTypeFont` so the ``isinstance`` gate
    inside ``get_open_type_font`` accepts our stub without monkey-patching
    the builtin. We skip the superclass ``__init__`` (which wants a
    TTFDataStream) — none of the methods we override touch that state."""

    def __init__(
        self,
        *,
        supported: bool = True,
        supported_raises: bool = False,
        is_ps: bool = True,
        draw_callable: Any | None = None,
        units_per_em: int = 1000,
    ) -> None:
        # Deliberately do NOT call super().__init__ — the data-stream
        # surface isn't needed for these stub-driven tests.
        self._supported = supported
        self._supported_raises = supported_raises
        self._is_ps = is_ps
        self._units_per_em = units_per_em
        self._tt = _StubInnerTT(draw_callable or self._default_draw)

    def is_supported_otf(self) -> bool:
        if self._supported_raises:
            raise RuntimeError("boom")
        return self._supported

    def is_post_script(self) -> bool:
        return self._is_ps

    def get_units_per_em(self) -> int:
        return self._units_per_em

    def get_unicode_cmap_subtable(self) -> Any:
        return None

    @staticmethod
    def _default_draw(pen: Any) -> None:
        pen.moveTo((0.0, 0.0))
        pen.lineTo((100.0, 100.0))
        pen.closePath()


# ---------- get_open_type_font -------------------------------------------


def test_get_open_type_font_returns_program_when_supported() -> None:
    font = PDCIDFontType2()
    stub = _StubOTFFont(supported=True)
    font.get_true_type_font = lambda: stub  # type: ignore[assignment,method-assign,return-value]
    assert font.get_open_type_font() is stub


def test_get_open_type_font_returns_none_when_unsupported_outlines() -> None:
    # A stub TTF that is NOT an OpenTypeFont instance returns ``None``
    # directly via the first ``isinstance`` gate.
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: object()  # type: ignore[assignment,method-assign,return-value]
    assert font.get_open_type_font() is None


def test_get_open_type_font_returns_none_when_supported_raises() -> None:
    font = PDCIDFontType2()
    stub = _StubOTFFont(supported_raises=True)
    font.get_true_type_font = lambda: stub  # type: ignore[assignment,method-assign,return-value]
    assert font.get_open_type_font() is None


def test_get_open_type_font_returns_none_when_supported_false() -> None:
    font = PDCIDFontType2()
    stub = _StubOTFFont(supported=False)
    font.get_true_type_font = lambda: stub  # type: ignore[assignment,method-assign,return-value]
    assert font.get_open_type_font() is None


# ---------- get_cmap_lookup exception path -------------------------------


def test_get_cmap_lookup_returns_none_when_program_raises() -> None:
    class _RaisingTTF:
        def get_unicode_cmap_lookup(self, _is_strict: bool) -> Any:
            raise RuntimeError("cmap unavailable")

    font = PDCIDFontType2()
    font.get_true_type_font = lambda: _RaisingTTF()  # type: ignore[assignment,method-assign,return-value]
    assert font.get_cmap_lookup() is None


# ---------- generate_bounding_box — TTF raises ----------------------------


def test_generate_bounding_box_falls_back_when_ttf_bbox_raises() -> None:
    class _RaisingTTF:
        def get_font_bbox(self) -> Any:
            raise RuntimeError("no head table")

        def get_units_per_em(self) -> int:
            return 1000

    font = PDCIDFontType2()
    font.get_true_type_font = lambda: _RaisingTTF()  # type: ignore[assignment,method-assign,return-value]
    # No descriptor, no bbox -> falls back to super().get_bounding_box()
    # which returns ``None`` for a font with no metrics.
    result = font.generate_bounding_box()
    # super().get_bounding_box() may return None — both are valid for
    # this fallback path; the important thing is no exception escaped.
    assert result is None or hasattr(result, "lower_left_x")


# ---------- get_path / get_path_from_outlines ----------------------------


def test_get_path_routes_to_outlines_for_postscript_program() -> None:
    drawn: list[str] = []

    def draw(pen: Any) -> None:
        drawn.append("yes")
        pen.moveTo((0.0, 0.0))
        pen.lineTo((10.0, 10.0))
        pen.closePath()

    stub = _StubOTFFont(is_ps=True, draw_callable=draw)
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: stub  # type: ignore[assignment,method-assign,return-value]
    path = font.get_path(1)
    assert path
    assert drawn == ["yes"]


def test_get_path_returns_empty_when_outlines_returns_none() -> None:
    # Program declares postscript but returns no glyph commands.
    def draw_empty(_pen: Any) -> None:
        return None

    stub = _StubOTFFont(is_ps=True, draw_callable=draw_empty)
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: stub  # type: ignore[assignment,method-assign,return-value]
    assert font.get_path(1) == []


def test_get_path_from_outlines_returns_none_when_not_ps() -> None:
    stub = _StubOTFFont(is_ps=False)
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: stub  # type: ignore[assignment,method-assign,return-value]
    assert font.get_path_from_outlines(1) is None


def test_get_path_from_outlines_returns_none_when_no_program() -> None:
    font = PDCIDFontType2()
    assert font.get_path_from_outlines(1) is None


def test_get_path_from_outlines_returns_none_on_draw_exception() -> None:
    def draw_raises(_pen: Any) -> None:
        raise RuntimeError("bad charstring")

    stub = _StubOTFFont(is_ps=True, draw_callable=draw_raises)
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: stub  # type: ignore[assignment,method-assign,return-value]
    assert font.get_path_from_outlines(1) is None


def test_get_path_from_outlines_returns_none_when_glyph_set_raises() -> None:
    class _BrokenTT:
        def getGlyphName(self, _gid: int) -> str:  # noqa: N802
            raise RuntimeError("no glyph names")

        def getGlyphSet(self) -> Any:  # noqa: N802
            return {}

    class _BrokenOTF:
        _tt = _BrokenTT()

        def is_post_script(self) -> bool:
            return True

    stub = _BrokenOTF()
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: stub  # type: ignore[assignment,method-assign,return-value]
    assert font.get_path_from_outlines(1) is None


def test_get_path_from_outlines_returns_commands_when_present() -> None:
    drew: list[str] = []

    def draw(pen: Any) -> None:
        pen.moveTo((1.0, 2.0))
        pen.lineTo((3.0, 4.0))
        pen.closePath()
        drew.append("ok")

    stub = _StubOTFFont(is_ps=True, draw_callable=draw)
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: stub  # type: ignore[assignment,method-assign,return-value]
    path = font.get_path_from_outlines(1)
    assert path is not None
    assert drew == ["ok"]


# ---------- encode --------------------------------------------------------


class _FakeCmapSubtable:
    """Mimics fontTools' cmap subtable shape: ``get_glyph_id(code)``."""

    def __init__(self, mapping: dict[int, int]) -> None:
        self._mapping = mapping

    def get_glyph_id(self, codepoint: int) -> int:
        return self._mapping.get(codepoint, 0)


class _FakeCmap:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeUcs2Cmap:
    """Mimics CMap.to_cid used by the predefined-CMap branch of encode."""

    def __init__(self, mapping: dict[int, int]) -> None:
        self._mapping = mapping

    def to_cid(self, code: int) -> int:
        return self._mapping.get(code, 0)


class _FakeToUnicodeCmap:
    def __init__(self, mapping: dict[str, bytes]) -> None:
        self._mapping = mapping

    def get_codes_from_unicode(self, s: str) -> bytes | None:
        return self._mapping.get(s)


def _build_embedded_font(
    *,
    cmap_mapping: dict[int, int] | None = None,
    parent_cmap_name: str | None = None,
    ucs2_mapping: dict[int, int] | None = None,
    to_unicode: dict[str, bytes] | None = None,
) -> PDCIDFontType2:
    """Construct a font whose ``is_embedded()`` is True (with a real
    PDType0Font subclass parent and stub TTF) ready for :meth:`encode`
    exercises."""
    from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

    class _StubParent(PDType0Font):
        def __init__(self) -> None:
            super().__init__()
            self._stub_cmap = (
                _FakeCmap(parent_cmap_name) if parent_cmap_name else None
            )
            self._stub_ucs2 = (
                _FakeUcs2Cmap(ucs2_mapping) if ucs2_mapping is not None else None
            )
            self._stub_to_unicode = (
                _FakeToUnicodeCmap(to_unicode) if to_unicode is not None else None
            )

        def get_cmap(self) -> Any:  # type: ignore[override]
            return self._stub_cmap

        def get_cmap_ucs2(self) -> Any:  # type: ignore[override]
            return self._stub_ucs2

        def get_to_unicode_cmap(self) -> Any:  # type: ignore[override]
            return self._stub_to_unicode

    parent = _StubParent()
    font = PDCIDFontType2(parent_type0_font=parent)

    class _StubTTF:
        def get_unicode_cmap_subtable(self) -> Any:
            return (
                _FakeCmapSubtable(cmap_mapping) if cmap_mapping is not None else None
            )

    stub_ttf = _StubTTF()
    font.get_true_type_font = lambda: stub_ttf  # type: ignore[assignment,method-assign,return-value]
    font.is_embedded = lambda: True  # type: ignore[assignment,method-assign,return-value]
    return font


def test_encode_embedded_identity_h_uses_unicode_cmap() -> None:
    font = _build_embedded_font(
        cmap_mapping={ord("A"): 0x41}, parent_cmap_name="Identity-H"
    )
    assert font.encode(ord("A")) == b"\x00\x41"


def test_encode_embedded_predefined_cmap_uses_ucs2_to_cid() -> None:
    font = _build_embedded_font(
        cmap_mapping={ord("B"): 0},
        parent_cmap_name="GB-EUC-H",  # any non-Identity- name
        ucs2_mapping={ord("B"): 0x99},
    )
    assert font.encode(ord("B")) == b"\x00\x99"


def test_encode_embedded_falls_back_to_to_unicode_cmap() -> None:
    font = _build_embedded_font(
        cmap_mapping={ord("C"): 0},
        parent_cmap_name="Identity-H",
        to_unicode={"C": b"\x12\x34"},
    )
    # Cmap returns 0 (notdef) → ToUnicode bytes returned directly.
    assert font.encode(ord("C")) == b"\x12\x34"


def test_encode_embedded_raises_when_cid_zero_and_no_fallback() -> None:
    font = _build_embedded_font(
        cmap_mapping={ord("D"): 0},
        parent_cmap_name="Identity-H",
        to_unicode=None,
    )
    with pytest.raises(ValueError, match="No glyph"):
        font.encode(ord("D"))


def test_encode_non_embedded_uses_cmap_subtable() -> None:
    font = PDCIDFontType2()
    font.is_embedded = lambda: False  # type: ignore[assignment,method-assign,return-value]

    class _StubTTF:
        def get_unicode_cmap_subtable(self) -> Any:
            return _FakeCmapSubtable({ord("X"): 0x88})

    font.get_true_type_font = lambda: _StubTTF()  # type: ignore[assignment,method-assign,return-value]
    assert font.encode(ord("X")) == b"\x00\x88"


def test_encode_non_embedded_raises_when_no_subtable() -> None:
    font = PDCIDFontType2()
    font.is_embedded = lambda: False  # type: ignore[assignment,method-assign,return-value]

    class _StubTTF:
        def get_unicode_cmap_subtable(self) -> Any:
            return None

    font.get_true_type_font = lambda: _StubTTF()  # type: ignore[assignment,method-assign,return-value]
    with pytest.raises(ValueError, match="No glyph"):
        font.encode(ord("Y"))


def test_encode_non_embedded_raises_when_subtable_returns_zero() -> None:
    font = PDCIDFontType2()
    font.is_embedded = lambda: False  # type: ignore[assignment,method-assign,return-value]

    class _StubTTF:
        def get_unicode_cmap_subtable(self) -> Any:
            return _FakeCmapSubtable({})

    font.get_true_type_font = lambda: _StubTTF()  # type: ignore[assignment,method-assign,return-value]
    with pytest.raises(ValueError, match="No glyph"):
        font.encode(ord("Z"))


# ---------- find_font_or_substitute -------------------------------------


def test_find_font_or_substitute_returns_none_for_default_mapper() -> None:
    # Default mapper has no get_cid_font implementation that returns
    # anything for an unknown name -> returns None (line 770 path).
    FontMappers.reset()
    try:
        font = PDCIDFontType2()
        assert font.find_font_or_substitute() is None
    finally:
        FontMappers.reset()


def test_find_font_or_substitute_uses_custom_mapper() -> None:
    sentinel = CIDFontMapping(None, None, is_fallback=True)

    class _CustomMapper(FontMapper):
        def get_true_type_font(self, *_: Any, **__: Any) -> Any:
            return None

        def get_open_type_font(self, *_: Any, **__: Any) -> Any:
            return None

        def get_font_box_font(self, *_: Any, **__: Any) -> Any:
            return None

        def get_cid_font(self, *_: Any, **__: Any) -> Any:
            return sentinel

    FontMappers.set(_CustomMapper())
    try:
        font = PDCIDFontType2()
        assert font.find_font_or_substitute() is sentinel
    finally:
        FontMappers.reset()


def test_find_font_or_substitute_handles_mapper_exception() -> None:
    class _ExplodingMapper(FontMapper):
        def get_true_type_font(self, *_: Any, **__: Any) -> Any:
            return None

        def get_open_type_font(self, *_: Any, **__: Any) -> Any:
            return None

        def get_font_box_font(self, *_: Any, **__: Any) -> Any:
            return None

        def get_cid_font(self, *_: Any, **__: Any) -> Any:
            raise RuntimeError("mapper crashed")

    FontMappers.set(_ExplodingMapper())
    try:
        font = PDCIDFontType2()
        assert font.find_font_or_substitute() is None
    finally:
        FontMappers.reset()


def test_find_font_or_substitute_returns_none_when_get_cid_missing() -> None:
    class _NoCidMapper(FontMapper):
        def get_true_type_font(self, *_: Any, **__: Any) -> Any:
            return None

        def get_open_type_font(self, *_: Any, **__: Any) -> Any:
            return None

        def get_font_box_font(self, *_: Any, **__: Any) -> Any:
            return None

    # Explicitly delete the inherited concrete ``get_cid_font`` so the
    # callable-check fails and the function returns ``None`` (line 770).
    mapper = _NoCidMapper()
    mapper.get_cid_font = None  # type: ignore[assignment,method-assign]
    FontMappers.set(mapper)
    try:
        font = PDCIDFontType2()
        assert font.find_font_or_substitute() is None
    finally:
        FontMappers.reset()


def test_find_font_or_substitute_handles_instance_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom() -> Any:
        raise RuntimeError("registry broken")

    monkeypatch.setattr(FontMappers, "instance", classmethod(lambda cls: boom()))
    font = PDCIDFontType2()
    assert font.find_font_or_substitute() is None


def test_find_font_or_substitute_forwards_base_font_or_name() -> None:
    captured: dict[str, Any] = {}

    class _CapturingMapper(FontMapper):
        def get_true_type_font(self, *_: Any, **__: Any) -> Any:
            return None

        def get_open_type_font(self, *_: Any, **__: Any) -> Any:
            return None

        def get_font_box_font(self, *_: Any, **__: Any) -> Any:
            return None

        def get_cid_font(
            self, base: str, desc: Any, cid_info: Any
        ) -> Any:
            captured["base"] = base
            captured["desc"] = desc
            captured["cid_info"] = cid_info
            return None

    FontMappers.set(_CapturingMapper())
    try:
        font = PDCIDFontType2()
        # No base/name set -> empty string passed.
        assert font.find_font_or_substitute() is None
        assert captured["base"] == ""
    finally:
        FontMappers.reset()


# ---------- is_open_type_post_script edge cases --------------------------


def test_is_open_type_post_script_returns_false_when_no_program() -> None:
    font = PDCIDFontType2()
    assert font.is_open_type_post_script() is False


def test_is_open_type_post_script_returns_false_when_attr_missing() -> None:
    font = PDCIDFontType2()
    # Program present but no is_post_script callable.
    font.get_true_type_font = lambda: object()  # type: ignore[assignment,method-assign,return-value]
    assert font.is_open_type_post_script() is False


def test_is_open_type_post_script_returns_false_on_exception() -> None:
    class _RaisingPS:
        def is_post_script(self) -> bool:
            raise RuntimeError("boom")

    font = PDCIDFontType2()
    font.get_true_type_font = lambda: _RaisingPS()  # type: ignore[assignment,method-assign,return-value]
    assert font.is_open_type_post_script() is False


def test_is_open_type_post_script_returns_true_for_ps_program() -> None:
    class _PSProgram:
        def is_post_script(self) -> bool:
            return True

    font = PDCIDFontType2()
    font.get_true_type_font = lambda: _PSProgram()  # type: ignore[assignment,method-assign,return-value]
    assert font.is_open_type_post_script() is True
