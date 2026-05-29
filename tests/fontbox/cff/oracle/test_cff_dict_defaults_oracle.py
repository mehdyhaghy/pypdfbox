"""Live Apache PDFBox differential parity for fontbox **CFF Top/Private
DICT operator defaults** and the ``/FontMatrix``.

Per Adobe Technote #5176 Tables 9 & 23 several DICT operators carry an
implicit default applied when the operator is absent. Apache FontBox's
``CFFParser.parseFont`` materialises those defaults into the maps it
later exposes via ``CFFFont.getTopDict()`` and
``CFFType1Font.getPrivateDict()`` — so even when the byte stream omits
``/FontMatrix`` the resolved Top DICT map carries ``[0.001 0 0 0.001 0
0]``; an omitted ``/defaultWidthX`` comes back as ``0``. The hint
operators ``/BlueValues`` / ``/StdHW`` / ``/StdVW`` carry *no* default,
so an omission stays ``null`` / ``None``.

That default-materialisation boundary is the differential target. A
parser that returns only the operators physically present (the natural
fontTools ``rawDict`` view) would diverge from PDFBox here: PDFBox's
``getTopDict().get("FontMatrix")`` is non-null even for a font that
never wrote the operator, while a raw view would report ``null``. Two
synthetic name-keyed CFFs (see
``tests/fixtures/fontbox/cff/make_dict_defaults_fixtures.py``) cover
both sides:

* ``dict_defaults_absent.cff`` — omits every defaulted operator; the
  resolved maps must come back stamped with the canonical defaults.
* ``dict_defaults_present.cff`` — sets every operator to a non-default
  value; the resolved maps must carry the explicit values.

Numeric values are compared after normalising each token to ``float``,
because Java's ``Double.toString`` renders ``0.0005`` as ``5.0E-4``
while Python renders it ``0.0005`` — a textual artefact, not a parity
divergence. The resolved getters
(``getFontMatrix()`` / ``getFontBBox()``) are pinned alongside the raw
maps so the default flows through both the convenience accessor and
the DICT snapshot.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.fontbox.cff.cff_parser import CFFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO = Path(__file__).resolve().parents[4]
_CFF_FIXTURES = _REPO / "tests" / "fixtures" / "fontbox" / "cff"

_ABSENT_CFF = _CFF_FIXTURES / "dict_defaults_absent.cff"
_PRESENT_CFF = _CFF_FIXTURES / "dict_defaults_present.cff"

_PRIV_KEYS = ("defaultWidthX", "nominalWidthX", "BlueValues", "StdHW", "StdVW")


# --------------------------------------------------------------------------- #
# Probe-line parsing — see oracle/probes/CffDictDefaultsProbe.java for schema.
# --------------------------------------------------------------------------- #


def _parse_probe(text: str) -> dict[str, object]:
    facts: dict[str, object] = {"priv": {}}
    for line in text.splitlines():
        cols = line.split("\t")
        tag = cols[0]
        if tag == "NAME" and len(cols) >= 2:
            facts["name"] = cols[1]
        elif tag == "FONTMATRIX" and len(cols) >= 2:
            facts["font_matrix"] = cols[1]
        elif tag == "FM_RAW" and len(cols) >= 2:
            facts["fm_raw"] = cols[1]
        elif tag == "FONTBBOX" and len(cols) >= 2:
            facts["font_bbox"] = cols[1]
        elif tag == "BBOX_RAW" and len(cols) >= 2:
            facts["bbox_raw"] = cols[1]
        elif tag == "TOP" and len(cols) >= 3 and cols[1] == "CharstringType":
            facts["charstring_type"] = cols[2]
        elif tag == "PRIV" and len(cols) >= 3:
            facts["priv"][cols[1]] = cols[2]  # type: ignore[index]
    return facts


def _norm_numlist(value: object) -> object:
    """Normalise a number / number-list (or the ``<null>`` sentinel) so a
    Java ``5.0E-4`` token and a Python ``0.0005`` repr compare equal.

    Returns ``None`` for the ``<null>`` / ``None`` sentinel, a tuple of
    floats for a list-shaped value, and a single float otherwise.
    """
    if value is None or value == "<null>":
        return None
    if isinstance(value, str):
        parts = value.split()
        if len(parts) > 1:
            return tuple(float(p) for p in parts)
        return float(parts[0])
    if isinstance(value, (list, tuple)):
        return tuple(float(v) for v in value)
    return float(value)


def _py_facts(data: bytes) -> dict[str, object]:
    font = CFFParser().parse(data)[0]
    top = font.get_top_dict()
    priv = font.get_private_dict()
    return {
        "name": font.get_name(),
        "font_matrix": font.get_font_matrix(),
        "fm_raw": top.get("FontMatrix"),
        "font_bbox": font.get_font_b_box(),
        "bbox_raw": top.get("FontBBox"),
        "charstring_type": top.get("CharstringType"),
        "priv": {key: priv.get(key) for key in _PRIV_KEYS},
    }


def _assert_parity(probe_text: str, data: bytes) -> None:
    java = _parse_probe(probe_text)
    py = _py_facts(data)

    assert py["name"] == java["name"], ("name", py["name"], java["name"])

    for key in ("font_matrix", "fm_raw", "font_bbox", "bbox_raw", "charstring_type"):
        pj = _norm_numlist(java[key])
        pp = _norm_numlist(py[key])
        assert pp == pj, (key, pp, pj)

    java_priv = java["priv"]  # type: ignore[assignment]
    py_priv = py["priv"]  # type: ignore[assignment]
    for key in _PRIV_KEYS:
        pj = _norm_numlist(java_priv[key])  # type: ignore[index]
        pp = _norm_numlist(py_priv[key])  # type: ignore[index]
        assert pp == pj, ("priv", key, pp, pj)


# --------------------------------------------------------------------------- #
# Differential tests.
# --------------------------------------------------------------------------- #


@requires_oracle
def test_absent_operators_stamp_defaults_match_pdfbox() -> None:
    """Every defaulted operator is physically absent; PDFBox's
    ``getTopDict()`` / ``getPrivateDict()`` come back stamped with the
    canonical defaults (FontMatrix ``[0.001 0 0 0.001 0 0]``, FontBBox
    ``[0 0 0 0]``, CharstringType ``2``, defaultWidthX / nominalWidthX
    ``0``) while the hint operators stay absent. pypdfbox must
    materialise the same defaults — a raw ``rawDict`` view would report
    ``None`` and diverge."""
    data = _ABSENT_CFF.read_bytes()
    probe = run_probe_text("CffDictDefaultsProbe", str(_ABSENT_CFF))
    _assert_parity(probe, data)


@requires_oracle
def test_present_operators_carry_explicit_values_match_pdfbox() -> None:
    """Every operator is set to a non-default value; the resolved maps
    must carry the explicit value, never the parser-stamped default.
    Pins that the default-stamping never clobbers a present operator and
    that the hint operators (BlueValues/StdHW/StdVW) flow through
    unchanged."""
    data = _PRESENT_CFF.read_bytes()
    probe = run_probe_text("CffDictDefaultsProbe", str(_PRESENT_CFF))
    _assert_parity(probe, data)


@requires_oracle
def test_font_matrix_getter_matches_raw_default() -> None:
    """``CFFFont.get_font_matrix()`` (PDFBox: ``getFontMatrix()``) and the
    raw ``getTopDict().get("FontMatrix")`` snapshot must agree, both for
    an absent operator (default materialised) and a present one. Pins the
    contract that the convenience accessor and the DICT map never drift."""
    for fixture in (_ABSENT_CFF, _PRESENT_CFF):
        font = CFFParser().parse(fixture.read_bytes())[0]
        getter = _norm_numlist(font.get_font_matrix())
        raw = _norm_numlist(font.get_top_dict().get("FontMatrix"))
        assert getter == raw, (fixture.name, getter, raw)
