"""Write-side helpers on :class:`PDOptionalContentProperties` — not part of
upstream PDFBox 3.0; pypdfbox enrichment that wraps ``set_group_enabled``
plus an :meth:`add_group` / :meth:`remove_group` symmetric pair and the
upstream-named :meth:`get_group_names` accessor.

The toggling tests synthesize a small OCMD/OCG hierarchy and feed the
resulting visibility set into :class:`PDOptionalContentMembershipDictionary`
so we exercise the real read-side parity path
(:meth:`compute_visible_ocgs`)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentMembershipDictionary,
    PDOptionalContentProperties,
)


def _build(
    *names: str,
) -> tuple[PDOptionalContentProperties, list[PDOptionalContentGroup]]:
    props = PDOptionalContentProperties()
    groups = [PDOptionalContentGroup(n) for n in names]
    for g in groups:
        props.add_group(g)
    return props, groups


def _default_config(props: PDOptionalContentProperties) -> COSDictionary:
    d = props.get_cos_object().get_dictionary_object(COSName.D)  # type: ignore[attr-defined]
    assert isinstance(d, COSDictionary)
    return d


def _state_array(
    props: PDOptionalContentProperties, name: str
) -> COSArray:
    arr = _default_config(props).get_dictionary_object(COSName.get_pdf_name(name))
    assert isinstance(arr, COSArray)
    return arr


# ---------- set_visible / set_hidden / set_visibility ----------


def test_set_visible_routes_through_set_group_enabled() -> None:
    props, (a, _b) = _build("A", "B")
    # First call: not yet in /ON or /OFF → returns False (added).
    assert props.set_visible(a) is False
    assert props.is_group_enabled(a) is True


def test_set_hidden_routes_through_set_group_enabled() -> None:
    props, (a, _b) = _build("A", "B")
    assert props.set_hidden(a) is False
    assert props.is_group_enabled(a) is False


def test_set_visibility_round_trip_by_name() -> None:
    props, (a, b) = _build("A", "B")
    props.set_visibility("A", False)
    assert props.is_group_enabled(a) is False
    # Toggling back returns True (entry was on /OFF).
    assert props.set_visibility("A", True) is True
    assert props.is_group_enabled(a) is True
    # B untouched.
    assert props.is_group_enabled(b) is True


def test_set_visible_appends_duplicate_when_already_on_matching_upstream() -> None:
    props, (a,) = _build("A")

    # First enable: not in /OFF, so found=False, group appended to /ON.
    assert props.set_visible(a) is False
    # Second enable: upstream setGroupEnabled(group, True) scans only /OFF,
    # never /ON, so it still returns False and appends the group to /ON a
    # second time (a duplicate). pypdfbox mirrors that exactly.
    assert props.set_visible(a) is False

    on = _state_array(props, "ON")
    off = _state_array(props, "OFF")
    assert on.size() == 2
    assert on.get_object(0) is a.get_cos_object()
    assert on.get_object(1) is a.get_cos_object()
    assert off.size() == 0


def test_set_group_enabled_moves_only_first_match_matching_upstream() -> None:
    props, (a,) = _build("A")
    d = _default_config(props)
    on = COSArray([a.get_cos_object(), a.get_cos_object()])
    off = COSArray([a.get_cos_object(), a.get_cos_object()])
    d.set_item(COSName.get_pdf_name("ON"), on)
    d.set_item(COSName.get_pdf_name("OFF"), off)

    # Upstream setGroupEnabled(a, False) scans /ON, moves the FIRST match to
    # /OFF, and stops (break). It does not de-duplicate the arrays: /ON keeps
    # its second copy, /OFF grows to three.
    assert props.set_group_enabled(a, False) is True
    # is_group_enabled checks /ON first, so the surviving /ON entry wins.
    assert props.is_group_enabled(a) is True
    assert _state_array(props, "ON").size() == 1
    assert _state_array(props, "OFF").size() == 3


def test_set_visibility_drives_compute_visible_ocgs() -> None:
    """End-to-end: set_visibility's bookkeeping is honoured by the same
    /D /ON, /D /OFF resolution that compute_visible_ocgs reads."""
    props, (a, b, c) = _build("A", "B", "C")
    props.set_hidden(b)
    props.set_visible(c)  # already on by base state, but explicit /ON entry
    visible = props.compute_visible_ocgs()
    assert visible == {id(a.get_cos_object()), id(c.get_cos_object())}


def test_set_visibility_feeds_ocmd_anyon() -> None:
    """compute_visible_ocgs after set_visible/set_hidden produces the same
    visibility set the OCMD policy consumes — read-side parity sanity."""
    props, (a, b) = _build("A", "B")
    props.set_hidden(a)
    props.set_hidden(b)
    visible = props.compute_visible_ocgs()

    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_o_cgs([a, b])
    ocmd.set_visibility_policy("AnyOn")
    assert ocmd.is_visible(visible) is False

    props.set_visible(a)
    assert ocmd.is_visible(props.compute_visible_ocgs()) is True


# ---------- remove_group ----------


def test_remove_group_by_object_clears_ocgs_and_d() -> None:
    props, (a, b) = _build("A", "B")
    # Toggle A through /OFF so the /D /OFF array also references it.
    props.set_hidden(a)

    assert props.remove_group(a) is True
    assert props.has_group("A") is False
    assert props.get_group_names() == ["B"]

    d = props.get_cos_object().get_dictionary_object(COSName.D)  # type: ignore[attr-defined]
    assert isinstance(d, COSDictionary)

    order = d.get_dictionary_object(COSName.get_pdf_name("Order"))
    assert isinstance(order, COSArray)
    assert order.size() == 1  # only B remains in /Order

    off = d.get_dictionary_object(COSName.get_pdf_name("OFF"))
    if isinstance(off, COSArray):
        # /OFF must no longer reference A.
        for entry in off:
            assert entry is not a.get_cos_object()


def test_remove_group_by_name_drops_all_matching() -> None:
    props = PDOptionalContentProperties()
    a1 = PDOptionalContentGroup("Layer X")
    a2 = PDOptionalContentGroup("Layer X")  # duplicate name, distinct OCG
    b = PDOptionalContentGroup("Layer Y")
    props.add_group(a1)
    props.add_group(a2)
    props.add_group(b)

    assert props.remove_group("Layer X") is True
    assert props.get_group_names() == ["Layer Y"]


def test_remove_group_returns_false_for_unknown() -> None:
    props, _ = _build("A")
    other = PDOptionalContentGroup("Ghost")
    assert props.remove_group(other) is False
    assert props.remove_group("Ghost") is False
    # A untouched.
    assert props.get_group_names() == ["A"]


# ---------- multiple same-named groups (upstream loops over ALL) ----------


def test_set_group_enabled_by_name_toggles_all_matching() -> None:
    """Upstream ``setGroupEnabled(String, boolean)`` loops over EVERY OCG
    whose /Name matches and toggles each. Two distinct OCGs sharing a name
    must therefore BOTH move to /D /OFF, and the name-level
    ``is_group_enabled`` then reports false for the whole name."""
    props = PDOptionalContentProperties()
    dup1 = PDOptionalContentGroup("Dup")
    dup2 = PDOptionalContentGroup("Dup")
    solo = PDOptionalContentGroup("Solo")
    for g in (dup1, dup2, solo):
        props.add_group(g)

    # Neither "Dup" group had a prior on/off setting → upstream returns False.
    assert props.set_group_enabled("Dup", False) is False

    off = _state_array(props, "OFF")
    assert off.size() == 2
    assert {
        id(props.to_dictionary(off.get(i))) for i in range(off.size())
    } == {id(dup1.get_cos_object()), id(dup2.get_cos_object())}

    assert props.is_group_enabled("Dup") is False
    assert props.is_group_enabled("Solo") is True

    # Re-enabling by name moves BOTH back to /ON; both had an /OFF setting
    # → upstream returns True.
    assert props.set_group_enabled("Dup", True) is True
    assert _state_array(props, "OFF").size() == 0
    assert _state_array(props, "ON").size() == 2
    assert props.is_group_enabled("Dup") is True


def test_set_group_enabled_unknown_name_returns_false_no_side_effect() -> None:
    """Enabling a name that matches no OCG returns False and writes nothing
    to /D /ON (the array is created lazily but stays empty)."""
    props, (a,) = _build("A")
    props.set_visible(a)  # seed /ON with one real entry
    on_before = _state_array(props, "ON").size()
    assert props.set_group_enabled("Ghost", True) is False
    assert _state_array(props, "ON").size() == on_before


# ---------- BaseState OFF interaction ----------


def test_set_group_enabled_under_base_state_off_writes_to_on() -> None:
    """``set_group_enabled(group, True)`` ignores /BaseState and always
    writes to /D /ON. Under BaseState OFF an unlisted group resolves to
    disabled (``enabled = base_state != OFF``); an explicitly enabled group
    flips to true via its /ON membership."""
    props, (a, b) = _build("A", "B")
    props.set_base_state("OFF")

    # Unlisted group under BaseState OFF → disabled.
    assert props.is_group_enabled(b) is False

    props.set_group_enabled(a, True)
    on = _state_array(props, "ON")
    assert on.size() == 1
    assert on.get_object(0) is a.get_cos_object()
    assert props.is_group_enabled(a) is True
    # B still unlisted → still disabled under BaseState OFF.
    assert props.is_group_enabled(b) is False


# ---------- get_group_names (upstream parity) ----------


def test_get_group_names_returns_array_order() -> None:
    props, _ = _build("First", "Second", "Third")
    assert props.get_group_names() == ["First", "Second", "Third"]


def test_get_group_names_substitutes_empty_for_non_dict_entry() -> None:
    """Upstream getGroupNames() emits "" when an /OCGs slot does not
    resolve to a COSDictionary."""
    props = PDOptionalContentProperties()
    ocgs = props.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("OCGs")
    )
    assert isinstance(ocgs, COSArray)
    # Append a stray COSName — non-dictionary entry.
    ocgs.add(COSName.get_pdf_name("not-a-dict"))
    # Plus a real OCG.
    g = PDOptionalContentGroup("Real")
    props.add_group(g)

    names = props.get_group_names()
    assert names == ["", "Real"]


def test_get_group_names_returns_empty_for_no_ocgs() -> None:
    props = PDOptionalContentProperties()
    assert props.get_group_names() == []
