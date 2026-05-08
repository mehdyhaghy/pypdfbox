from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary
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


def test_wave327_get_field_ignores_cyclic_kids_for_missing_name() -> None:
    form = PDAcroForm()
    parent = COSDictionary()
    parent.set_string("T", "parent")
    child = COSDictionary()
    child.set_string("T", "child")

    parent_kids = COSArray()
    parent_kids.add(child)
    parent.set_item("Kids", parent_kids)
    child_kids = COSArray()
    child_kids.add(parent)
    child.set_item("Kids", child_kids)

    fields = COSArray()
    fields.add(parent)
    form.get_cos_object().set_item("Fields", fields)

    assert form.get_field("missing") is None


def test_wave327_get_field_finds_descendant_before_cyclic_back_edge() -> None:
    form = PDAcroForm()
    parent = COSDictionary()
    parent.set_string("T", "parent")
    child = COSDictionary()
    child.set_string("T", "child")

    parent_kids = COSArray()
    parent_kids.add(child)
    parent.set_item("Kids", parent_kids)
    child_kids = COSArray()
    child_kids.add(parent)
    child.set_item("Kids", child_kids)

    fields = COSArray()
    fields.add(parent)
    form.get_cos_object().set_item("Fields", fields)

    found = form.get_field("parent.child")

    assert found is not None
    assert found.get_cos_object() is child


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


# ---------- Wave 113 — set_fields(None), /Fields-removed parity, raw
# /SigFlags accessors + class-level flag constants.


def test_set_fields_with_none_clears_root_fields() -> None:
    """``set_fields(None)`` resets the form's ``/Fields`` entry to an
    empty array — symmetric with ``set_calc_order(None)``. Upstream's
    ``setFields(null)`` would NPE, so this is a pypdfbox-only hardening."""
    form = PDAcroForm()
    a = PDFieldStub(form)
    a.set_partial_name("a")
    form.set_fields([a])
    assert len(form.get_fields()) == 1

    form.set_fields(None)
    assert form.get_fields() == []
    # /Fields entry is still present (as empty array) — matches the
    # constructor's default-state shape, not "entry absent".
    from pypdfbox.cos import COSArray, COSName
    fields_entry = form.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Fields"))
    assert isinstance(fields_entry, COSArray)
    assert fields_entry.size() == 0


def test_set_fields_invalidates_field_cache_when_cleared() -> None:
    """Clearing fields via ``set_fields(None)`` drops the cache so the
    next ``get_field`` reflects the empty tree (mirrors upstream
    ``testFieldsEntry`` once /Fields is cleared)."""
    form = PDAcroForm()
    field = PDFieldStub(form)
    field.set_partial_name("name")
    form.set_fields([field])
    form.set_cache_fields(True)
    assert form.get_field("name") is not None

    form.set_fields(None)
    assert form.get_field("name") is None


def test_get_fields_handles_missing_fields_entry() -> None:
    """Upstream parity with ``PDAcroFormTest.testFieldsEntry``: when
    ``/Fields`` is missing entirely (PDFBOX-2965 — some PDFs drop the
    required entry), ``get_fields`` returns an empty list and
    ``get_field`` returns ``None`` without raising."""
    from pypdfbox.cos import COSName

    form = PDAcroForm()
    # Drop the required /Fields entry the constructor seeds.
    form.get_cos_object().remove_item(COSName.get_pdf_name("Fields"))

    assert form.get_fields() == []
    assert form.get_field("foo") is None
    # Iteration over the field tree must also be safe.
    assert list(form.get_field_tree()) == []


def test_get_field_with_none_argument_returns_none() -> None:
    """Defensive null-guard mirrors upstream's
    ``Objects.equals(field.getFullyQualifiedName(), null)`` walk —
    passing ``None`` should never raise, just return ``None``."""
    form = PDAcroForm()
    a = PDFieldStub(form)
    a.set_partial_name("a")
    form.set_fields([a])
    assert form.get_field(None) is None  # type: ignore[arg-type]


