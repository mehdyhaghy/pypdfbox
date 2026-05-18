"""Wave 1356 final-push coverage tests for
:mod:`pypdfbox.pdmodel.font.pd_true_type_font`.

Closes the last residual lines in 0.9.0rc1:

* Line 442 — ``get_normalized_path`` early-return when ``_code_to_gid``
  returns 0 and the font is neither embedded nor Standard 14.
* Line 825 — ``get_path_from_outlines`` returning ``None`` when the CFF
  charstring resolves to a name but yields an empty path (distinct from
  the ``.notdef`` short-circuit at 813-814 and the exception path at
  819-823).
* Lines 960-961 — ``encode_codepoint`` raising when both the AGL name
  *and* the synthesised ``uniXXXX`` form miss in the embedded TTF.
* Lines 967-969 — ``encode_codepoint`` raising when ``encoding.contains``
  is True but ``encoding.get_name_to_code_map`` has no entry for the
  glyph name.
* Line 1030 — ``_scale_path`` short-circuiting ``None`` points.
* Line 1038 — ``_scale_path`` passing non-``(x,y)`` shaped arguments
  through unchanged (nested point lists, scalars, etc).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.font import PDFontDescriptor, PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_true_type_font import _scale_path

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


def _font_with_embedded_ttf() -> PDTrueTypeFont:
    font = PDTrueTypeFont()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_raw_data(_ttf_bytes())
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    font.set_true_type_font(_load_ttf())
    return font


# ---------- get_normalized_path line 442 -----------------------------------


def test_get_normalized_path_drops_gid_zero_when_not_embedded_or_standard14(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 442 — gid 0 + ``is_embedded() == False`` + ``is_standard14()
    == False`` returns ``[]``. ``get_true_type_font()`` must still yield
    a real TTF (otherwise we exit at line 438), so we wire the TTF
    directly and patch the two flag methods to ``False``."""
    font = _font_with_embedded_ttf()
    # TTF is live (line 437 passes) but we lie about embedding state so
    # the line-441 condition is true.
    monkeypatch.setattr(font, "is_embedded", lambda: False)
    monkeypatch.setattr(font, "is_standard14", lambda: False)
    # Force _code_to_gid to return 0 — line 441 condition is now true.
    monkeypatch.setattr(font, "_code_to_gid", lambda _c, _t: 0)
    assert font.get_normalized_path(0x41) == []


# ---------- get_path_from_outlines line 825 --------------------------------


def test_get_path_from_outlines_returns_none_when_cff_path_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 825 — ``cff.get_path(name)`` returns an empty list for a
    non-``.notdef`` name; the ``if not path`` guard short-circuits to
    ``None``."""
    font = _font_with_embedded_ttf()
    ttf = font.get_true_type_font()
    assert ttf is not None

    class _Encoding:
        def get_name(self, _code: int) -> str:
            return "A"

    class _CFF:
        def get_path(self, _name: str) -> list[tuple[Any, ...]]:
            return []

    ttf.get_cff = lambda: _CFF()  # type: ignore[attr-defined]
    monkeypatch.setattr(font, "get_encoding_typed", lambda: _Encoding())
    assert font.get_path_from_outlines(0x41) is None


# ---------- encode_codepoint lines 960-961 ---------------------------------


def test_encode_codepoint_raises_when_agl_and_uni_both_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 960-961 — encoding contains the name, but neither the
    AGL name nor the ``uniXXXX`` fallback is present in the embedded
    TTF."""
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.font.encoding import WinAnsiEncoding

    font = _font_with_embedded_ttf()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), WinAnsiEncoding.INSTANCE.get_cos_object()
    )
    ttf = font.get_true_type_font()
    assert ttf is not None
    # has_glyph always False → AGL miss *and* uni miss → line 960 raises.
    monkeypatch.setattr(type(ttf), "has_glyph", lambda _self, _key: False)
    with pytest.raises(ValueError, match="No glyph for U"):
        font.encode_codepoint(0x41)


# ---------- encode_codepoint lines 967-969 ---------------------------------


