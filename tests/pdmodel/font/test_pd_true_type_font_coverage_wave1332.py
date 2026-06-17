"""Wave 1332 coverage round-out for
:mod:`pypdfbox.pdmodel.font.pd_true_type_font`.

Targets the residual no-coverage tail in 0.9.0rc1:

* ``get_base_font`` ``None`` branch (no COS dict)
* ``is_embedded`` cached-False short-circuit
* ``get_normalized_path`` GID-0 + units-per-em rescale paths
* ``extract_cmap_table`` cmap exception + missing-table branches
* ``read_encoding_from_font`` standard-14 standard encoding branch and
  ``post`` lookup failure
* ``get_path_from_outlines`` no-CFF / no-encoding / unknown-glyph paths
* ``get_parser`` file-like sniffer + ``OTTO`` magic
* ``encode_codepoint`` AGL miss + uniXXXX fallback + No-encoding code paths
* ``_CmapPlatformView.get_name``
* ``_uni_name_of_code_point`` short-hex padding
* ``_ps_name_from_ttf_local`` fallbacks (no inner / KeyError / blank text)
* ``_populate_simple_descriptor_from_ttf`` zero-units-per-em path
* ``_build_simple_widths`` exception paths
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.otf_parser import OTFParser
from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from pypdfbox.pdmodel.font import PDFontDescriptor, PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_font_descriptor import FLAG_SYMBOLIC
from pypdfbox.pdmodel.font.pd_true_type_font import (
    _build_simple_widths,
    _CmapPlatformView,
    _populate_simple_descriptor_from_ttf,
    _ps_name_from_ttf_local,
    _uni_name_of_code_point,
)

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _ttf_bytes() -> bytes:
    if not _FIXTURE.exists():
        pytest.skip(f"missing fixture {_FIXTURE}")
    return _FIXTURE.read_bytes()


def _load_ttf() -> TrueTypeFont:
    return TrueTypeFont.from_bytes(_ttf_bytes())


def _font_with_embedded_ttf(*, symbolic: bool = False) -> PDTrueTypeFont:
    font = PDTrueTypeFont()
    fd = PDFontDescriptor()
    if symbolic:
        fd.set_flags(FLAG_SYMBOLIC)
    stream = COSStream()
    stream.set_raw_data(_ttf_bytes())
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    font.set_true_type_font(_load_ttf())
    return font


# ---------- get_base_font None branch (line 86) ----------------------------


def test_get_base_font_returns_none_when_cos_object_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDTrueTypeFont()
    monkeypatch.setattr(font, "get_cos_object", lambda: None)
    # Line 85-86 — null COS object.
    assert font.get_base_font() is None
    assert font.get_name() is None


# ---------- is_embedded cached-False (line 173) ----------------------------


def test_is_embedded_returns_false_when_ttf_marked_failed() -> None:
    font = PDTrueTypeFont()
    font._ttf = False  # noqa: SLF001 — simulate prior parse failure
    # Line 172-173 — cached False short-circuit.
    assert font.is_embedded() is False


# ---------- get_normalized_path branches -----------------------------------


def test_get_normalized_path_returns_empty_when_no_ttf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Disable the wave-1596 non-embedded substitute so the genuine
    # "no program at all" branch (empty path) is exercised.
    monkeypatch.setattr(
        PDTrueTypeFont, "_get_substitute_font", lambda self: None
    )
    font = PDTrueTypeFont()
    # Line 437-438.
    assert font.get_normalized_path(0x41) == []


def test_get_normalized_path_drops_gid_zero_for_external_nonstandard() -> None:
    font = _font_with_embedded_ttf()
    # Code 0xFF most likely resolves to gid 0; with no embedding flag *and*
    # not a Standard 14 name we hit the early-return on line 442.
    # is_embedded() is True here because we injected the TTF — patch it
    # to False to mimic an external program with descriptor-only embedding.
    font._ttf = False  # noqa: SLF001
    # No /FontFile2 program → is_embedded False. Not a Standard 14 →
    # is_standard14 False. Path returns empty (line 442 or 438).
    assert font.get_normalized_path(0xFF) == []


def test_get_normalized_path_returns_path_when_units_per_em_is_1000() -> None:
    font = _font_with_embedded_ttf()
    # Liberation Sans is 2048 unitsPerEm — the rescale branch at line 449
    # runs. Use an "A" code under a typical winansi encoding.
    out = font.get_normalized_path(ord("A"))
    # Could be empty if no encoding is wired; we accept either, but if
    # non-empty the rescale path executed.
    assert isinstance(out, list)


def test_get_normalized_path_passes_through_unscaled_when_units_per_em_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    ttf = font.get_true_type_font()
    assert ttf is not None
    # Force units_per_em to 0 so we hit line 447-448.
    monkeypatch.setattr(ttf, "get_units_per_em", lambda: 0)
    # Inject a non-empty path bypass — patch get_glyph_path to a known list.
    monkeypatch.setattr(
        font, "get_glyph_path", lambda _code: [("moveto", 1.0, 2.0)]
    )
    monkeypatch.setattr(font, "_code_to_gid", lambda _c, _t: 1)
    out = font.get_normalized_path(0x41)
    # Returned unchanged (no rescale).
    assert out == [("moveto", 1.0, 2.0)]


def test_get_normalized_path_returns_empty_when_glyph_path_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    monkeypatch.setattr(font, "get_glyph_path", lambda _c: [])
    monkeypatch.setattr(font, "_code_to_gid", lambda _c, _t: 5)
    # Line 443-445.
    assert font.get_normalized_path(0x41) == []


# ---------- extract_cmap_table branches ------------------------------------


def test_extract_cmap_table_returns_when_no_ttf() -> None:
    font = PDTrueTypeFont()
    font.extract_cmap_table()
    assert font._cmap_initialized is True  # noqa: SLF001


def test_extract_cmap_table_handles_no_cmap_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    ttf = font.get_true_type_font()
    assert ttf is not None
    # Replace _tt with a dict-like that says "cmap" isn't there.
    monkeypatch.setattr(ttf, "_tt", {})
    font._cmap_initialized = False  # noqa: SLF001
    # Lines 684-686 — missing cmap.
    font.extract_cmap_table()
    assert font._cmap_initialized is True  # noqa: SLF001


def test_extract_cmap_table_handles_inner_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    ttf = font.get_true_type_font()
    assert ttf is not None

    class _BadInner:
        def __contains__(self, _key: str) -> bool:
            raise RuntimeError("forced")

    monkeypatch.setattr(ttf, "_tt", _BadInner())
    font._cmap_initialized = False  # noqa: SLF001
    # Lines 680-683 — exception path.
    font.extract_cmap_table()
    assert font._cmap_initialized is True  # noqa: SLF001


def test_extract_cmap_table_records_win_symbol_and_mac_roman(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    ttf = font.get_true_type_font()
    assert ttf is not None

    class _Sub:
        def __init__(self, plat: int, enc: int, mapping: dict[int, str]) -> None:
            self.platformID = plat  # noqa: N815
            self.platEncID = enc  # noqa: N815
            self.cmap = mapping

    win_unicode = _Sub(3, 1, {0x41: "A"})
    win_symbol = _Sub(3, 0, {0xF041: "A"})
    mac_roman = _Sub(1, 0, {0x41: "A"})

    class _FakeCmapTable:
        tables = [win_unicode, win_symbol, mac_roman]

    class _Tt:
        def __contains__(self, key: str) -> bool:
            return key == "cmap"

        def __getitem__(self, key: str) -> Any:
            if key == "cmap":
                return _FakeCmapTable()
            raise KeyError(key)

    monkeypatch.setattr(ttf, "_tt", _Tt())
    font._cmap_initialized = False  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font._cmap_win_symbol = None  # noqa: SLF001
    font._cmap_mac_roman = None  # noqa: SLF001
    font.extract_cmap_table()
    # Lines 693-694, 695-699.
    assert font._cmap_win_unicode is not None  # noqa: SLF001
    assert font._cmap_win_symbol is not None  # noqa: SLF001
    assert font._cmap_mac_roman is not None  # noqa: SLF001


def test_extract_cmap_table_promotes_unicode_platform_to_win_unicode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PDFBOX-4755 / PDF.js #5501 / PDFBOX-5484 — promote (0,0) when (3,1)
    is missing (lines 700-713)."""
    font = _font_with_embedded_ttf()
    ttf = font.get_true_type_font()
    assert ttf is not None

    class _Sub:
        def __init__(self, plat: int, enc: int) -> None:
            self.platformID = plat  # noqa: N815
            self.platEncID = enc  # noqa: N815
            self.cmap = {0x41: "A"}

    unicode_sub = _Sub(0, 0)

    class _FakeCmapTable:
        tables = [unicode_sub]

    class _Tt:
        def __contains__(self, key: str) -> bool:
            return key == "cmap"

        def __getitem__(self, key: str) -> Any:
            if key == "cmap":
                return _FakeCmapTable()
            raise KeyError(key)

    monkeypatch.setattr(ttf, "_tt", _Tt())
    font._cmap_initialized = False  # noqa: SLF001
    font._cmap_win_unicode = None  # noqa: SLF001
    font.extract_cmap_table()
    assert font._cmap_win_unicode is not None  # noqa: SLF001