def test_signature_flag_constants_match_pdf_spec() -> None:
    """``FLAG_SIGNATURES_EXIST`` and ``FLAG_APPEND_ONLY`` are exposed at
    class scope so callers can drive ``set_signature_flags`` directly.
    Values mirror PDF 32000-1 §12.7.3 Table 219 (1 and 2 respectively)."""
    assert PDAcroForm.FLAG_SIGNATURES_EXIST == 1
    assert PDAcroForm.FLAG_APPEND_ONLY == 2


def test_get_signature_flags_round_trips_raw_int() -> None:
    """``get_signature_flags`` exposes the raw ``/SigFlags`` integer —
    callers can persist or compare against bit masks directly without
    losing reserved bits."""
    form = PDAcroForm()
    assert form.get_signature_flags() == 0

    form.set_signature_flags(
        PDAcroForm.FLAG_SIGNATURES_EXIST | PDAcroForm.FLAG_APPEND_ONLY
    )
    assert form.get_signature_flags() == 3
    assert form.is_signatures_exist() is True
    assert form.is_appendonly() is True

    # Reserved/unknown bits must round-trip too.
    form.set_signature_flags(0xFF)
    assert form.get_signature_flags() == 0xFF
    assert form.is_signatures_exist() is True
    assert form.is_appendonly() is True


def test_set_signature_flags_preserves_unrelated_bits_when_toggling() -> None:
    """Setting raw flags then toggling individual flags via the typed
    helpers must preserve unrelated bits (parity with the bit-by-bit
    upstream ``setFlag`` semantics)."""
    form = PDAcroForm()
    # Set a custom bit (bit 7) plus signatures-exist.
    form.set_signature_flags(0x80 | PDAcroForm.FLAG_SIGNATURES_EXIST)
    form.set_appendonly(True)
    # All three bits live together.
    assert form.get_signature_flags() == (
        0x80 | PDAcroForm.FLAG_SIGNATURES_EXIST | PDAcroForm.FLAG_APPEND_ONLY
    )

    # Clearing only one flag preserves the other two.
    form.set_signatures_exist(False)
    assert form.get_signature_flags() == (0x80 | PDAcroForm.FLAG_APPEND_ONLY)


# ---------- Wave 169 — predicate helpers + QUADDING constants.


def test_quadding_constants_match_pd_variable_text() -> None:
    """``QUADDING_*`` are exposed at class scope so callers driving
    ``set_q`` directly don't need to import :class:`PDVariableText`.
    Values mirror PDF 32000-1 §12.7.3.3 Table 222 (0/1/2)."""
    assert PDAcroForm.QUADDING_LEFT == 0
    assert PDAcroForm.QUADDING_CENTERED == 1
    assert PDAcroForm.QUADDING_RIGHT == 2

    # Sanity check: the constants line up with what set_q / get_q
    # round-trip.
    form = PDAcroForm()
    form.set_q(PDAcroForm.QUADDING_CENTERED)
    assert form.get_q() == 1
    form.set_q(PDAcroForm.QUADDING_RIGHT)
    assert form.get_q() == 2


def test_quadding_constants_match_pd_variable_text_module() -> None:
    """Cross-check the values against :class:`PDVariableText`
    constants — re-exposing them on PDAcroForm is for ergonomics, not
    a different value."""
    from pypdfbox.pdmodel.interactive.form.pd_variable_text import PDVariableText

    assert PDAcroForm.QUADDING_LEFT == PDVariableText.QUADDING_LEFT
    assert PDAcroForm.QUADDING_CENTERED == PDVariableText.QUADDING_CENTERED
    assert PDAcroForm.QUADDING_RIGHT == PDVariableText.QUADDING_RIGHT


def test_has_fields_returns_false_when_empty() -> None:
    """``has_fields`` is ``False`` for a freshly-built form (constructor
    seeds an empty ``/Fields`` array) and after ``set_fields(None)``."""
    form = PDAcroForm()
    assert form.has_fields() is False

    field = PDFieldStub(form)
    field.set_partial_name("name")
    form.set_fields([field])
    assert form.has_fields() is True

    form.set_fields(None)
    assert form.has_fields() is False


def test_has_fields_returns_false_when_fields_entry_missing() -> None:
    """``has_fields`` survives a missing ``/Fields`` entry (PDFBOX-2965
    parity — some PDFs drop the required entry entirely)."""
    from pypdfbox.cos import COSName

    form = PDAcroForm()
    form.get_cos_object().remove_item(COSName.get_pdf_name("Fields"))
    assert form.has_fields() is False


