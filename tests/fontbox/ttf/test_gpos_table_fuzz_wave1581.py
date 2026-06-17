"""Wave 1581 — synthetic-GPOS parity fuzz for :class:`GlyphPositioningTable`.

Hammers the GPOS kerning-extraction surface that upstream PDFBox does *not*
ship (FontBox 3.0.7 has no ``GlyphPositioningTable``), so parity here is against
the **documented OpenType GPOS contract** rather than a live Java oracle:

* Coverage format 1 (glyph list) and format 2 (range-based) — both decode to a
  fontTools ``Coverage.glyphs`` list; we round-trip through real bytes so
  fontTools actually picks each on-disk coverage format.
* ClassDef format 1 (start glyph + class array) and format 2 (class ranges) —
  likewise round-tripped so the on-disk ClassDef format is exercised.
* PairPos format 1 (per-glyph ``PairSet`` of ``PairValueRecord``) and format 2
  (``Class1Record × Class2Record`` matrix; ``class1*classCount + class2`` index
  math; the class-0 "everything not assigned" bucket of ``ClassDef2``).
* ``ValueRecord`` parsing under various ``ValueFormat`` flag bits — XAdvance
  present yields the kern, XAdvance absent (only XPlacement / YAdvance) yields 0,
  and a signed (negative) XAdvance survives intact.
* Empty / unsupported-lookup skipping (type 1 single-adjustment, type 4
  mark-to-base) and the type-9 extension unwrap for an offset-overflow-wrapped
  ``kern`` feature (wave-1581 real bug fix).
* The script -> feature -> lookup navigation chain
  (``get_supported_script_tags`` / ``get_supported_feature_tags`` /
  ``get_lookup_indices_for_feature``).

Most cases build a complete SFNT via ``FontBuilder`` and parse it back through
:class:`TTFParser` so the entire on-disk decode path (real coverage / classdef /
value formats fontTools chooses) is exercised end-to-end, not just direct
object construction.
"""

from __future__ import annotations

import io

from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables._g_l_y_f import Glyph
from fontTools.ttLib.tables.otBase import ValueRecord

from pypdfbox.fontbox.ttf.glyph_positioning_table import GlyphPositioningTable
from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

# X-advance ValueFormat bit (OT spec § ValueRecord).
_VF_X_ADVANCE = 0x0004
_VF_X_PLACEMENT = 0x0001
_VF_Y_ADVANCE = 0x0008


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def _mk_value(**fields: int) -> ValueRecord:
    """fontTools ``ValueRecord`` carrying exactly ``fields`` (mirrors the
    on-disk ``ValueFormat`` mask: only present fields are set)."""
    v = ValueRecord()
    for name, val in fields.items():
        setattr(v, name, val)
    return v


def _empty_glyf_font(glyphs: list[str]) -> FontBuilder:
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(glyphs)
    fb.setupCharacterMap(
        {ord("A") + i - 1: glyphs[i] for i in range(1, len(glyphs))}
    )
    fb.setupGlyf({g: Glyph() for g in glyphs})
    fb.setupHorizontalMetrics({g: (500, 0) for g in glyphs})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "T", "styleName": "R"})
    fb.setupOS2()
    fb.setupPost()
    return fb


def _script_list(script_tag: str = "DFLT") -> ot.ScriptList:
    sr = ot.ScriptRecord()
    sr.ScriptTag = script_tag
    script = ot.Script()
    lsys = ot.LangSys()
    lsys.LookupOrder = None
    lsys.ReqFeatureIndex = 0xFFFF
    lsys.FeatureIndex = [0]
    lsys.FeatureCount = 1
    script.DefaultLangSys = lsys
    script.LangSysRecord = []
    script.LangSysCount = 0
    sr.Script = script
    sl = ot.ScriptList()
    sl.ScriptRecord = [sr]
    sl.ScriptCount = 1
    return sl


