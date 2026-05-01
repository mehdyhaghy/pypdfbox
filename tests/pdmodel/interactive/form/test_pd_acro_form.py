from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.interactive.form import (
    PDAcroForm,
    PDFieldStub,
    PDNonTerminalField,
)


def test_acro_form_round_trips_top_level_fields() -> None:
    form = PDAcroForm()
    stub = PDFieldStub(form, COSDictionary(), None)
    stub.set_partial_name("name")
    form.set_fields([stub])

    fields = form.get_fields()
    assert len(fields) == 1
    assert isinstance(fields[0], PDFieldStub)
    assert fields[0].get_cos_object() is stub.get_cos_object()
    assert fields[0].get_partial_name() == "name"


def test_field_partial_alternate_and_mapping_names_round_trip() -> None:
    form = PDAcroForm()
    stub = PDFieldStub(form)
    stub.set_partial_name("first_name")
    stub.set_alternate_field_name("First Name")
    stub.set_mapping_name("firstName")

    assert stub.get_partial_name() == "first_name"
    assert stub.get_alternate_field_name() == "First Name"
    assert stub.get_mapping_name() == "firstName"


def test_fully_qualified_name_concatenates_with_dot() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("address")
    child = PDFieldStub(form)
    child.set_partial_name("street")
    parent.set_children([child])

    children = parent.get_children()
    assert len(children) == 1
    assert children[0].get_fully_qualified_name() == "address.street"


def test_field_flags_and_read_only_round_trip() -> None:
    form = PDAcroForm()
    stub = PDFieldStub(form)
    assert stub.get_field_flags() == 0
    assert stub.is_read_only() is False

    stub.set_field_flags(0b101)  # bit 0 (read-only) + bit 2 (no-export)
    assert stub.get_field_flags() == 0b101
    assert stub.is_read_only() is True
    assert stub.is_no_export() is True
    assert stub.is_required() is False

    stub.set_read_only(False)
    assert stub.is_read_only() is False
    assert stub.is_no_export() is True


def test_signatures_exist_and_need_appearances_round_trip() -> None:
    form = PDAcroForm()
    assert form.is_signatures_exist() is False
    assert form.is_appendonly() is False
    assert form.is_need_appearances() is False

    form.set_signatures_exist(True)
    form.set_appendonly(True)
    form.set_need_appearances(True)

    assert form.is_signatures_exist() is True
    assert form.is_appendonly() is True
    assert form.is_need_appearances() is True

    form.set_signatures_exist(False)
    assert form.is_signatures_exist() is False
    assert form.is_appendonly() is True


def test_get_field_by_fully_qualified_name() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("address")
    child = PDFieldStub(form)
    child.set_partial_name("street")
    parent.set_children([child])
    form.set_fields([parent])

    found = form.get_field("address.street")
    assert found is not None
    assert found.get_partial_name() == "street"
    assert form.get_field("address") is not None
    assert form.get_field("does.not.exist") is None


def test_field_tree_and_iterator_walk_recursively_in_order() -> None:
    form = PDAcroForm()
    address = PDNonTerminalField(form)
    address.set_partial_name("address")
    street = PDFieldStub(form)
    street.set_partial_name("street")
    city = PDFieldStub(form)
    city.set_partial_name("city")
    address.set_children([street, city])
    name = PDFieldStub(form)
    name.set_partial_name("name")
    form.set_fields([address, name])

    assert [field.get_fully_qualified_name() for field in form.get_field_tree()] == [
        "address",
        "address.street",
        "address.city",
        "name",
    ]
    assert [field.get_fully_qualified_name() for field in form.get_field_iterator()] == [
        "address",
        "address.street",
        "address.city",
        "name",
    ]


def test_field_cache_can_be_enabled_and_disabled() -> None:
    form = PDAcroForm()
    field = PDFieldStub(form)
    field.set_partial_name("original")
    form.set_fields([field])

    assert form.is_caching_fields() is False
    form.set_cache_fields(True)
    assert form.is_caching_fields() is True
    cached = form.get_field("original")
    assert cached is form.get_field("original")

    assert cached is not None
    cached.set_partial_name("renamed")
    assert form.get_field("renamed") is None
    assert form.get_field("original") is cached

    form.set_cache_fields(False)
    assert form.is_caching_fields() is False
    assert form.get_field("original") is None
    assert form.get_field("renamed") is not None


def test_field_cache_is_invalidated_when_fields_are_replaced() -> None:
    form = PDAcroForm()
    old_field = PDFieldStub(form)
    old_field.set_partial_name("old")
    form.set_fields([old_field])
    form.set_cache_fields(True)
    assert form.get_field("old") is not None

    new_field = PDFieldStub(form)
    new_field.set_partial_name("new")
    form.set_fields([new_field])

    assert form.get_field("old") is None
    assert form.get_field("new") is not None