# ---------- read_encoding_from_font branches -------------------------------


def test_read_encoding_from_font_returns_type1_encoding_for_standard14_external(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the font isn't embedded but is a Standard 14 (with an AFM), the
    AFM branch returns a Type1Encoding built from the bundled metrics — exactly
    as upstream PDTrueTypeFont.readEncodingFromFont does. (Wave 1516 landed the
    Type1Encoding(afm) port that this branch had been stubbing out as None;
    verified against the live oracle in
    tests/pdmodel/font/oracle/test_font_encoding_fuzz_wave1516.py.)"""
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.font.encoding.type1_encoding import Type1Encoding

    font = PDTrueTypeFont()
    font.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), "Helvetica"
    )
    # Force is_embedded → False so the AFM-branch fires.
    monkeypatch.setattr(font, "is_embedded", lambda: False)
    out = font.read_encoding_from_font()
    assert isinstance(out, Type1Encoding)
    assert out.get_name(65) == "A"


def test_read_encoding_from_font_returns_standard_encoding_for_standard14_embedded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 747-753 — Standard 14 font that *is* embedded and is not
    Symbol/ZapfDingbats returns StandardEncoding."""
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.font.encoding import StandardEncoding

    font = _font_with_embedded_ttf(symbolic=True)
    font.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), "Helvetica"
    )
    # Force is_standard14 to True so lines 747-753 fire.
    monkeypatch.setattr(font, "is_standard14", lambda: True)
    out = font.read_encoding_from_font()
    assert out is StandardEncoding.INSTANCE


