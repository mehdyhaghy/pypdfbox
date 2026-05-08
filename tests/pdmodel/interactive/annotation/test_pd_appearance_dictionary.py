from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
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

# ---------- PDAppearanceDictionary ----------


def test_default_constructor_seeds_normal_with_subdict() -> None:
    """No-arg ctor mirrors upstream — /N is seeded with an empty
    subdictionary because /N is required by spec. /R and /D fall back
    to /N rather than being absent."""
    ap = PDAppearanceDictionary()
    n = ap.get_normal_appearance()
    assert n is not None
    assert n.is_sub_dictionary()
    assert n.get_sub_dictionary() == {}


def test_constructor_with_empty_dict_all_entries_none() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    assert ap.get_normal_appearance() is None
    assert ap.get_rollover_appearance() is None
    assert ap.get_down_appearance() is None


def test_get_cos_object_returns_underlying_dict() -> None:
    raw = COSDictionary()
    ap = PDAppearanceDictionary(raw)
    assert ap.get_cos_object() is raw


def test_constructor_rejects_non_dict() -> None:
    with pytest.raises(TypeError):
        PDAppearanceDictionary("not a dict")  # type: ignore[arg-type]


def test_set_normal_appearance_round_trip_with_entry() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    stream = COSStream()
    entry = PDAppearanceEntry(stream)
    ap.set_normal_appearance(entry)
    rt = ap.get_normal_appearance()
    assert rt is not None
    assert rt.is_stream()
    assert rt.get_cos_object() is stream
    # The underlying dict stores the raw COSStream (not the wrapper).
    assert ap.get_cos_object().get_dictionary_object(COSName.get_pdf_name("N")) is stream


def test_set_normal_appearance_accepts_appearance_stream() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    stream = COSStream()
    pap = PDAppearanceStream(stream)
    ap.set_normal_appearance(pap)
    rt = ap.get_normal_appearance()
    assert rt is not None
    assert rt.is_stream()
    assert rt.get_cos_object() is stream


def test_set_normal_appearance_clear_with_none() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    ap.set_normal_appearance(PDAppearanceEntry(COSStream()))
    ap.set_normal_appearance(None)
    assert ap.get_normal_appearance() is None


def test_set_rollover_appearance_round_trip() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    stream = COSStream()
    ap.set_rollover_appearance(PDAppearanceEntry(stream))
    rt = ap.get_rollover_appearance()
    assert rt is not None
    assert rt.is_stream()
    assert rt.get_cos_object() is stream


def test_get_rollover_falls_back_to_normal() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    n_stream = COSStream()
    ap.set_normal_appearance(PDAppearanceEntry(n_stream))
    rollover = ap.get_rollover_appearance()
    assert rollover is not None
    assert rollover.get_cos_object() is n_stream


def test_set_down_appearance_round_trip() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    stream = COSStream()
    ap.set_down_appearance(PDAppearanceEntry(stream))
    rt = ap.get_down_appearance()
    assert rt is not None
    assert rt.is_stream()
    assert rt.get_cos_object() is stream


def test_get_down_falls_back_to_normal() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    n_stream = COSStream()
    ap.set_normal_appearance(PDAppearanceEntry(n_stream))
    down = ap.get_down_appearance()
    assert down is not None
    assert down.get_cos_object() is n_stream


# ---------- PDAppearanceEntry ----------


def test_appearance_entry_with_stream_is_stream() -> None:
    stream = COSStream()
    entry = PDAppearanceEntry(stream)
    assert entry.is_stream()
    assert not entry.is_sub_dictionary()
    assert entry.get_cos_object() is stream


def test_appearance_entry_get_appearance_stream_returns_wrapper() -> None:
    stream = COSStream()
    entry = PDAppearanceEntry(stream)
    pap = entry.get_appearance_stream()
    assert isinstance(pap, PDAppearanceStream)
    assert pap.get_cos_object() is stream


def test_appearance_entry_get_sub_dictionary_raises_on_stream() -> None:
    entry = PDAppearanceEntry(COSStream())
    with pytest.raises(ValueError):
        entry.get_sub_dictionary()


