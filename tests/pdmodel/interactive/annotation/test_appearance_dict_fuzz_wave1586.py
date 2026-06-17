"""Fuzz / parity hammering of the annotation appearance-dictionary surface.

Wave 1586, Agent E. Targets PDAppearanceDictionary, PDAppearanceEntry, and the
PDAnnotation /AP /AS /Rect handling against the behaviour of upstream PDFBox
3.0.7:

* ``PDAppearanceDictionary.PDAppearanceDictionary.java`` — get_normal /
  get_rollover / get_down with the spec-mandated /N fallback.
* ``PDAppearanceEntry.java`` — ``isSubDictionary() == !(entry instanceof
  COSStream)`` and ``isStream() == entry instanceof COSStream`` (stream check
  first, because COSStream extends COSDictionary); getSubDictionary skips
  non-stream values (PDFBOX-1599 /null guard).
* ``PDAnnotation.java`` — getAppearance / getNormalAppearanceStream (/AS state
  selection) / getRectangle (exactly-4 numeric entries, then PDRectangle min/max
  normalization of reversed corners).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_entry import (
    PDAppearanceEntry,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_N = COSName.get_pdf_name("N")
_R = COSName.get_pdf_name("R")
_D = COSName.get_pdf_name("D")
_AP = COSName.get_pdf_name("AP")
_AS = COSName.get_pdf_name("AS")
_RECT = COSName.get_pdf_name("Rect")


def _stream() -> COSStream:
    return COSStream()


def _ap_with(n_value: COSStream | COSDictionary) -> PDAppearanceDictionary:
    ap = COSDictionary()
    ap.set_item(_N, n_value)
    return PDAppearanceDictionary(ap)


def _annot(**items: COSDictionary | COSArray | COSName | COSStream) -> PDAnnotation:
    d = COSDictionary()
    for key, value in items.items():
        d.set_item(COSName.get_pdf_name(key), value)
    return PDAnnotation(d)


# ---------- PDAppearanceEntry: is_stream vs is_sub_dictionary ----------


def test_entry_single_stream_is_stream_not_subdict() -> None:
    """A direct appearance stream: isStream true, isSubDictionary false.
    Upstream: !(entry instanceof COSStream) == false."""
    e = PDAppearanceEntry(_stream())
    assert e.is_stream()
    assert not e.is_sub_dictionary()


def test_entry_plain_dict_is_subdict_not_stream() -> None:
    """A plain COSDictionary: isSubDictionary true, isStream false."""
    e = PDAppearanceEntry(COSDictionary())
    assert e.is_sub_dictionary()
    assert not e.is_stream()


def test_entry_stream_detected_first_even_though_stream_is_a_dict() -> None:
    """COSStream extends COSDictionary; the stream check must win so the
    entry is never misclassified as a subdictionary."""
    st = _stream()
    assert isinstance(st, COSDictionary)
    e = PDAppearanceEntry(st)
    assert e.is_stream()
    assert not e.is_sub_dictionary()


def test_entry_none_is_neither_stream_nor_subdict() -> None:
    e = PDAppearanceEntry(None)
    assert not e.is_stream()
    assert not e.is_sub_dictionary()


def test_entry_rejects_non_cos_dict_or_stream() -> None:
    with pytest.raises(TypeError):
        PDAppearanceEntry(COSArray())
    with pytest.raises(TypeError):
        PDAppearanceEntry(COSName.get_pdf_name("On"))


def test_entry_get_cos_object_none_raises() -> None:
    with pytest.raises(ValueError):
        PDAppearanceEntry(None).get_cos_object()


def test_entry_get_appearance_stream_on_stream_entry() -> None:
    st = _stream()
    e = PDAppearanceEntry(st)
    aps = e.get_appearance_stream()
    assert isinstance(aps, PDAppearanceStream)
    assert aps.get_cos_object() is st


def test_entry_get_appearance_stream_on_subdict_raises() -> None:
    """Upstream throws IllegalStateException -> ValueError here."""
    e = PDAppearanceEntry(COSDictionary())
    with pytest.raises(ValueError):
        e.get_appearance_stream()


def test_entry_get_appearance_stream_none_returns_none() -> None:
    assert PDAppearanceEntry(None).get_appearance_stream() is None


def test_entry_get_sub_dictionary_on_stream_raises() -> None:
    with pytest.raises(ValueError):
        PDAppearanceEntry(_stream()).get_sub_dictionary()


def test_entry_get_sub_dictionary_maps_state_to_streams() -> None:
    sub = COSDictionary()
    off = _stream()
    on = _stream()
    sub.set_item(COSName.get_pdf_name("Off"), off)
    sub.set_item(COSName.get_pdf_name("On"), on)
    e = PDAppearanceEntry(sub)
    mapping = e.get_sub_dictionary()
    assert set(mapping.keys()) == {"Off", "On"}
    assert mapping["Off"].get_cos_object() is off
    assert mapping["On"].get_cos_object() is on


def test_entry_get_sub_dictionary_skips_non_stream_values() -> None:
    """PDFBOX-1599: a /null (or any non-stream) value among the state
    entries is skipped, not surfaced as an appearance stream."""
    sub = COSDictionary()
    on = _stream()
    sub.set_item(COSName.get_pdf_name("On"), on)
    sub.set_item(COSName.get_pdf_name("Bad"), COSName.get_pdf_name("nope"))
    sub.set_item(COSName.get_pdf_name("Str"), COSString("x"))
    mapping = PDAppearanceEntry(sub).get_sub_dictionary()
    assert set(mapping.keys()) == {"On"}


def test_entry_is_empty_semantics() -> None:
    assert PDAppearanceEntry(None).is_empty()
    assert PDAppearanceEntry(COSDictionary()).is_empty()  # no streams
    assert not PDAppearanceEntry(_stream()).is_empty()  # direct stream
    sub = COSDictionary()
    sub.set_item(COSName.get_pdf_name("On"), _stream())
    assert not PDAppearanceEntry(sub).is_empty()


# ---------- PDAppearanceDictionary: N / R / D accessors ----------


def test_dict_no_arg_ctor_seeds_n_with_empty_subdict() -> None:
    ap = PDAppearanceDictionary()
    n = ap.get_normal_appearance()
    assert n is not None and n.is_sub_dictionary()
    assert n.get_sub_dictionary() == {}


def test_dict_empty_read_dict_all_none() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    assert ap.get_normal_appearance() is None
    assert ap.get_rollover_appearance() is None
    assert ap.get_down_appearance() is None


def test_dict_normal_single_stream() -> None:
    st = _stream()
    ap = _ap_with(st)
    n = ap.get_normal_appearance()
    assert n is not None and n.is_stream()
    assert n.get_appearance_stream().get_cos_object() is st


def test_dict_normal_subdict() -> None:
    sub = COSDictionary()
    sub.set_item(COSName.get_pdf_name("On"), _stream())
    n = _ap_with(sub).get_normal_appearance()
    assert n is not None and n.is_sub_dictionary()


def test_dict_rollover_falls_back_to_normal_when_absent() -> None:
    st = _stream()
    ap = _ap_with(st)
    r = ap.get_rollover_appearance()
    assert r is not None and r.is_stream()
    assert r.get_appearance_stream().get_cos_object() is st


def test_dict_down_falls_back_to_normal_when_absent() -> None:
    sub = COSDictionary()
    sub.set_item(COSName.get_pdf_name("On"), _stream())
    ap = _ap_with(sub)
    d = ap.get_down_appearance()
    assert d is not None and d.is_sub_dictionary()


def test_dict_explicit_rollover_returns_own_entry_not_normal() -> None:
    raw = COSDictionary()
    raw.set_item(_N, COSDictionary())
    r_stream = _stream()
    raw.set_item(_R, r_stream)
    ap = PDAppearanceDictionary(raw)
    r = ap.get_rollover_appearance()
    assert r.is_stream()
    assert r.get_appearance_stream().get_cos_object() is r_stream


def test_dict_explicit_down_returns_own_entry_not_normal() -> None:
    raw = COSDictionary()
    raw.set_item(_N, COSDictionary())
    d_stream = _stream()
    raw.set_item(_D, d_stream)
    ap = PDAppearanceDictionary(raw)
    d = ap.get_down_appearance()
    assert d.is_stream()
    assert d.get_appearance_stream().get_cos_object() is d_stream


def test_dict_has_presence_predicates() -> None:
    raw = COSDictionary()
    raw.set_item(_N, COSDictionary())
    raw.set_item(_R, _stream())
    ap = PDAppearanceDictionary(raw)
    assert ap.has_normal_appearance()
    assert ap.has_rollover_appearance()
    assert not ap.has_down_appearance()


def test_dict_non_dict_non_stream_n_yields_none() -> None:
    """An /N that is neither a dict nor a stream (e.g. a name) -> None,
    mirroring upstream getCOSDictionary returning null."""
    raw = COSDictionary()
    raw.set_item(_N, COSName.get_pdf_name("bogus"))
    ap = PDAppearanceDictionary(raw)
    assert ap.get_normal_appearance() is None


# ---------- set round-trips ----------


def test_dict_set_normal_stream_round_trip() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    aps = PDAppearanceStream(_stream())
    ap.set_normal_appearance(aps)
    got = ap.get_normal_appearance()
    assert got.is_stream()
    assert got.get_cos_object() is aps.get_cos_object()


def test_dict_set_normal_entry_round_trip() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    sub = COSDictionary()
    sub.set_item(COSName.get_pdf_name("On"), _stream())
    entry = PDAppearanceEntry(sub)
    ap.set_normal_appearance(entry)
    got = ap.get_normal_appearance()
    assert got.is_sub_dictionary()
    assert got.get_cos_object() is sub


def test_dict_set_rollover_down_round_trip() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    rs = PDAppearanceStream(_stream())
    ds = PDAppearanceStream(_stream())
    ap.set_rollover_appearance(rs)
    ap.set_down_appearance(ds)
    assert ap.get_rollover_appearance().get_cos_object() is rs.get_cos_object()
    assert ap.get_down_appearance().get_cos_object() is ds.get_cos_object()


def test_dict_set_normal_none_removes_key() -> None:
    raw = COSDictionary()
    raw.set_item(_N, _stream())
    ap = PDAppearanceDictionary(raw)
    ap.set_normal_appearance(None)
    assert not ap.has_normal_appearance()
    assert ap.get_normal_appearance() is None


def test_dict_set_accepts_raw_cos_stream_and_dict() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    st = _stream()
    ap.set_normal_appearance(st)
    assert ap.get_normal_appearance().get_cos_object() is st
    sub = COSDictionary()
    ap.set_rollover_appearance(sub)
    assert ap.get_rollover_appearance().get_cos_object() is sub


# ---------- PDAnnotation /AP /AS ----------


def test_annot_no_ap_returns_none() -> None:
    a = _annot()
    assert a.get_appearance() is None
    assert a.get_appearance_dictionary() is None
    assert a.get_normal_appearance_stream() is None


def test_annot_ap_single_stream_no_as_needed() -> None:
    ap = COSDictionary()
    st = _stream()
    ap.set_item(_N, st)
    a = _annot(AP=ap)
    nas = a.get_normal_appearance_stream()
    assert nas is not None
    assert nas.get_cos_object() is st


def test_annot_checkbox_subdict_as_selects_state() -> None:
    ap = COSDictionary()
    sub = COSDictionary()
    off = _stream()
    on = _stream()
    sub.set_item(COSName.get_pdf_name("Off"), off)
    sub.set_item(COSName.get_pdf_name("On"), on)
    ap.set_item(_N, sub)
    a = _annot(AP=ap, AS=COSName.get_pdf_name("On"))
    assert a.get_appearance_state() == "On"
    assert a.get_normal_appearance_stream().get_cos_object() is on


def test_annot_checkbox_switch_as_switches_stream() -> None:
    ap = COSDictionary()
    sub = COSDictionary()
    off = _stream()
    on = _stream()
    sub.set_item(COSName.get_pdf_name("Off"), off)
    sub.set_item(COSName.get_pdf_name("On"), on)
    ap.set_item(_N, sub)
    a = _annot(AP=ap, AS=COSName.get_pdf_name("On"))
    a.set_appearance_state("Off")
    assert a.get_normal_appearance_stream().get_cos_object() is off


def test_annot_subdict_missing_as_yields_none() -> None:
    ap = COSDictionary()
    sub = COSDictionary()
    sub.set_item(COSName.get_pdf_name("On"), _stream())
    ap.set_item(_N, sub)
    a = _annot(AP=ap)
    assert a.get_appearance_state() is None
    assert a.get_normal_appearance_stream() is None


def test_annot_subdict_as_naming_unknown_state_yields_none() -> None:
    ap = COSDictionary()
    sub = COSDictionary()
    sub.set_item(COSName.get_pdf_name("On"), _stream())
    ap.set_item(_N, sub)
    a = _annot(AP=ap, AS=COSName.get_pdf_name("Nope"))
    assert a.get_normal_appearance_stream() is None


def test_annot_set_appearance_state_string_and_cosname() -> None:
    a = _annot()
    a.set_appearance_state("On")
    assert a.get_appearance_state() == "On"
    a.set_appearance_state(COSName.get_pdf_name("Off"))
    assert a.get_appearance_state() == "Off"
    a.set_appearance_state(None)
    assert a.get_appearance_state() is None


def test_annot_set_appearance_dictionary_round_trip() -> None:
    a = _annot()
    pad = PDAppearanceDictionary()
    a.set_appearance(pad)
    got = a.get_appearance()
    assert got is not None
    assert got.get_cos_object() is pad.get_cos_object()
    a.set_appearance(None)
    assert a.get_appearance() is None


# ---------- PDAnnotation /Rect normalization ----------


def test_annot_rect_reversed_corners_normalized() -> None:
    """/Rect given as [urx ury llx lly] -> normalized to proper
    lower-left/upper-right via PDRectangle min/max (spec §7.9.5)."""
    arr = COSArray()
    for v in (100.0, 200.0, 10.0, 20.0):  # urx ury llx lly (reversed)
        arr.add(COSFloat(v))
    a = _annot(Rect=arr)
    r = a.get_rectangle()
    assert r is not None
    assert r.get_lower_left_x() == 10.0
    assert r.get_lower_left_y() == 20.0
    assert r.get_upper_right_x() == 100.0
    assert r.get_upper_right_y() == 200.0
    assert r.get_width() == 90.0
    assert r.get_height() == 180.0


def test_annot_rect_proper_order_unchanged() -> None:
    arr = COSArray()
    for v in (10, 20, 100, 200):
        arr.add(COSInteger.get(v))
    a = _annot(Rect=arr)
    r = a.get_rectangle()
    assert (r.get_lower_left_x(), r.get_lower_left_y()) == (10.0, 20.0)
    assert (r.get_upper_right_x(), r.get_upper_right_y()) == (100.0, 200.0)


def test_annot_rect_mixed_axis_reversal() -> None:
    """Only the x pair reversed; normalization is per-axis."""
    arr = COSArray()
    for v in (100.0, 20.0, 10.0, 200.0):  # urx lly llx ury
        arr.add(COSFloat(v))
    a = _annot(Rect=arr)
    r = a.get_rectangle()
    assert r.get_lower_left_x() == 10.0
    assert r.get_upper_right_x() == 100.0
    assert r.get_lower_left_y() == 20.0
    assert r.get_upper_right_y() == 200.0


def test_annot_rect_wrong_size_returns_none() -> None:
    for n in (0, 3, 5):
        arr = COSArray()
        for i in range(n):
            arr.add(COSFloat(float(i)))
        assert _annot(Rect=arr).get_rectangle() is None


def test_annot_rect_non_numeric_element_returns_none() -> None:
    arr = COSArray()
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(0.0))
    arr.add(COSName.get_pdf_name("x"))
    arr.add(COSFloat(10.0))
    assert _annot(Rect=arr).get_rectangle() is None


def test_annot_rect_non_array_returns_none() -> None:
    a = _annot(Rect=COSName.get_pdf_name("nope"))
    assert a.get_rectangle() is None


def test_annot_rect_missing_returns_none() -> None:
    assert _annot().get_rectangle() is None


def test_annot_rect_set_round_trip() -> None:
    a = _annot()
    a.set_rectangle(PDRectangle(1.0, 2.0, 3.0, 4.0))
    r = a.get_rectangle()
    assert (r.get_lower_left_x(), r.get_upper_right_y()) == (1.0, 4.0)
    a.set_rectangle(None)
    assert a.get_rectangle() is None


def test_annot_get_rect_alias_matches_get_rectangle() -> None:
    arr = COSArray()
    for v in (1.0, 2.0, 3.0, 4.0):
        arr.add(COSFloat(v))
    a = _annot(Rect=arr)
    assert a.get_rect() == a.get_rectangle()
