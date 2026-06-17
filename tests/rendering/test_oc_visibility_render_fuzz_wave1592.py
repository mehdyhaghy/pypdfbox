"""Render-time optional-content (OCG/OCMD) visibility fuzz — wave 1592.

These tests hammer the renderer's hidden-OCG nesting machinery and the
``/OC`` is-hidden predicates *directly*, without rasterising. They drive the
same ``PDFRenderer`` helpers that the draw operators consult
(``_push_marked_content`` / ``_pop_marked_content`` /
``_is_content_rendered`` / ``_property_list_is_hidden`` / ``is_group_enabled``)
and a mock draw counter, asserting the gate decisions match upstream
PDFBox ``PageDrawer`` optional-content handling:

* ``BDC /OC <MC>`` opens a hidden frame iff the group/membership is OFF;
* nested frames stack — an inner ON frame does not un-hide an outer OFF;
* the hidden-nesting counter pushes at ``BDC`` and pops at ``EMC`` (and a
  stray ``EMC`` on an empty stack is a no-op, never underflowing);
* a non-``/OC`` marked-content tag (``/Artifact`` etc.) is always visible;
* an ``/OC`` reference that resolves to nothing (missing group) is visible;
* an image / form XObject ``/OC`` entry is consulted independently of the
  marked-content stack;
* an OCMD is hidden per its ``/VE`` expression (or ``/P`` + ``/OCGs`` policy)
  against the current OCG states.

Parity reference: upstream ``org.apache.pdfbox.rendering.PageDrawer``
(``beginMarkedContentSequence`` / ``endMarkedContentSequence`` /
``isContentRendered`` / ``isHiddenOCG``).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (  # noqa: E501
    PDOptionalContentMembershipDictionary,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)
from pypdfbox.rendering.pdf_renderer import PDFRenderer

_OC = COSName.get_pdf_name("OC")
_ARTIFACT = COSName.get_pdf_name("Artifact")
_SPAN = COSName.get_pdf_name("Span")


# ---------------------------------------------------------------------------
# Test harness: a bare renderer whose property-list resolution is stubbed so
# the OC-stack machinery can be exercised without a full PDDocument. Mirrors
# the way ``__init__`` initialises the two OC fields.
# ---------------------------------------------------------------------------


def _bare_renderer(hidden_map: dict[object, bool] | None = None) -> PDFRenderer:
    """A renderer whose ``_property_list_is_hidden`` consults ``hidden_map``
    (identity → bool). Bypasses ``__init__`` so no document is needed."""
    r = PDFRenderer.__new__(PDFRenderer)
    r._nest_hidden_ocg = 0
    r._marked_content_oc_stack = []
    r._resources = None
    r._document = None
    hidden_map = hidden_map or {}

    def _resolve(props: object) -> object:
        # The BDC operand here is passed through verbatim (it already is the
        # typed property list for these direct-drive tests).
        return props

    def _is_hidden(prop: object) -> bool:
        if prop is None:
            return False
        return bool(hidden_map.get(id(prop), False))

    r._resolve_oc_property = _resolve  # type: ignore[method-assign]
    r._property_list_is_hidden = _is_hidden  # type: ignore[method-assign]
    return r


def _bdc_oc(r: PDFRenderer, marker: object) -> None:
    """Open a ``BDC /OC <marker>`` frame."""
    r._push_marked_content(_OC, marker)


def _bdc_tag(r: PDFRenderer, tag: COSName) -> None:
    """Open a non-OC ``BMC <tag>`` frame (carries no optional content)."""
    r._push_marked_content(tag, None)


def _emc(r: PDFRenderer) -> None:
    r._pop_marked_content()


# ---------------------------------------------------------------------------
# Single-frame on/off
# ---------------------------------------------------------------------------


def test_bdc_oc_on_paints() -> None:
    """A ``BDC /OC`` whose group is ON keeps content rendered."""
    on = object()
    r = _bare_renderer({id(on): False})
    _bdc_oc(r, on)
    assert r._is_content_rendered() is True
    assert r._nest_hidden_ocg == 0
    _emc(r)
    assert r._is_content_rendered() is True


def test_bdc_oc_off_skips() -> None:
    """A ``BDC /OC`` whose group is OFF suppresses content."""
    off = object()
    r = _bare_renderer({id(off): True})
    _bdc_oc(r, off)
    assert r._is_content_rendered() is False
    assert r._nest_hidden_ocg == 1
    _emc(r)
    assert r._is_content_rendered() is True
    assert r._nest_hidden_ocg == 0


def test_bdc_oc_off_then_on_sequence_independent() -> None:
    """Two sequential (non-nested) OC frames each gate independently."""
    off, on = object(), object()
    r = _bare_renderer({id(off): True, id(on): False})
    _bdc_oc(r, off)
    assert r._is_content_rendered() is False
    _emc(r)
    assert r._is_content_rendered() is True
    _bdc_oc(r, on)
    assert r._is_content_rendered() is True
    _emc(r)
    assert r._is_content_rendered() is True


# ---------------------------------------------------------------------------
# Nesting
# ---------------------------------------------------------------------------


def test_nested_outer_off_inner_on_inner_skipped() -> None:
    """Outer OFF hides everything until its EMC — an inner ON frame does NOT
    un-hide. The inner EMC must not decrement the hidden counter."""
    outer_off, inner_on = object(), object()
    r = _bare_renderer({id(outer_off): True, id(inner_on): False})
    _bdc_oc(r, outer_off)
    assert r._is_content_rendered() is False
    _bdc_oc(r, inner_on)  # ON, but nested inside OFF
    assert r._is_content_rendered() is False
    assert r._nest_hidden_ocg == 1  # inner ON added no hidden depth
    _emc(r)  # inner EMC — must stay hidden
    assert r._is_content_rendered() is False
    assert r._nest_hidden_ocg == 1
    _emc(r)  # outer EMC
    assert r._is_content_rendered() is True
    assert r._nest_hidden_ocg == 0


def test_nested_outer_on_inner_off_inner_only_skipped() -> None:
    """Outer ON, inner OFF — only the inner span is hidden; visibility is
    restored at the inner EMC."""
    outer_on, inner_off = object(), object()
    r = _bare_renderer({id(outer_on): False, id(inner_off): True})
    _bdc_oc(r, outer_on)
    assert r._is_content_rendered() is True
    _bdc_oc(r, inner_off)
    assert r._is_content_rendered() is False
    assert r._nest_hidden_ocg == 1
    _emc(r)  # inner EMC restores visibility
    assert r._is_content_rendered() is True
    assert r._nest_hidden_ocg == 0
    _emc(r)
    assert r._is_content_rendered() is True


def test_double_hidden_requires_two_pops() -> None:
    """Two OFF frames stack the hidden counter to 2; one EMC is not enough to
    un-hide."""
    a, b = object(), object()
    r = _bare_renderer({id(a): True, id(b): True})
    _bdc_oc(r, a)
    _bdc_oc(r, b)
    assert r._nest_hidden_ocg == 2
    assert r._is_content_rendered() is False
    _emc(r)
    assert r._nest_hidden_ocg == 1
    assert r._is_content_rendered() is False
    _emc(r)
    assert r._nest_hidden_ocg == 0
    assert r._is_content_rendered() is True


@pytest.mark.parametrize("depth", [3, 5, 8, 12])
def test_deep_off_nesting_balances(depth: int) -> None:
    """N stacked OFF frames push the counter to N and exactly N EMCs restore
    visibility — never going negative or leaking."""
    markers = [object() for _ in range(depth)]
    r = _bare_renderer({id(m): True for m in markers})
    for i, m in enumerate(markers, start=1):
        _bdc_oc(r, m)
        assert r._nest_hidden_ocg == i
    for remaining in range(depth - 1, -1, -1):
        _emc(r)
        assert r._nest_hidden_ocg == remaining
    assert r._is_content_rendered() is True


@pytest.mark.parametrize(
    "pattern",
    [
        "FH",  # off-frame then visible-frame
        "HF",
        "FHF",
        "HFH",
        "FFHH",
        "HHFF",
        "FHHF",
    ],
)
def test_interleaved_on_off_patterns_balance(pattern: str) -> None:
    """Interleaved ON('F')/OFF('H') frames keep the counter consistent and
    return to zero after all EMCs."""
    on, off = object(), object()
    r = _bare_renderer({id(on): False, id(off): True})
    opened: list[str] = []
    for ch in pattern:
        marker = off if ch == "H" else on
        _bdc_oc(r, marker)
        opened.append(ch)
    # Hidden depth equals the number of 'H' frames opened.
    assert r._nest_hidden_ocg == pattern.count("H")
    for _ in opened:
        _emc(r)
    assert r._nest_hidden_ocg == 0
    assert r._is_content_rendered() is True


# ---------------------------------------------------------------------------
# Non-OC tags / missing groups / stray EMC
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tag", [_ARTIFACT, _SPAN, COSName.get_pdf_name("P")])
def test_non_oc_tag_always_visible(tag: COSName) -> None:
    """A marked-content tag that is not ``/OC`` never gates content, even when
    a property list is supplied."""
    always_hidden = object()
    r = _bare_renderer({id(always_hidden): True})
    r._push_marked_content(tag, always_hidden)
    assert r._is_content_rendered() is True
    assert r._nest_hidden_ocg == 0
    _emc(r)
    assert r._is_content_rendered() is True


def test_bmc_oc_without_properties_is_visible() -> None:
    """``BMC /OC`` with no property-list operand carries no OCG → visible."""
    r = _bare_renderer()
    r._push_marked_content(_OC, None)
    assert r._is_content_rendered() is True
    assert r._nest_hidden_ocg == 0
    _emc(r)
    assert r._is_content_rendered() is True


def test_bdc_oc_missing_group_defaults_visible() -> None:
    """An ``/OC`` operand that resolves to ``None`` (missing /Properties
    entry) is treated as visible, matching upstream which only hides content
    it can positively resolve as OFF."""
    r = _bare_renderer()

    # Resolution yields None (e.g. a /Properties name with no entry).
    def _resolve_none(_props: object) -> object:
        return None

    r._resolve_oc_property = _resolve_none  # type: ignore[method-assign]
    r._push_marked_content(_OC, COSName.get_pdf_name("MissingMC"))
    assert r._is_content_rendered() is True
    assert r._nest_hidden_ocg == 0


def test_stray_emc_on_empty_stack_is_noop() -> None:
    """An unbalanced ``EMC`` (no matching ``BDC``) must not underflow the
    hidden counter or raise."""
    r = _bare_renderer()
    _emc(r)
    _emc(r)
    assert r._nest_hidden_ocg == 0
    assert r._marked_content_oc_stack == []
    assert r._is_content_rendered() is True


def test_extra_emc_after_balanced_pair_is_noop() -> None:
    """One extra EMC beyond the balanced pairs is ignored, not negative."""
    off = object()
    r = _bare_renderer({id(off): True})
    _bdc_oc(r, off)
    _emc(r)
    _emc(r)  # stray
    assert r._nest_hidden_ocg == 0
    assert r._is_content_rendered() is True


def test_emc_never_decrements_below_zero_with_visible_frames() -> None:
    """Popping visible frames never touches the hidden counter."""
    on = object()
    r = _bare_renderer({id(on): False})
    _bdc_oc(r, on)
    _bdc_oc(r, on)
    assert r._nest_hidden_ocg == 0
    _emc(r)
    _emc(r)
    _emc(r)  # stray
    assert r._nest_hidden_ocg == 0


# ---------------------------------------------------------------------------
# is_group_enabled / missing-group default via real OCProperties
# ---------------------------------------------------------------------------


class _FakeCatalog:
    def __init__(self, ocp: PDOptionalContentProperties | None) -> None:
        self._ocp = ocp

    def get_oc_properties(self) -> PDOptionalContentProperties | None:
        return self._ocp


class _FakeDoc:
    def __init__(self, ocp: PDOptionalContentProperties | None) -> None:
        self._cat = _FakeCatalog(ocp)

    def get_document_catalog(self) -> _FakeCatalog:
        return self._cat


def _renderer_with_ocp(ocp: PDOptionalContentProperties | None) -> PDFRenderer:
    r = PDFRenderer.__new__(PDFRenderer)
    r._nest_hidden_ocg = 0
    r._marked_content_oc_stack = []
    r._document = _FakeDoc(ocp)
    r._resources = None
    return r


def test_is_group_enabled_no_ocproperties_returns_true() -> None:
    """With no /OCProperties at all, every group reads enabled (upstream
    ``PDFRenderer.isGroupEnabled`` returns true when config is absent)."""
    r = _renderer_with_ocp(None)
    g = PDOptionalContentGroup("Anything")
    assert r.is_group_enabled(g) is True
    assert r._property_list_is_hidden(g) is False


def test_is_group_enabled_off_group_hidden() -> None:
    """A group placed in the default config's /OFF array is hidden."""
    ocp = PDOptionalContentProperties()
    g = PDOptionalContentGroup("Layer")
    ocp.add_group(g)
    ocp.set_group_enabled(g, False)
    r = _renderer_with_ocp(ocp)
    assert r.is_group_enabled(g) is False
    assert r._property_list_is_hidden(g) is True