def test_appearance_entry_with_subdictionary_is_sub_dictionary() -> None:
    sub = COSDictionary()
    on_stream = COSStream()
    off_stream = COSStream()
    sub.set_item(COSName.get_pdf_name("On"), on_stream)
    sub.set_item(COSName.get_pdf_name("Off"), off_stream)
    entry = PDAppearanceEntry(sub)
    assert entry.is_sub_dictionary()
    assert not entry.is_stream()
    mapping = entry.get_sub_dictionary()
    assert set(mapping.keys()) == {"On", "Off"}
    assert mapping["On"].get_cos_object() is on_stream
    assert mapping["Off"].get_cos_object() is off_stream


def test_appearance_entry_subdictionary_skips_non_stream_values() -> None:
    """Mirrors upstream's PDFBOX-1599 guard: ``/null`` (or any non-stream)
    entries among states are silently skipped."""
    sub = COSDictionary()
    sub.set_item(COSName.get_pdf_name("On"), COSStream())
    sub.set_name(COSName.get_pdf_name("Off"), "NotAStream")
    entry = PDAppearanceEntry(sub)
    mapping = entry.get_sub_dictionary()
    assert set(mapping.keys()) == {"On"}


def test_appearance_entry_get_appearance_stream_raises_on_subdictionary() -> None:
    entry = PDAppearanceEntry(COSDictionary())
    with pytest.raises(ValueError):
        entry.get_appearance_stream()


def test_appearance_entry_rejects_bad_type() -> None:
    with pytest.raises(TypeError):
        PDAppearanceEntry("not a cos object")  # type: ignore[arg-type]


# ---------- PDAppearanceStream ----------


def test_appearance_stream_get_cos_object() -> None:
    stream = COSStream()
    pap = PDAppearanceStream(stream)
    assert pap.get_cos_object() is stream


def test_appearance_stream_rejects_non_stream() -> None:
    with pytest.raises(TypeError):
        PDAppearanceStream(COSDictionary())  # type: ignore[arg-type]


# ---------- PDAppearanceStream — PDContentStream byte access ----------


def test_appearance_stream_get_content_stream_returns_cos_stream() -> None:
    stream = COSStream()
    pap = PDAppearanceStream(stream)
    assert pap.get_content_stream() is stream


def test_appearance_stream_get_contents_returns_decoded_bytes() -> None:
    stream = COSStream()
    payload = b"q 1 0 0 1 0 0 cm Q"
    stream.set_data(payload)

    pap = PDAppearanceStream(stream)
    with pap.get_contents() as contents:
        assert contents.read() == payload


def test_appearance_stream_get_contents_for_stream_parsing() -> None:
    stream = COSStream()
    payload = b"0 0 10 10 re f"
    stream.set_data(payload)

    pap = PDAppearanceStream(stream)
    parser_view = pap.get_contents_for_stream_parsing()
    random_view = pap.get_contents_for_random_access()
    try:
        assert parser_view.length() == random_view.length()
        assert parser_view.length() == len(payload)
    finally:
        parser_view.close()
        random_view.close()


# ---------- PDAppearanceStream — PDFormXObject parity additions ----------


def test_appearance_stream_form_type_defaults_to_one_when_absent() -> None:
    """Mirrors upstream ``PDFormXObject.getFormType()`` defaulting to 1."""
    pap = PDAppearanceStream(COSStream())
    assert pap.get_form_type() == 1


def test_appearance_stream_set_form_type_round_trip() -> None:
    pap = PDAppearanceStream(COSStream())
    pap.set_form_type(1)
    assert pap.get_form_type() == 1
    # The value lives under the /FormType entry on the stream dict.
    assert pap.get_cos_object().get_int(COSName.get_pdf_name("FormType")) == 1


def test_appearance_stream_get_bbox_returns_none_when_absent() -> None:
    pap = PDAppearanceStream(COSStream())
    assert pap.get_bbox() is None


def test_appearance_stream_set_bbox_round_trip() -> None:
    pap = PDAppearanceStream(COSStream())
    bbox = PDRectangle.from_xywh(0.0, 0.0, 100.0, 50.0)
    pap.set_bbox(bbox)
    rt = pap.get_bbox()
    assert rt is not None
    assert rt.get_lower_left_x() == 0.0
    assert rt.get_lower_left_y() == 0.0
    assert rt.get_upper_right_x() == 100.0
    assert rt.get_upper_right_y() == 50.0


