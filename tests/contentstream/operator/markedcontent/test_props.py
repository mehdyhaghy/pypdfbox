"""Tests for the shared marked-content helpers in
``pypdfbox.contentstream.operator.markedcontent._props``.

Covers tag extraction, property-list resolution, ``/MCID`` accessors,
and the ``/Artifact`` predicate. The helpers are exercised both
directly (no engine) and indirectly through the operator classes — the
direct tests pin down semantics for downstream callers (extractors /
structure builders) that consume the helpers without going through the
operator pipeline.
"""
from __future__ import annotations

import pytest

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator.markedcontent import (
    ARTIFACT_TAG,
    MCID_DEFAULT,
    MCID_KEY,
    extract_tag,
    get_mcid,
    has_mcid,
    is_artifact_tag,
    resolve_property_dict,
)
from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.pd_resources import PDResources

# ---- Constants -------------------------------------------------------

def test_mcid_key_is_pdf_name() -> None:
    assert COSName.get_pdf_name("MCID") == MCID_KEY


def test_artifact_tag_is_pdf_name() -> None:
    assert COSName.get_pdf_name("Artifact") == ARTIFACT_TAG


def test_mcid_default_is_minus_one() -> None:
    # Upstream PDMarkedContent.getMCID() uses -1 as the absent sentinel;
    # COSDictionary.get_int() also defaults to -1, so the constant
    # documents intent without changing behaviour.
    assert MCID_DEFAULT == -1


# ---- extract_tag -----------------------------------------------------

def test_extract_tag_returns_first_name_operand() -> None:
    tag = COSName.get_pdf_name("Span")
    assert extract_tag([tag]) is tag


def test_extract_tag_with_extra_operands_picks_first() -> None:
    tag = COSName.get_pdf_name("P")
    extra = COSDictionary()
    assert extract_tag([tag, extra]) is tag


def test_extract_tag_with_empty_operands_returns_none() -> None:
    assert extract_tag([]) is None


def test_extract_tag_with_non_name_first_operand_returns_none() -> None:
    # A malformed BMC with a string instead of a name — pypdfbox is
    # tolerant: the helper returns None and the operator silently no-ops
    # the tag.
    assert extract_tag([COSString("not-a-name")]) is None


def test_extract_tag_with_non_name_first_operand_does_not_scan() -> None:
    # Even if a later operand is a name, only the first slot counts —
    # the operand grammar for BMC/BDC/MP/DP places the tag at index 0.
    later = COSName.get_pdf_name("Span")
    assert extract_tag([COSDictionary(), later]) is None


# ---- resolve_property_dict ------------------------------------------

class _ResEngine(PDFStreamEngine):
    """Minimal engine exposing get_resources(); avoids the full engine
    setup chain when all we want is the resources accessor."""

    def __init__(self, resources: PDResources | None) -> None:
        super().__init__()
        if resources is not None:
            self._resources = resources


def test_resolve_property_dict_with_inline_dict() -> None:
    tag = COSName.get_pdf_name("Span")
    props = COSDictionary()
    assert resolve_property_dict([tag, props], None) is props


def test_resolve_property_dict_with_inline_dict_ignores_context() -> None:
    # An inline dictionary takes precedence and never consults the
    # engine's resources — even when a context is supplied.
    tag = COSName.get_pdf_name("Span")
    props = COSDictionary()
    engine = _ResEngine(PDResources())
    assert resolve_property_dict([tag, props], engine) is props


def test_resolve_property_dict_too_few_operands() -> None:
    assert resolve_property_dict([], None) is None
    assert resolve_property_dict([COSName.get_pdf_name("Span")], None) is None


def test_resolve_property_dict_named_lookup() -> None:
    res = PDResources()
    inner = COSDictionary()
    inner.set_item(MCID_KEY, COSInteger.get(42))
    name = COSName.get_pdf_name("MyProps")
    res.put(COSName.get_pdf_name("Properties"), name, inner)
    engine = _ResEngine(res)

    out = resolve_property_dict(
        [COSName.get_pdf_name("Span"), name], engine
    )
    assert out is not None
    assert out.get_int(MCID_KEY) == 42


def test_resolve_property_dict_named_lookup_missing_returns_none() -> None:
    engine = _ResEngine(PDResources())
    out = resolve_property_dict(
        [
            COSName.get_pdf_name("Span"),
            COSName.get_pdf_name("AbsentProps"),
        ],
        engine,
    )
    assert out is None