def test_is_group_enabled_on_group_visible() -> None:
    ocp = PDOptionalContentProperties()
    g = PDOptionalContentGroup("Layer")
    ocp.add_group(g)
    ocp.set_group_enabled(g, True)
    r = _renderer_with_ocp(ocp)
    assert r.is_group_enabled(g) is True
    assert r._property_list_is_hidden(g) is False


def test_group_not_in_config_uses_base_state() -> None:
    """A group absent from /ON and /OFF falls back to the /D BaseState; the
    default BaseState is ON → visible."""
    ocp = PDOptionalContentProperties()
    # No groups registered → BaseState default "ON".
    r = _renderer_with_ocp(ocp)
    stray = PDOptionalContentGroup("Unregistered")
    assert r.is_group_enabled(stray) is True
    assert r._property_list_is_hidden(stray) is False


def test_base_state_off_hides_unlisted_group() -> None:
    """When the default config's BaseState is OFF, a group not explicitly in
    /ON is hidden."""
    ocp = PDOptionalContentProperties()
    g = PDOptionalContentGroup("Layer")
    ocp.add_group(g)
    ocp.set_base_state("OFF")
    r = _renderer_with_ocp(ocp)
    assert r.is_group_enabled(g) is False
    assert r._property_list_is_hidden(g) is True