def _feature_list(feature_tag: str = "kern") -> ot.FeatureList:
    fr = ot.FeatureRecord()
    fr.FeatureTag = feature_tag
    feat = ot.Feature()
    feat.FeatureParams = None
    feat.LookupListIndex = [0]
    feat.LookupCount = 1
    fr.Feature = feat
    fl = ot.FeatureList()
    fl.FeatureRecord = [fr]
    fl.FeatureCount = 1
    return fl


def _gpos_with_lookup(
    lookup: ot.Lookup,
    *,
    script_tag: str = "DFLT",
    feature_tag: str = "kern",
) -> ot.GPOS:
    gpos = ot.GPOS()
    gpos.Version = 0x00010000
    gpos.ScriptList = _script_list(script_tag)
    gpos.FeatureList = _feature_list(feature_tag)
    ll = ot.LookupList()
    ll.Lookup = [lookup]
    ll.LookupCount = 1
    gpos.LookupList = ll
    return gpos


def _parse_with_gpos(glyphs: list[str], gpos: ot.GPOS) -> GlyphPositioningTable:
    """Serialise a font carrying ``gpos`` then parse it back through the
    real pypdfbox TTF parser so the full on-disk decode path is exercised."""
    fb = _empty_glyf_font(glyphs)
    t = newTable("GPOS")
    t.table = gpos
    fb.font["GPOS"] = t
    buf = io.BytesIO()
    fb.font.save(buf)
    data = buf.getvalue()
    font = TTFParser(False).parse(RandomAccessReadBuffer(data))
    g = font.get_gpos()
    assert g is not None
    return g


def _bind_direct(glyphs: list[str], gpos: ot.GPOS) -> GlyphPositioningTable:
    """Bind a hand-built GPOS object directly (no byte round-trip)."""
    t = GlyphPositioningTable()
    t._gpos_table = gpos
    t._glyph_order = list(glyphs)
    t._glyph_name_to_gid = {n: i for i, n in enumerate(glyphs)}
    # Mirror populate_from_fonttools' tag harvest for the direct path.
    sl = gpos.ScriptList
    fl = gpos.FeatureList
    t._script_tags = (
        [str(sr.ScriptTag) for sr in sl.ScriptRecord] if sl else []
    )
    t._feature_tags = (
        [str(fr.FeatureTag).strip() for fr in fl.FeatureRecord] if fl else []
    )
    return t


def _pair_format1_lookup(
    coverage_glyphs: list[str],
    pairs_by_first: dict[str, list[tuple[str, ValueRecord]]],
) -> ot.Lookup:
    pp = ot.PairPos()
    pp.Format = 1
    cov = ot.Coverage()
    cov.glyphs = coverage_glyphs
    pp.Coverage = cov
    pp.ValueFormat1 = _VF_X_ADVANCE
    pp.ValueFormat2 = 0
    pair_sets = []
    for first in coverage_glyphs:
        ps = ot.PairSet()
        recs = []
        for second, value in pairs_by_first.get(first, []):
            pvr = ot.PairValueRecord()
            pvr.SecondGlyph = second
            pvr.Value1 = value
            pvr.Value2 = None
            recs.append(pvr)
        ps.PairValueRecord = recs
        ps.PairValueCount = len(recs)
        pair_sets.append(ps)
    pp.PairSet = pair_sets
    pp.PairSetCount = len(pair_sets)
    lk = ot.Lookup()
    lk.LookupType = 2
    lk.LookupFlag = 0
    lk.SubTable = [pp]
    lk.SubTableCount = 1
    return lk


