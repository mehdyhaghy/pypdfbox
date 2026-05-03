"""Round-out tests for :class:`PDActionURI` covering the
:meth:`get_is_map` / :meth:`set_is_map` aliases that mirror the raw
PDF dictionary entry name verbatim.
"""

from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDActionURI

_URI: COSName = COSName.get_pdf_name("URI")
_IS_MAP: COSName = COSName.get_pdf_name("IsMap")


def test_default_subtype_is_uri() -> None:
    action = PDActionURI()
    assert action.get_sub_type() == "URI"


def test_uri_round_trip() -> None:
    action = PDActionURI()
    assert action.get_uri() is None

    action.set_uri("https://example.test/landing")
    assert action.get_uri() == "https://example.test/landing"


def test_uri_set_none_removes_entry() -> None:
    action = PDActionURI()
    action.set_uri("https://example.test/")
    assert action.get_cos_object().contains_key(_URI)

    action.set_uri(None)
    assert not action.get_cos_object().contains_key(_URI)
    assert action.get_uri() is None


def test_get_is_map_default_is_false() -> None:
    action = PDActionURI()
    assert action.get_is_map() is False


def test_set_is_map_round_trips() -> None:
    action = PDActionURI()

    action.set_is_map(True)
    assert action.get_is_map() is True
    # Alias on the other accessor pair stays in sync.
    assert action.should_track_mouse_position() is True

    action.set_is_map(False)
    assert action.get_is_map() is False
    assert action.should_track_mouse_position() is False


def test_is_map_aliases_round_trip_via_either_setter() -> None:
    """Setting via ``set_track_mouse_position`` is observable through
    ``get_is_map`` and vice versa."""
    action = PDActionURI()

    action.set_track_mouse_position(True)
    assert action.get_is_map() is True

    action.set_is_map(False)
    assert action.should_track_mouse_position() is False


def test_is_map_stored_as_cos_boolean() -> None:
    action = PDActionURI()
    action.set_is_map(True)

    raw = action.get_cos_object().get_item(_IS_MAP)
    assert isinstance(raw, COSBoolean)


def test_has_uri_tracks_presence() -> None:
    action = PDActionURI()
    assert action.has_uri() is False

    action.set_uri("https://example.test/")
    assert action.has_uri() is True

    action.set_uri(None)
    assert action.has_uri() is False


def test_has_is_map_distinguishes_default_from_explicit_false() -> None:
    """``get_is_map`` collapses absence and explicit ``false`` to
    ``False``; ``has_is_map`` lets callers tell them apart."""
    action = PDActionURI()
    assert action.has_is_map() is False
    assert action.get_is_map() is False

    action.set_is_map(False)
    assert action.has_is_map() is True
    assert action.get_is_map() is False

    action.set_is_map(True)
    assert action.has_is_map() is True
    assert action.get_is_map() is True


def test_get_uri_as_cos_string_returns_raw_entry() -> None:
    action = PDActionURI()
    assert action.get_uri_as_cos_string() is None

    action.set_uri("https://example.test/")
    raw = action.get_uri_as_cos_string()
    assert isinstance(raw, COSString)
    assert raw.get_string() == "https://example.test/"


def test_get_uri_as_cos_string_none_when_not_a_string() -> None:
    """When ``/URI`` is present but not a ``COSString`` (malformed
    producer), the typed accessor declines to surface it."""
    action = PDActionURI()
    action.get_cos_object().set_item(_URI, COSName.get_pdf_name("NotAString"))
    assert action.get_uri_as_cos_string() is None


# ---------- clear_uri / clear_is_map -----------------------------------


def test_clear_uri_removes_entry() -> None:
    action = PDActionURI()
    action.set_uri("https://example.test/")
    assert action.has_uri() is True

    action.clear_uri()
    assert action.has_uri() is False
    assert action.get_uri() is None


def test_clear_uri_is_idempotent_when_absent() -> None:
    """``clear_uri`` on a freshly-constructed action (no ``/URI`` entry)
    is a no-op — no error, no spurious key creation."""
    action = PDActionURI()
    assert action.has_uri() is False

    action.clear_uri()
    assert action.has_uri() is False