# ---------- Wave 40 — refresh_appearances + has_xfa + xfa_is_dynamic +
# need_appearances_if_exists + scripting handler + cache_fields alias.


def test_refresh_appearances_no_args_walks_field_tree() -> None:
    """``refresh_appearances`` with no fields argument iterates the
    full field tree and dispatches into each terminal's
    :meth:`construct_appearances`. Lite ``construct_appearances`` is a
    no-op debug log — the call must succeed."""
    form = PDAcroForm()
    field = PDFieldStub(form)
    field.set_partial_name("name")
    form.set_fields([field])
    form.refresh_appearances()  # no exception


def test_refresh_appearances_explicit_field_list() -> None:
    """When called with an explicit list, only that list is walked
    (matches upstream signature)."""
    form = PDAcroForm()
    field = PDFieldStub(form)
    field.set_partial_name("name")
    form.set_fields([field])
    form.refresh_appearances([field])


def test_refresh_appearances_skips_non_terminals() -> None:
    """Non-terminal fields are not dispatched — upstream guards via
    ``instanceof PDTerminalField``. Just verifies the call succeeds when
    only a non-terminal is in the tree."""
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("address")
    form.set_fields([parent])
    form.refresh_appearances()  # no exception


def test_has_xfa_round_trips_with_set_xfa() -> None:
    """``has_xfa`` should reflect ``/XFA`` presence after set/clear."""
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.interactive.form.pd_xfa_resource import PDXFAResource

    form = PDAcroForm()
    assert form.has_xfa() is False
    assert form.xfa_is_dynamic() is False

    # Synthesise a tiny /XFA byte stream and wrap.
    payload = COSDictionary()
    form.get_cos_object().set_item(COSName.get_pdf_name("XFA"), payload)
    assert form.has_xfa() is True
    # /XFA present + /Fields empty (none added) → dynamic XFA.
    assert form.xfa_is_dynamic() is True

    # When fields are present /XFA is not "dynamic-only".
    field = PDFieldStub(form)
    field.set_partial_name("name")
    form.set_fields([field])
    assert form.has_xfa() is True
    assert form.xfa_is_dynamic() is False

    # set_xfa(None) clears the entry.
    form.set_xfa(None)
    assert form.has_xfa() is False
    assert form.xfa_is_dynamic() is False

    # set_xfa with a typed wrapper writes the COS payload back.
    wrapper = PDXFAResource(payload)
    form.set_xfa(wrapper)
    assert form.has_xfa() is True
    assert form.xfa() is not None


def test_get_need_appearances_alias() -> None:
    """``get_need_appearances`` is the upstream-named alias for
    ``is_need_appearances`` — same default + same round-trip."""
    form = PDAcroForm()
    assert form.get_need_appearances() is False
    form.set_need_appearances(True)
    assert form.get_need_appearances() is True
    form.set_need_appearances(False)
    assert form.get_need_appearances() is False


def test_get_need_appearances_if_exists_returns_none_when_absent() -> None:
    """``get_need_appearances_if_exists`` is tri-state: ``None`` when
    /NeedAppearances is absent, otherwise the boolean value."""
    form = PDAcroForm()
    assert form.get_need_appearances_if_exists() is None
    form.set_need_appearances(True)
    assert form.get_need_appearances_if_exists() is True
    form.set_need_appearances(False)
    assert form.get_need_appearances_if_exists() is False


def test_scripting_handler_round_trip() -> None:
    """Scripting handler is opaque on the lite surface — round-trips
    whatever object the caller registers."""
    form = PDAcroForm()
    assert form.get_scripting_handler() is None

    sentinel = object()
    form.set_scripting_handler(sentinel)
    assert form.get_scripting_handler() is sentinel

    form.set_scripting_handler(None)
    assert form.get_scripting_handler() is None


def test_cache_fields_alias_enables_caching() -> None:
    """``cache_fields`` is an upstream-named synonym for
    ``set_cache_fields(True)``."""
    form = PDAcroForm()
    assert form.is_caching_fields() is False
    form.cache_fields()
    assert form.is_caching_fields() is True


def test_get_signature_fields_filters_to_signature_subclass() -> None:
    """``get_signature_fields`` returns only ``PDSignatureField``
    instances reachable from the field tree."""
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField

    form = PDAcroForm()
    plain = PDFieldStub(form)
    plain.set_partial_name("name")
    sig = PDSignatureField(form)
    sig.set_partial_name("Signature1")
    form.set_fields([plain, sig])

    sig_fields = form.get_signature_fields()
    assert len(sig_fields) == 1
    assert sig_fields[0].get_partial_name() == "Signature1"