def test_has_fields_skips_non_dictionary_entries() -> None:
    """``has_fields`` only counts dictionary entries — non-dict entries
    in ``/Fields`` (e.g. nulls or stray names) don't count as fields,
    matching the dictionary-only filter in ``get_fields``."""
    from pypdfbox.cos import COSArray, COSName, COSNull

    form = PDAcroForm()
    arr = COSArray()
    arr.add(COSNull.NULL)
    form.get_cos_object().set_item(COSName.get_pdf_name("Fields"), arr)
    assert form.has_fields() is False

    # Add a real dict entry — now the array reports as having fields.
    field = PDFieldStub(form)
    field.set_partial_name("name")
    arr.add(field.get_cos_object())
    assert form.has_fields() is True


def test_is_empty_combines_has_fields_and_has_xfa() -> None:
    """``is_empty`` is true when both ``/Fields`` is empty AND ``/XFA``
    is absent — the form's catalog entry could safely be dropped."""
    from pypdfbox.cos import COSDictionary, COSName

    form = PDAcroForm()
    assert form.is_empty() is True

    # Adding a field flips it.
    field = PDFieldStub(form)
    field.set_partial_name("name")
    form.set_fields([field])
    assert form.is_empty() is False

    form.set_fields(None)
    assert form.is_empty() is True

    # Adding only an XFA payload still counts as non-empty.
    form.get_cos_object().set_item(COSName.get_pdf_name("XFA"), COSDictionary())
    assert form.is_empty() is False


def test_has_calc_order_returns_false_when_absent() -> None:
    """``has_calc_order`` is ``False`` for a fresh form (no ``/CO``)
    and ``True`` after ``set_calc_order`` is given a non-empty list."""
    form = PDAcroForm()
    assert form.has_calc_order() is False

    field = PDFieldStub(form)
    field.set_partial_name("total")
    form.set_calc_order([field])
    assert form.has_calc_order() is True

    # Empty list / None drops the entry — predicate flips back.
    form.set_calc_order(None)
    assert form.has_calc_order() is False
    form.set_calc_order([])
    assert form.has_calc_order() is False


def test_has_calc_order_skips_non_dictionary_entries() -> None:
    """``has_calc_order`` mirrors the dictionary-only filter in
    ``get_calc_order`` — a ``/CO`` array containing only non-dict
    entries reports as empty."""
    from pypdfbox.cos import COSArray, COSName, COSNull

    form = PDAcroForm()
    arr = COSArray()
    arr.add(COSNull.NULL)
    form.get_cos_object().set_item(COSName.get_pdf_name("CO"), arr)
    assert form.has_calc_order() is False
    # And get_calc_order agrees.
    assert form.get_calc_order() == []


def test_set_need_appearances_with_none_removes_entry() -> None:
    """``set_need_appearances(None)`` mirrors upstream's boxed-Boolean
    null semantic by dropping ``/NeedAppearances`` from the dict."""
    from pypdfbox.cos import COSName

    form = PDAcroForm()
    form.set_need_appearances(True)
    assert form.get_cos_object().contains_key(COSName.get_pdf_name("NeedAppearances"))
    assert form.is_need_appearances() is True

    # None clears the entry — tri-state flips back to "absent".
    form.set_need_appearances(None)
    assert not form.get_cos_object().contains_key(COSName.get_pdf_name("NeedAppearances"))
    assert form.get_need_appearances_if_exists() is None
    # Falls back to default (False).
    assert form.is_need_appearances() is False


def test_set_need_appearances_with_none_on_fresh_form_is_no_op() -> None:
    """Removing an absent ``/NeedAppearances`` is a clean no-op — no
    exception, no entry created."""
    from pypdfbox.cos import COSName

    form = PDAcroForm()
    assert not form.get_cos_object().contains_key(COSName.get_pdf_name("NeedAppearances"))
    form.set_need_appearances(None)
    assert not form.get_cos_object().contains_key(COSName.get_pdf_name("NeedAppearances"))


