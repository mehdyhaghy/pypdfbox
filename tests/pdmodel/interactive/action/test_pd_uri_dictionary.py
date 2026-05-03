"""Parity tests for ``PDURIDictionary`` — the document-level ``/URI``
dictionary that holds the ``/Base`` entry used to resolve relative URIs
in URI actions (PDF 32000-1 §12.6.4.7)."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDURIDictionary

_BASE: COSName = COSName.get_pdf_name("Base")


def test_default_constructor_creates_empty_cos_dictionary() -> None:
    """No-arg constructor allocates a fresh empty ``COSDictionary``."""
    uri = PDURIDictionary()
    cos = uri.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.size() == 0


def test_constructor_wraps_existing_dictionary_identity() -> None:
    """Wrapping an existing dictionary preserves identity — no copy."""
    raw = COSDictionary()
    raw.set_string(_BASE, "https://example.test/")
    uri = PDURIDictionary(raw)
    assert uri.get_cos_object() is raw


def test_constructor_with_none_creates_empty_cos_dictionary() -> None:
    """Explicit ``None`` argument matches the default constructor."""
    uri = PDURIDictionary(None)
    assert isinstance(uri.get_cos_object(), COSDictionary)
    assert uri.get_cos_object().size() == 0


def test_get_base_returns_none_when_absent() -> None:
    """Fresh dictionary has no ``/Base`` entry."""
    uri = PDURIDictionary()
    assert uri.get_base() is None


def test_set_base_round_trip() -> None:
    """``set_base`` writes ``/Base`` as a COS string that ``get_base``
    reads back identically."""
    uri = PDURIDictionary()
    uri.set_base("https://example.test/")
    assert uri.get_base() == "https://example.test/"
    raw = uri.get_cos_object().get_dictionary_object(_BASE)
    assert isinstance(raw, COSString)


def test_set_base_overwrites_previous_value() -> None:
    """Re-setting ``/Base`` replaces the previous value."""
    uri = PDURIDictionary()
    uri.set_base("https://first.test/")
    uri.set_base("https://second.test/")
    assert uri.get_base() == "https://second.test/"


def test_set_base_none_removes_entry() -> None:
    """Setting ``/Base`` to ``None`` strips the entry from the dict.

    pypdfbox treats ``None`` as ``remove_item`` rather than writing a
    null COS string, mirroring how upstream callers reach a clean state
    after writing then clearing the base URI."""
    uri = PDURIDictionary()
    uri.set_base("https://example.test/")
    assert uri.get_base() == "https://example.test/"

    uri.set_base(None)
    assert uri.get_base() is None
    assert uri.get_cos_object().get_dictionary_object(_BASE) is None


def test_set_base_none_on_empty_dictionary_is_noop() -> None:
    """Removing ``/Base`` when it was never set leaves the dict empty."""
    uri = PDURIDictionary()
    uri.set_base(None)
    assert uri.get_base() is None
    assert uri.get_cos_object().size() == 0


def test_get_base_reads_existing_dictionary_entry() -> None:
    """Wrapping a pre-populated dictionary surfaces ``/Base`` verbatim."""
    raw = COSDictionary()
    raw.set_string(_BASE, "https://prefilled.test/path/")
    uri = PDURIDictionary(raw)
    assert uri.get_base() == "https://prefilled.test/path/"


def test_get_cos_object_returns_same_instance_repeatedly() -> None:
    """``get_cos_object`` returns the same backing dictionary each call
    so callers can mutate via the COS layer."""
    uri = PDURIDictionary()
    first = uri.get_cos_object()
    second = uri.get_cos_object()
    assert first is second


# ---------- BASE constant ----------


def test_base_key_constant_matches_pdf_spec() -> None:
    """``BASE`` exposes the spec key name verbatim for portable callers."""
    assert PDURIDictionary.BASE == "Base"


# ---------- has_base predicate ----------


def test_has_base_false_on_empty_dictionary() -> None:
    """A fresh dictionary has no ``/Base`` entry."""
    uri = PDURIDictionary()
    assert uri.has_base() is False


def test_has_base_true_after_set_base() -> None:
    """``set_base`` flips ``has_base`` to ``True``."""
    uri = PDURIDictionary()
    uri.set_base("https://example.test/")
    assert uri.has_base() is True


def test_has_base_true_for_explicit_empty_string() -> None:
    """``has_base`` distinguishes "absent" from "explicitly empty";
    an explicit empty string still counts as present."""
    uri = PDURIDictionary()
    uri.set_base("")
    assert uri.has_base() is True
    assert uri.get_base() == ""


def test_has_base_false_after_set_base_none() -> None:
    """Removing ``/Base`` flips ``has_base`` back to ``False``."""
    uri = PDURIDictionary()
    uri.set_base("https://example.test/")
    uri.set_base(None)
    assert uri.has_base() is False


# ---------- get_base_as_cos_string typed accessor ----------


def test_get_base_as_cos_string_returns_none_when_absent() -> None:
    """Typed accessor returns ``None`` when ``/Base`` is missing."""
    uri = PDURIDictionary()
    assert uri.get_base_as_cos_string() is None


def test_get_base_as_cos_string_returns_cos_string_instance() -> None:
    """Typed accessor returns the raw ``COSString`` so callers can read
    the underlying bytes without going through string decode."""
    uri = PDURIDictionary()
    uri.set_base("https://example.test/")
    raw = uri.get_base_as_cos_string()
    assert isinstance(raw, COSString)
    assert raw.get_string() == "https://example.test/"


def test_get_base_as_cos_string_returns_none_for_wrong_type() -> None:
    """When ``/Base`` exists but isn't a ``COSString`` (malformed input),
    the typed accessor returns ``None`` rather than raising."""
    raw = COSDictionary()
    # A non-string entry — e.g. a sub-dictionary — should not be returned
    raw.set_item(_BASE, COSDictionary())
    uri = PDURIDictionary(raw)
    assert uri.get_base_as_cos_string() is None
    # And the string-form accessor still returns ``None``.
    assert uri.get_base() is None


# ---------- is_empty predicate ----------


def test_is_empty_true_on_default_constructor() -> None:
    """A freshly-constructed URI dictionary holds no entries."""
    uri = PDURIDictionary()
    assert uri.is_empty() is True


def test_is_empty_false_after_setting_base() -> None:
    """Setting any entry makes the dictionary non-empty."""
    uri = PDURIDictionary()
    uri.set_base("https://example.test/")
    assert uri.is_empty() is False


def test_is_empty_true_again_after_clearing_base() -> None:
    """After removing the only entry the dictionary is empty again."""
    uri = PDURIDictionary()
    uri.set_base("https://example.test/")
    uri.set_base(None)
    assert uri.is_empty() is True


# ---------- __repr__ ----------


def test_repr_marks_unset_base() -> None:
    """``__repr__`` clearly indicates an unset ``/Base``."""
    uri = PDURIDictionary()
    assert repr(uri) == "PDURIDictionary(Base=<unset>)"


def test_repr_quotes_set_base() -> None:
    """``__repr__`` round-trips through ``repr()`` on the URI string."""
    uri = PDURIDictionary()
    uri.set_base("https://example.test/")
    assert repr(uri) == "PDURIDictionary(Base='https://example.test/')"