def _pair_format2_lookup(
    coverage_glyphs: list[str],
    class_def_1: dict[str, int],
    class_def_2: dict[str, int],
    matrix: dict[tuple[int, int], int],
    class1_count: int,
    class2_count: int,
) -> ot.Lookup:
    pp = ot.PairPos()
    pp.Format = 2
    cov = ot.Coverage()
    cov.glyphs = coverage_glyphs
    pp.Coverage = cov
    cd1 = ot.ClassDef()
    cd1.classDefs = dict(class_def_1)
    cd2 = ot.ClassDef()
    cd2.classDefs = dict(class_def_2)
    pp.ClassDef1 = cd1
    pp.ClassDef2 = cd2
    pp.Class1Count = class1_count
    pp.Class2Count = class2_count
    pp.ValueFormat1 = _VF_X_ADVANCE
    pp.ValueFormat2 = 0
    c1recs = []
    for c1 in range(class1_count):
        rec = ot.Class1Record()
        c2recs = []
        for c2 in range(class2_count):
            cr = ot.Class2Record()
            cr.Value1 = _mk_value(XAdvance=matrix.get((c1, c2), 0))
            cr.Value2 = None
            c2recs.append(cr)
        rec.Class2Record = c2recs
        c1recs.append(rec)
    pp.Class1Record = c1recs
    lk = ot.Lookup()
    lk.LookupType = 2
    lk.LookupFlag = 0
    lk.SubTable = [pp]
    lk.SubTableCount = 1
    return lk


# --------------------------------------------------------------------------- #
# Format 1 — per-glyph PairSet (Coverage format 1)
# --------------------------------------------------------------------------- #
def test_format1_pair_positive_kern() -> None:
    glyphs = [".notdef", "A", "V", "W"]
    gid = {n: i for i, n in enumerate(glyphs)}
    lk = _pair_format1_lookup(
        ["A"], {"A": [("V", _mk_value(XAdvance=-80)), ("W", _mk_value(XAdvance=30))]}
    )
    g = _parse_with_gpos(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["V"]) == -80
    assert g.get_kerning(gid["A"], gid["W"]) == 30


def test_format1_unknown_pair_is_zero() -> None:
    glyphs = [".notdef", "A", "V", "W"]
    gid = {n: i for i, n in enumerate(glyphs)}
    lk = _pair_format1_lookup(["A"], {"A": [("V", _mk_value(XAdvance=-80))]})
    g = _parse_with_gpos(glyphs, _gpos_with_lookup(lk))
    # Pair not covered -> 0.
    assert g.get_kerning(gid["A"], gid["W"]) == 0
    # Reversed pair not covered -> 0.
    assert g.get_kerning(gid["V"], gid["A"]) == 0


def test_format1_multiple_coverage_glyphs() -> None:
    glyphs = [".notdef", "A", "T", "V", "W"]
    gid = {n: i for i, n in enumerate(glyphs)}
    lk = _pair_format1_lookup(
        ["A", "T"],
        {
            "A": [("V", _mk_value(XAdvance=-50))],
            "T": [("W", _mk_value(XAdvance=20)), ("V", _mk_value(XAdvance=-15))],
        },
    )
    g = _parse_with_gpos(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["V"]) == -50
    assert g.get_kerning(gid["T"], gid["W"]) == 20
    assert g.get_kerning(gid["T"], gid["V"]) == -15
    assert g.get_kerning(gid["A"], gid["W"]) == 0


def test_format1_negative_value_signed() -> None:
    glyphs = [".notdef", "A", "V"]
    gid = {n: i for i, n in enumerate(glyphs)}
    lk = _pair_format1_lookup(["A"], {"A": [("V", _mk_value(XAdvance=-200))]})
    g = _parse_with_gpos(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["V"]) == -200


# --------------------------------------------------------------------------- #
# ValueFormat flag bits
# --------------------------------------------------------------------------- #
def test_value_format_without_x_advance_is_zero() -> None:
    """A ValueRecord carrying only XPlacement (no XAdvance bit) yields 0."""
    glyphs = [".notdef", "A", "V"]
    gid = {n: i for i, n in enumerate(glyphs)}
    pp = ot.PairPos()
    pp.Format = 1
    cov = ot.Coverage()
    cov.glyphs = ["A"]
    pp.Coverage = cov
    pp.ValueFormat1 = _VF_X_PLACEMENT  # only placement, no advance
    pp.ValueFormat2 = 0
    ps = ot.PairSet()
    pvr = ot.PairValueRecord()
    pvr.SecondGlyph = "V"
    pvr.Value1 = _mk_value(XPlacement=99)
    pvr.Value2 = None
    ps.PairValueRecord = [pvr]
    ps.PairValueCount = 1
    pp.PairSet = [ps]
    pp.PairSetCount = 1
    lk = ot.Lookup()
    lk.LookupType = 2
    lk.LookupFlag = 0
    lk.SubTable = [pp]
    lk.SubTableCount = 1
    g = _parse_with_gpos(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["V"]) == 0
    assert g.has_kerning() is False


