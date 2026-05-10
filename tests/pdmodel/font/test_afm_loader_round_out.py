"""Wave 263 round-out tests for :class:`AfmMetrics`.

Covers parity-aliasing accessors layered on top of the underlying
:class:`pypdfbox.fontbox.afm.FontMetrics` — ``get_character_width``,
``get_character_height``, ``get_char_metric`` / ``has_char_metric``,
``get_font_b_box`` / ``has_font_b_box``, ``get_italic_angle``,
``is_fixed_pitch``, and ``get_afm_version``.

These complement ``test_standard14_afm.py`` (width / descriptor dict)
and ``test_afm_loader_enriched.py`` (kern pairs / ligatures / headers)
by pinning down the upstream-shaped ``FontMetrics``-style surface
without re-routing through :meth:`AfmMetrics.get_font_metrics_object`.
"""
from __future__ import annotations

from pypdfbox.fontbox.afm import CharMetric
from pypdfbox.fontbox.ttf.glyph_data import BoundingBox
from pypdfbox.pdmodel.font.afm_loader import load_standard14

# ---------- get_character_width -------------------------------------------


def test_get_character_width_helvetica_a_matches_glyph_width() -> None:
    afm = load_standard14("Helvetica")
    assert afm.get_character_width("A") == 667.0
    assert afm.get_character_width("A") == afm.get_glyph_width("A")


def test_get_character_width_unknown_glyph_returns_zero() -> None:
    afm = load_standard14("Helvetica")
    assert afm.get_character_width("not-a-glyph") == 0.0


def test_get_character_width_courier_uniform_600() -> None:
    """Courier is monospaced — every defined glyph has WX 600."""
    afm = load_standard14("Courier")
    for name in ("A", "M", "i", "space", "period"):
        assert afm.get_character_width(name) == 600.0


# ---------- get_character_height ------------------------------------------


def test_get_character_height_helvetica_a_uses_bbox() -> None:
    """Helvetica WY is zero on every glyph, so height comes from the bbox."""
    afm = load_standard14("Helvetica")
    a_bbox = next(m for m in afm.get_char_metrics() if m.get_name() == "A").get_bounding_box()
    assert a_bbox is not None
    assert afm.get_character_height("A") == a_bbox.get_height()


def test_get_character_height_unknown_glyph_returns_zero() -> None:
    afm = load_standard14("Helvetica")
    assert afm.get_character_height("does-not-exist") == 0.0


def test_get_character_height_helvetica_space_zero() -> None:
    """``space`` has zero bbox in Helvetica.afm, so height should be 0."""
    afm = load_standard14("Helvetica")
    assert afm.get_character_height("space") == 0.0


# ---------- get_char_metric / has_char_metric -----------------------------


def test_get_char_metric_returns_typed_char_metric() -> None:
    afm = load_standard14("Helvetica")
    cm = afm.get_char_metric("A")
    assert isinstance(cm, CharMetric)
    assert cm.get_name() == "A"
    assert cm.get_wx() == 667.0


def test_get_char_metric_unknown_returns_none() -> None:
    afm = load_standard14("Helvetica")
    assert afm.get_char_metric("zzz-fake") is None


def test_get_char_metric_none_input_returns_none() -> None:
    """Parity with upstream — null-safe lookup so callers can chain off
    ``Encoding.getName(code)`` results without a pre-check."""
    afm = load_standard14("Helvetica")
    assert afm.get_char_metric(None) is None


def test_has_char_metric_for_present_and_absent() -> None:
    afm = load_standard14("Helvetica")
    assert afm.has_char_metric("A") is True
    assert afm.has_char_metric("not-real") is False


def test_has_char_metric_none_input_returns_false() -> None:
    afm = load_standard14("Helvetica")
    assert afm.has_char_metric(None) is False


# ---------- get_font_b_box / has_font_b_box -------------------------------


def test_get_font_b_box_returns_typed_bbox() -> None:
    afm = load_standard14("Helvetica")
    bbox = afm.get_font_b_box()
    assert isinstance(bbox, BoundingBox)
    # Helvetica.afm header: FontBBox -166 -225 1000 931
    assert int(bbox.get_lower_left_x()) == -166
    assert int(bbox.get_lower_left_y()) == -225
    assert int(bbox.get_upper_right_x()) == 1000
    assert int(bbox.get_upper_right_y()) == 931


def test_get_font_b_box_matches_descriptor_dict_tuple() -> None:
    afm = load_standard14("Times-Roman")
    bbox = afm.get_font_b_box()
    assert bbox is not None
    descriptor_tuple = afm.get_font_metrics()["FontBBox"]
    assert (
        int(bbox.get_lower_left_x()),
        int(bbox.get_lower_left_y()),
        int(bbox.get_upper_right_x()),
        int(bbox.get_upper_right_y()),
    ) == descriptor_tuple


def test_has_font_b_box_true_for_all_standard14() -> None:
    """All 14 Adobe AFMs declare a ``FontBBox`` header."""
    from pypdfbox.pdmodel.font.afm_loader import standard14_names

    for name in standard14_names():
        afm = load_standard14(name)
        assert afm.has_font_b_box() is True, name


# ---------- get_italic_angle ----------------------------------------------


def test_get_italic_angle_zero_for_helvetica() -> None:
    assert load_standard14("Helvetica").get_italic_angle() == 0.0


def test_get_italic_angle_negative_for_oblique() -> None:
    """Italic / oblique faces ship a negative ItalicAngle (clockwise)."""
    assert load_standard14("Helvetica-Oblique").get_italic_angle() == -12.0
    assert load_standard14("Times-Italic").get_italic_angle() == -15.5


def test_get_italic_angle_matches_descriptor_dict() -> None:
    afm = load_standard14("Times-BoldItalic")
    assert afm.get_italic_angle() == afm.get_font_metrics()["ItalicAngle"]


# ---------- is_fixed_pitch ------------------------------------------------


def test_is_fixed_pitch_true_for_courier_family() -> None:
    for name in (
        "Courier",
        "Courier-Bold",
        "Courier-Oblique",
        "Courier-BoldOblique",
    ):
        assert load_standard14(name).is_fixed_pitch() is True, name


def test_is_fixed_pitch_false_for_proportional_fonts() -> None:
    for name in (
        "Helvetica",
        "Times-Roman",
        "Symbol",
        "ZapfDingbats",
    ):
        assert load_standard14(name).is_fixed_pitch() is False, name


def test_is_fixed_pitch_matches_descriptor_dict() -> None:
    afm = load_standard14("Courier")
    assert afm.is_fixed_pitch() == afm.get_font_metrics()["IsFixedPitch"]


# ---------- get_afm_version -----------------------------------------------


def test_get_afm_version_is_4_1_for_all_standard14() -> None:
    """Adobe shipped all 14 Core AFMs at format version 4.1."""
    from pypdfbox.pdmodel.font.afm_loader import standard14_names

    for name in standard14_names():
        assert load_standard14(name).get_afm_version() == 4.1, name


def test_get_afm_version_matches_underlying_object() -> None:
    afm = load_standard14("Helvetica")
    assert afm.get_afm_version() == afm.get_font_metrics_object().get_afm_version()
