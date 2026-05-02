"""Wave 185 round-out for pdmodel/graphics/optionalcontent.

Covers four small gaps:

- ``PDOptionalContentGroup.get_render_state`` /
  ``set_render_state`` accept a :class:`RenderDestination` enum value
  (mirrors upstream ``getRenderState(RenderDestination)``), in addition
  to the existing string overload.
- ``PDOptionalContentGroup.__str__`` mirrors upstream
  ``toString() -> super.toString() + " (" + getName() + ")"``.
- ``PDOptionalContentMembershipDictionary.contains_ocg`` predicate.
- ``PDOptionalContentMembershipDictionary.add_ocg`` incremental append
  (single-dict ↔ array promotion + duplicate suppression).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    RenderState,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (  # noqa: E501
    PDOptionalContentMembershipDictionary,
)
from pypdfbox.rendering.render_destination import RenderDestination


# ---------- get_render_state / set_render_state accept RenderDestination ----


def test_get_render_state_accepts_render_destination_print() -> None:
    ocg = PDOptionalContentGroup("L1")
    ocg.set_render_state("OFF", "Print")
    # Same lookup, but via the typed enum.
    assert ocg.get_render_state(RenderDestination.PRINT) == "OFF"


def test_get_render_state_accepts_render_destination_view() -> None:
    ocg = PDOptionalContentGroup("L1")
    ocg.set_render_state("ON", "View")
    assert ocg.get_render_state(RenderDestination.VIEW) == "ON"


def test_get_render_state_accepts_render_destination_export() -> None:
    ocg = PDOptionalContentGroup("L1")
    ocg.set_render_state("OFF", "Export")
    assert ocg.get_render_state(RenderDestination.EXPORT) == "OFF"


def test_set_render_state_accepts_render_destination_typed() -> None:
    ocg = PDOptionalContentGroup("L1")
    ocg.set_render_state("OFF", RenderDestination.PRINT)
    # Round-trip via the string form to confirm the COSName landed under /Print.
    assert ocg.get_render_state("Print") == "OFF"


def test_set_render_state_typed_destination_round_trip_view() -> None:
    ocg = PDOptionalContentGroup("L1")
    ocg.set_render_state("ON", RenderDestination.VIEW)
    cos = ocg.get_cos_object()
    usage = cos.get_dictionary_object(COSName.get_pdf_name("Usage"))
    assert isinstance(usage, COSDictionary)
    view = usage.get_dictionary_object(COSName.get_pdf_name("View"))
    assert isinstance(view, COSDictionary)
    assert view.get_dictionary_object(
        COSName.get_pdf_name("ViewState")
    ) == COSName.get_pdf_name("ON")


def test_get_render_state_enum_accepts_typed_destination() -> None:
    ocg = PDOptionalContentGroup("L1")
    ocg.set_render_state_enum(RenderState.ON, RenderDestination.PRINT)
    assert ocg.get_render_state_enum(RenderDestination.PRINT) is RenderState.ON


def test_get_render_state_rejects_unknown_destination_type() -> None:
    ocg = PDOptionalContentGroup("L1")
    ocg.set_render_state("OFF", "Export")
    with pytest.raises(TypeError):
        ocg.get_render_state(42)  # type: ignore[arg-type]


def test_set_render_state_rejects_unknown_destination_type() -> None:
    ocg = PDOptionalContentGroup("L1")
    with pytest.raises(TypeError):
        ocg.set_render_state("ON", 3.14)  # type: ignore[arg-type]


def test_get_render_state_default_destination_falls_back_to_export() -> None:
    """When no destination is supplied the resolver should look only at
    /Export, mirroring upstream behaviour where ``state`` stays null until
    the export fallback runs."""
    ocg = PDOptionalContentGroup("L1")
    ocg.set_render_state("OFF", RenderDestination.EXPORT)
    # Explicit None destination → still returns the Export state.
    assert ocg.get_render_state(None) == "OFF"


# ---------- __str__ ----------


def test_str_includes_name() -> None:
    ocg = PDOptionalContentGroup("ColorLayer")
    s = str(ocg)
    # Upstream form: "<super.toString()> (<name>)"; we don't pin the prefix
    # but the name in parens must be present.
    assert "(ColorLayer)" in s


def test_str_with_unnamed_ocg() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("OCG"))  # type: ignore[attr-defined]
    ocg = PDOptionalContentGroup(raw)
    # When /Name absent get_name() returns None; toString round-trips it.
    assert "(None)" in str(ocg)


def test_repr_unchanged_after_str_addition() -> None:
    """``__repr__`` is supplied by ``PDPropertyList`` and includes the
    /Type discriminator. Adding ``__str__`` should not silently override
    the repr (which would break debug dumps that walk OCG lists)."""
    ocg = PDOptionalContentGroup("Layer")
    r = repr(ocg)
    assert "PDOptionalContentGroup" in r
    assert "type=" in r


# ---------- OCMD.contains_ocg ----------


def test_contains_ocg_true_after_set_ocgs_list() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    ocmd.set_ocgs([a, b])
    assert ocmd.contains_ocg(a) is True
    assert ocmd.contains_ocg(b) is True


def test_contains_ocg_false_for_unrelated_group() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    other = PDOptionalContentGroup("Other")
    ocmd.set_ocgs([a])
    assert ocmd.contains_ocg(other) is False


def test_contains_ocg_handles_single_dict_form() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    ocmd.set_ocgs(a)  # writes /OCGs as a single dict, not an array
    assert ocmd.contains_ocg(a) is True


def test_contains_ocg_empty_when_ocgs_missing() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    assert ocmd.contains_ocg(a) is False


def test_contains_ocg_accepts_raw_cos_dictionary() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    ocmd.set_ocgs([a])
    # Identity match against the raw dict.
    assert ocmd.contains_ocg(a.get_cos_object()) is True


def test_contains_ocg_identity_not_name_based() -> None:
    """Two OCGs sharing a /Name must not be conflated — membership is
    by identity of the wrapped ``COSDictionary``."""
    ocmd = PDOptionalContentMembershipDictionary()
    a1 = PDOptionalContentGroup("Same")
    a2 = PDOptionalContentGroup("Same")
    ocmd.set_ocgs([a1])
    assert ocmd.contains_ocg(a1) is True
    assert ocmd.contains_ocg(a2) is False


def test_contains_ocg_rejects_invalid_type() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    with pytest.raises(TypeError):
        ocmd.contains_ocg("Layer")  # type: ignore[arg-type]


# ---------- OCMD.add_ocg ----------


def test_add_ocg_creates_array_when_ocgs_missing() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    ocmd.add_ocg(a)
    raw = ocmd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("OCGs"))
    assert isinstance(raw, COSArray)
    assert raw.size() == 1
    assert raw.get_object(0) is a.get_cos_object()


def test_add_ocg_appends_to_existing_array() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    ocmd.set_ocgs([a])
    ocmd.add_ocg(b)
    groups = ocmd.get_ocgs()
    assert [g.get_name() for g in groups] == ["A", "B"]


def test_add_ocg_promotes_single_dict_to_array() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    ocmd.set_ocgs(a)  # writes /OCGs as a single dict
    ocmd.add_ocg(b)
    raw = ocmd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("OCGs"))
    assert isinstance(raw, COSArray)
    assert raw.size() == 2
    groups = ocmd.get_ocgs()
    assert [g.get_name() for g in groups] == ["A", "B"]


def test_add_ocg_duplicate_is_noop_array() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    ocmd.set_ocgs([a])
    ocmd.add_ocg(a)
    ocmd.add_ocg(a)
    assert len(ocmd.get_ocgs()) == 1


def test_add_ocg_duplicate_is_noop_single_dict() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    ocmd.set_ocgs(a)
    ocmd.add_ocg(a)
    raw = ocmd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("OCGs"))
    # Should still be the single-dict form, not promoted to a 1-element array.
    assert raw is a.get_cos_object()


def test_add_ocg_accepts_raw_cos_dictionary() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    ocmd.add_ocg(a.get_cos_object())
    assert ocmd.contains_ocg(a) is True


def test_add_ocg_rejects_invalid_type() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    with pytest.raises(TypeError):
        ocmd.add_ocg(42)  # type: ignore[arg-type]


def test_add_ocg_then_contains_round_trip() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    c = PDOptionalContentGroup("C")
    ocmd.add_ocg(a)
    ocmd.add_ocg(b)
    ocmd.add_ocg(c)
    assert ocmd.contains_ocg(a) is True
    assert ocmd.contains_ocg(b) is True
    assert ocmd.contains_ocg(c) is True
    # And /P remains unchanged at the default.
    assert ocmd.get_visibility_policy() == "AnyOn"
