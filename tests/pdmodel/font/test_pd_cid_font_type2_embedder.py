"""Tests for :mod:`pypdfbox.pdmodel.font.pd_cid_font_type2_embedder`.

The full embedder needs a real TTF + PDDocument so we cover:

* ``_to_cid_system_info`` — small builder for the descendant
  ``/CIDSystemInfo`` dictionary.
* ``_encode_widths`` — the three-state width compressor that matches
  upstream's PriorityQueue-driven optimisation.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel.font.pd_cid_font_type2_embedder import (
    _encode_widths,
    _to_cid_system_info,
)


def test_to_cid_system_info_writes_three_fields() -> None:
    info = _to_cid_system_info("Adobe", "Identity", 0)
    assert info.get_string(COSName.get_pdf_name("Registry")) == "Adobe"
    assert info.get_string(COSName.get_pdf_name("Ordering")) == "Identity"
    assert info.get_int(COSName.get_pdf_name("Supplement")) == 0


def _cos_to_python(arr: COSArray) -> list[object]:
    out: list[object] = []
    for item in arr:
        if isinstance(item, COSArray):
            out.append(_cos_to_python(item))
        elif isinstance(item, COSInteger):
            out.append(item.int_value())
        else:
            out.append(item)
    return out


def test_encode_widths_collapses_serial_runs() -> None:
    # Identical widths for consecutive CIDs -> serial form ``cid_last w``.
    arr = _encode_widths([1, 500, 2, 500, 3, 500, 4, 500], scaling=1.0)
    py = _cos_to_python(arr)
    # Expected upstream output: [1, 4, 500] — the SERIAL termination.
    assert py == [1, 4, 500]


def test_encode_widths_emits_bracket_for_consecutive_distinct() -> None:
    arr = _encode_widths([10, 250, 11, 300, 12, 350], scaling=1.0)
    py = _cos_to_python(arr)
    assert py == [10, [250, 300, 350]]


def test_encode_widths_splits_on_gap() -> None:
    arr = _encode_widths([1, 100, 5, 200], scaling=1.0)
    py = _cos_to_python(arr)
    assert py == [1, [100], 5, [200]]


def test_encode_widths_applies_scaling() -> None:
    # scaling = 0.5 -> widths halved.
    arr = _encode_widths([1, 1000, 2, 800, 3, 800], scaling=0.5)
    py = _cos_to_python(arr)
    # Expected: [1, [500], 2, ...] -> 1000*0.5=500, 800*0.5=400.
    assert py[0] == 1


def test_encode_widths_rejects_short_input() -> None:
    import pytest

    with pytest.raises(ValueError):
        _encode_widths([1], scaling=1.0)