def test_clear_is_map_distinct_from_set_is_map_false() -> None:
    """``clear_is_map`` returns the entry to the implicit-default state
    (``has_is_map`` False); ``set_is_map(False)`` explicitly stamps a
    ``COSBoolean`` False that ``has_is_map`` reports as present."""
    action = PDActionURI()

    action.set_is_map(False)
    assert action.has_is_map() is True
    assert action.get_is_map() is False

    action.clear_is_map()
    assert action.has_is_map() is False
    # Still reads False because that's the spec default.
    assert action.get_is_map() is False


def test_clear_is_map_after_true_value() -> None:
    action = PDActionURI()
    action.set_is_map(True)
    assert action.has_is_map() is True

    action.clear_is_map()
    assert action.has_is_map() is False
    assert action.get_is_map() is False


# ---------- is_empty ---------------------------------------------------


def test_is_empty_for_absent_entry() -> None:
    action = PDActionURI()
    assert action.is_empty() is True


def test_is_empty_for_empty_string() -> None:
    action = PDActionURI()
    action.set_uri("")
    # Entry is present but value is the empty string — semantically empty.
    assert action.has_uri() is True
    assert action.is_empty() is True


def test_is_empty_false_for_real_uri() -> None:
    action = PDActionURI()
    action.set_uri("https://example.test/")
    assert action.is_empty() is False


# ---------- scheme predicates -------------------------------------------


def test_get_scheme_https() -> None:
    action = PDActionURI()
    action.set_uri("https://example.test/path?q=1")
    assert action.get_scheme() == "https"


def test_get_scheme_http_case_insensitive() -> None:
    """Schemes are case-insensitive per RFC 3986 — get_scheme
    canonicalises to lower-case."""
    action = PDActionURI()
    action.set_uri("HTTP://example.test/")
    assert action.get_scheme() == "http"


def test_get_scheme_mailto() -> None:
    action = PDActionURI()
    action.set_uri("mailto:user@example.test")
    assert action.get_scheme() == "mailto"


def test_get_scheme_none_for_relative_uri() -> None:
    action = PDActionURI()
    action.set_uri("chapter2.pdf")
    assert action.get_scheme() is None


def test_get_scheme_none_for_fragment_only() -> None:
    """A pure fragment reference ``#anchor`` has no scheme (it has no
    ``":"`` separator) and is treated as relative."""
    action = PDActionURI()
    action.set_uri("#anchor")
    assert action.get_scheme() is None


def test_get_scheme_none_for_absent_entry() -> None:
    action = PDActionURI()
    assert action.get_scheme() is None


def test_get_scheme_none_for_empty_string() -> None:
    action = PDActionURI()
    action.set_uri("")
    assert action.get_scheme() is None


def test_get_scheme_rejects_non_alpha_first_char() -> None:
    """RFC 3986 requires the scheme to start with an ALPHA character.
    A value like ``"123:foo"`` is therefore not a valid scheme — it
    should be treated as relative rather than mis-classified."""
    action = PDActionURI()
    action.set_uri("123:foo")
    assert action.get_scheme() is None


def test_is_http_true_only_for_http_scheme() -> None:
    action = PDActionURI()
    action.set_uri("http://example.test/")
    assert action.is_http() is True
    assert action.is_https() is False
    assert action.is_mailto() is False


def test_is_https_true_only_for_https_scheme() -> None:
    action = PDActionURI()
    action.set_uri("https://example.test/")
    assert action.is_https() is True
    assert action.is_http() is False
    assert action.is_mailto() is False


def test_is_mailto_true_only_for_mailto_scheme() -> None:
    action = PDActionURI()
    action.set_uri("mailto:user@example.test")
    assert action.is_mailto() is True
    assert action.is_http() is False
    assert action.is_https() is False


def test_scheme_predicates_false_for_absent_entry() -> None:
    action = PDActionURI()
    assert action.is_http() is False
    assert action.is_https() is False
    assert action.is_mailto() is False


def test_is_relative_true_for_relative_path() -> None:
    action = PDActionURI()
    action.set_uri("page2.pdf")
    assert action.is_relative() is True


def test_is_relative_false_for_absolute_uri() -> None:
    action = PDActionURI()
    action.set_uri("https://example.test/")
    assert action.is_relative() is False


def test_is_relative_false_for_absent_entry() -> None:
    """``is_relative`` distinguishes "no URI at all" (absent / empty —
    use :meth:`is_empty`) from "URI without scheme"."""
    action = PDActionURI()
    assert action.is_relative() is False


def test_is_relative_false_for_empty_string() -> None:
    action = PDActionURI()
    action.set_uri("")
    assert action.is_relative() is False