def test_value_format_y_advance_only_is_zero() -> None:
    """Only the XAdvance component is surfaced; YAdvance alone yields 0."""
    glyphs = [".notdef", "A", "V"]
    gid = {n: i for i, n in enumerate(glyphs)}
    pp = ot.PairPos()
    pp.Format = 1
    cov = ot.Coverage()
    cov.glyphs = ["A"]
    pp.Coverage = cov
    pp.ValueFormat1 = _VF_Y_ADVANCE
    pp.ValueFormat2 = 0
    ps = ot.PairSet()
    pvr = ot.PairValueRecord()
    pvr.SecondGlyph = "V"
    pvr.Value1 = _mk_value(YAdvance=77)
    pvr.Value2 = None
    ps.PairValueRecord = [pvr]
    ps.PairValueCount = 1
    pp.PairSet = [ps]
    pp.PairSetCount = 1
    lk = ot.Lookup()
    lk.LookupType = 2
    lk.LookupFlag = 0
    lk.SubTable = [pp]
    lk.SubTableCount = 1
    g = _parse_with_gpos(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["V"]) == 0


def test_extract_x_advance_none_record() -> None:
    assert GlyphPositioningTable._extract_x_advance(None) == 0


def test_extract_x_advance_missing_attr() -> None:
    assert GlyphPositioningTable._extract_x_advance(_mk_value(XPlacement=5)) == 0


def test_extract_x_advance_negative() -> None:
    assert GlyphPositioningTable._extract_x_advance(_mk_value(XAdvance=-42)) == -42


# --------------------------------------------------------------------------- #
# Format 2 — class-based (ClassDef + Class1×Class2 matrix)
# --------------------------------------------------------------------------- #
def test_format2_class_matrix_index_math() -> None:
    """``class1*classCount + class2`` cell selection, round-tripped through
    real bytes so the on-disk Coverage/ClassDef formats are exercised."""
    glyphs = [".notdef"] + [chr(ord("A") + i) for i in range(20)]
    gid = {n: i for i, n in enumerate(glyphs)}
    lk = _pair_format2_lookup(
        coverage_glyphs=["A", "B", "C", "D", "E"],
        class_def_1={"A": 1, "B": 1, "C": 2, "D": 2, "E": 2},
        class_def_2={g: 1 for g in ["F", "G", "H", "I", "J"]},
        matrix={(c1, c2): 100 * c1 + c2 for c1 in range(3) for c2 in range(2)},
        class1_count=3,
        class2_count=2,
    )
    g = _parse_with_gpos(glyphs, _gpos_with_lookup(lk))
    # A: c1=1, F: c2=1 -> 100*1 + 1 = 101
    assert g.get_kerning(gid["A"], gid["F"]) == 101
    # C: c1=2, G: c2=1 -> 201
    assert g.get_kerning(gid["C"], gid["G"]) == 201
    # B (c1=1) vs J (c2=1) -> 101
    assert g.get_kerning(gid["B"], gid["J"]) == 101


def test_format2_class0_second_glyph_bucket() -> None:
    """A second glyph not listed in ClassDef2 falls in class 0 — the
    'everything not assigned' bucket — and picks the c2=0 cell."""
    glyphs = [".notdef"] + [chr(ord("A") + i) for i in range(20)]
    gid = {n: i for i, n in enumerate(glyphs)}
    lk = _pair_format2_lookup(
        coverage_glyphs=["A"],
        class_def_1={"A": 1},
        class_def_2={"F": 1},
        matrix={(1, 0): 500, (1, 1): 600},
        class1_count=2,
        class2_count=2,
    )
    g = _parse_with_gpos(glyphs, _gpos_with_lookup(lk))
    # K is not in ClassDef2 -> class 0 -> cell (1,0) = 500.
    assert g.get_kerning(gid["A"], gid["K"]) == 500
    # F is class 1 -> cell (1,1) = 600.
    assert g.get_kerning(gid["A"], gid["F"]) == 600


