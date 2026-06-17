"""Canonical hand-written parity suite for :class:`PDAttributeObject`.

Sibling files (``test_pd_attribute_object_wave275.py``,
``..._wave1241.py``, ``..._wave1252.py``, ``..._parity.py``) carry the
historical wave-by-wave round-out tests; this module is the
canonically-named suite per the project's task-granularity rule and consolidates the
upstream-faithful surface coverage that's grown across waves.

It explicitly captures the wave 1256 parity-script false positives so
future runs of ``scripts/parity.py`` can be cross-referenced against
the documented Java-ism set:

* ``pd_default_attribute_object`` / ``pd_export_format_attribute_object``
  / ``pd_layout_attribute_object`` / ``pd_list_attribute_object`` /
  ``pd_print_field_attribute_object`` / ``pd_table_attribute_object`` /
  ``pd_user_attribute_object``

are class names referenced inside the static ``create()`` switch
(``return new PDXxxAttributeObject(dictionary);``) and are NOT real
methods — the parity-extraction regex misclassifies the multi-token
``ret == "return new"`` because ``return new`` isn't a single Java
keyword. Tracking these here keeps the intent explicit.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDAttributeObject,
    PDDefaultAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDExportFormatAttributeObject,
    PDLayoutAttributeObject,
    PDListAttributeObject,
    PDPrintFieldAttributeObject,
    PDTableAttributeObject,
    PDUserAttributeObject,
)

_O = COSName.get_pdf_name("O")


# ---------- create() factory dispatch (PDAttributeObject.java L63-L93) ----------


@pytest.mark.parametrize(
    ("owner", "expected_cls"),
    [
        ("Layout", PDLayoutAttributeObject),
        ("List", PDListAttributeObject),
        ("PrintField", PDPrintFieldAttributeObject),
        ("Table", PDTableAttributeObject),
        ("UserProperties", PDUserAttributeObject),
        ("XML-1.00", PDExportFormatAttributeObject),
        ("HTML-3.2", PDExportFormatAttributeObject),
        ("HTML-4.01", PDExportFormatAttributeObject),
        ("OEB-1.00", PDExportFormatAttributeObject),
        ("RTF-1.05", PDExportFormatAttributeObject),
        ("CSS-1.00", PDExportFormatAttributeObject),
        ("CSS-2.00", PDExportFormatAttributeObject),
    ],
)
def test_create_dispatches_known_owner_to_typed_subclass(
    owner: str, expected_cls: type
) -> None:
    cos = COSDictionary()
    cos.set_name(_O, owner)
    attr = PDAttributeObject.create(cos)
    assert isinstance(attr, expected_cls)
    assert attr.get_cos_object() is cos


def test_create_unknown_owner_falls_back_to_default() -> None:
    cos = COSDictionary()
    cos.set_name(_O, "WhollyUnknownOwner")
    attr = PDAttributeObject.create(cos)
    assert isinstance(attr, PDDefaultAttributeObject)
    # Pass-through: the underlying COSDictionary identity is preserved.
    assert attr.get_cos_object() is cos


def test_create_owner_missing_falls_back_to_default() -> None:
    cos = COSDictionary()
    attr = PDAttributeObject.create(cos)
    assert isinstance(attr, PDDefaultAttributeObject)
    assert attr.get_owner() is None


# ---------- is_empty() (PDAttributeObject.java L143-L147) ----------


def test_is_empty_true_when_only_owner_present() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    # "only entry is the owner?" — upstream comment.
    assert attr.is_empty() is True


def test_is_empty_false_when_other_entries_present() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    attr.set_revision_number(2)
    assert attr.is_empty() is False


def test_is_empty_false_when_no_entries() -> None:
    # No /O at all -> upstream returns false because get_owner() is null.
    attr = PDAttributeObject()
    assert attr.is_empty() is False


# ---------- toString / __str__ (PDAttributeObject.java L194-L197) ----------


def test_to_string_with_owner_set() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    assert str(attr) == "O=Layout"
    assert attr.to_string() == "O=Layout"


def test_to_string_without_owner_emits_none_marker() -> None:
    attr = PDAttributeObject()
    # Upstream prints "O=null"; Python prints "O=None". Documented
    # divergence — tracked here as the expected snake-case Python form.
    assert str(attr) == "O=None"


# ---------- arrayToString(Object[]) parity (line 205-213) ----------


def test_array_to_string_object_array_empty() -> None:
    assert PDAttributeObject.array_to_string([]) == "[]"


def test_array_to_string_object_array_single() -> None:
    assert PDAttributeObject.array_to_string(["x"]) == "[x]"


def test_array_to_string_object_array_multiple() -> None:
    assert PDAttributeObject.array_to_string(["a", "b", "c"]) == "[a, b, c]"


# ---------- arrayToString(float[]) parity (line 221-229) ----------


def test_array_to_string_float_finite_matches_java_float_to_string() -> None:
    # Java Float.toString(1.0f) = "1.0", Float.toString(2.5f) = "2.5"
    assert PDAttributeObject.array_to_string([1.0, 2.5, 3.0]) == "[1.0, 2.5, 3.0]"


def test_array_to_string_float_nan_uses_java_form() -> None:
    # Java Float.toString(Float.NaN) = "NaN" (mixed-case);
    # Python str(float('nan')) = "nan" (lowercase) — we map to the Java form.
    assert (
        PDAttributeObject.array_to_string([math.nan, 1.0])
        == "[NaN, 1.0]"
    )


def test_array_to_string_float_positive_infinity_uses_java_form() -> None:
    # Java Float.toString(Float.POSITIVE_INFINITY) = "Infinity"
    assert (
        PDAttributeObject.array_to_string([math.inf, 0.0])
        == "[Infinity, 0.0]"
    )


def test_array_to_string_float_negative_infinity_uses_java_form() -> None:
    # Java Float.toString(Float.NEGATIVE_INFINITY) = "-Infinity"
    assert (
        PDAttributeObject.array_to_string([-math.inf, 4.5])
        == "[-Infinity, 4.5]"
    )


def test_array_to_string_mixed_int_and_float() -> None:
    # Ints fall through to str() and look like Java's "1, 2"; floats
    # always carry the trailing ".0".
    assert (
        PDAttributeObject.array_to_string([1, 2.5, 3])
        == "[1, 2.5, 3]"
    )


# ---------- private isValueChanged + protected potentiallyNotifyChanged ----------


def test_is_value_changed_pure_static_no_state_dependency() -> None:
    # is_value_changed is genuinely static — no `self` reads.
    assert PDAttributeObject.is_value_changed(None, None) is False


def test_potentially_notify_changed_no_back_pointer_safe() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    # Without a parent structure element bound, the change ping is a
    # debug-logged no-op and must not raise.
    attr.potentially_notify_changed(None, None)


# ---------- structure-element back-pointer round-trip ----------


def test_structure_element_back_pointer_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_structure_element(elem)
    assert attr.get_structure_element() is elem
    attr.set_structure_element(None)
    assert attr.get_structure_element() is None


def test_notify_changed_on_bound_attribute_bumps_revision() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(13)
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    elem.add_attribute(attr)

    attr.notify_changed()
    # Upstream: notifyChanged delegates to
    # PDStructureElement.attributeChanged(this), which bumps the
    # attribute's revision counter to the structure element's.
    assert elem.get_attributes().get_revision_number_at(0) == 13