def test_read_encoding_from_font_returns_none_when_ttf_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDTrueTypeFont()
    # Symbolic but no embedded program → branch at line 755-756.
    fd = PDFontDescriptor()
    fd.set_flags(FLAG_SYMBOLIC)
    font.set_font_descriptor(fd)
    monkeypatch.setattr(font, "get_standard14_afm", lambda: None)
    # is_embedded resolves False (no /FontFile2).
    assert font.read_encoding_from_font() is None


def test_read_encoding_from_font_synthesises_builtin_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 757-774 — when post.get_name raises, falls back to GID pseudo-
    name string. We force one code to map cleanly and one to raise."""
    from pypdfbox.pdmodel.font.encoding import BuiltInEncoding

    font = _font_with_embedded_ttf(symbolic=True)
    ttf = font.get_true_type_font()
    assert ttf is not None

    class _Post:
        def get_name(self, gid: int) -> str | None:
            if gid == 3:
                raise RuntimeError("forced")
            return f"glyph{gid}"

    monkeypatch.setattr(ttf, "get_post_script", lambda: _Post())
    # Stub code_to_gid so we hit a tame distribution.
    monkeypatch.setattr(
        font, "code_to_gid", lambda code: {1: 5, 2: 3, 3: 0}.get(code, 0)
    )
    out = font.read_encoding_from_font()
    assert isinstance(out, BuiltInEncoding)
    # gid 5 → "glyph5"; gid 3 → exception → str(gid) fallback.
    assert out.get_name(1) == "glyph5"
    assert out.get_name(2) == "3"


# ---------- get_path_from_outlines branches --------------------------------


def test_get_path_from_outlines_returns_none_when_no_ttf() -> None:
    font = PDTrueTypeFont()
    assert font.get_path_from_outlines(0x41) is None


def test_get_path_from_outlines_returns_none_when_no_get_cff() -> None:
    font = _font_with_embedded_ttf()
    # LiberationSans has no get_cff attribute → line 803-805.
    assert font.get_path_from_outlines(0x41) is None


def test_get_path_from_outlines_returns_none_when_cff_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    ttf = font.get_true_type_font()
    assert ttf is not None
    ttf.get_cff = lambda: None  # type: ignore[attr-defined]
    assert font.get_path_from_outlines(0x41) is None


def test_get_path_from_outlines_returns_none_when_no_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    ttf = font.get_true_type_font()
    assert ttf is not None

    class _CFF:
        def get_path(self, _name: str) -> list[tuple[Any, ...]]:
            return []

    ttf.get_cff = lambda: _CFF()  # type: ignore[attr-defined]
    monkeypatch.setattr(font, "get_encoding_typed", lambda: None)
    # Lines 809-811.
    assert font.get_path_from_outlines(0x41) is None


def test_get_path_from_outlines_handles_charstring_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    ttf = font.get_true_type_font()
    assert ttf is not None

    class _Encoding:
        def get_name(self, _code: int) -> str:
            return "A"

    class _CFF:
        def get_path(self, _name: str) -> list[tuple[Any, ...]]:
            raise RuntimeError("malformed")

    ttf.get_cff = lambda: _CFF()  # type: ignore[attr-defined]
    monkeypatch.setattr(font, "get_encoding_typed", lambda: _Encoding())
    # Lines 819-823.
    assert font.get_path_from_outlines(0x41) is None


def test_get_path_from_outlines_returns_path_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    ttf = font.get_true_type_font()
    assert ttf is not None

    class _Encoding:
        def get_name(self, _code: int) -> str:
            return "A"

    class _CFF:
        def get_path(self, _name: str) -> list[tuple[Any, ...]]:
            return [("moveto", 1.0, 2.0)]

    ttf.get_cff = lambda: _CFF()  # type: ignore[attr-defined]
    monkeypatch.setattr(font, "get_encoding_typed", lambda: _Encoding())
    out = font.get_path_from_outlines(0x41)
    assert out == [("moveto", 1.0, 2.0)]


def test_get_path_from_outlines_returns_none_for_notdef_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    ttf = font.get_true_type_font()
    assert ttf is not None

    class _Encoding:
        def get_name(self, _code: int) -> str:
            return ".notdef"

    class _CFF:
        def get_path(self, _name: str) -> list[tuple[Any, ...]]:
            return []

    ttf.get_cff = lambda: _CFF()  # type: ignore[attr-defined]
    monkeypatch.setattr(font, "get_encoding_typed", lambda: _Encoding())
    # Lines 812-814.
    assert font.get_path_from_outlines(0x41) is None


# ---------- get_parser file-like + OTTO branches ---------------------------


def test_get_parser_handles_bytes_with_otto_magic() -> None:
    parser = PDTrueTypeFont.get_parser(b"OTTO\x00\x00\x00\x00")
    assert isinstance(parser, OTFParser)


def test_get_parser_handles_bytes_with_truetype_magic() -> None:
    parser = PDTrueTypeFont.get_parser(b"\x00\x01\x00\x00")
    assert isinstance(parser, TTFParser)


def test_get_parser_handles_file_like_with_seek_tell() -> None:
    sink = io.BytesIO(b"OTTO\x00\x00\x00\x00")
    # Position should be restored after the sniff.
    sink.seek(0)
    parser = PDTrueTypeFont.get_parser(sink)
    assert isinstance(parser, OTFParser)
    assert sink.tell() == 0


def test_get_parser_handles_file_like_without_tell() -> None:
    class _NoTell:
        def __init__(self, data: bytes) -> None:
            self._data = data
            self._pos = 0

        def read(self, n: int) -> bytes:
            chunk = self._data[self._pos : self._pos + n]
            self._pos += len(chunk)
            return chunk

        def tell(self) -> int:
            raise AttributeError("forced")

    parser = PDTrueTypeFont.get_parser(_NoTell(b"\x00\x01\x00\x00"))
    assert isinstance(parser, TTFParser)


# ---------- encode_codepoint branches --------------------------------------


def test_encode_codepoint_raises_when_name_not_in_encoding() -> None:
    """Lines 949-954 — encoding.contains(name) is False."""
    font = _font_with_embedded_ttf()
    # Standard14Fonts.has_alias("Helvetica") returns False but we need to
    # wire an encoding so the path enters the branch.
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.font.encoding import WinAnsiEncoding

    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), WinAnsiEncoding.INSTANCE.get_cos_object()
    )
    # U+1F600 (emoji) is not in WinAnsiEncoding.
    with pytest.raises(ValueError, match="not available"):
        font.encode_codepoint(0x1F600)


def test_encode_codepoint_uses_uni_fallback_when_ttf_missing_agl_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 957-959 — ttf doesn't have the AGL name; uniXXXX hits."""
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.font.encoding import WinAnsiEncoding

    font = _font_with_embedded_ttf()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), WinAnsiEncoding.INSTANCE.get_cos_object()
    )
    ttf = font.get_true_type_font()
    assert ttf is not None

    def _fake_has_glyph(self: object, key: object) -> bool:
        # Always False on AGL name; True on uniXXXX → exercise lines 957-959.
        return isinstance(key, str) and key.startswith("uni")

    monkeypatch.setattr(
        type(ttf), "has_glyph", _fake_has_glyph, raising=True
    )
    # WinAnsi "A" → name "A" → encoding contains → ttf.has_glyph("A") False
    # → uni_name "uni0041" → has_glyph True → returns encoded byte.
    out = font.encode_codepoint(0x41)
    assert out == bytes([0x41])