def test_set_need_appearances_round_trips_false() -> None:
    """``False`` writes the entry as ``false`` (not "remove") — only
    ``None`` is special-cased to remove the entry."""
    from pypdfbox.cos import COSName

    form = PDAcroForm()
    form.set_need_appearances(False)
    assert form.get_cos_object().contains_key(COSName.get_pdf_name("NeedAppearances"))
    assert form.get_need_appearances_if_exists() is False
    assert form.is_need_appearances() is False


def test_has_default_resources_returns_false_when_absent() -> None:
    """Fresh form has no ``/DR`` — predicate is ``False`` and
    ``get_default_resources`` agrees with ``None``."""
    form = PDAcroForm()
    assert form.has_default_resources() is False
    assert form.get_default_resources() is None


def test_has_default_resources_round_trips_with_set_default_resources() -> None:
    """``set_default_resources`` toggles the predicate; passing ``None``
    drops the entry and flips it back."""
    from pypdfbox.pdmodel.pd_resources import PDResources

    form = PDAcroForm()
    resources = PDResources()
    form.set_default_resources(resources)
    assert form.has_default_resources() is True
    assert form.get_default_resources() is not None

    form.set_default_resources(None)
    assert form.has_default_resources() is False
    assert form.get_default_resources() is None


def test_has_default_resources_returns_false_for_non_dict_entry() -> None:
    """A malformed ``/DR`` whose value is not a dictionary is treated
    as absent — same guard as ``get_default_resources``."""
    from pypdfbox.cos import COSArray, COSName

    form = PDAcroForm()
    # Stuff a non-dict value under /DR (synthetic — shouldn't happen in
    # well-formed PDFs but the guard exists upstream too).
    form.get_cos_object().set_item(COSName.get_pdf_name("DR"), COSArray())
    assert form.has_default_resources() is False
    assert form.get_default_resources() is None


def test_has_default_appearance_returns_false_when_absent() -> None:
    """Fresh form has no ``/DA`` — predicate is ``False``;
    ``get_default_appearance`` returns ``""`` (upstream parity)."""
    form = PDAcroForm()
    assert form.has_default_appearance() is False
    assert form.get_default_appearance() == ""
    assert form.get_default_appearance_if_exists() is None


def test_has_default_appearance_distinguishes_empty_from_absent() -> None:
    """An explicit empty ``/DA`` is "present" — distinguishes from
    "absent", which both yield ``""`` from ``get_default_appearance``."""
    form = PDAcroForm()
    form.set_default_appearance("")
    assert form.has_default_appearance() is True
    assert form.get_default_appearance() == ""
    assert form.get_default_appearance_if_exists() == ""


def test_has_default_appearance_round_trip_with_value() -> None:
    """``set_default_appearance`` toggles the predicate to ``True``."""
    form = PDAcroForm()
    form.set_default_appearance("/Helv 12 Tf 0 g")
    assert form.has_default_appearance() is True
    assert form.get_default_appearance() == "/Helv 12 Tf 0 g"


def test_get_q_if_exists_returns_none_when_absent() -> None:
    """Fresh form has no ``/Q`` — ``get_q_if_exists`` returns ``None``
    while ``get_q`` falls back to ``QUADDING_LEFT`` (0)."""
    form = PDAcroForm()
    assert form.get_q_if_exists() is None
    assert form.get_q() == PDAcroForm.QUADDING_LEFT


def test_get_q_if_exists_distinguishes_explicit_zero_from_absent() -> None:
    """An explicit ``/Q = 0`` is "present" with value ``0`` — distinguishes
    from "absent", which both return ``0`` via ``get_q``."""
    form = PDAcroForm()
    form.set_q(PDAcroForm.QUADDING_LEFT)  # 0
    assert form.get_q_if_exists() == 0
    assert form.get_q() == 0


def test_get_q_if_exists_returns_explicit_value() -> None:
    """``get_q_if_exists`` round-trips each documented quadding value."""
    form = PDAcroForm()
    for q in (PDAcroForm.QUADDING_LEFT, PDAcroForm.QUADDING_CENTERED, PDAcroForm.QUADDING_RIGHT):
        form.set_q(q)
        assert form.get_q_if_exists() == q
        assert form.get_q() == q