def test_format2_first_glyph_class0_default() -> None:
    """A coverage glyph not listed in ClassDef1 is class 0 (default)."""
    glyphs = [".notdef", "A", "B", "F", "G"]
    gid = {n: i for i, n in enumerate(glyphs)}
    # A,B are in coverage; only B mapped in ClassDef1 -> A is class 0.
    lk = _pair_format2_lookup(
        coverage_glyphs=["A", "B"],
        class_def_1={"B": 1},
        class_def_2={"F": 1},
        matrix={(0, 1): 11, (1, 1): 22},
        class1_count=2,
        class2_count=2,
    )
    g = _bind_direct(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["F"]) == 11  # class1=0
    assert g.get_kerning(gid["B"], gid["F"]) == 22  # class1=1


def test_format2_zero_cell_skipped() -> None:
    glyphs = [".notdef", "A", "F", "G"]
    gid = {n: i for i, n in enumerate(glyphs)}
    lk = _pair_format2_lookup(
        coverage_glyphs=["A"],
        class_def_1={"A": 1},
        class_def_2={"F": 1, "G": 2},
        matrix={(1, 1): 0, (1, 2): 40},  # cell (1,1) is zero -> skipped
        class1_count=2,
        class2_count=3,
    )
    g = _bind_direct(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["F"]) == 0
    assert g.get_kerning(gid["A"], gid["G"]) == 40


def test_format2_out_of_range_class1_skipped() -> None:
    """A coverage glyph whose ClassDef1 class exceeds the Class1Record count
    is skipped rather than indexing out of range."""
    glyphs = [".notdef", "A", "F"]
    gid = {n: i for i, n in enumerate(glyphs)}
    lk = _pair_format2_lookup(
        coverage_glyphs=["A"],
        class_def_1={"A": 9},  # class 9 but only 2 Class1Records
        class_def_2={"F": 1},
        matrix={(0, 1): 12, (1, 1): 13},
        class1_count=2,
        class2_count=2,
    )
    g = _bind_direct(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["F"]) == 0


# --------------------------------------------------------------------------- #
# Type 9 extension unwrap (wave-1581 real bug fix)
# --------------------------------------------------------------------------- #
def _extension_lookup(inner_pair_lookup: ot.Lookup, ext_target: int = 2) -> ot.Lookup:
    inner_sub = inner_pair_lookup.SubTable[0]
    ext = ot.ExtensionPos()
    ext.Format = 1
    ext.ExtensionLookupType = ext_target
    ext.ExtSubTable = inner_sub
    lk = ot.Lookup()
    lk.LookupType = 9
    lk.LookupFlag = 0
    lk.SubTable = [ext]
    lk.SubTableCount = 1
    return lk


def test_type9_extension_wraps_pairpos_format1() -> None:
    glyphs = [".notdef", "A", "V"]
    gid = {n: i for i, n in enumerate(glyphs)}
    inner = _pair_format1_lookup(["A"], {"A": [("V", _mk_value(XAdvance=-25))]})
    lk = _extension_lookup(inner)
    g = _bind_direct(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["V"]) == -25
    assert g.has_kerning() is True


def test_type9_extension_roundtrip_bytes() -> None:
    """Full byte round-trip: fontTools keeps LookupType=9, ExtSubTable holds
    the wrapped PairPos; the kern must still surface."""
    glyphs = [".notdef", "A", "V"]
    gid = {n: i for i, n in enumerate(glyphs)}
    inner = _pair_format1_lookup(["A"], {"A": [("V", _mk_value(XAdvance=-33))]})
    lk = _extension_lookup(inner)
    g = _parse_with_gpos(glyphs, _gpos_with_lookup(lk))
    assert g.get_lookup_types() == [9]
    assert g.get_kerning(gid["A"], gid["V"]) == -33