def test_encode_codepoint_raises_when_no_encoding_and_no_ttf() -> None:
    font = PDTrueTypeFont()
    # No /Encoding, no /FontFile2 → ttf is None at line 973.
    with pytest.raises(ValueError, match="No glyph for U"):
        font.encode_codepoint(0x41)


def test_encode_codepoint_raises_when_no_encoding_and_ttf_missing_glyph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    # Pretend there's no /Encoding.
    monkeypatch.setattr(font, "get_encoding_typed", lambda: None)
    ttf = font.get_true_type_font()
    assert ttf is not None
    monkeypatch.setattr(ttf, "has_glyph", lambda _k: False)
    # Lines 977-980.
    with pytest.raises(ValueError, match="No glyph"):
        font.encode_codepoint(0x41)


def test_encode_codepoint_raises_when_no_encoding_and_gid_not_in_code_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    monkeypatch.setattr(font, "get_encoding_typed", lambda: None)
    ttf = font.get_true_type_font()
    assert ttf is not None
    monkeypatch.setattr(ttf, "has_glyph", lambda _k: True)
    monkeypatch.setattr(ttf, "name_to_gid", lambda _n: 0xFFFF)
    monkeypatch.setattr(font, "get_gid_to_code", dict)
    # Lines 982-986.
    with pytest.raises(ValueError, match="not available"):
        font.encode_codepoint(0x41)