def test_xfa_is_dynamic_false_when_no_xfa() -> None:
    """``xfa_is_dynamic`` is ``False`` whenever ``/XFA`` is absent —
    independent of whether ``/Fields`` is empty."""
    form = PDAcroForm()
    assert form.xfa_is_dynamic() is False  # no /XFA, no fields
    field = PDFieldStub(form)
    field.set_partial_name("name")
    form.set_fields([field])
    assert form.xfa_is_dynamic() is False  # no /XFA, has fields


# ---------- Wave 71 — get_default_appearance_if_exists +
# remove_field / remove_fields parity helpers.


def test_get_default_appearance_if_exists_returns_none_when_absent() -> None:
    """``get_default_appearance_if_exists`` is tri-state: ``None`` when
    /DA is absent, otherwise the string value (which may be empty)."""
    form = PDAcroForm()
    assert form.get_default_appearance_if_exists() is None
    form.set_default_appearance("/Helv 0 Tf 0 g")
    assert form.get_default_appearance_if_exists() == "/Helv 0 Tf 0 g"
    form.set_default_appearance("")
    assert form.get_default_appearance_if_exists() == ""


def test_get_default_appearance_if_exists_distinguishes_empty_from_absent() -> None:
    """Empty ``/DA`` is distinguishable from missing ``/DA``: the plain
    accessor returns ``""`` for both, the tri-state returns ``None`` only
    when the entry is absent."""
    form = PDAcroForm()
    assert form.get_default_appearance() == ""
    assert form.get_default_appearance_if_exists() is None
    form.set_default_appearance("")
    assert form.get_default_appearance() == ""
    assert form.get_default_appearance_if_exists() == ""


def test_remove_field_removes_top_level_field() -> None:
    """``remove_field`` drops a root-level field from ``/Fields``."""
    form = PDAcroForm()
    a = PDFieldStub(form)
    a.set_partial_name("a")
    b = PDFieldStub(form)
    b.set_partial_name("b")
    form.set_fields([a, b])

    assert form.remove_field(a) is True
    remaining = form.get_fields()
    assert len(remaining) == 1
    assert remaining[0].get_partial_name() == "b"


def test_remove_field_returns_false_when_not_present() -> None:
    """``remove_field`` returns ``False`` when the field is not part of
    its expected container."""
    form = PDAcroForm()
    detached = PDFieldStub(form)
    detached.set_partial_name("orphan")
    # Form has no /Fields entries — removing should be a no-op.
    assert form.remove_field(detached) is False


def test_remove_field_removes_child_from_parent_kids() -> None:
    """``remove_field`` honours the parent back-pointer: a child field
    is dropped from its parent's ``/Kids`` array, not from ``/Fields``."""
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("address")
    street = PDFieldStub(form)
    street.set_partial_name("street")
    city = PDFieldStub(form)
    city.set_partial_name("city")
    parent.set_children([street, city])
    form.set_fields([parent])

    assert form.remove_field(street) is True
    children = parent.get_children()
    assert len(children) == 1
    assert children[0].get_partial_name() == "city"
    # Root /Fields is unaffected.
    assert len(form.get_fields()) == 1


def test_remove_fields_removes_each_and_returns_count() -> None:
    """``remove_fields`` walks its argument and returns the number of
    fields actually removed."""
    form = PDAcroForm()
    a = PDFieldStub(form)
    a.set_partial_name("a")
    b = PDFieldStub(form)
    b.set_partial_name("b")
    c = PDFieldStub(form)
    c.set_partial_name("c")
    form.set_fields([a, b, c])

    detached = PDFieldStub(form)
    detached.set_partial_name("orphan")

    # Two-of-three present; one orphan that won't be removed.
    removed = form.remove_fields([a, c, detached])
    assert removed == 2
    remaining = [f.get_partial_name() for f in form.get_fields()]
    assert remaining == ["b"]


def test_remove_field_invalidates_field_cache() -> None:
    """Removing a field while caching is enabled drops the cache so the
    next ``get_field`` rebuilds against the new tree."""
    form = PDAcroForm()
    keep = PDFieldStub(form)
    keep.set_partial_name("keep")
    drop = PDFieldStub(form)
    drop.set_partial_name("drop")
    form.set_fields([keep, drop])
    form.set_cache_fields(True)
    assert form.get_field("drop") is not None

    form.remove_field(drop)
    assert form.get_field("drop") is None
    assert form.get_field("keep") is not None