# ---------------------------------------------------------------------------
# OCMD visibility through the renderer's _property_list_is_hidden
# ---------------------------------------------------------------------------


def _ocp_with(states: dict[str, bool]) -> tuple[
    PDOptionalContentProperties, dict[str, PDOptionalContentGroup]
]:
    ocp = PDOptionalContentProperties()
    groups: dict[str, PDOptionalContentGroup] = {}
    for name, on in states.items():
        g = PDOptionalContentGroup(name)
        ocp.add_group(g)
        ocp.set_group_enabled(g, on)
        groups[name] = g
    return ocp, groups


@pytest.mark.parametrize(
    ("policy", "states", "expect_hidden"),
    [
        # AnyOn: visible iff >=1 ON.
        ("AnyOn", {"a": True, "b": False}, False),
        ("AnyOn", {"a": False, "b": False}, True),
        ("AnyOn", {"a": True, "b": True}, False),
        # AllOn: visible iff every ON.
        ("AllOn", {"a": True, "b": True}, False),
        ("AllOn", {"a": True, "b": False}, True),
        # AnyOff: visible iff >=1 OFF.
        ("AnyOff", {"a": True, "b": False}, False),
        ("AnyOff", {"a": True, "b": True}, True),
        # AllOff: visible iff every OFF.
        ("AllOff", {"a": False, "b": False}, False),
        ("AllOff", {"a": True, "b": False}, True),
    ],
)
def test_ocmd_policy_hidden_decision(
    policy: str, states: dict[str, bool], expect_hidden: bool
) -> None:
    """The renderer's ``_property_list_is_hidden`` evaluates an OCMD's /P
    policy against the live OCG states."""
    ocp, groups = _ocp_with(states)
    ocmd = PDOptionalContentMembershipDictionary()
    for g in groups.values():
        ocmd.add_ocg(g)
    ocmd.set_visibility_policy(policy)
    r = _renderer_with_ocp(ocp)
    assert r._property_list_is_hidden(ocmd) is expect_hidden