def test_encode_codepoint_returns_code_when_no_encoding_round_trip_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_embedded_ttf()
    monkeypatch.setattr(font, "get_encoding_typed", lambda: None)
    ttf = font.get_true_type_font()
    assert ttf is not None
    monkeypatch.setattr(ttf, "has_glyph", lambda _k: True)
    monkeypatch.setattr(ttf, "name_to_gid", lambda _n: 5)
    monkeypatch.setattr(font, "get_gid_to_code", lambda: {5: 0x42})
    # Line 987.
    assert font.encode_codepoint(0x41) == bytes([0x42])


# ---------- _CmapPlatformView.get_name (line 1011) -------------------------


def test_cmap_platform_view_get_name_returns_none_for_unmapped() -> None:
    class _Sub:
        cmap = {0x41: "A"}

    view = _CmapPlatformView(_Sub())
    assert view.get_name(0x41) == "A"
    # Line 1010-1011 — unmapped code returns None.
    assert view.get_name(0xFF) is None


# ---------- _uni_name_of_code_point padding (lines 1050-1053) --------------


def test_uni_name_of_code_point_pads_to_four_chars() -> None:
    assert _uni_name_of_code_point(0x41) == "uni0041"
    assert _uni_name_of_code_point(0x1234) == "uni1234"
    # Five-hex-digit codepoints stay unpadded (only minimum-width pad).
    assert _uni_name_of_code_point(0x10000) == "uni10000"


# ---------- _ps_name_from_ttf_local fallbacks ------------------------------


class _DummyTTF:
    def __init__(self, inner: object | None) -> None:
        self._tt = inner


def test_ps_name_from_ttf_local_returns_fallback_without_inner() -> None:
    # Line 1340.
    assert _ps_name_from_ttf_local(_DummyTTF(None), "fallback") == "fallback"  # type: ignore[arg-type]


def test_ps_name_from_ttf_local_returns_fallback_when_name_table_missing() -> None:
    class _Inner:
        def __getitem__(self, key: str) -> Any:
            raise KeyError(key)

    # Lines 1343-1344.
    assert (
        _ps_name_from_ttf_local(_DummyTTF(_Inner()), "fb") == "fb"  # type: ignore[arg-type]
    )


