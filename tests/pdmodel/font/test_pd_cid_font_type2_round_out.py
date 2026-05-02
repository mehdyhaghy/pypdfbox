"""Round-out tests for :class:`PDCIDFontType2` (Wave 201).

Covers:
* :meth:`encode_glyph_id` — 2-byte big-endian, mirroring upstream
  ``PDCIDFontType2.encodeGlyphId``.
* :meth:`get_normalized_path` — embedded TTF path scaled to 1/1000 em,
  with the "no notdef for substitute fonts" Acrobat quirk.
* :meth:`is_open_type_post_script` — predicate over the embedded
  program's PostScript-flavoured OTF flag.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor

# ---------- synthetic stand-ins ----------


class _StubGlyph:
    def __init__(self, y_min: int, y_max: int, draw_cmds: list[tuple] | None = None) -> None:
        self.yMin = y_min  # noqa: N815 — fontTools attribute name
        self.yMax = y_max  # noqa: N815 — fontTools attribute name
        self._draw_cmds = draw_cmds or []

    def draw(self, pen: Any) -> None:
        for cmd in self._draw_cmds:
            head = cmd[0]
            args = cmd[1:]
            if head == "moveto":
                pen.moveTo(args)
            elif head == "lineto":
                pen.lineTo(args)
            elif head == "curveto":
                # Pen API uses curveTo with 3 (x, y) tuples
                pen.curveTo(args[0:2], args[2:4], args[4:6])
            elif head == "closepath":
                pen.closePath()


class _StubGlyfTable:
    def __init__(self, glyphs: dict[str, _StubGlyph]) -> None:
        self._glyphs = glyphs

    def __getitem__(self, name: str) -> _StubGlyph:
        return self._glyphs[name]


class _StubGlyphSet:
    def __init__(self, glyphs: dict[str, _StubGlyph]) -> None:
        self._glyphs = glyphs

    def __getitem__(self, name: str) -> _StubGlyph:
        return self._glyphs[name]


class _StubTTInner:
    def __init__(
        self,
        glyph_order: list[str],
        glyphs: dict[str, _StubGlyph],
        head: SimpleNamespace,
    ) -> None:
        self._order = glyph_order
        self._glyphs = glyphs
        self._tables = {"glyf": _StubGlyfTable(glyphs), "head": head}

    def __contains__(self, key: str) -> bool:
        return key in self._tables

    def __getitem__(self, key: str) -> Any:
        return self._tables[key]

    def getGlyphOrder(self) -> list[str]:  # noqa: N802 — fontTools name
        return self._order

    def getGlyphName(self, gid: int) -> str:  # noqa: N802 — fontTools name
        return self._order[gid]

    def getGlyphSet(self) -> _StubGlyphSet:  # noqa: N802 — fontTools name
        return _StubGlyphSet(self._glyphs)


class _StubTTF:
    """Minimal stand-in for a parsed fontTools TrueTypeFont. Carries
    the duck-typed surface PDCIDFontType2 reads — units-per-em, glyph
    order, glyph data, and an optional ``is_post_script`` flag for the
    OTF predicate."""

    def __init__(
        self,
        units_per_em: int,
        glyph_order: list[str],
        glyphs: dict[str, _StubGlyph],
        is_post_script: bool | None = None,
    ) -> None:
        self._units_per_em = units_per_em
        self._tt = _StubTTInner(glyph_order, glyphs, SimpleNamespace())
        self._is_post_script = is_post_script

    def get_units_per_em(self) -> int:
        return self._units_per_em

    def get_advance_width(self, gid: int) -> int:
        return 0

    @property
    def advance_widths(self) -> list[int]:
        return []

    # Optional — only present when the test wants to assert the OTF
    # predicate path. PDCIDFontType2.is_open_type_post_script duck-types
    # via getattr so leaving it out tests the "not OTF" branch.
    def is_post_script(self) -> bool:
        if self._is_post_script is None:
            raise AttributeError("is_post_script not provided")
        return self._is_post_script


def _make_font_with_stub_ttf(stub: _StubTTF) -> PDCIDFontType2:
    font = PDCIDFontType2()
    font.get_true_type_font = lambda _stub=stub: _stub  # type: ignore[method-assign]
    # is_embedded() is consulted by get_normalized_path's notdef quirk;
    # default to False unless the test explicitly wires up a /FontFile2.
    return font


# ---------- encode_glyph_id ----------


def test_encode_glyph_id_emits_two_byte_big_endian() -> None:
    """Mirrors upstream's
    ``new byte[] {(byte)(glyphId >> 8 & 0xff), (byte)(glyphId & 0xff)}``.
    """
    font = PDCIDFontType2()
    assert font.encode_glyph_id(0) == b"\x00\x00"
    assert font.encode_glyph_id(1) == b"\x00\x01"
    assert font.encode_glyph_id(0x1234) == b"\x12\x34"
    assert font.encode_glyph_id(0xFFFF) == b"\xff\xff"


def test_encode_glyph_id_masks_to_16_bits() -> None:
    """Wider GIDs are truncated to 16 bits — matches the Java cast."""
    font = PDCIDFontType2()
    # 0x10001 & 0xFFFF == 0x0001
    assert font.encode_glyph_id(0x10001) == b"\x00\x01"
    # 0x12345678 & 0xFFFF == 0x5678
    assert font.encode_glyph_id(0x12345678) == b"\x56\x78"


def test_encode_glyph_id_returns_two_bytes_always() -> None:
    """CIDs are always 2-byte for TrueType — even for a zero GID."""
    font = PDCIDFontType2()
    assert len(font.encode_glyph_id(0)) == 2
    assert len(font.encode_glyph_id(0xFFFF)) == 2


# ---------- get_normalized_path ----------


def test_get_normalized_path_empty_when_no_program() -> None:
    font = PDCIDFontType2()
    assert font.get_normalized_path(1) == []


def test_get_normalized_path_unscaled_for_1000_upem() -> None:
    """A 1000-upem font emits the path verbatim — no scaling
    transform applied since the path is already in 1/1000 em."""
    glyphs = {
        ".notdef": _StubGlyph(0, 0),
        "A": _StubGlyph(
            0, 700,
            draw_cmds=[
                ("moveto", 0, 0),
                ("lineto", 500, 0),
                ("lineto", 500, 700),
                ("lineto", 0, 700),
                ("closepath",),
            ],
        ),
    }
    stub = _StubTTF(units_per_em=1000, glyph_order=[".notdef", "A"], glyphs=glyphs)
    font = _make_font_with_stub_ttf(stub)
    raw = font.get_glyph_path(1)
    normalized = font.get_normalized_path(1)
    assert normalized == raw


def test_get_normalized_path_scales_2048_upem_to_1000() -> None:
    """A 2048-upem font scales by 1000/2048 ≈ 0.488..."""
    glyphs = {
        ".notdef": _StubGlyph(0, 0),
        "A": _StubGlyph(
            0, 1024,
            draw_cmds=[
                ("moveto", 0, 0),
                ("lineto", 1024, 0),
                ("lineto", 1024, 2048),
                ("closepath",),
            ],
        ),
    }
    stub = _StubTTF(units_per_em=2048, glyph_order=[".notdef", "A"], glyphs=glyphs)
    font = _make_font_with_stub_ttf(stub)
    normalized = font.get_normalized_path(1)
    assert normalized[0] == ("moveto", pytest.approx(0.0), pytest.approx(0.0))
    # 1024 * (1000 / 2048) = 500
    assert normalized[1] == ("lineto", pytest.approx(500.0), pytest.approx(0.0))
    # 2048 * (1000 / 2048) = 1000
    assert normalized[2] == ("lineto", pytest.approx(500.0), pytest.approx(1000.0))
    assert normalized[3] == ("closepath",)


def test_get_normalized_path_scales_curveto_arguments() -> None:
    """Curve-to commands carry six numeric args — all scaled."""
    glyphs = {
        ".notdef": _StubGlyph(0, 0),
        "A": _StubGlyph(
            0, 2048,
            draw_cmds=[
                ("moveto", 0, 0),
                ("curveto", 256, 512, 768, 1024, 1024, 2048),
                ("closepath",),
            ],
        ),
    }
    stub = _StubTTF(units_per_em=2048, glyph_order=[".notdef", "A"], glyphs=glyphs)
    font = _make_font_with_stub_ttf(stub)
    normalized = font.get_normalized_path(1)
    # 256 * (1000/2048) = 125.0; 512 -> 250.0; 768 -> 375.0; 1024 -> 500.0; 2048 -> 1000.0
    assert normalized[1] == (
        "curveto",
        pytest.approx(125.0),
        pytest.approx(250.0),
        pytest.approx(375.0),
        pytest.approx(500.0),
        pytest.approx(500.0),
        pytest.approx(1000.0),
    )


def test_get_normalized_path_suppresses_notdef_for_substitute_font() -> None:
    """Acrobat quirk: a non-embedded (substitute) font draws no
    notdef — upstream returns an empty GeneralPath when GID 0 lands
    on a substitute. Our port returns ``[]`` for the same reason
    (PDFBOX-2372)."""
    glyphs = {
        ".notdef": _StubGlyph(
            0, 700,
            draw_cmds=[
                ("moveto", 0, 0),
                ("lineto", 500, 0),
                ("lineto", 500, 700),
                ("closepath",),
            ],
        ),
    }
    stub = _StubTTF(units_per_em=1000, glyph_order=[".notdef"], glyphs=glyphs)
    font = _make_font_with_stub_ttf(stub)
    # No /FontFile2 wired up -> is_embedded() is False -> notdef suppressed.
    assert font.is_embedded() is False
    assert font.get_normalized_path(0) == []


def test_get_normalized_path_emits_notdef_for_embedded_font() -> None:
    """When embedded, the notdef quirk *doesn't* apply — even GID 0
    yields its outline if non-empty."""
    glyphs = {
        ".notdef": _StubGlyph(
            0, 700,
            draw_cmds=[
                ("moveto", 0, 0),
                ("lineto", 500, 0),
                ("closepath",),
            ],
        ),
    }
    stub = _StubTTF(units_per_em=1000, glyph_order=[".notdef"], glyphs=glyphs)
    font = _make_font_with_stub_ttf(stub)
    # Wire up /FontFile2 so is_embedded() reports True.
    fd = PDFontDescriptor()
    fd.set_font_file2(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True
    normalized = font.get_normalized_path(0)
    assert normalized[0] == ("moveto", pytest.approx(0.0), pytest.approx(0.0))
    assert normalized[-1] == ("closepath",)


def test_get_normalized_path_empty_when_zero_units_per_em() -> None:
    """Defensive: 0 upem on the stub returns the path unchanged
    (avoid divide-by-zero) — matches the safe path in
    :meth:`get_font_matrix`."""
    glyphs = {
        ".notdef": _StubGlyph(0, 0),
        "A": _StubGlyph(
            0, 100,
            draw_cmds=[("moveto", 0, 0), ("lineto", 100, 100), ("closepath",)],
        ),
    }
    stub = _StubTTF(units_per_em=0, glyph_order=[".notdef", "A"], glyphs=glyphs)
    font = _make_font_with_stub_ttf(stub)
    fd = PDFontDescriptor()
    fd.set_font_file2(COSStream())
    font.set_font_descriptor(fd)
    normalized = font.get_normalized_path(1)
    # 0 upem returns the unscaled path verbatim.
    assert normalized[0] == ("moveto", 0, 0)


# ---------- is_open_type_post_script ----------


def test_is_open_type_post_script_false_when_no_program() -> None:
    font = PDCIDFontType2()
    assert font.is_open_type_post_script() is False


def test_is_open_type_post_script_true_for_post_script_otf_program() -> None:
    """Stub reports ``is_post_script() == True`` -> predicate True."""
    stub = _StubTTF(
        units_per_em=1000,
        glyph_order=[".notdef"],
        glyphs={".notdef": _StubGlyph(0, 0)},
        is_post_script=True,
    )
    font = _make_font_with_stub_ttf(stub)
    assert font.is_open_type_post_script() is True


def test_is_open_type_post_script_false_for_truetype_outlined_program() -> None:
    """A plain TrueType program reports ``is_post_script() == False``."""
    stub = _StubTTF(
        units_per_em=1000,
        glyph_order=[".notdef"],
        glyphs={".notdef": _StubGlyph(0, 0)},
        is_post_script=False,
    )
    font = _make_font_with_stub_ttf(stub)
    assert font.is_open_type_post_script() is False


def test_is_open_type_post_script_false_when_predicate_missing() -> None:
    """Programs without an ``is_post_script`` accessor (vanilla TTF
    parsers without the OTF helper) report False — duck-typed via
    ``getattr`` rather than raising."""

    class _StubBareTTF:
        # No is_post_script attribute at all.
        def get_units_per_em(self) -> int:
            return 1000

    font = PDCIDFontType2()
    bare: Any = _StubBareTTF()
    font.get_true_type_font = lambda _b=bare: _b  # type: ignore[method-assign]
    assert font.is_open_type_post_script() is False


def test_is_open_type_post_script_false_when_predicate_raises() -> None:
    """Defensive: if the underlying predicate explodes, callers see
    ``False`` rather than the exception bubbling up — keeps the
    upstream branching guard side-effect-free."""

    class _StubExplodingTTF:
        def is_post_script(self) -> bool:
            raise RuntimeError("boom")

    font = PDCIDFontType2()
    bad: Any = _StubExplodingTTF()
    font.get_true_type_font = lambda _b=bad: _b  # type: ignore[method-assign]
    assert font.is_open_type_post_script() is False
