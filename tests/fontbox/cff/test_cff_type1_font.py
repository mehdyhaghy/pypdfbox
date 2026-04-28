"""Hand-written tests for :class:`CFFType1Font` (name-keyed CFF subtype).

Empty-instance tests run unconditionally; parsed-font tests are gated
on a name-keyed OTF being present on the host (mirrors the strategy in
``test_cff_font_parity.py``)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font

# Candidate locations for a name-keyed CFF font (Type 1 flavour).
_TYPE1_OTF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/STIXGeneral.otf",
    "/System/Library/Fonts/Supplemental/STIXGeneralItalic.otf",
    "/usr/share/fonts/opentype/stix/STIXGeneral.otf",
]


def _load_type1_cff_bytes() -> bytes | None:
    try:
        from fontTools.ttLib import TTFont  # noqa: PLC0415
    except ImportError:
        return None
    for candidate in _TYPE1_OTF_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            ttf = TTFont(str(path))
            if "CFF " not in ttf:
                continue
            # Skip CIDKeyed candidates here — we want a Type 1 flavour.
            top = ttf["CFF "].cff[ttf["CFF "].cff.fontNames[0]]
            if hasattr(top, "ROS"):
                continue
            buf = io.BytesIO()
            ttf["CFF "].cff.compile(buf, ttf, isCFF2=False)
            return buf.getvalue()
        except Exception:  # noqa: BLE001
            continue
    return None


_TYPE1_BYTES = _load_type1_cff_bytes()
_SKIP_REASON = "no name-keyed CFF/OTF fixture available on this host"


# ---------- empty instance ----------


class TestCFFType1FontEmptyInstance:
    def test_default_accessors_safe(self) -> None:
        f = CFFType1Font()
        assert f.is_cid_font() is False
        assert f.get_encoding() is None
        assert f.is_standard_encoding() is False
        assert f.is_expert_encoding() is False
        assert f.is_custom_encoding() is False
        assert f.name_to_gid("anything") == 0
        assert f.name_to_gid("") == 0
        assert f.code_to_name(65) == ".notdef"
        assert f.code_to_name(-1) == ".notdef"
        assert f.code_to_name(256) == ".notdef"


class TestCFFType1FontFromCIDFontRaises:
    def test_from_bytes_rejects_cid_keyed(self) -> None:
        try:
            from fontTools.ttLib import TTFont  # noqa: PLC0415
        except ImportError:
            pytest.skip("fontTools not installed")
        candidates = [
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        ]
        data: bytes | None = None
        for c in candidates:
            p = Path(c)
            if not p.exists():
                continue
            try:
                ttf = TTFont(str(p), fontNumber=0)
                if "CFF " not in ttf:
                    continue
                buf = io.BytesIO()
                ttf["CFF "].cff.compile(buf, ttf, isCFF2=False)
                data = buf.getvalue()
                break
            except Exception:  # noqa: BLE001
                continue
        if data is None:
            pytest.skip("no CIDKeyed font available")
        with pytest.raises(OSError):
            CFFType1Font.from_bytes(data)


# ---------- parsed-font tests ----------


@pytest.fixture(scope="module")
def type1_font() -> CFFType1Font:
    if _TYPE1_BYTES is None:
        pytest.skip(_SKIP_REASON)
    return CFFType1Font.from_bytes(_TYPE1_BYTES)


def test_parsed_type1_is_not_cid(type1_font: CFFType1Font) -> None:
    assert type1_font.is_cid_font() is False


def test_parsed_type1_has_encoding(type1_font: CFFType1Font) -> None:
    enc = type1_font.get_encoding()
    assert enc is not None
    # Either a string ("StandardEncoding"/"ExpertEncoding") or a custom
    # array — both branches are valid; just one must hold.
    assert (
        type1_font.is_standard_encoding()
        or type1_font.is_expert_encoding()
        or type1_font.is_custom_encoding()
    )


def test_parsed_type1_name_to_gid_known_glyph(type1_font: CFFType1Font) -> None:
    # ``.notdef`` is always GID 0 in a well-formed CFF.
    assert type1_font.name_to_gid(".notdef") == 0
    # An obviously-bogus glyph name resolves to .notdef (GID 0).
    assert type1_font.name_to_gid("__definitely_not_a_glyph__") == 0


def test_parsed_type1_code_to_name_predefined(type1_font: CFFType1Font) -> None:
    # Predefined encodings are now resolved via the canonical Adobe
    # tables: StandardEncoding (CFF EncodingId 0) maps code 65 → "A",
    # Expert (id 1) maps code 65 → "Asmall". Round-out wave 41.
    if type1_font.is_standard_encoding():
        assert type1_font.code_to_name(65) == "A"
    if type1_font.is_expert_encoding():
        assert type1_font.code_to_name(65) == "Asmall"


def test_from_cff_font_round_trip(type1_font: CFFType1Font) -> None:
    base = CFFFont()
    base._fontset = type1_font._fontset  # noqa: SLF001
    base._top = type1_font._top  # noqa: SLF001
    again = CFFType1Font.from_cff_font(base)
    assert again.is_cid_font() is False
    assert again.get_encoding() == type1_font.get_encoding()


def test_standard_encoding_predefined_resolves() -> None:
    """When a font reports StandardEncoding the wrapper resolves
    individual codes via the canonical Adobe Standard Encoding."""
    # Construct a minimal "looks-like-standard-encoding" Type1 by stubbing.
    class _Top:
        Encoding = "StandardEncoding"
        rawDict: dict = {}  # noqa: RUF012

    f = CFFType1Font()
    f._top = _Top()  # noqa: SLF001
    assert f.is_standard_encoding() is True
    assert f.code_to_name(65) == "A"
    assert f.code_to_name(32) == "space"
    # Round-trip name → code.
    assert f.name_to_code("A") == 65
    assert f.name_to_code("__bogus__") == -1


def test_expert_encoding_predefined_resolves() -> None:
    """ExpertEncoding code 65 maps to SID 253 → "asuperior" per
    Adobe Technote #5176 Appendix B (CFFExpertEncoding table)."""
    class _Top:
        Encoding = "ExpertEncoding"
        rawDict: dict = {}  # noqa: RUF012

    f = CFFType1Font()
    f._top = _Top()  # noqa: SLF001
    assert f.is_expert_encoding() is True
    assert f.code_to_name(65) == "asuperior"
    # Code 32 ("space") is in both Standard and Expert.
    assert f.code_to_name(32) == "space"
    # Unmapped code → .notdef.
    assert f.code_to_name(70) == ".notdef"
    # Round-trip.
    assert f.name_to_code("asuperior") == 65


def test_custom_encoding_array_round_trip() -> None:
    """A list-shaped /Encoding looks up codes by index and finds the
    code for a glyph name by linear scan."""
    class _Top:
        Encoding = [".notdef", "A", "B", "C"]
        rawDict: dict = {}  # noqa: RUF012

    f = CFFType1Font()
    f._top = _Top()  # noqa: SLF001
    assert f.is_custom_encoding() is True
    assert f.code_to_name(0) == ".notdef"
    assert f.code_to_name(1) == "A"
    assert f.code_to_name(2) == "B"
    assert f.name_to_code("C") == 3
    assert f.name_to_code("Z") == -1


def test_get_type1_char_string_returns_wrapper(type1_font: CFFType1Font) -> None:
    cs = type1_font.get_type1_char_string(".notdef")
    # Wrapper exposes get_path / get_width regardless of underlying state.
    assert hasattr(cs, "get_path")
    assert hasattr(cs, "get_width")
    # Unknown name routes to GID 0 (.notdef).
    cs2 = type1_font.get_type1_char_string("__no_such_glyph__")
    assert hasattr(cs2, "get_path")