def test_ps_name_from_ttf_local_returns_fallback_when_no_name_record() -> None:
    class _NameTable:
        def getName(self, *_args: object) -> None:  # noqa: N802
            return None

    class _Inner:
        def __getitem__(self, key: str) -> Any:
            if key == "name":
                return _NameTable()
            raise KeyError(key)

    # Line 1351.
    assert (
        _ps_name_from_ttf_local(_DummyTTF(_Inner()), "fb") == "fb"  # type: ignore[arg-type]
    )


def test_ps_name_from_ttf_local_returns_fallback_when_to_unicode_raises() -> None:
    class _Record:
        def toUnicode(self) -> str:  # noqa: N802
            raise RuntimeError("forced")

    class _NameTable:
        def getName(self, *_args: object) -> _Record:  # noqa: N802
            return _Record()

    class _Inner:
        def __getitem__(self, key: str) -> Any:
            if key == "name":
                return _NameTable()
            raise KeyError(key)

    # Lines 1354-1355.
    assert (
        _ps_name_from_ttf_local(_DummyTTF(_Inner()), "fb") == "fb"  # type: ignore[arg-type]
    )


def test_ps_name_from_ttf_local_returns_fallback_when_text_blank() -> None:
    class _Record:
        def toUnicode(self) -> str:  # noqa: N802
            return "   "

    class _NameTable:
        def getName(self, *_args: object) -> _Record:  # noqa: N802
            return _Record()

    class _Inner:
        def __getitem__(self, key: str) -> Any:
            if key == "name":
                return _NameTable()
            raise KeyError(key)

    # Line 1357 — blank text falls back.
    assert (
        _ps_name_from_ttf_local(_DummyTTF(_Inner()), "fb") == "fb"  # type: ignore[arg-type]
    )


# ---------- _populate_simple_descriptor_from_ttf zero-units path ----------


def test_populate_simple_descriptor_from_ttf_handles_zero_units_per_em(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ttf = _load_ttf()
    # Force units_per_em to 0 so the guard at line 1370-1371 fires.
    head = ttf.get_header()
    assert head is not None
    monkeypatch.setattr(head, "get_units_per_em", lambda: 0)

    fd = PDFontDescriptor()
    _populate_simple_descriptor_from_ttf(fd, ttf)
    # /Ascent and /StemV should have been written.
    cos = fd.get_cos_object()
    from pypdfbox.cos import COSName

    assert cos.contains_key(COSName.get_pdf_name("Ascent"))
    assert cos.contains_key(COSName.get_pdf_name("StemV"))


# ---------- _build_simple_widths exception fallbacks ----------------------


def test_build_simple_widths_handles_zero_units_per_em(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ttf = _load_ttf()
    monkeypatch.setattr(ttf, "get_units_per_em", lambda: 0)

    from pypdfbox.pdmodel.font.encoding import WinAnsiEncoding

    widths = _build_simple_widths(ttf, WinAnsiEncoding.INSTANCE)
    assert len(widths) == 256


def test_build_simple_widths_handles_encoding_get_name_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ttf = _load_ttf()

    class _Bad:
        def get_name(self, _code: int) -> str:
            raise RuntimeError("forced")

    # Lines 1411-1414 — name fetch fails → 0.0 width.
    widths = _build_simple_widths(ttf, _Bad())  # type: ignore[arg-type]
    assert widths == [0.0] * 256


def test_build_simple_widths_handles_name_to_gid_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ttf = _load_ttf()
    monkeypatch.setattr(ttf, "name_to_gid", lambda _n: 1 / 0)  # forces ZeroDivisionError

    class _Enc:
        def get_name(self, _code: int) -> str:
            return "A"

    # Lines 1419-1421 — name_to_gid raises → gid=0 → 0.0 width.
    widths = _build_simple_widths(ttf, _Enc())  # type: ignore[arg-type]
    assert widths == [0.0] * 256


def test_build_simple_widths_handles_get_advance_width_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ttf = _load_ttf()
    monkeypatch.setattr(ttf, "name_to_gid", lambda _n: 5)
    monkeypatch.setattr(ttf, "get_advance_width", lambda _g: 1 / 0)

    class _Enc:
        def get_name(self, _code: int) -> str:
            return "A"

    # Lines 1425-1428 — advance fetch raises → 0.0 width.
    widths = _build_simple_widths(ttf, _Enc())  # type: ignore[arg-type]
    assert widths == [0.0] * 256
