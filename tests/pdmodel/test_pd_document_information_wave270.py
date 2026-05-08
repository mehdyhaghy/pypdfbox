"""Wave 270 — pdmodel/PDDocumentInformation cold-gap round-out.

Covers the new ``clear_*`` per-field helpers and the :meth:`is_pristine`
predicate. The existing wave tests already cover the standard /Title …
/Trapped accessors and custom-metadata surface; this file targets the
remaining cold gaps without duplicating that ground.
"""

from __future__ import annotations

import datetime as _dt

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocumentInformation

# ---------- clear_* helpers ----------


def test_clear_title_removes_entry_wave270() -> None:
    info = PDDocumentInformation()
    info.set_title("Hello")
    assert info.has_title()
    info.clear_title()
    assert info.get_title() is None
    assert not info.has_title()
    assert not info.get_cos_object().contains_key(COSName.get_pdf_name("Title"))


def test_clear_title_on_absent_is_noop_wave270() -> None:
    info = PDDocumentInformation()
    info.clear_title()  # should not raise
    assert info.is_empty()


def test_clear_author_removes_entry_wave270() -> None:
    info = PDDocumentInformation()
    info.set_author("Bob")
    info.clear_author()
    assert info.get_author() is None
    assert not info.has_author()


def test_clear_subject_removes_entry_wave270() -> None:
    info = PDDocumentInformation()
    info.set_subject("Topic")
    info.clear_subject()
    assert info.get_subject() is None
    assert not info.has_subject()


def test_clear_keywords_removes_entry_wave270() -> None:
    info = PDDocumentInformation()
    info.set_keywords("a, b")
    info.clear_keywords()
    assert info.get_keywords() is None
    assert not info.has_keywords()


def test_clear_creator_removes_entry_wave270() -> None:
    info = PDDocumentInformation()
    info.set_creator("WordProcessor")
    info.clear_creator()
    assert info.get_creator() is None
    assert not info.has_creator()


def test_clear_producer_removes_entry_wave270() -> None:
    info = PDDocumentInformation()
    info.set_producer("pypdfbox")
    info.clear_producer()
    assert info.get_producer() is None
    assert not info.has_producer()


def test_clear_creation_date_removes_entry_wave270() -> None:
    info = PDDocumentInformation()
    info.set_creation_date(_dt.datetime(2024, 6, 1, tzinfo=_dt.UTC))
    assert info.has_creation_date()
    info.clear_creation_date()
    assert info.get_creation_date() is None
    assert not info.has_creation_date()


def test_clear_modification_date_removes_entry_wave270() -> None:
    info = PDDocumentInformation()
    info.set_modification_date(_dt.datetime(2024, 6, 1, tzinfo=_dt.UTC))
    info.clear_modification_date()
    assert info.get_modification_date() is None
    assert not info.has_modification_date()


def test_clear_trapped_removes_entry_wave270() -> None:
    info = PDDocumentInformation()
    info.set_trapped("True")
    assert info.has_trapped()
    info.clear_trapped()
    assert info.get_trapped() is None
    assert not info.has_trapped()


def test_clear_helpers_match_set_none_semantics_wave270() -> None:
    """``clear_<field>()`` should be observationally identical to
    ``set_<field>(None)`` for every standard field — the helpers are
    purely sugar."""
    a = PDDocumentInformation()
    b = PDDocumentInformation()
    a.set_title("t")
    a.set_author("a")
    a.set_subject("s")
    b.set_title("t")
    b.set_author("a")
    b.set_subject("s")
    a.set_title(None)
    a.set_author(None)
    a.set_subject(None)
    b.clear_title()
    b.clear_author()
    b.clear_subject()
    assert a.get_metadata_keys() == b.get_metadata_keys()
    assert a.is_empty() and b.is_empty()


# ---------- is_pristine ----------


def test_is_pristine_on_empty_dict_wave270() -> None:
    info = PDDocumentInformation()
    assert info.is_pristine()


def test_is_pristine_with_only_producer_wave270() -> None:
    info = PDDocumentInformation()
    info.set_producer("pypdfbox 0.x")
    # Only /Producer is set — common shape after a fresh save where the
    # writer stamps the field automatically. Should still count as
    # "pristine" because no caller-supplied metadata was added.
    assert info.is_pristine()


def test_is_pristine_false_when_title_set_wave270() -> None:
    info = PDDocumentInformation()
    info.set_producer("pypdfbox")
    info.set_title("A Real Title")
    assert not info.is_pristine()


def test_is_pristine_false_when_only_author_set_wave270() -> None:
    info = PDDocumentInformation()
    info.set_author("Alice")
    assert not info.is_pristine()


def test_is_pristine_false_when_custom_key_present_wave270() -> None:
    info = PDDocumentInformation()
    info.set_custom_metadata_value("MyApp:Build", "abc123")
    assert not info.is_pristine()


def test_is_pristine_round_trips_through_clear_wave270() -> None:
    info = PDDocumentInformation()
    info.set_title("x")
    info.set_author("y")
    assert not info.is_pristine()
    info.clear_title()
    info.clear_author()
    assert info.is_pristine()