def test_encode_codepoint_raises_when_name_not_in_inverted_code_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 967-969 — encoding contains the name (so line 950 passes),
    the TTF carries the glyph (lines 957-962 pass), but
    ``get_name_to_code_map`` is missing the entry."""
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.font.encoding import WinAnsiEncoding

    font = _font_with_embedded_ttf()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), WinAnsiEncoding.INSTANCE.get_cos_object()
    )
    ttf = font.get_true_type_font()
    assert ttf is not None
    # TTF has the glyph (line 957 short-circuit).
    monkeypatch.setattr(type(ttf), "has_glyph", lambda _self, _key: True)

    # Patch the encoding wrapper returned by get_encoding_typed so its
    # get_name_to_code_map yields an empty dict for the lookup.
    real_encoding = font.get_encoding_typed()
    assert real_encoding is not None

    class _MaskedEncoding:
        def contains(self, name: str) -> bool:
            return real_encoding.contains(name)

        def get_encoding_name(self) -> str:
            return real_encoding.get_encoding_name()

        def get_name_to_code_map(self) -> dict[str, int]:
            # Strip the entry the round-trip would otherwise resolve.
            return {}

    monkeypatch.setattr(font, "get_encoding_typed", lambda: _MaskedEncoding())
    with pytest.raises(ValueError, match="not available"):
        font.encode_codepoint(0x41)


# ---------- get_width_for_code line 351 ------------------------------------


def test_get_width_from_font_returns_float_when_units_per_em_is_1000(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 351 — ``units_per_em == 1000`` short-circuits the rescale
    and returns ``float(advance)`` directly."""
    font = _font_with_embedded_ttf()
    ttf = font.get_true_type_font()
    assert ttf is not None
    # Liberation Sans is 2048 unitsPerEm; force it to 1000 to exercise
    # the line-350 branch.
    monkeypatch.setattr(ttf, "get_units_per_em", lambda: 1000)
    monkeypatch.setattr(ttf, "get_advance_width", lambda _gid: 567)
    monkeypatch.setattr(font, "_code_to_gid", lambda _c, _t: 1)
    out = font.get_width_from_font(0x41)
    assert isinstance(out, float)
    assert out == 567.0


# ---------- _scale_path lines 1030 + 1038 ----------------------------------


def test_scale_path_preserves_none_points() -> None:
    """Line 1030 — ``None`` qCurveTo sentinel points pass through."""
    path: list[tuple[Any, ...]] = [("qCurveTo", (None, (1.0, 2.0)))]
    out = _scale_path(path, 0.5)
    assert out == [("qCurveTo", (None, (0.5, 1.0)))]


def test_scale_path_passes_through_non_pair_arguments() -> None:
    """Line 1038 — args that are not (x, y) two-tuples (e.g. nested
    point lists or bare scalars) are forwarded unchanged."""
    nested = (1.0, 2.0, 3.0)  # length 3, not a point
    scalar = 42  # not a tuple/list at all
    path: list[tuple[Any, ...]] = [
        ("custom", (nested, scalar, (5.0, 6.0))),
    ]
    out = _scale_path(path, 2.0)
    assert out == [("custom", (nested, scalar, (10.0, 12.0)))]


def test_scale_path_handles_nested_point_list_as_first_element() -> None:
    """Line 1038 — the ``isinstance(pt[0], (tuple, list))`` guard treats a
    list-of-points as a non-point and forwards it unchanged."""
    nested_points = ((1.0, 2.0), (3.0, 4.0))  # tuple whose first elt is tuple
    path: list[tuple[Any, ...]] = [("composite", (nested_points,))]
    out = _scale_path(path, 3.0)
    assert out == [("composite", (nested_points,))]


def test_scale_path_close_path_passes_through_unchanged() -> None:
    """``closePath`` carries no args — covered by the verb short-circuit
    before line 1030/1038 even runs. Sanity-check the unchanged shape."""
    path: list[tuple[Any, ...]] = [("closePath", ())]
    assert _scale_path(path, 7.5) == [("closePath", ())]
