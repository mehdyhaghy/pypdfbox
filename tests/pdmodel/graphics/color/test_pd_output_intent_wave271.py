"""Wave 271 — round-out clearers, ``/N`` writer, and emptiness predicate
for ``PDOutputIntent``.

Targets the small enrichment surface added on top of upstream PDFBox 3.0
``PDOutputIntent``:

- symmetric ``clear_*`` shortcuts for every optional entry
  (``/Info``, ``/OutputCondition``, ``/OutputConditionIdentifier``,
  ``/RegistryName``, ``/DestOutputProfile``, ``/DestOutputProfileRef``,
  ``/S``)
- ``set_n_for_profile`` writer that updates ``/N`` on the embedded ICC
  stream after construction
- ``is_empty`` structural-emptiness predicate
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.color import PDOutputIntent

# ---------- clear_* symmetric to has_* ----------


def test_clear_info_removes_entry() -> None:
    intent = PDOutputIntent()
    intent.set_info("sRGB IEC61966-2.1")
    assert intent.has_info() is True
    intent.clear_info()
    assert intent.has_info() is False
    assert intent.get_info() is None


def test_clear_info_noop_when_absent() -> None:
    # No exception when the entry was never set.
    intent = PDOutputIntent()
    intent.clear_info()
    assert intent.has_info() is False


def test_clear_output_condition_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_output_condition("sheet-fed offset")
    assert intent.has_output_condition() is True
    intent.clear_output_condition()
    assert intent.has_output_condition() is False
    assert intent.get_output_condition() is None


def test_clear_output_condition_identifier_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_output_condition_identifier("CGATS TR 001")
    assert intent.has_output_condition_identifier() is True
    intent.clear_output_condition_identifier()
    assert intent.has_output_condition_identifier() is False


def test_clear_registry_name_round_trip() -> None:
    intent = PDOutputIntent()
    intent.set_registry_name("http://www.color.org")
    assert intent.has_registry_name() is True
    intent.clear_registry_name()
    assert intent.has_registry_name() is False


def test_clear_dest_output_profile_drops_stream() -> None:
    intent = PDOutputIntent()
    intent.set_dest_output_profile(COSStream())
    assert intent.has_dest_output_profile() is True
    intent.clear_dest_output_profile()
    assert intent.has_dest_output_profile() is False
    assert intent.get_dest_output_profile() is None


def test_clear_dest_output_profile_ref_drops_dict() -> None:
    intent = PDOutputIntent()
    intent.set_dest_output_profile_ref(COSDictionary())
    assert intent.has_dest_output_profile_ref() is True
    intent.clear_dest_output_profile_ref()
    assert intent.has_dest_output_profile_ref() is False


def test_clear_subtype_removes_entry() -> None:
    intent = PDOutputIntent()
    intent.set_subtype("GTS_PDFA1")
    assert intent.has_subtype() is True
    intent.clear_subtype()
    assert intent.has_subtype() is False
    assert intent.is_pdfa() is False
    assert intent.is_pdfx() is False
    assert intent.is_pdfe() is False


def test_clear_subtype_equivalent_to_set_none() -> None:
    a = PDOutputIntent()
    a.set_subtype("GTS_PDFA1")
    a.clear_subtype()
    b = PDOutputIntent()
    b.set_subtype("GTS_PDFA1")
    b.set_subtype(None)
    assert a.has_subtype() == b.has_subtype()


# ---------- set_n_for_profile ----------


def test_set_n_for_profile_writes_to_stream() -> None:
    intent = PDOutputIntent()
    stream = COSStream()
    intent.set_dest_output_profile(stream)
    intent.set_n_for_profile(4)
    # /N is on the stream's dictionary, not on the intent dictionary.
    assert stream.get_int(COSName.get_pdf_name("N")) == 4
    assert intent.get_n_for_profile() == 4


def test_set_n_for_profile_overwrites_existing() -> None:
    intent = PDOutputIntent()
    stream = COSStream()
    intent.set_dest_output_profile(stream)
    intent.set_n_for_profile(3)
    intent.set_n_for_profile(4)
    assert intent.get_n_for_profile() == 4


def test_set_n_for_profile_none_removes_entry() -> None:
    intent = PDOutputIntent()
    stream = COSStream()
    intent.set_dest_output_profile(stream)
    intent.set_n_for_profile(3)
    intent.set_n_for_profile(None)
    # /N gone; get_n_for_profile falls back to ICC sniff which returns
    # None on an empty stream.
    assert intent.get_n_for_profile() is None


def test_set_n_for_profile_rejects_non_positive() -> None:
    intent = PDOutputIntent()
    intent.set_dest_output_profile(COSStream())
    with pytest.raises(ValueError):
        intent.set_n_for_profile(0)
    with pytest.raises(ValueError):
        intent.set_n_for_profile(-1)


def test_set_n_for_profile_without_stream_raises() -> None:
    # /N lives on the ICC stream's dictionary — no stream means no place
    # to write it.
    intent = PDOutputIntent()
    with pytest.raises(OSError):
        intent.set_n_for_profile(3)


# ---------- is_empty ----------


def test_is_empty_true_on_fresh_intent() -> None:
    intent = PDOutputIntent()
    # A fresh intent has only /Type /OutputIntent — not "content".
    assert intent.is_empty() is True


def test_is_empty_false_after_set_subtype() -> None:
    intent = PDOutputIntent()
    intent.set_subtype("GTS_PDFA1")
    assert intent.is_empty() is False


def test_is_empty_false_after_set_info() -> None:
    intent = PDOutputIntent()
    intent.set_info("sRGB IEC61966-2.1")
    assert intent.is_empty() is False


def test_is_empty_false_after_set_dest_output_profile() -> None:
    intent = PDOutputIntent()
    intent.set_dest_output_profile(COSStream())
    assert intent.is_empty() is False


def test_is_empty_false_after_set_dest_output_profile_ref() -> None:
    intent = PDOutputIntent()
    intent.set_dest_output_profile_ref(COSDictionary())
    assert intent.is_empty() is False


def test_is_empty_round_trips_through_clear() -> None:
    intent = PDOutputIntent()
    intent.set_info("sRGB IEC61966-2.1")
    intent.set_subtype("GTS_PDFA1")
    intent.set_output_condition_identifier("CGATS TR 001")
    intent.set_registry_name("http://www.color.org")
    intent.set_output_condition("sheet-fed offset")
    intent.set_dest_output_profile(COSStream())
    intent.set_dest_output_profile_ref(COSDictionary())
    assert intent.is_empty() is False
    intent.clear_info()
    intent.clear_subtype()
    intent.clear_output_condition_identifier()
    intent.clear_registry_name()
    intent.clear_output_condition()
    intent.clear_dest_output_profile()
    intent.clear_dest_output_profile_ref()
    assert intent.is_empty() is True