def test_type9_extension_wraps_non_pair_ignored() -> None:
    """A type-9 lookup whose ExtensionLookupType is not 2 contributes no
    kerning pairs."""
    glyphs = [".notdef", "A", "V"]
    gid = {n: i for i, n in enumerate(glyphs)}
    inner = _pair_format1_lookup(["A"], {"A": [("V", _mk_value(XAdvance=-25))]})
    lk = _extension_lookup(inner, ext_target=1)  # claims to wrap a Single (type 1)
    g = _bind_direct(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["V"]) == 0


def test_type9_extension_wraps_format2() -> None:
    glyphs = [".notdef", "A", "B", "F", "G"]
    gid = {n: i for i, n in enumerate(glyphs)}
    inner = _pair_format2_lookup(
        coverage_glyphs=["A"],
        class_def_1={"A": 1},
        class_def_2={"F": 1},
        matrix={(1, 1): 70},
        class1_count=2,
        class2_count=2,
    )
    lk = _extension_lookup(inner)
    g = _bind_direct(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["F"]) == 70


# --------------------------------------------------------------------------- #
# Unsupported / empty lookups
# --------------------------------------------------------------------------- #
def test_single_adjustment_lookup_no_kerning() -> None:
    """A type-1 (single adjustment) lookup contributes no pair kerning."""
    glyphs = [".notdef", "A", "V"]
    gid = {n: i for i, n in enumerate(glyphs)}
    sp = ot.SinglePos()
    sp.Format = 1
    cov = ot.Coverage()
    cov.glyphs = ["A"]
    sp.Coverage = cov
    sp.ValueFormat = _VF_X_ADVANCE
    sp.Value = _mk_value(XAdvance=100)
    lk = ot.Lookup()
    lk.LookupType = 1
    lk.LookupFlag = 0
    lk.SubTable = [sp]
    lk.SubTableCount = 1
    g = _bind_direct(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["V"]) == 0
    assert g.has_kerning() is False
    assert g.get_lookup_types() == [1]


def test_mark_to_base_lookup_skipped() -> None:
    """A type-4 mark-to-base lookup is skipped by the kerning builder."""
    glyphs = [".notdef", "A", "V"]
    gid = {n: i for i, n in enumerate(glyphs)}
    lk = ot.Lookup()
    lk.LookupType = 4
    lk.LookupFlag = 0
    lk.SubTable = []
    lk.SubTableCount = 0
    g = _bind_direct(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["V"]) == 0
    assert g.has_kerning() is False


def test_empty_lookup_list_no_kerning() -> None:
    glyphs = [".notdef", "A", "V"]
    gid = {n: i for i, n in enumerate(glyphs)}
    gpos = ot.GPOS()
    gpos.Version = 0x00010000
    gpos.ScriptList = _script_list()
    gpos.FeatureList = _feature_list()
    ll = ot.LookupList()
    ll.Lookup = []
    ll.LookupCount = 0
    gpos.LookupList = ll
    g = _bind_direct(glyphs, gpos)
    assert g.get_kerning(gid["A"], gid["V"]) == 0
    assert g.get_lookup_count() == 0
    assert g.get_lookup_types() == []


