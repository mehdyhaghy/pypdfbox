"""Live PDFBox differential parity for the AFM-parsed Standard-14 metrics.

This wave targets the FontBox ``org.apache.fontbox.afm.FontMetrics`` surface as
exposed through ``Standard14Fonts.getAFM(name)`` — the parsed Adobe Core-14 AFM
object, *not* the ``PDFont.getWidth`` advance path (covered by Std14Metrics /
FontMetrics probes) and *not* the Symbol/ZapfDingbats built-in encoding tables
(covered elsewhere). It pins:

* the AFM header strings — ``FontName`` / ``FullName`` / ``FamilyName`` /
  ``Weight`` / ``EncodingScheme`` / ``CharacterSet`` and the ``AFMVersion``;
* the vertical metrics — ``CapHeight`` / ``XHeight`` / ``Ascender`` /
  ``Descender`` / ``ItalicAngle`` / ``StdHW`` / ``StdVW`` plus the underline
  position/thickness;
* the font ``FontBBox``;
* every per-glyph ``CharMetric`` (glyph name, character code, ``WX`` advance,
  and the glyph bounding box) — the whole table, sorted by glyph name;
* the kern-pair list.

Crucially, upstream ``Standard14Fonts.getAFM`` parses with the *reduced* dataset
(``AFMParser.parse(true)``), so the kern-pair and composite blocks are skipped
and ``getKernPairs()`` is empty for the bundled Core-14 AFMs even though the AFM
files themselves ship thousands of ``KPX`` lines. pypdfbox's ``load_standard14``
must mirror that (``parse(reduced_dataset=True)``); this test asserts ``NKERN
0`` for all five faces, which is the part the live oracle locks in.

The ``AfmFontMetricsProbe`` output is reconstructed line-for-line on the Python
side from ``Standard14Fonts.get_afm(name).get_font_metrics_object()`` and
compared verbatim against Apache PDFBox 3.0.7.
"""

from __future__ import annotations

from pypdfbox.fontbox.afm.font_metrics import FontMetrics
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from tests.oracle.harness import requires_oracle, run_probe_text

# The 5 distinct AFM faces (matches AfmFontMetricsProbe.NAMES); the other 9
# Standard-14 fonts are bold/oblique siblings parsed from independent files.
_NAMES = ("Helvetica", "Times-Roman", "Courier", "Symbol", "ZapfDingbats")


def _fmt(value: float) -> str:
    """Canonical 4-decimal formatting; collapse -0.0 to 0.0 (probe parity)."""
    if value == 0.0:
        value = 0.0
    return f"{value:.4f}"


def _nz(value: str | None) -> str:
    return "" if value is None else value


def _bbox_fields(bbox: object) -> str:
    if bbox is None:
        return "NULL\tNULL\tNULL\tNULL"
    return "\t".join(
        _fmt(v)
        for v in (
            bbox.get_lower_left_x(),
            bbox.get_lower_left_y(),
            bbox.get_upper_right_x(),
            bbox.get_upper_right_y(),
        )
    )


def _emit(fm: FontMetrics) -> list[str]:
    lines: list[str] = [f"FONT\t{_nz(fm.get_font_name())}"]
    lines.append(
        "HDR\t"
        + "\t".join(
            [
                _fmt(fm.get_afm_version()),
                _nz(fm.get_full_name()),
                _nz(fm.get_family_name()),
                _nz(fm.get_weight()),
                _nz(fm.get_encoding_scheme()),
                _nz(fm.get_character_set()),
            ]
        )
    )
    lines.append(
        "VM\t"
        + "\t".join(
            _fmt(v)
            for v in (
                fm.get_cap_height(),
                fm.get_x_height(),
                fm.get_ascender(),
                fm.get_descender(),
                fm.get_italic_angle(),
                fm.get_standard_horizontal_width(),
                fm.get_standard_vertical_width(),
                fm.get_underline_position(),
                fm.get_underline_thickness(),
            )
        )
    )
    bbox = fm.get_font_b_box()
    lines.append("BBOX\tNULL" if bbox is None else f"BBOX\t{_bbox_fields(bbox)}")

    metrics = fm.get_char_metrics()
    kerns = fm.get_kern_pairs()
    lines.append(f"NCHAR\t{len(metrics)}")
    lines.append(f"NKERN\t{len(kerns)}")

    for cm in sorted(metrics, key=lambda m: _nz(m.get_name())):
        lines.append(
            "CM\t"
            + "\t".join(
                [
                    _nz(cm.get_name()),
                    str(cm.get_character_code()),
                    _fmt(cm.get_wx()),
                    _bbox_fields(cm.get_bounding_box()),
                ]
            )
        )

    for kp in sorted(
        kerns,
        key=lambda k: (
            _nz(k.get_first_kern_character()),
            _nz(k.get_second_kern_character()),
        ),
    ):
        lines.append(
            "KP\t"
            + "\t".join(
                [
                    _nz(kp.get_first_kern_character()),
                    _nz(kp.get_second_kern_character()),
                    _fmt(kp.get_x()),
                    _fmt(kp.get_y()),
                ]
            )
        )
    return lines


def _python_output() -> str:
    blocks: list[str] = []
    for name in _NAMES:
        fm = Standard14Fonts.get_afm(name).get_font_metrics_object()
        blocks.extend(_emit(fm))
    # PrintStream emits a trailing newline after the last line.
    return "\n".join(blocks) + "\n"


@requires_oracle
def test_afm_font_metrics_matches_pdfbox() -> None:
    java = run_probe_text("AfmFontMetricsProbe")
    assert _python_output() == java


@requires_oracle
def test_getafm_uses_reduced_dataset_no_kern_pairs() -> None:
    # Regression pin for the wave-1460 fix: upstream getAFM parses with the
    # reduced dataset, so getKernPairs() is empty for every bundled AFM even
    # though the files ship thousands of KPX lines.
    java = run_probe_text("AfmFontMetricsProbe")
    assert "NKERN\t0\n" in java
    for name in _NAMES:
        fm = Standard14Fonts.get_afm(name).get_font_metrics_object()
        assert fm.get_kern_pairs() == []
