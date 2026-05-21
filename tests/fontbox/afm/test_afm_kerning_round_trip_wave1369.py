"""Wave 1369 — AFM track-kern + pair-kern round-trip parity tests.

AFM (Adobe Font Metric) kerning data lives in a ``StartKernData`` /
``EndKernData`` block. Inside it there can be:

* ``StartTrackKern`` / ``EndTrackKern`` — track-kerning entries
  describing a piecewise-linear kern interpolation across point sizes
  (AFM spec 5004 §9.2);
* ``StartKernPairs`` (writing direction 0+1), ``StartKernPairs0``
  (direction 0), or ``StartKernPairs1`` (direction 1), each enclosing
  ``KP`` / ``KPH`` / ``KPX`` / ``KPY`` kern-pair entries.

These tests cover the four kern-pair command variants, the
direction-specific buckets, the ``KPH`` hex-name decoder, and a
multi-block scenario combining track + pair kerning. Each test feeds a
synthetic AFM snippet and checks the round-tripped values.
"""
from __future__ import annotations

import pytest

from pypdfbox.fontbox.afm import AFMParser, FontMetrics, KernPair, TrackKern


def _parse(body: str) -> FontMetrics:
    raw = ("StartFontMetrics 4.1\n" + body + "EndFontMetrics\n").encode("latin-1")
    return AFMParser(raw).parse()


# ---------- StartTrackKern ----------


def test_track_kern_round_trip_single_entry() -> None:
    fm = _parse(
        "StartKernData\n"
        "StartTrackKern 1\n"
        "TrackKern 0 8 -1.5 32 -3.0\n"
        "EndTrackKern\n"
        "EndKernData\n"
    )
    tk = fm.get_track_kern()
    assert len(tk) == 1
    entry = tk[0]
    assert isinstance(entry, TrackKern)
    assert entry.get_degree() == 0
    assert entry.get_min_point_size() == pytest.approx(8.0)
    assert entry.get_min_kern() == pytest.approx(-1.5)
    assert entry.get_max_point_size() == pytest.approx(32.0)
    assert entry.get_max_kern() == pytest.approx(-3.0)


def test_track_kern_multiple_entries_preserve_order() -> None:
    fm = _parse(
        "StartKernData\n"
        "StartTrackKern 3\n"
        "TrackKern 0 6 -0.5 24 -2.0\n"
        "TrackKern 1 8 -1.0 32 -3.0\n"
        "TrackKern 2 10 -1.5 40 -4.0\n"
        "EndTrackKern\n"
        "EndKernData\n"
    )
    tk = fm.get_track_kern()
    assert [t.get_degree() for t in tk] == [0, 1, 2]
    assert [t.get_min_point_size() for t in tk] == [6.0, 8.0, 10.0]


def test_track_kern_empty_block_is_legal() -> None:
    # ``StartTrackKern 0`` with no entries — upstream simply moves on.
    fm = _parse(
        "StartKernData\n"
        "StartTrackKern 0\n"
        "EndTrackKern\n"
        "EndKernData\n"
    )
    assert fm.get_track_kern() == []


# ---------- KP / KPX / KPY / KPH ----------


