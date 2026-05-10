"""Enriched AfmMetrics surface — kern pairs, ligatures, header round-out.

The pre-existing ``test_standard14_afm.py`` covers width / font-descriptor
behaviour. This file exercises the new accessors added when the loader was
ported to the in-tree :class:`pypdfbox.fontbox.afm.AFMParser`.
"""
from __future__ import annotations

from pypdfbox.fontbox.afm import CharMetric, FontMetrics, KernPair, Ligature
from pypdfbox.pdmodel.font.afm_loader import load_standard14

# ---------- header parity round-out -----------------------------------------


def test_helvetica_header_full_set() -> None:
    afm = load_standard14("Helvetica")
    assert afm.get_full_name() == "Helvetica"
    assert afm.get_family_name() == "Helvetica"
    assert afm.get_weight() == "Medium"
    assert afm.get_font_version() == "002.000"
    assert afm.get_encoding_scheme() == "AdobeStandardEncoding"
    assert afm.get_character_set() == "ExtendedRoman"
    notice = afm.get_notice()
    assert notice is not None
    assert "Adobe Systems Incorporated" in notice


def test_helvetica_underline_metrics() -> None:
    afm = load_standard14("Helvetica")
    assert afm.get_underline_position() == -100.0
    assert afm.get_underline_thickness() == 50.0


def test_helvetica_stem_widths() -> None:
    afm = load_standard14("Helvetica")
    # StdHW / StdVW present in Helvetica.afm header.
    assert afm.get_standard_horizontal_width() == 76.0
    assert afm.get_standard_vertical_width() == 88.0


def test_helvetica_comments_round_trip() -> None:
    afm = load_standard14("Helvetica")
    comments = afm.get_comments()
    assert len(comments) == 4
    assert any("UniqueID 43054" in c for c in comments)


# ---------- char metrics / bounding boxes -----------------------------------


def test_helvetica_char_metric_count_matches_upstream() -> None:
    afm = load_standard14("Helvetica")
    metrics = afm.get_char_metrics()
    assert len(metrics) == 315  # upstream parity
    assert all(isinstance(m, CharMetric) for m in metrics)


def test_helvetica_space_char_metric() -> None:
    afm = load_standard14("Helvetica")
    space = next(
        (m for m in afm.get_char_metrics() if m.get_name() == "space"), None
    )
    assert space is not None
    assert space.get_character_code() == 32
    assert space.get_wx() == 278.0
    bbox = space.get_bounding_box()
    assert bbox is not None
    assert bbox.as_tuple() == (0.0, 0.0, 0.0, 0.0)
    assert space.get_ligatures() == []


def test_helvetica_ring_char_metric_bbox() -> None:
    afm = load_standard14("Helvetica")
    ring = next(
        (m for m in afm.get_char_metrics() if m.get_name() == "ring"), None
    )
    assert ring is not None
    assert ring.get_character_code() == 202
    assert ring.get_wx() == 333.0
    bbox = ring.get_bounding_box()
    assert bbox is not None
    assert bbox.as_tuple() == (75.0, 572.0, 259.0, 756.0)


# ---------- ligature coverage ------------------------------------------------


def test_helvetica_f_glyph_has_fi_and_fl_ligatures() -> None:
    """Helvetica.afm declares ``L i fi`` and ``L l fl`` on glyph ``f``."""
    afm = load_standard14("Helvetica")
    ligatures = afm.get_ligatures("f")
    assert len(ligatures) == 2
    assert all(isinstance(lig, Ligature) for lig in ligatures)
    pairs = {(lig.get_successor(), lig.get_ligature()) for lig in ligatures}
    assert pairs == {("i", "fi"), ("l", "fl")}


def test_get_ligatures_returns_empty_for_glyphs_without_any() -> None:
    afm = load_standard14("Helvetica")
    assert afm.get_ligatures("space") == []
    assert afm.get_ligatures("not-a-glyph") == []


def test_symbol_has_no_ligatures() -> None:
    """Adobe Symbol has no ligature ``L`` entries on any glyph."""
    afm = load_standard14("Symbol")
    for cm in afm.get_char_metrics():
        assert cm.get_ligatures() == []


# ---------- kern pair coverage ----------------------------------------------


def test_helvetica_kern_pairs_count_matches_upstream() -> None:
    afm = load_standard14("Helvetica")
    pairs = afm.get_kern_pairs()
    assert len(pairs) == 2705
    assert all(isinstance(p, KernPair) for p in pairs)


def _find_kern_pair(
    pairs: list[KernPair], first: str, second: str
) -> KernPair | None:
    return next(
        (p for p in pairs
         if p.get_first_kern_character() == first
         and p.get_second_kern_character() == second),
        None,
    )


def test_helvetica_known_kern_pair_a_ucircumflex() -> None:
    """``KPX A Ucircumflex -50`` from Helvetica.afm."""
    afm = load_standard14("Helvetica")
    pair = _find_kern_pair(afm.get_kern_pairs(), "A", "Ucircumflex")
    assert pair is not None
    assert pair.get_x() == -50.0
    assert pair.get_y() == 0.0  # KPX has zero y


def test_helvetica_known_kern_pair_w_agrave() -> None:
    """``KPX W agrave -40`` from Helvetica.afm."""
    afm = load_standard14("Helvetica")
    pair = _find_kern_pair(afm.get_kern_pairs(), "W", "agrave")
    assert pair is not None
    assert pair.get_x() == -40.0


def test_courier_has_no_kern_pairs() -> None:
    """Monospaced Courier has no StartKernData block at all."""
    afm = load_standard14("Courier")
    assert afm.get_kern_pairs() == []


# ---------- underlying FontMetrics object ----------------------------------


def test_get_font_metrics_object_is_typed_dataclass() -> None:
    afm = load_standard14("Helvetica")
    fm = afm.get_font_metrics_object()
    assert isinstance(fm, FontMetrics)
    assert fm.get_font_name() == "Helvetica"
    # AFM version on the StartFontMetrics line.
    assert fm.get_afm_version() == 4.1


def test_get_font_metrics_object_average_width_matches_helper() -> None:
    afm = load_standard14("Helvetica")
    fm = afm.get_font_metrics_object()
    # FontMetrics.get_average_character_width matches AfmMetrics helper.
    assert abs(fm.get_average_character_width() - afm.get_average_width()) < 1e-9


def test_get_font_metrics_object_kern_pairs0_and_1_empty() -> None:
    """Helvetica only uses StartKernPairs (writing-direction-agnostic)."""
    fm = load_standard14("Helvetica").get_font_metrics_object()
    assert fm.get_kern_pairs0() == []
    assert fm.get_kern_pairs1() == []
    assert fm.get_composites() == []


def test_get_font_metrics_object_is_fixed_v_default() -> None:
    """Helvetica has no VVector; IsFixedV defaults to ``False``."""
    fm = load_standard14("Helvetica").get_font_metrics_object()
    assert fm.get_v_vector() is None
    assert fm.get_is_fixed_v() is False