def test_appearance_stream_set_bbox_none_clears_entry() -> None:
    pap = PDAppearanceStream(COSStream())
    pap.set_bbox(PDRectangle.from_width_height(10.0, 20.0))
    assert pap.get_bbox() is not None
    pap.set_bbox(None)
    assert pap.get_bbox() is None
    assert not pap.get_cos_object().contains_key(COSName.get_pdf_name("BBox"))


def test_appearance_stream_set_bbox_rejects_bad_type() -> None:
    pap = PDAppearanceStream(COSStream())
    with pytest.raises(TypeError):
        pap.set_bbox("not a rectangle")  # type: ignore[arg-type]


def test_appearance_stream_struct_parents_default_minus_one() -> None:
    """Mirrors upstream ``PDFormXObject.getStructParents()`` whose backing
    ``COSDictionary.getInt`` defaults to -1 when the key is absent."""
    pap = PDAppearanceStream(COSStream())
    assert pap.get_struct_parents() == -1


def test_appearance_stream_set_struct_parents_round_trip() -> None:
    pap = PDAppearanceStream(COSStream())
    pap.set_struct_parents(7)
    assert pap.get_struct_parents() == 7
    assert (
        pap.get_cos_object().get_int(COSName.get_pdf_name("StructParents")) == 7
    )


# ---------- PDAppearanceStream — /Matrix ----------


def test_appearance_stream_matrix_default_identity_when_absent() -> None:
    """``/Matrix`` defaults to the identity matrix per PDF §8.10.2."""
    pap = PDAppearanceStream(COSStream())
    assert pap.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_appearance_stream_matrix_round_trip_via_sequence() -> None:
    pap = PDAppearanceStream(COSStream())
    pap.set_matrix([2.0, 0.0, 0.0, 3.0, 10.0, 20.0])
    assert pap.get_matrix() == [2.0, 0.0, 0.0, 3.0, 10.0, 20.0]


def test_appearance_stream_matrix_accepts_tuple() -> None:
    """Sequence parameter accepts any 6-element numeric iterable."""
    pap = PDAppearanceStream(COSStream())
    pap.set_matrix((1.0, 2.0, 3.0, 4.0, 5.0, 6.0))
    assert pap.get_matrix() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_appearance_stream_matrix_accepts_raw_cos_array() -> None:
    """Low-level escape hatch: pass a raw ``COSArray`` straight through."""
    from pypdfbox.cos import COSArray, COSFloat

    pap = PDAppearanceStream(COSStream())
    raw = COSArray(
        [
            COSFloat(1.0),
            COSFloat(0.0),
            COSFloat(0.0),
            COSFloat(1.0),
            COSFloat(50.0),
            COSFloat(100.0),
        ]
    )
    pap.set_matrix(raw)
    assert pap.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Matrix")
    ) is raw
    assert pap.get_matrix() == [1.0, 0.0, 0.0, 1.0, 50.0, 100.0]


def test_appearance_stream_matrix_set_none_clears_entry() -> None:
    pap = PDAppearanceStream(COSStream())
    pap.set_matrix([1.0, 0.0, 0.0, 1.0, 5.0, 5.0])
    assert pap.get_cos_object().contains_key(COSName.get_pdf_name("Matrix"))
    pap.set_matrix(None)
    assert not pap.get_cos_object().contains_key(COSName.get_pdf_name("Matrix"))
    # After clearing, the getter must return the identity default again.
    assert pap.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_appearance_stream_matrix_wrong_length_raises() -> None:
    pap = PDAppearanceStream(COSStream())
    with pytest.raises(ValueError):
        pap.set_matrix([1.0, 0.0, 0.0, 1.0, 0.0])  # only 5
    with pytest.raises(ValueError):
        pap.set_matrix([1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])  # 7