def test_kp_xy_pair_round_trip() -> None:
    # ``KP`` carries both x and y kerning amounts.
    fm = _parse(
        "StartKernData\n"
        "StartKernPairs 1\n"
        "KP A V -100 -50\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    pairs = fm.get_kern_pairs()
    assert len(pairs) == 1
    kp: KernPair = pairs[0]
    assert kp.get_first_kern_character() == "A"
    assert kp.get_second_kern_character() == "V"
    assert kp.get_x() == pytest.approx(-100.0)
    assert kp.get_y() == pytest.approx(-50.0)


def test_kpx_x_only_round_trip() -> None:
    fm = _parse(
        "StartKernData\n"
        "StartKernPairs 1\n"
        "KPX A V -120\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    pairs = fm.get_kern_pairs()
    assert len(pairs) == 1
    assert pairs[0].get_x() == pytest.approx(-120.0)
    assert pairs[0].get_y() == 0.0


def test_kpy_y_only_round_trip() -> None:
    fm = _parse(
        "StartKernData\n"
        "StartKernPairs 1\n"
        "KPY A V -80\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    pairs = fm.get_kern_pairs()
    assert pairs[0].get_x() == 0.0
    assert pairs[0].get_y() == pytest.approx(-80.0)


def test_kph_hex_name_decoded() -> None:
    # KPH uses hex-encoded glyph names ``<HHHH>`` — typically for non-
    # ASCII glyph names. The parser must decode them to latin-1 strings.
    fm = _parse(
        "StartKernData\n"
        "StartKernPairs 1\n"
        "KPH <0041> <0056> -90 -30\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    pairs = fm.get_kern_pairs()
    # The hex 0041 / 0056 decode to latin-1 \x00A and \x00V respectively
    # (two-byte hex stays as two bytes in latin-1 form).
    kp = pairs[0]
    assert kp.get_first_kern_character() == "\x00A"
    assert kp.get_second_kern_character() == "\x00V"
    assert kp.get_x() == pytest.approx(-90.0)
    assert kp.get_y() == pytest.approx(-30.0)


def test_kph_rejects_malformed_hex() -> None:
    # Missing closing ``>``.
    body = (
        "StartKernData\n"
        "StartKernPairs 1\n"
        "KPH <0041 V -90 -30\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    with pytest.raises(OSError):
        _parse(body)


# ---------- direction-specific buckets ----------


def test_kern_pairs0_lands_in_direction_0_list() -> None:
    fm = _parse(
        "StartKernData\n"
        "StartKernPairs0 1\n"
        "KPX A V -100\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    assert len(fm.get_kern_pairs0()) == 1
    # Not in the direction-agnostic bucket.
    assert fm.get_kern_pairs() == []
    assert fm.get_kern_pairs1() == []


def test_kern_pairs1_lands_in_direction_1_list() -> None:
    fm = _parse(
        "StartKernData\n"
        "StartKernPairs1 1\n"
        "KPX A V -100\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    assert len(fm.get_kern_pairs1()) == 1
    assert fm.get_kern_pairs() == []
    assert fm.get_kern_pairs0() == []


# ---------- multi-block ----------


def test_kern_data_with_track_and_multi_direction_pairs() -> None:
    fm = _parse(
        "StartKernData\n"
        "StartTrackKern 1\n"
        "TrackKern 0 8 -1.5 32 -3.0\n"
        "EndTrackKern\n"
        "StartKernPairs 1\n"
        "KP A V -90 -45\n"
        "EndKernPairs\n"
        "StartKernPairs0 1\n"
        "KPX B W -75\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    assert len(fm.get_track_kern()) == 1
    assert len(fm.get_kern_pairs()) == 1
    assert len(fm.get_kern_pairs0()) == 1
    # ``get_total_kern_pair_count`` should sum across all three lists.
    assert fm.get_total_kern_pair_count() == 2


# ---------- error path: unknown command ----------


def test_unknown_kern_command_raises() -> None:
    body = (
        "StartKernData\n"
        "MysteryKernType 1\n"
        "EndKernData\n"
    )
    with pytest.raises(OSError, match="Unknown kerning"):
        _parse(body)


def test_unknown_kern_pair_command_raises() -> None:
    body = (
        "StartKernData\n"
        "StartKernPairs 1\n"
        "ZZZ A V -100\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )
    with pytest.raises(OSError, match="kern pair"):
        _parse(body)


# ---------- TrackKern object identity ----------


def test_track_kern_get_returns_copy() -> None:
    # ``get_track_kern`` returns a list copy — mutating it must not
    # change the FontMetrics' internal store.
    fm = _parse(
        "StartKernData\n"
        "StartTrackKern 1\n"
        "TrackKern 0 8 -1 32 -3\n"
        "EndTrackKern\n"
        "EndKernData\n"
    )
    first = fm.get_track_kern()
    first.clear()
    assert len(fm.get_track_kern()) == 1
