from types import SimpleNamespace

import pytest

from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


class _MetricDescendant:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def get_glyph_width(self, cid: int) -> float:
        self.calls.append(("width", cid))
        return 640.0

    # PDFBOX-6175: per-glyph descendant methods take the raw code plus the
    # parent Type 0 font and resolve code -> CID through the parent.
    def get_height(self, code: int, parent: PDType0Font) -> float:
        self.calls.append(("height", parent.code_to_cid(code)))
        return -880.0

    def get_width_from_font(self, code: int, parent: PDType0Font) -> float:
        # no embedded program -> 0.0, as a real descendant answers
        return 0.0

    def get_vertical_displacement_vector_y(
        self, code: int, parent: PDType0Font
    ) -> float:
        # Upstream getVerticalDisplacementVectorY takes the raw *code* and
        # resolves code->CID itself; the parent passes the code through.
        self.calls.append(("vdvy", code))
        return -880.0

    def get_position_vector(
        self, code: int, parent: PDType0Font
    ) -> tuple[float, float]:
        self.calls.append(("vector", parent.code_to_cid(code)))
        return (120.0, -340.0)

    def has_glyph(self, code: int, parent: PDType0Font) -> bool:
        cid = parent.code_to_cid(code)
        self.calls.append(("glyph", cid))
        return cid == 42

    def get_average_font_width(self) -> float:
        return 512.0


def test_wave565_metric_accessors_delegate_after_cid_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    descendant = _MetricDescendant()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code + 40)
    monkeypatch.setattr(font, "is_vertical", lambda: True)

    assert font.has_glyph(2) is True
    assert font.get_width_from_font(2) == 0.0
    assert font.get_glyph_width(2) == 640.0
    assert font.get_height(2) == -880.0
    assert font.get_average_font_width() == 512.0
    # Vertical displacement now comes from get_vertical_displacement_vector_y
    # (the /W2 w1y metric with /DW2 fallback), passed the raw code 2 — not
    # get_height(cid). -880/1000 = -0.88.
    assert font.get_displacement(2) == (0.0, -0.88)
    assert font.get_position_vector(2) == (-0.12, 0.34)
    assert descendant.calls == [
        ("glyph", 42),
        ("width", 42),
        ("height", 42),
        ("vdvy", 2),
        ("vector", 42),
    ]


def test_wave565_metric_accessors_handle_missing_descendant() -> None:
    font = PDType0Font()

    assert font.has_glyph(1) is False
    assert font.get_width_from_font(1) == 0.0
    assert font.get_glyph_width(1) == 0.0
    assert font.get_height(1) == 0.0
    assert font.get_average_font_width() == 0.0
    assert font.get_displacement(1) == (0.0, 0.0)
    assert font.get_position_vector(1) == (0.0, 0.0)
    assert font.get_bounding_box() is None


def test_wave565_encode_string_falls_back_for_non_identity_or_missing_gsub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    plain_calls: list[str] = []
    monkeypatch.setattr(
        font,
        "get_cmap",
        lambda: SimpleNamespace(get_name=lambda: "Custom-H"),
    )
    monkeypatch.setattr(
        font,
        "encode",
        lambda text: plain_calls.append(str(text)) or b"plain",
    )

    assert font.encode_string("fi") == b"plain"
    assert plain_calls == ["fi"]

    monkeypatch.setattr(
        font,
        "get_cmap",
        lambda: SimpleNamespace(get_name=lambda: "Identity-H"),
    )
    monkeypatch.setattr(font, "_get_gsub_table", lambda: None)

    assert font.encode_string("fl") == b"plain"
    assert plain_calls == ["fi", "fl"]


def test_wave565_encode_string_emits_substituted_gids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(
        font,
        "get_cmap",
        lambda: SimpleNamespace(get_name=lambda: "Identity-H"),
    )
    monkeypatch.setattr(font, "_get_gsub_table", lambda: object())
    monkeypatch.setattr(font, "code_to_gid", lambda cp: cp - 60)
    monkeypatch.setattr(font, "apply_gsub_features", lambda gids: [321] if gids else [])

    assert font.encode_string("AB") == b"\x01A"


def test_wave565_embedded_cmap_fallback_handles_bad_best_cmap_and_finds_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    class InnerTTF(dict):
        def getGlyphOrder(self) -> list[str]:
            return [".notdef", "target"]

    descendant = PDCIDFontType2()
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code)
    monkeypatch.setattr(descendant, "is_embedded", lambda: True)
    monkeypatch.setattr(descendant, "code_to_gid", lambda _code, _parent: 1)

    broken_inner = InnerTTF(
        cmap=SimpleNamespace(
            getBestCmap=lambda: (_ for _ in ()).throw(AttributeError("bad"))
        )
    )
    monkeypatch.setattr(
        descendant,
        "get_true_type_font",
        lambda: SimpleNamespace(_tt=broken_inner),
    )
    assert font._unicode_from_embedded_cmap(7) is None

    good_inner = InnerTTF(cmap=SimpleNamespace(getBestCmap=lambda: {0x2603: "target"}))
    monkeypatch.setattr(
        descendant,
        "get_true_type_font",
        lambda: SimpleNamespace(_tt=good_inner),
    )
    assert font._unicode_from_embedded_cmap(7) == "\u2603"