def test_appearance_stream_matrix_short_array_falls_back_to_identity() -> None:
    """A truncated ``/Matrix`` with fewer than 6 entries is treated as
    absent and the getter returns the identity matrix."""
    from pypdfbox.cos import COSArray, COSFloat

    stream = COSStream()
    stream.set_item(
        COSName.get_pdf_name("Matrix"),
        COSArray([COSFloat(1.0), COSFloat(2.0), COSFloat(3.0)]),
    )
    pap = PDAppearanceStream(stream)
    assert pap.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_appearance_stream_matrix_integer_entries_round_trip_as_float() -> None:
    """``COSInteger`` entries are converted to ``float`` — matches the
    upstream Matrix.createMatrix path which reads numeric COS entries
    as doubles."""
    from pypdfbox.cos import COSArray, COSInteger

    stream = COSStream()
    stream.set_item(
        COSName.get_pdf_name("Matrix"),
        COSArray(
            [
                COSInteger(1),
                COSInteger(0),
                COSInteger(0),
                COSInteger(1),
                COSInteger(7),
                COSInteger(8),
            ]
        ),
    )
    pap = PDAppearanceStream(stream)
    matrix = pap.get_matrix()
    assert matrix == [1.0, 0.0, 0.0, 1.0, 7.0, 8.0]
    assert all(isinstance(v, float) for v in matrix)


# ---------- PDAppearanceEntry — is_empty() ----------


def test_appearance_entry_is_empty_for_none() -> None:
    entry = PDAppearanceEntry()
    assert entry.is_empty()


def test_appearance_entry_is_empty_false_for_stream() -> None:
    """A direct stream entry is never empty regardless of stream contents."""
    entry = PDAppearanceEntry(COSStream())
    assert not entry.is_empty()


def test_appearance_entry_is_empty_for_subdict_with_no_streams() -> None:
    """The placeholder ``/N`` subdictionary seeded by the no-arg
    PDAppearanceDictionary ctor is a real-world empty entry."""
    entry = PDAppearanceEntry(COSDictionary())
    assert entry.is_empty()


def test_appearance_entry_is_empty_skips_non_stream_values() -> None:
    """Subdictionary with only non-stream (e.g. ``/null``) values is
    considered empty — same PDFBOX-1599 guard as get_sub_dictionary."""
    sub = COSDictionary()
    sub.set_name(COSName.get_pdf_name("Off"), "NotAStream")
    entry = PDAppearanceEntry(sub)
    assert entry.is_empty()


def test_appearance_entry_is_empty_false_with_one_stream() -> None:
    sub = COSDictionary()
    sub.set_item(COSName.get_pdf_name("On"), COSStream())
    entry = PDAppearanceEntry(sub)
    assert not entry.is_empty()


# ---------- PDAppearanceDictionary — has_*_appearance ----------


def test_appearance_dict_has_normal_after_default_ctor() -> None:
    """No-arg ctor seeds /N — has_normal_appearance must be True."""
    ap = PDAppearanceDictionary()
    assert ap.has_normal_appearance()
    assert not ap.has_rollover_appearance()
    assert not ap.has_down_appearance()


def test_appearance_dict_has_predicates_default_false_for_empty_dict() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    assert not ap.has_normal_appearance()
    assert not ap.has_rollover_appearance()
    assert not ap.has_down_appearance()


def test_appearance_dict_has_rollover_after_set() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    ap.set_rollover_appearance(PDAppearanceEntry(COSStream()))
    assert ap.has_rollover_appearance()
    # /N still absent — fallback is just for the typed getter.
    assert not ap.has_normal_appearance()


def test_appearance_dict_has_down_distinguishes_real_from_fallback() -> None:
    """``get_down_appearance`` falls back to /N, but
    ``has_down_appearance`` must report only the explicit /D key."""
    ap = PDAppearanceDictionary(COSDictionary())
    ap.set_normal_appearance(PDAppearanceEntry(COSStream()))
    # /D not set — get_down_appearance returns the /N fallback...
    assert ap.get_down_appearance() is not None
    # ...but has_down_appearance reports the truth.
    assert not ap.has_down_appearance()
    ap.set_down_appearance(PDAppearanceEntry(COSStream()))
    assert ap.has_down_appearance()


def test_appearance_dict_has_predicates_clear_via_none() -> None:
    ap = PDAppearanceDictionary(COSDictionary())
    ap.set_rollover_appearance(PDAppearanceEntry(COSStream()))
    assert ap.has_rollover_appearance()
    ap.set_rollover_appearance(None)
    assert not ap.has_rollover_appearance()