def test_ocmd_ve_not_inverts_polarity() -> None:
    """An OCMD with ``/VE = [/Not <ocg>]`` over an OFF group is VISIBLE
    (``Not(OFF) == visible``); flipping the group ON makes it HIDDEN."""
    ocp, groups = _ocp_with({"L": False})
    g = groups["L"]
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.add_ocg(g)
    ve = COSArray()
    ve.add(COSName.get_pdf_name("Not"))
    ve.add(g.get_cos_object())
    ocmd.set_visibility_expression(ve)
    r = _renderer_with_ocp(ocp)
    # group OFF → Not(OFF) → visible → not hidden
    assert r._property_list_is_hidden(ocmd) is False
    # flip the group ON in the default config → Not(ON) → hidden
    ocp.set_group_enabled(g, True)
    assert r._property_list_is_hidden(ocmd) is True


def test_ocmd_ve_and_or_combinations() -> None:
    """A nested ``/VE = [/Or [/And A B] [/Not C]]`` evaluates against live
    OCG states through the renderer."""
    ocp, groups = _ocp_with({"A": True, "B": False, "C": True})
    a, b, c = groups["A"], groups["B"], groups["C"]
    ocmd = PDOptionalContentMembershipDictionary()
    for g in (a, b, c):
        ocmd.add_ocg(g)
    inner_and = COSArray()
    inner_and.add(COSName.get_pdf_name("And"))
    inner_and.add(a.get_cos_object())
    inner_and.add(b.get_cos_object())
    inner_not = COSArray()
    inner_not.add(COSName.get_pdf_name("Not"))
    inner_not.add(c.get_cos_object())
    ve = COSArray()
    ve.add(COSName.get_pdf_name("Or"))
    ve.add(inner_and)
    ve.add(inner_not)
    ocmd.set_visibility_expression(ve)
    r = _renderer_with_ocp(ocp)
    # And(A=ON, B=OFF) = False; Not(C=ON) = False; Or(False, False) = False
    # → not visible → hidden.
    assert r._property_list_is_hidden(ocmd) is True
    # Turn B ON → And(ON, ON) = True → Or True → visible.
    ocp.set_group_enabled(b, True)
    assert r._property_list_is_hidden(ocmd) is False


