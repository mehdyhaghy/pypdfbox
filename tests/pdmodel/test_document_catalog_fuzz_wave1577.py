"""Non-oracle fuzz audit for :class:`PDDocumentCatalog` accessors (wave 1577,
agent D).

Hammers the document-catalog accessors directly over hand-built (and often
malformed) root dictionaries, asserting against the Apache PDFBox 3.0.7
contract WITHOUT requiring the live Java oracle harness. The differential
(byte-for-byte vs Java) audit lives in
``tests/pdmodel/oracle/test_document_catalog_fuzz_wave1547.py``; this module
pins the same behaviours as plain in-process asserts so regressions are caught
even on machines without the oracle JVM.

Key upstream-parity facts pinned here (PDF 32000-1 §7.7.3.3 / Table 28):

* ``getPageMode()`` is DEFAULT-applying upstream — absent / unrecognised name
  → ``UseNone``. pypdfbox splits this into the tolerant ``get_page_mode()``
  (``None`` when absent / unknown, lets callers distinguish explicit-vs-default)
  and the upstream-faithful ``get_page_mode_or_default()`` (``UseNone``).
* ``getPageLayout()`` similarly defaults to ``SinglePage``; mirrored by
  ``get_page_layout_or_default()``.
* ``getOpenAction()`` dispatches on the COS shape: ``COSDictionary`` →
  ``PDAction`` (``None`` when ``/S`` is absent or unknown, matching upstream's
  ``PDActionFactory.createAction`` null arm), ``COSArray`` → ``PDDestination``,
  anything else (name / string shorthand) → ``None``.
* ``getVersion()`` reads ``/Version`` as a name (spec form) or string (lenient).
* ``getOutputIntents()`` returns a *list*; pypdfbox skips non-dict array
  entries defensively (a pinned divergence — upstream casts unconditionally and
  throws ``ClassCastException``).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel import PDDocument, PDDocumentCatalog
from pypdfbox.pdmodel.interactive.action import PDActionGoTo, PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)
from pypdfbox.pdmodel.page_layout import PageLayout
from pypdfbox.pdmodel.page_mode import PageMode

_N = COSName.get_pdf_name


# --------------------------------------------------------------------- helpers


def _catalog(**entries: object) -> PDDocumentCatalog:
    """Build a :class:`PDDocumentCatalog` directly over a hand-built root.

    Each kwarg maps a PDF key name to a COS value; ``/Type /Catalog`` is
    stamped automatically (the constructor does this anyway, but being explicit
    keeps the fuzzed dict honest).
    """
    root = COSDictionary()
    root.set_item(_N("Type"), _N("Catalog"))
    for key, value in entries.items():
        root.set_item(_N(key), value)
    doc = PDDocument()
    return PDDocumentCatalog(doc, root)


def _action(sub_type: str | None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("Action"))
    if sub_type is not None:
        d.set_item(_N("S"), _N(sub_type))
    return d


def _dest_array() -> COSArray:
    arr = COSArray()
    page = COSDictionary()
    page.set_item(_N("Type"), _N("Page"))
    arr.add(page)
    arr.add(_N("Fit"))
    return arr


# ---------------------------------------------------------------- page mode


@pytest.mark.parametrize(
    ("name", "member"),
    [
        ("UseNone", PageMode.USE_NONE),
        ("UseOutlines", PageMode.USE_OUTLINES),
        ("UseThumbs", PageMode.USE_THUMBS),
        ("FullScreen", PageMode.FULL_SCREEN),
        ("UseOC", PageMode.USE_OPTIONAL_CONTENT),
        ("UseAttachments", PageMode.USE_ATTACHMENTS),
    ],
)
def test_page_mode_each_enum_value(name: str, member: PageMode) -> None:
    cat = _catalog(PageMode=_N(name))
    assert cat.get_page_mode() is member
    assert cat.get_page_mode() == name
    assert cat.get_page_mode_or_default() is member


def test_page_mode_absent_is_none_but_default_use_none() -> None:
    cat = _catalog()
    # Tolerant accessor distinguishes "explicit" from "default".
    assert cat.get_page_mode() is None
    # Default-applying accessor mirrors upstream getPageMode() == UseNone.
    assert cat.get_page_mode_or_default() is PageMode.USE_NONE


def test_page_mode_unknown_name_is_none_default_use_none() -> None:
    cat = _catalog(PageMode=_N("UseXfa"))
    assert cat.get_page_mode() is None
    assert cat.get_page_mode_or_default() is PageMode.USE_NONE


def test_page_mode_string_form_is_lenient() -> None:
    # Spec form is a name; upstream getNameAsString also accepts a COSString.
    cat = _catalog(PageMode=COSString("UseThumbs"))
    assert cat.get_page_mode() is PageMode.USE_THUMBS


def test_page_mode_wrong_type_is_none() -> None:
    cat = _catalog(PageMode=COSInteger.get(1))
    assert cat.get_page_mode() is None
    assert cat.get_page_mode_or_default() is PageMode.USE_NONE


def test_page_mode_round_trip_enum_and_string() -> None:
    cat = _catalog()
    cat.set_page_mode(PageMode.FULL_SCREEN)
    assert cat.get_page_mode() is PageMode.FULL_SCREEN
    assert cat.get_cos_object().get_name_as_string(_N("PageMode")) == "FullScreen"
    cat.set_page_mode("UseAttachments")
    assert cat.get_page_mode() is PageMode.USE_ATTACHMENTS
    cat.set_page_mode(None)
    assert cat.get_page_mode() is None


# ---------------------------------------------------------------- page layout


@pytest.mark.parametrize(
    ("name", "member"),
    [
        ("SinglePage", PageLayout.SINGLE_PAGE),
        ("OneColumn", PageLayout.ONE_COLUMN),
        ("TwoColumnLeft", PageLayout.TWO_COLUMN_LEFT),
        ("TwoColumnRight", PageLayout.TWO_COLUMN_RIGHT),
        ("TwoPageLeft", PageLayout.TWO_PAGE_LEFT),
        ("TwoPageRight", PageLayout.TWO_PAGE_RIGHT),
    ],
)
def test_page_layout_each_enum_value(name: str, member: PageLayout) -> None:
    cat = _catalog(PageLayout=_N(name))
    assert cat.get_page_layout() is member
    assert cat.get_page_layout() == name
    assert cat.get_page_layout_or_default() is member


def test_page_layout_absent_default_single_page() -> None:
    cat = _catalog()
    assert cat.get_page_layout() is None
    assert cat.get_page_layout_or_default() is PageLayout.SINGLE_PAGE


def test_page_layout_unknown_name_default_single_page() -> None:
    cat = _catalog(PageLayout=_N("Sideways"))
    assert cat.get_page_layout() is None
    assert cat.get_page_layout_or_default() is PageLayout.SINGLE_PAGE


def test_page_layout_string_form_is_lenient() -> None:
    cat = _catalog(PageLayout=COSString("OneColumn"))
    assert cat.get_page_layout() is PageLayout.ONE_COLUMN


def test_page_layout_round_trip() -> None:
    cat = _catalog()
    cat.set_page_layout(PageLayout.TWO_PAGE_RIGHT)
    assert cat.get_page_layout() is PageLayout.TWO_PAGE_RIGHT
    cat.set_page_layout("TwoColumnLeft")
    assert cat.get_page_layout() is PageLayout.TWO_COLUMN_LEFT
    cat.set_page_layout(None)
    assert cat.get_page_layout() is None


def test_page_layout_from_string_is_case_sensitive() -> None:
    # Upstream PageLayout.fromString matches the exact PDF name (case-sensitive).
    with pytest.raises(ValueError):
        PageLayout.from_string("onecolumn")
    with pytest.raises(ValueError):
        PageMode.from_string("usenone")


# ---------------------------------------------------------------- open action


def test_open_action_dict_with_known_subtype_is_action() -> None:
    cat = _catalog(OpenAction=_action("GoTo"))
    action = cat.get_open_action()
    assert isinstance(action, PDActionGoTo)


def test_open_action_uri_subtype() -> None:
    cat = _catalog(OpenAction=_action("URI"))
    assert isinstance(cat.get_open_action(), PDActionURI)


def test_open_action_dict_without_subtype_is_none() -> None:
    # /D-only shorthand dict: upstream PDActionFactory returns null (no /S).
    cat = _catalog(OpenAction=_action(None))
    assert cat.get_open_action() is None


def test_open_action_dict_unknown_subtype_is_none() -> None:
    # Unknown /S → upstream factory returns null (no PDActionUnknown fallback).
    cat = _catalog(OpenAction=_action("Bogus"))
    assert cat.get_open_action() is None


def test_open_action_array_is_destination() -> None:
    cat = _catalog(OpenAction=_dest_array())
    dest = cat.get_open_action()
    assert isinstance(dest, PDDestination)
    assert not isinstance(dest, (PDActionGoTo, PDActionURI))


def test_open_action_name_shorthand_is_none() -> None:
    # Catalog dispatch ignores name/string shorthand (returns None), unlike the
    # looser PDDestinationOrAction.create factory.
    cat = _catalog(OpenAction=_N("Foo"))
    assert cat.get_open_action() is None


def test_open_action_string_shorthand_is_none() -> None:
    cat = _catalog(OpenAction=COSString("Foo"))
    assert cat.get_open_action() is None


def test_open_action_absent_is_none() -> None:
    cat = _catalog()
    assert cat.get_open_action() is None
    assert cat.has_open_action() is False


def test_open_action_has_predicate() -> None:
    assert _catalog(OpenAction=_action("GoTo")).has_open_action()
    assert _catalog(OpenAction=_dest_array()).has_open_action()
    assert not _catalog(OpenAction=_N("Foo")).has_open_action()


# ---------------------------------------------------------------- version


def test_version_name_form() -> None:
    cat = _catalog(Version=_N("1.7"))
    assert cat.get_version() == "1.7"


def test_version_string_form_lenient() -> None:
    cat = _catalog(Version=COSString("1.5"))
    assert cat.get_version() == "1.5"


def test_version_wrong_type_is_none() -> None:
    assert _catalog(Version=COSFloat(2.0)).get_version() is None
    assert _catalog(Version=COSInteger.get(2)).get_version() is None
    assert _catalog(Version=COSArray()).get_version() is None


def test_version_absent_is_none() -> None:
    assert _catalog().get_version() is None


def test_version_overrides_header_on_document() -> None:
    # PDDocument.get_version consults the catalog /Version only when the header
    # is already >= 1.4, then returns the max. Default header is 1.4.
    doc = PDDocument()
    assert doc.get_version() == pytest.approx(1.4)
    doc.get_document_catalog().set_version("1.7")
    assert doc.get_version() == pytest.approx(1.7)
    doc.close()


def test_version_round_trip() -> None:
    cat = _catalog()
    cat.set_version("2.0")
    assert cat.get_version() == "2.0"
    cat.set_version(None)
    assert cat.get_version() is None


# ---------------------------------------------------------------- language


def test_language_string_form() -> None:
    assert _catalog(Lang=COSString("en-US")).get_language() == "en-US"


def test_language_name_form_is_none() -> None:
    # /Lang is a text string; a name value is not accepted (upstream reads it
    # as a COSString only).
    assert _catalog(Lang=_N("en-US")).get_language() is None


def test_language_wrong_type_is_none() -> None:
    assert _catalog(Lang=COSInteger.get(1)).get_language() is None


def test_language_round_trip() -> None:
    cat = _catalog()
    cat.set_language("fr-CA")
    assert cat.get_language() == "fr-CA"
    cat.set_language(None)
    assert cat.get_language() is None


# ---------------------------------------------------------------- mark info


def test_mark_info_present_is_wrapper() -> None:
    mi = COSDictionary()
    mi.set_item(_N("Type"), _N("MarkInfo"))
    mi.set_boolean(_N("Marked"), True)
    cat = _catalog(MarkInfo=mi)
    assert cat.get_mark_info() is not None
    assert cat.is_document_marked() is True


def test_mark_info_absent_is_none_marked_false() -> None:
    cat = _catalog()
    assert cat.get_mark_info() is None
    assert cat.is_document_marked() is False
    assert cat.has_user_properties() is False
    assert cat.has_suspects() is False


def test_mark_info_wrong_type_is_none() -> None:
    cat = _catalog(MarkInfo=COSArray())
    assert cat.get_mark_info() is None
    assert cat.is_document_marked() is False


def test_mark_info_set_document_marked_creates_dict() -> None:
    cat = _catalog()
    cat.set_document_marked(True)
    assert cat.is_document_marked() is True
    assert cat.get_mark_info() is not None


# ---------------------------------------------------------------- output intents


def test_output_intents_clean_array_is_list() -> None:
    arr = COSArray()
    oi = COSDictionary()
    oi.set_item(_N("Type"), _N("OutputIntent"))
    oi.set_item(_N("S"), _N("GTS_PDFA1"))
    arr.add(oi)
    cat = _catalog(OutputIntents=arr)
    intents = cat.get_output_intents()
    assert isinstance(intents, list)
    assert len(intents) == 1


def test_output_intents_absent_is_empty_list() -> None:
    cat = _catalog()
    assert cat.get_output_intents() == []


def test_output_intents_wrong_type_is_empty_list() -> None:
    cat = _catalog(OutputIntents=COSDictionary())
    assert cat.get_output_intents() == []


def test_output_intents_skips_non_dict_entries() -> None:
    # Pinned divergence: upstream casts each entry to COSDictionary and throws
    # ClassCastException on the stray name; pypdfbox skips it defensively.
    arr = COSArray()
    oi = COSDictionary()
    oi.set_item(_N("S"), _N("GTS_PDFA1"))
    arr.add(oi)
    arr.add(_N("NotADict"))
    cat = _catalog(OutputIntents=arr)
    assert len(cat.get_output_intents()) == 1


# ---------------------------------------------------------------- outline / names


def test_document_outline_present_is_wrapper() -> None:
    outline = COSDictionary()
    cat = _catalog(Outlines=outline)
    assert cat.get_document_outline() is not None
    assert cat.has_outline() is True


def test_document_outline_absent_is_none() -> None:
    cat = _catalog()
    assert cat.get_document_outline() is None
    assert cat.has_outline() is False


def test_document_outline_wrong_type_is_none() -> None:
    cat = _catalog(Outlines=COSInteger.get(0))
    assert cat.get_document_outline() is None


def test_names_present_is_wrapper() -> None:
    cat = _catalog(Names=COSDictionary())
    assert cat.get_names() is not None
    assert cat.has_names() is True


def test_names_absent_is_none() -> None:
    cat = _catalog()
    assert cat.get_names() is None
    assert cat.has_names() is False


def test_names_wrong_type_is_none() -> None:
    cat = _catalog(Names=COSArray())
    assert cat.get_names() is None
