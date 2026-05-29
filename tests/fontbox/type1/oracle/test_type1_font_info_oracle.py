"""Live Apache PDFBox differential parity for the Type 1 ``/FontInfo`` and
top-level metadata facet (``pypdfbox.fontbox.type1.Type1Font``).

Distinct from ``test_type1_font_oracle.py`` (which exercises name / matrix /
encoding / per-glyph widths reached through a PDF): this probe loads a Type 1
``.pfb`` program *directly* via ``Type1Font.createWithPFB(byte[])`` and asserts
every cleartext metadata accessor — the textual ``/FontInfo`` fields
(``FullName`` / ``FamilyName`` / ``Weight`` / ``version`` / ``Notice`` /
``ItalicAngle`` / ``isFixedPitch`` / ``UnderlinePosition`` /
``UnderlineThickness``) plus the top-level numerics (``PaintType`` /
``FontType`` / ``UniqueID`` / ``StrokeWidth`` / ``FontBBox``).

``oracle/probes/Type1FontInfoProbe.java`` emits these as canonical ``KEY
VALUE`` lines from Apache PDFBox; :func:`_pypdfbox_lines` reproduces the same
lines from pypdfbox. The two must agree line-for-line, except numeric lines
which are compared with a small tolerance (PDFBox widens its ``float`` fields
to ``double`` on the way out).

Fixtures are the bundled hand-built Type 1 PFBs (permissive, generated for the
parity suite) with rich ``/FontInfo`` dicts and distinct ``/FontBBox`` values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.type1.type1_font import Type1Font
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "type1"

_PFBS = [
    "DemoType1.pfb",
    "CustomEncType1.pfb",
    "SeacType1.pfb",
    "CurvedFlexType1.pfb",
]

# Keys whose value is a single number (compared numerically).
_NUMERIC_KEYS = {
    "ITALICANGLE",
    "UNDERLINEPOSITION",
    "UNDERLINETHICKNESS",
    "STROKEWIDTH",
}
# Keys whose value is four numbers (the bbox) — may also be the literal "null".
_BBOX_KEY = "FONTBBOX"


def _canon_number(value: float) -> str:
    """Render a number the way the Java probe's ``canonNumber`` does:
    integral values as plain integers, otherwise the default repr."""
    if value == int(value):
        return str(int(value))
    return repr(float(value))


def _pypdfbox_lines(pfb_path: Path) -> list[str]:
    """Reproduce the probe's canonical lines from pypdfbox: load the .pfb
    directly and emit the metadata accessor rows in the same order."""
    t1 = Type1Font.create_with_pfb(pfb_path.read_bytes())
    lines = [
        f"FONTNAME {t1.get_font_name()}",
        f"FULLNAME {t1.get_full_name()}",
        f"FAMILYNAME {t1.get_family_name()}",
        f"WEIGHT {t1.get_weight()}",
        f"VERSION {t1.get_version()}",
        f"NOTICE {t1.get_notice()}",
        f"ITALICANGLE {_canon_number(t1.get_italic_angle())}",
        f"ISFIXEDPITCH {'true' if t1.is_fixed_pitch() else 'false'}",
        f"UNDERLINEPOSITION {_canon_number(t1.get_underline_position())}",
        f"UNDERLINETHICKNESS {_canon_number(t1.get_underline_thickness())}",
        f"PAINTTYPE {t1.get_paint_type()}",
        f"FONTTYPE {t1.get_font_type()}",
        f"UNIQUEID {t1.get_unique_id()}",
        f"STROKEWIDTH {_canon_number(t1.get_stroke_width())}",
    ]
    bbox = t1.get_font_bbox()
    if bbox is None:
        lines.append("FONTBBOX null")
    else:
        lines.append("FONTBBOX " + " ".join(_canon_number(v) for v in bbox))
    return lines


def _assert_lines_match(java: list[str], py: list[str]) -> None:
    """Compare key-by-key: numeric keys numerically, the rest verbatim."""
    assert len(py) == len(java)
    for jline, pline in zip(java, py, strict=True):
        jkey = jline.split(" ", 1)[0]
        pkey = pline.split(" ", 1)[0]
        assert pkey == jkey
        if jkey in _NUMERIC_KEYS:
            jval = float(jline.split(" ", 1)[1])
            pval = float(pline.split(" ", 1)[1])
            assert pval == pytest.approx(jval, abs=1e-6), f"{jkey}: {pval} != {jval}"
        elif jkey == _BBOX_KEY:
            jrest = jline.split(" ")[1:]
            prest = pline.split(" ")[1:]
            if jrest == ["null"]:
                assert prest == ["null"]
            else:
                assert len(prest) == len(jrest) == 4
                for a, b in zip(prest, jrest, strict=True):
                    assert float(a) == pytest.approx(float(b), abs=1e-6)
        else:
            assert pline == jline


@requires_oracle
@pytest.mark.parametrize("pfb_name", _PFBS)
def test_type1_font_info_matches_pdfbox(pfb_name: str) -> None:
    pfb_path = _FIXTURES / pfb_name
    assert pfb_path.is_file(), f"missing fixture: {pfb_path}"

    java = run_probe_text("Type1FontInfoProbe", str(pfb_path)).splitlines()
    py = _pypdfbox_lines(pfb_path)

    assert java, "PDFBox emitted no metadata lines"
    _assert_lines_match(java, py)


@requires_oracle
def test_demo_type1_font_info_values() -> None:
    """Spot-pin the discriminating textual /FontInfo values for DemoType1 so a
    regression in the cleartext parse is obvious even without diffing."""
    pfb_path = _FIXTURES / "DemoType1.pfb"
    java = run_probe_text("Type1FontInfoProbe", str(pfb_path)).splitlines()
    py = _pypdfbox_lines(pfb_path)

    assert "FULLNAME Demo Type1" in py
    assert "FAMILYNAME Demo" in py
    assert "WEIGHT Regular" in py
    assert "VERSION 001.001" in py
    # And those exact lines came from PDFBox too.
    for line in ("FULLNAME Demo Type1", "FAMILYNAME Demo", "WEIGHT Regular"):
        assert line in java