def test_resolve_property_dict_named_lookup_without_context() -> None:
    # Named lookup requires a context; without one we cannot resolve.
    out = resolve_property_dict(
        [
            COSName.get_pdf_name("Span"),
            COSName.get_pdf_name("MyProps"),
        ],
        None,
    )
    assert out is None


def test_resolve_property_dict_with_string_property_returns_none() -> None:
    # Per ISO 32000-1 §14.6, the second operand must be a name or a
    # dictionary. Anything else is malformed — return None.
    out = resolve_property_dict(
        [COSName.get_pdf_name("Span"), COSString("oops")],
        _ResEngine(PDResources()),
    )
    assert out is None


def test_resolve_property_dict_context_without_get_resources() -> None:
    # Some engine stand-ins (or registry-only registrations) won't
    # expose get_resources — the helper must defensively skip rather
    # than AttributeError.
    class _Bare:
        pass

    out = resolve_property_dict(
        [
            COSName.get_pdf_name("Span"),
            COSName.get_pdf_name("MyProps"),
        ],
        _Bare(),
    )
    assert out is None


def test_resolve_property_dict_get_resources_raises_swallowed() -> None:
    class _Boom:
        def get_resources(self):  # noqa: ANN001 — test stub
            raise RuntimeError("synthetic")

    out = resolve_property_dict(
        [
            COSName.get_pdf_name("Span"),
            COSName.get_pdf_name("MyProps"),
        ],
        _Boom(),
    )
    assert out is None


def test_resolve_property_dict_get_resources_returns_none_swallowed() -> None:
    # Page with no resources at all — get_resources() may legitimately
    # return None. The helper must treat this as "unresolved".
    class _NoRes:
        def get_resources(self):  # noqa: ANN001 — test stub
            return None

    out = resolve_property_dict(
        [
            COSName.get_pdf_name("Span"),
            COSName.get_pdf_name("MyProps"),
        ],
        _NoRes(),
    )
    assert out is None


# ---- get_mcid / has_mcid --------------------------------------------

def test_get_mcid_with_none_properties() -> None:
    assert get_mcid(None) == -1


def test_get_mcid_with_empty_dict() -> None:
    assert get_mcid(COSDictionary()) == -1


def test_get_mcid_with_value() -> None:
    d = COSDictionary()
    d.set_item(MCID_KEY, COSInteger.get(7))
    assert get_mcid(d) == 7


def test_get_mcid_zero_is_distinct_from_default() -> None:
    # MCID 0 is a valid identifier (typical for the first marked
    # sequence on a page); don't conflate it with the -1 sentinel.
    d = COSDictionary()
    d.set_item(MCID_KEY, COSInteger.get(0))
    assert get_mcid(d) == 0


@pytest.mark.parametrize("mcid", [1, 100, 12345])
def test_get_mcid_round_trips_positive_values(mcid: int) -> None:
    d = COSDictionary()
    d.set_item(MCID_KEY, COSInteger.get(mcid))
    assert get_mcid(d) == mcid


def test_has_mcid_false_for_none() -> None:
    assert has_mcid(None) is False


def test_has_mcid_false_for_empty() -> None:
    assert has_mcid(COSDictionary()) is False


def test_has_mcid_true_when_present() -> None:
    d = COSDictionary()
    d.set_item(MCID_KEY, COSInteger.get(0))
    assert has_mcid(d) is True


def test_has_mcid_true_even_when_value_is_minus_one() -> None:
    # A literal -1 stored in /MCID is technically malformed but
    # representable; has_mcid distinguishes "key absent" from "value is
    # the sentinel".
    d = COSDictionary()
    d.set_item(MCID_KEY, COSInteger.get(-1))
    assert has_mcid(d) is True
    assert get_mcid(d) == -1


# ---- is_artifact_tag -------------------------------------------------

def test_is_artifact_tag_true_for_artifact() -> None:
    assert is_artifact_tag(COSName.get_pdf_name("Artifact")) is True


def test_is_artifact_tag_true_for_cached_constant() -> None:
    # The package re-exports ARTIFACT_TAG; using it directly should
    # behave identically to a freshly-constructed name (COSName is
    # interned via get_pdf_name).
    assert is_artifact_tag(ARTIFACT_TAG) is True


def test_is_artifact_tag_false_for_other_tag() -> None:
    assert is_artifact_tag(COSName.get_pdf_name("Span")) is False


def test_is_artifact_tag_false_for_none() -> None:
    assert is_artifact_tag(None) is False


def test_is_artifact_tag_case_sensitive() -> None:
    # PDF names are case-sensitive — /artifact (lowercase) is not the
    # standard structural tag.
    assert is_artifact_tag(COSName.get_pdf_name("artifact")) is False