def test_ocmd_drives_marked_content_gate_end_to_end() -> None:
    """A ``BDC /OC <OCMD>`` opens a hidden frame iff the OCMD evaluates to not
    visible, exercising the full push → is_content_rendered → pop path with a
    real OCMD resolved through the renderer."""
    ocp, groups = _ocp_with({"L": False})
    g = groups["L"]
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.add_ocg(g)
    ocmd.set_visibility_policy("AnyOn")  # AnyOn over a single OFF → not visible
    r = _renderer_with_ocp(ocp)

    # The BDC operand is the OCMD object directly for this end-to-end drive.
    r._resolve_oc_property = lambda props: props  # type: ignore[method-assign]
    r._push_marked_content(_OC, ocmd)
    assert r._is_content_rendered() is False  # hidden (AnyOn over OFF)
    r._pop_marked_content()
    assert r._is_content_rendered() is True

    # Flip the group ON → AnyOn over ON → visible → frame stays visible.
    ocp.set_group_enabled(g, True)
    r._push_marked_content(_OC, ocmd)
    assert r._is_content_rendered() is True
    r._pop_marked_content()


def test_malformed_ocmd_fails_open_visible() -> None:
    """A property list whose visibility evaluation raises is treated as
    visible (fail-open), matching upstream which only hides positively
    resolved OFF content."""
    ocp, _groups = _ocp_with({})

    class _Boom(PDOptionalContentMembershipDictionary):
        def is_visible_with(self, _resolver: object) -> bool:  # type: ignore[override]
            raise RuntimeError("malformed /VE")

    boom = _Boom()
    r = _renderer_with_ocp(ocp)
    assert r._property_list_is_hidden(boom) is False


def test_none_property_list_not_hidden() -> None:
    r = _renderer_with_ocp(PDOptionalContentProperties())
    assert r._property_list_is_hidden(None) is False
