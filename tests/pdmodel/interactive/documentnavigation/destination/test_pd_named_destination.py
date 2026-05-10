"""Coverage for :class:`PDNamedDestination` typed predicates and accessors.

Mirrors upstream
``org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDNamedDestination``
and rounds out edge-case behavior: bytes input on the setter, the
:meth:`is_name_form` / :meth:`is_string_form` / :meth:`is_empty` typed
predicates, and ``__repr__`` formatting for diagnostic logs.

PDF 32000-1 §12.3.2.3 allows the named-destination value to be either a
name (``/Foo``) or a byte string (``(Foo)``); both forms must round-trip
through :meth:`get_named_destination` while preserving the original COS
shape until an explicit setter call replaces it with a ``COSString``.
"""

from __future__ import annotations

from pypdfbox.cos import COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)

# ---------------------------------------------------------------------------
# is_name_form / is_string_form / is_empty predicates
# ---------------------------------------------------------------------------


def test_is_empty_true_for_default_constructor() -> None:
    dest = PDNamedDestination()

    assert dest.is_empty() is True
    assert dest.is_name_form() is False
    assert dest.is_string_form() is False
    assert dest.get_named_destination() is None
    assert dest.get_cos_object() is None


def test_is_name_form_true_when_constructed_from_cos_name() -> None:
    dest = PDNamedDestination(COSName.get_pdf_name("Chapter1"))

    assert dest.is_name_form() is True
    assert dest.is_string_form() is False
    assert dest.is_empty() is False
    assert dest.get_named_destination() == "Chapter1"


def test_is_string_form_true_when_constructed_from_cos_string() -> None:
    dest = PDNamedDestination(COSString("Chapter2"))

    assert dest.is_string_form() is True
    assert dest.is_name_form() is False
    assert dest.is_empty() is False
    assert dest.get_named_destination() == "Chapter2"


def test_is_string_form_true_when_constructed_from_python_str() -> None:
    """The ``str`` overload upstream wraps the name in ``new COSString(...)``,
    not in a ``COSName``. The form predicates must reflect that — even a
    name-shaped string like ``"Chapter1"`` is stored as a string."""
    dest = PDNamedDestination("Chapter1")

    assert dest.is_string_form() is True
    assert dest.is_name_form() is False


def test_predicates_mutually_exclusive() -> None:
    """At most one of ``is_empty``, ``is_name_form``, ``is_string_form`` is
    ever ``True``. They partition the wrapper's possible internal states."""
    cases = [
        PDNamedDestination(),
        PDNamedDestination(COSName.get_pdf_name("X")),
        PDNamedDestination(COSString("X")),
        PDNamedDestination("X"),
    ]
    for dest in cases:
        flags = (dest.is_empty(), dest.is_name_form(), dest.is_string_form())
        assert sum(flags) == 1, f"flags={flags} for {dest!r}"


# ---------------------------------------------------------------------------
# set_named_destination — bytes parity with constructor
# ---------------------------------------------------------------------------


def test_set_named_destination_accepts_bytes() -> None:
    """Symmetry: the constructor accepts ``bytes`` (PDFDocEncoding raw),
    and so does the setter. Round-trip through ``get_named_destination``
    decodes back to ``str``."""
    dest = PDNamedDestination()
    dest.set_named_destination(b"RawTarget")

    assert dest.is_string_form() is True
    assert dest.get_named_destination() == "RawTarget"


def test_set_named_destination_clears_with_none() -> None:
    dest = PDNamedDestination(COSName.get_pdf_name("Existing"))
    dest.set_named_destination(None)

    assert dest.is_empty() is True
    assert dest.get_named_destination() is None
    assert dest.get_cos_object() is None


def test_set_named_destination_replaces_cos_name_with_cos_string() -> None:
    """Upstream parity: ``setNamedDestination`` always writes a ``COSString``,
    even if the slot was previously a ``COSName``. This matters because
    name-form is a 1-byte literal whereas string-form uses PDFDocEncoding
    (or UTF-16BE for non-Latin1 chars), and writers serialize the two
    shapes very differently."""
    dest = PDNamedDestination(COSName.get_pdf_name("Old"))
    assert dest.is_name_form() is True

    dest.set_named_destination("New")
    assert dest.is_name_form() is False
    assert dest.is_string_form() is True
    assert dest.get_named_destination() == "New"


def test_set_named_destination_with_empty_string_keeps_string_form() -> None:
    dest = PDNamedDestination()
    dest.set_named_destination("")

    assert dest.is_empty() is False
    assert dest.is_string_form() is True
    assert dest.get_named_destination() == ""


def test_set_named_destination_with_empty_bytes_keeps_string_form() -> None:
    dest = PDNamedDestination()
    dest.set_named_destination(b"")

    assert dest.is_empty() is False
    assert dest.is_string_form() is True
    assert dest.get_named_destination() == ""


# ---------------------------------------------------------------------------
# get_cos_object — preserves identity for COSName / COSString inputs
# ---------------------------------------------------------------------------


def test_get_cos_object_returns_the_original_cos_name_instance() -> None:
    """Constructor with a ``COSName`` keeps the same instance on the way
    out — important so writer round-trips don't create a duplicated name
    object in the ``/Dests`` name tree."""
    name = COSName.get_pdf_name("Section3")
    dest = PDNamedDestination(name)

    assert dest.get_cos_object() is name


def test_get_cos_object_returns_the_original_cos_string_instance() -> None:
    string = COSString("Section3")
    dest = PDNamedDestination(string)

    assert dest.get_cos_object() is string


# ---------------------------------------------------------------------------
# __repr__ — diagnostic formatting
# ---------------------------------------------------------------------------


def test_repr_for_empty_destination() -> None:
    assert repr(PDNamedDestination()) == "PDNamedDestination(<empty>)"


def test_repr_for_name_form() -> None:
    dest = PDNamedDestination(COSName.get_pdf_name("Chapter4"))

    assert repr(dest) == "PDNamedDestination(name='Chapter4')"


def test_repr_for_string_form() -> None:
    dest = PDNamedDestination(COSString("Chapter4"))

    assert repr(dest) == "PDNamedDestination(string='Chapter4')"


def test_repr_for_str_constructor_uses_string_form() -> None:
    """``str`` ctor wraps in a ``COSString``, so ``__repr__`` shows the
    ``string=`` discriminator, not ``name=``."""
    dest = PDNamedDestination("Chapter4")

    assert repr(dest) == "PDNamedDestination(string='Chapter4')"


# ---------------------------------------------------------------------------
# Round-trip via get_cos_object → PDNamedDestination(...)
# ---------------------------------------------------------------------------


def test_round_trip_via_cos_object_preserves_form() -> None:
    """Re-wrapping a destination's ``get_cos_object()`` should yield an
    equivalent destination with the same form predicates. This matters
    for code paths that pull a destination off the wire, hand it to
    :class:`PDDestination.create`, and re-wrap it later."""
    original = PDNamedDestination(COSName.get_pdf_name("Section2"))
    cos = original.get_cos_object()
    assert isinstance(cos, COSName)

    rewrapped = PDNamedDestination(cos)
    assert rewrapped.is_name_form() is True
    assert rewrapped.get_named_destination() == "Section2"


def test_round_trip_via_cos_object_preserves_string_form() -> None:
    original = PDNamedDestination(COSString("Section2"))
    cos = original.get_cos_object()
    assert isinstance(cos, COSString)

    rewrapped = PDNamedDestination(cos)
    assert rewrapped.is_string_form() is True
    assert rewrapped.get_named_destination() == "Section2"
