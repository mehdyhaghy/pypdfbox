"""Wave 1568 — AcroForm field-model fuzz (Agent A).

Hammers the field-tree traversal surface against upstream PDFBox 3.0.7
semantics: fully-qualified-name building across nested non-terminal /
terminal nodes (dot-joined ``/T`` chain, missing ``/T``, duplicate partial
names), ``get_field`` lookup by FQN (hit / miss / partial), inherited
``/FT`` / ``/V`` / ``/DV`` / ``/Ff`` attributes through ``get_inheritable_attribute``,
typed value get/set on text / choice / checkbox fields, ``/Kids``-vs-
widget-merged single fields, add / remove field, and the empty form.

These exercise the convergence fix landed in this wave:
``PDField.get_inheritable_attribute`` now stops the walk on ``containsKey``
(presence), matching upstream — a present-but-COSNull entry shadows the
ancestor value instead of falling through to inherit it.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_terminal_field import PDFieldStub
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_T = COSName.get_pdf_name("T")
_FT = COSName.get_pdf_name("FT")
_FF = COSName.get_pdf_name("Ff")
_V = COSName.get_pdf_name("V")
_DV = COSName.get_pdf_name("DV")
_KIDS = COSName.get_pdf_name("Kids")
_PARENT = COSName.get_pdf_name("Parent")
_OPT = COSName.get_pdf_name("Opt")


# ----------------------------------------------------------------------
# helpers — build raw COS field trees
# ----------------------------------------------------------------------


def _form_with_fields(*field_dicts: COSDictionary) -> PDAcroForm:
    form = PDAcroForm()
    arr = COSArray()
    for d in field_dicts:
        arr.add(d)
    form.get_cos_object().set_item(COSName.get_pdf_name("Fields"), arr)
    return form


def _terminal_dict(name: str | None, ft: str = "Tx", **extra: object) -> COSDictionary:
    d = COSDictionary()
    if name is not None:
        d.set_string(_T, name)
    if ft is not None:
        d.set_item(_FT, COSName.get_pdf_name(ft))
    for k, v in extra.items():
        d.set_item(COSName.get_pdf_name(k), v)
    return d


def _node_with_kids(
    name: str | None, *kids: COSDictionary, **extra: object
) -> COSDictionary:
    d = COSDictionary()
    if name is not None:
        d.set_string(_T, name)
    arr = COSArray()
    for kid in kids:
        kid.set_item(_PARENT, d)
        arr.add(kid)
    d.set_item(_KIDS, arr)
    for k, v in extra.items():
        d.set_item(COSName.get_pdf_name(k), v)
    return d


# ----------------------------------------------------------------------
# fully-qualified name building
# ----------------------------------------------------------------------


def test_fqn_single_terminal() -> None:
    form = _form_with_fields(_terminal_dict("foo"))
    field = form.get_fields()[0]
    assert field.get_fully_qualified_name() == "foo"


def test_fqn_two_level_dot_joined() -> None:
    kid = _terminal_dict("child")
    node = _node_with_kids("parent", kid)
    form = _form_with_fields(node)
    nt = form.get_fields()[0]
    assert isinstance(nt, PDNonTerminalField)
    child = nt.get_children()[0]
    assert child.get_fully_qualified_name() == "parent.child"


def test_fqn_three_level_dot_joined() -> None:
    leaf = _terminal_dict("leaf")
    mid = _node_with_kids("mid", leaf)
    top = _node_with_kids("top", mid)
    form = _form_with_fields(top)
    top_field = form.get_fields()[0]
    mid_field = top_field.get_children()[0]
    leaf_field = mid_field.get_children()[0]
    assert top_field.get_fully_qualified_name() == "top"
    assert mid_field.get_fully_qualified_name() == "top.mid"
    assert leaf_field.get_fully_qualified_name() == "top.mid.leaf"


def test_fqn_missing_partial_on_leaf_returns_parent_name() -> None:
    # Upstream: finalName is null -> result is the parent FQN alone.
    leaf = _terminal_dict(None)
    node = _node_with_kids("parent", leaf)
    form = _form_with_fields(node)
    # The kid has no /T, so the factory treats the node as a *terminal*
    # (no /T-bearing kid => not non-terminal). Build the relationship
    # explicitly to exercise the FQN walk.
    leaf_field = PDTextField(form, leaf, parent=PDNonTerminalField(form, node))
    assert leaf_field.get_fully_qualified_name() == "parent"


def test_fqn_missing_partial_everywhere_is_none() -> None:
    # No /T anywhere in the chain -> None (not "").
    leaf = _terminal_dict(None)
    field = PDTextField(PDAcroForm(), leaf)
    assert field.get_fully_qualified_name() is None


def test_fqn_present_but_empty_partial_is_empty_string() -> None:
    # /T () -> "" (distinct from missing -> None), per upstream getPartialName.
    leaf = _terminal_dict("")
    field = PDTextField(PDAcroForm(), leaf)
    assert field.get_partial_name() == ""
    assert field.get_fully_qualified_name() == ""


def test_fqn_parent_missing_t_only_child_t() -> None:
    # Parent node has no /T; child has /T -> FQN is just the child name.
    kid = _terminal_dict("only")
    node = _node_with_kids(None, kid)
    form = _form_with_fields(node)
    nt = form.get_fields()[0]
    assert isinstance(nt, PDNonTerminalField)
    child = nt.get_children()[0]
    assert child.get_fully_qualified_name() == "only"


def test_fqn_node_missing_t_grandchild_joins_skipping_node() -> None:
    # A mid-tree node carrying no /T: its FQN collapses to the parent's, and
    # the grandchild joins onto that. Wrap nodes directly so the missing-/T
    # node still presents as non-terminal regardless of factory heuristics.
    leaf = _terminal_dict("leaf")
    mid = _node_with_kids(None, leaf)  # no /T on mid
    top = _node_with_kids("top", mid)
    form = _form_with_fields(top)
    top_field = PDNonTerminalField(form, top)
    mid_field = PDNonTerminalField(form, mid, parent=top_field)
    leaf_field = PDTextField(form, leaf, parent=mid_field)
    # mid has no /T -> its FQN is the parent's; leaf joins onto that.
    assert mid_field.get_fully_qualified_name() == "top"
    assert leaf_field.get_fully_qualified_name() == "top.leaf"


def test_fqn_duplicate_partial_names_distinct_objects() -> None:
    a = _terminal_dict("dup")
    b = _terminal_dict("dup")
    node = _node_with_kids("p", a, b)
    form = _form_with_fields(node)
    nt = form.get_fields()[0]
    children = nt.get_children()
    assert {c.get_fully_qualified_name() for c in children} == {"p.dup"}
    # Two distinct field objects, same FQN.
    assert children[0].get_cos_object() is not children[1].get_cos_object()


def test_fqn_partial_name_with_dot_set_rejected() -> None:
    field = PDTextField(PDAcroForm())
    with pytest.raises(ValueError):
        field.set_partial_name("a.b")


# ----------------------------------------------------------------------
# get_field lookup
# ----------------------------------------------------------------------


def test_get_field_hit_top_level() -> None:
    form = _form_with_fields(_terminal_dict("alpha"), _terminal_dict("beta"))
    assert form.get_field("alpha") is not None
    assert form.get_field("beta") is not None


def test_get_field_hit_nested() -> None:
    leaf = _terminal_dict("leaf")
    top = _node_with_kids("top", leaf)
    form = _form_with_fields(top)
    found = form.get_field("top.leaf")
    assert found is not None
    assert found.get_partial_name() == "leaf"


def test_get_field_miss_unknown_name() -> None:
    form = _form_with_fields(_terminal_dict("alpha"))
    assert form.get_field("nope") is None


def test_get_field_partial_path_does_not_match_leaf() -> None:
    leaf = _terminal_dict("leaf")
    top = _node_with_kids("top", leaf)
    form = _form_with_fields(top)
    # "top" matches the non-terminal node itself, not the leaf.
    node = form.get_field("top")
    assert node is not None
    assert isinstance(node, PDNonTerminalField)
    # "top.leaf" is the only FQN reaching the leaf.
    assert form.get_field("leaf") is None


def test_get_field_none_argument_returns_none() -> None:
    form = _form_with_fields(_terminal_dict("alpha"))
    assert form.get_field(None) is None


def test_get_field_cache_matches_uncached() -> None:
    leaf = _terminal_dict("leaf")
    top = _node_with_kids("top", leaf)
    form = _form_with_fields(top)
    uncached = form.get_field("top.leaf")
    form.set_cache_fields(True)
    cached = form.get_field("top.leaf")
    assert (uncached is None) == (cached is None)
    assert cached is not None
    assert cached.get_fully_qualified_name() == "top.leaf"


def test_get_field_empty_form_returns_none() -> None:
    form = PDAcroForm()
    assert form.get_field("anything") is None


# ----------------------------------------------------------------------
# inheritance walk: /FT /V /DV /Ff
# ----------------------------------------------------------------------


def test_inherit_ft_from_parent_node() -> None:
    leaf = _terminal_dict("leaf", ft=None)  # no own /FT
    top = _node_with_kids("top", leaf, FT=COSName.get_pdf_name("Tx"))
    form = _form_with_fields(top)
    top_field = form.get_fields()[0]
    leaf_field = top_field.get_children()[0]
    assert leaf_field.get_field_type() == "Tx"


def test_inherit_ff_from_parent_node() -> None:
    leaf = _terminal_dict("leaf", ft="Tx")
    top = _node_with_kids("top", leaf, Ff=COSInteger.get(4096))
    form = _form_with_fields(top)
    top_field = form.get_fields()[0]
    leaf_field = top_field.get_children()[0]
    # Terminal field walks self -> parent; no own /Ff -> inherit 4096.
    assert leaf_field.get_field_flags() == 4096


def test_inherit_ff_own_wins_over_parent() -> None:
    leaf = _terminal_dict("leaf", ft="Tx", Ff=COSInteger.get(2))
    top = _node_with_kids("top", leaf, Ff=COSInteger.get(4096))
    form = _form_with_fields(top)
    leaf_field = form.get_fields()[0].get_children()[0]
    assert leaf_field.get_field_flags() == 2


def test_inherit_v_via_inheritable_attribute() -> None:
    leaf = _terminal_dict("leaf", ft="Tx")  # no own /V
    top = _node_with_kids("top", leaf, V=COSString("inherited"))
    form = _form_with_fields(top)
    leaf_field = form.get_fields()[0].get_children()[0]
    assert isinstance(leaf_field, PDTextField)
    assert leaf_field.get_value() == "inherited"


def test_inherit_v_from_acroform_root() -> None:
    leaf = _terminal_dict("leaf", ft="Tx")
    form = _form_with_fields(leaf)
    form.get_cos_object().set_item(_V, COSString("form-level"))
    field = form.get_fields()[0]
    assert field.get_inheritable_attribute(_V) == COSString("form-level")


def test_inherit_dv_via_inheritable_attribute() -> None:
    leaf = _terminal_dict("leaf", ft="Tx")
    top = _node_with_kids("top", leaf, DV=COSString("default"))
    form = _form_with_fields(top)
    leaf_field = form.get_fields()[0].get_children()[0]
    got = leaf_field.get_inheritable_attribute(_DV)
    assert got == COSString("default")


def test_present_but_null_shadows_parent_value() -> None:
    # Convergence fix (wave 1568): an explicit /V COSNull on the child must
    # stop the inheritance walk (upstream uses containsKey), returning null
    # instead of inheriting the parent's /V.
    leaf = _terminal_dict("leaf", ft="Tx")
    leaf.set_item(_V, COSNull.NULL)
    top = _node_with_kids("top", leaf, V=COSString("parent-value"))
    form = _form_with_fields(top)
    leaf_field = form.get_fields()[0].get_children()[0]
    assert leaf_field.get_inheritable_attribute(_V) is None


def test_present_value_stops_walk() -> None:
    leaf = _terminal_dict("leaf", ft="Tx", V=COSString("own"))
    top = _node_with_kids("top", leaf, V=COSString("parent"))
    form = _form_with_fields(top)
    leaf_field = form.get_fields()[0].get_children()[0]
    assert leaf_field.get_inheritable_attribute(_V) == COSString("own")


def test_non_terminal_field_type_is_local_only() -> None:
    # PDNonTerminalField.get_field_type must NOT walk the parent chain.
    leaf = _terminal_dict("leaf", ft="Tx")
    mid = _node_with_kids("mid", leaf)  # mid has no own /FT
    top = _node_with_kids("top", mid, FT=COSName.get_pdf_name("Tx"))
    form = _form_with_fields(top)
    mid_field = form.get_fields()[0].get_children()[0]
    assert isinstance(mid_field, PDNonTerminalField)
    assert mid_field.get_field_type() is None  # local only


def test_non_terminal_flags_is_local_only() -> None:
    leaf = _terminal_dict("leaf", ft="Tx")
    mid = _node_with_kids("mid", leaf)
    top = _node_with_kids("top", mid, Ff=COSInteger.get(8))
    form = _form_with_fields(top)
    mid_field = form.get_fields()[0].get_children()[0]
    assert isinstance(mid_field, PDNonTerminalField)
    assert mid_field.get_field_flags() == 0  # local only


# ----------------------------------------------------------------------
# value get/set on typed fields
# ----------------------------------------------------------------------


def test_text_field_set_get_value_roundtrip() -> None:
    field = PDTextField(PDAcroForm())
    field.set_value("hello", regenerate_appearance=False)
    assert field.get_value() == "hello"


def test_text_field_set_none_removes_v() -> None:
    field = PDTextField(PDAcroForm())
    field.set_value("x", regenerate_appearance=False)
    field.set_value(None, regenerate_appearance=False)
    assert field.get_value() == ""
    assert not field.get_cos_object().contains_key(_V)


def test_text_field_nul_rejected() -> None:
    field = PDTextField(PDAcroForm())
    with pytest.raises(ValueError):
        field.set_value("bad\0value", regenerate_appearance=False)


def test_checkbox_set_value_on_off() -> None:
    d = _terminal_dict("cb", ft="Btn")
    form = _form_with_fields(d)
    field = form.get_fields()[0]
    assert isinstance(field, PDCheckBox)
    on = field.get_on_value()
    field.set_value(on)
    assert field.get_value() == on
    field.set_value("Off")
    assert field.get_value() == "Off"


def test_combobox_set_get_value() -> None:
    d = _terminal_dict("cb", ft="Ch", Ff=COSInteger.get(1 << 17))  # Combo
    opt = COSArray()
    opt.add(COSString("Red"))
    opt.add(COSString("Green"))
    d.set_item(_OPT, opt)
    form = _form_with_fields(d)
    field = form.get_fields()[0]
    assert isinstance(field, PDComboBox)
    field.set_value("Green")
    assert field.get_value() == ["Green"]


def test_non_terminal_value_as_string_local_only() -> None:
    leaf = _terminal_dict("leaf", ft="Tx")
    top = _node_with_kids("top", leaf, V=COSString("v"))
    form = _form_with_fields(top)
    nt = form.get_fields()[0]
    assert isinstance(nt, PDNonTerminalField)
    # getValueAsString uses the COS toString form, not the decoded payload.
    assert nt.get_value_as_string() == COSString("v").to_string()


# ----------------------------------------------------------------------
# /Kids vs widget-merged single field
# ----------------------------------------------------------------------


def test_widget_merged_single_field_one_widget() -> None:
    # Terminal field with no /Kids -> the field dict itself acts as widget.
    d = _terminal_dict("w", ft="Tx")
    form = _form_with_fields(d)
    field = form.get_fields()[0]
    widgets = field.get_widgets()
    assert len(widgets) == 1
    assert widgets[0].get_cos_object() is d


def test_terminal_field_with_widget_kids_no_t() -> None:
    # /Kids whose entries have no /T are widget annotations -> still terminal.
    w1 = COSDictionary()
    w1.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget"))
    w2 = COSDictionary()
    w2.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget"))
    d = _terminal_dict("multi", ft="Tx")
    arr = COSArray()
    arr.add(w1)
    arr.add(w2)
    d.set_item(_KIDS, arr)
    form = _form_with_fields(d)
    field = form.get_fields()[0]
    assert field.is_terminal()
    assert len(field.get_widgets()) == 2


def test_kid_with_t_is_non_terminal() -> None:
    kid = _terminal_dict("k", ft="Tx")
    node = _node_with_kids("n", kid)
    form = _form_with_fields(node)
    field = form.get_fields()[0]
    assert isinstance(field, PDNonTerminalField)
    assert not field.is_terminal()


# ----------------------------------------------------------------------
# add / remove fields, empty form
# ----------------------------------------------------------------------


def test_remove_top_level_field() -> None:
    form = _form_with_fields(_terminal_dict("a"), _terminal_dict("b"))
    fields = form.get_fields()
    assert form.remove_field(fields[0]) is True
    remaining = {f.get_partial_name() for f in form.get_fields()}
    assert remaining == {"b"}


def test_remove_nested_field_from_kids() -> None:
    leaf1 = _terminal_dict("leaf1", ft="Tx")
    leaf2 = _terminal_dict("leaf2", ft="Tx")
    top = _node_with_kids("top", leaf1, leaf2)
    form = _form_with_fields(top)
    nt = form.get_fields()[0]
    assert isinstance(nt, PDNonTerminalField)
    child = nt.get_children()[0]
    assert form.remove_field(child) is True
    remaining = {c.get_partial_name() for c in nt.get_children()}
    assert remaining == {"leaf2"}


def test_remove_field_not_present_returns_false() -> None:
    form = _form_with_fields(_terminal_dict("a"))
    stray = PDTextField(form, _terminal_dict("stray"))
    assert form.remove_field(stray) is False


def test_set_fields_replaces_array() -> None:
    form = _form_with_fields(_terminal_dict("a"))
    new_field = PDTextField(form, _terminal_dict("z", ft="Tx"))
    form.set_fields([new_field])
    names = {f.get_partial_name() for f in form.get_fields()}
    assert names == {"z"}


def test_set_fields_none_clears() -> None:
    form = _form_with_fields(_terminal_dict("a"))
    form.set_fields(None)
    assert form.get_fields() == []
    assert form.is_empty() is True


def test_empty_form_predicates() -> None:
    form = PDAcroForm()
    assert form.get_fields() == []
    assert form.has_fields() is False
    assert form.is_empty() is True
    assert list(form.get_field_tree()) == []


def test_add_then_lookup_roundtrip() -> None:
    form = PDAcroForm()
    f1 = PDTextField(form, _terminal_dict("one", ft="Tx"))
    f2 = PDTextField(form, _terminal_dict("two", ft="Tx"))
    form.set_fields([f1, f2])
    assert form.get_field("one") is not None
    assert form.get_field("two") is not None
    assert form.has_fields() is True


def test_field_tree_yields_all_nodes() -> None:
    leaf = _terminal_dict("leaf", ft="Tx")
    top = _node_with_kids("top", leaf)
    other = _terminal_dict("solo", ft="Tx")
    form = _form_with_fields(top, other)
    fqns = {f.get_fully_qualified_name() for f in form.get_field_tree()}
    assert fqns == {"top", "top.leaf", "solo"}


def test_typeless_terminal_survives_tree_roundtrip() -> None:
    # Wave 1513 pinned divergence: a /T-present /FT-absent dict surfaces as a
    # generic PDFieldStub instead of being dropped.
    d = COSDictionary()
    d.set_string(_T, "typeless")
    form = _form_with_fields(d)
    fields = form.get_fields()
    assert len(fields) == 1
    assert isinstance(fields[0], PDFieldStub)
    assert form.get_field("typeless") is not None


def test_equality_is_dict_identity() -> None:
    d = _terminal_dict("x", ft="Tx")
    form = _form_with_fields(d)
    a = PDTextField(form, d)
    b = PDTextField(form, d)
    assert a == b  # same backing dict
    c = PDTextField(form, _terminal_dict("x", ft="Tx"))
    assert a != c  # distinct dict