# --------------------------------------------------------------------------- #
# Sentinel / boundary inputs
# --------------------------------------------------------------------------- #
def test_negative_gid_short_circuits_to_zero() -> None:
    glyphs = [".notdef", "A", "V"]
    gid = {n: i for i, n in enumerate(glyphs)}
    lk = _pair_format1_lookup(["A"], {"A": [("V", _mk_value(XAdvance=-25))]})
    g = _bind_direct(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(-1, gid["V"]) == 0
    assert g.get_kerning(gid["A"], -1) == 0


def test_no_gpos_table_kerning_zero() -> None:
    g = GlyphPositioningTable()
    assert g.get_kerning(1, 2) == 0
    assert g.has_kerning() is False
    assert g.get_lookup_count() == 0
    assert g.get_lookup_types() == []


# --------------------------------------------------------------------------- #
# Script -> feature -> lookup navigation chain
# --------------------------------------------------------------------------- #
def test_script_feature_lookup_navigation_roundtrip() -> None:
    glyphs = [".notdef", "A", "V"]
    gid = {n: i for i, n in enumerate(glyphs)}
    inner = _pair_format1_lookup(["A"], {"A": [("V", _mk_value(XAdvance=-25))]})
    g = _parse_with_gpos(
        glyphs, _gpos_with_lookup(inner, script_tag="latn", feature_tag="kern")
    )
    assert g.get_supported_script_tags() == {"latn"}
    assert g.get_supported_feature_tags() == ["kern"]
    assert g.get_lookup_count() == 1
    assert g.get_lookup_types() == [2]
    assert g.get_lookup_indices_for_feature("kern") == [0]
    assert g.get_lookup_indices_for_feature("liga") == []
    # The lookup referenced by the kern feature actually kerns.
    assert g.get_kerning(gid["A"], gid["V"]) == -25


def test_feature_record_and_subtable_accessors() -> None:
    glyphs = [".notdef", "A", "V"]
    inner = _pair_format1_lookup(["A"], {"A": [("V", _mk_value(XAdvance=-25))]})
    g = _parse_with_gpos(glyphs, _gpos_with_lookup(inner))
    fr = g.get_feature_record(0)
    assert fr is not None
    assert str(fr.FeatureTag).strip() == "kern"
    subs = g.get_lookup_subtables(0)
    assert len(subs) == 1
    assert int(subs[0].Format) == 1
    assert g.get_lookup(0) is not None
    assert g.get_lookup(5) is None
    assert g.get_lookup_subtables(5) == []
    assert g.get_feature_record(5) is None


def test_scriptlist_featurelist_lookuplist_present() -> None:
    glyphs = [".notdef", "A", "V"]
    inner = _pair_format1_lookup(["A"], {"A": [("V", _mk_value(XAdvance=-25))]})
    g = _parse_with_gpos(glyphs, _gpos_with_lookup(inner))
    assert g.get_script_list() is not None
    assert g.get_feature_list() is not None
    assert g.get_lookup_list() is not None
    assert g.get_raw_table() is not None


# --------------------------------------------------------------------------- #
# Two lookups, last-write-wins / union of kerning sources
# --------------------------------------------------------------------------- #
def test_two_pair_subtables_union() -> None:
    """Two PairPos subtables in one lookup both contribute; a later subtable
    overrides an earlier value for the same pair (last-write-wins)."""
    glyphs = [".notdef", "A", "V", "W"]
    gid = {n: i for i, n in enumerate(glyphs)}
    pp1 = _pair_format1_lookup(
        ["A"], {"A": [("V", _mk_value(XAdvance=-10)), ("W", _mk_value(XAdvance=5))]}
    ).SubTable[0]
    pp2 = _pair_format1_lookup(["A"], {"A": [("V", _mk_value(XAdvance=-99))]}).SubTable[
        0
    ]
    lk = ot.Lookup()
    lk.LookupType = 2
    lk.LookupFlag = 0
    lk.SubTable = [pp1, pp2]
    lk.SubTableCount = 2
    g = _bind_direct(glyphs, _gpos_with_lookup(lk))
    assert g.get_kerning(gid["A"], gid["V"]) == -99  # overridden by pp2
    assert g.get_kerning(gid["A"], gid["W"]) == 5  # only in pp1


def test_kerning_cached_across_calls() -> None:
    glyphs = [".notdef", "A", "V"]
    gid = {n: i for i, n in enumerate(glyphs)}
    lk = _pair_format1_lookup(["A"], {"A": [("V", _mk_value(XAdvance=-25))]})
    g = _bind_direct(glyphs, _gpos_with_lookup(lk))
    assert g._kerning_pairs is None
    first = g.get_kerning(gid["A"], gid["V"])
    assert g._kerning_pairs is not None
    second = g.get_kerning(gid["A"], gid["V"])
    assert first == second == -25


def test_fontbuilder_import_available() -> None:
    # Guards the test-only deps so a missing optional fontTools sub-module
    # fails loud here rather than mid-parametrize.
    assert TTFont is not None
    assert FontBuilder is not None
