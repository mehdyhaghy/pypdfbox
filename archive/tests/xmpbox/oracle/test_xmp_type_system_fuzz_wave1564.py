"""Live Apache xmpbox differential parity for the TYPE-SYSTEM container layer.

Where ``test_xmp_property_type_fuzz_wave1535.py`` fuzzes the simple value classes
(Integer/Real/Boolean/Date/Text constructor + getStringValue) and
``test_xmp_structured_type_fuzz_wave1536.py`` fuzzes the *typed* getters of the
individual structured types, this file reaches the parts those two leave
uncovered, comparing pypdfbox against the live Apache xmpbox 3.0.7 jar through
the ``XmpTypeSystemFuzzProbe`` probe:

  * :class:`ArrayProperty` — container-kind (Bag/Seq/Alt) detection, add +
    ``get_all_properties`` size, ``get_elements_as_string`` ordering,
    ``get_properties_by_local_name`` (None-vs-list), ``remove_property`` /
    ``remove_properties_by_name``, and the identity-based
    ``contains_property`` / ``is_same_property`` equivalence.
  * :class:`AbstractStructuredType` GENERIC field access (not the per-type typed
    getters): ``add_simple_property`` + ``get_property`` present/absent,
    ``get_property_value_as_string``, add-twice-replaces, wrong-type cast.
  * :class:`TypeMapping` ``instanciate_simple_property`` /
    ``instanciate_structured_type`` for a known vs unknown type.

Comparison surface: the probe emits ``key=value`` pairs joined by the ASCII unit
separator (0x1f), or ``ERR<US>ExceptionSimpleName`` when a call throws. The
Python side projects the same key=value shape; for the cases where both sides
raise we compare the *classification* ("ERR") rather than the exception class
name (Java throws ``IllegalArgumentException`` / ``ClassCastException`` /
``NullPointerException``; pypdfbox raises ``ValueError`` /
``BadFieldValueException``).

Wave 1564 real-bug pin: ``ArrayProperty.is_same_property`` (hence
``contains_property``) was value-based for simple properties; upstream has no
``equals`` override anywhere in the ``AbstractField`` hierarchy, so its
``isSameProperty`` falls back to *object identity* when the local names match.
Two distinct same-value siblings are NOT the same property (``c=false`` for the
``arr_contains_same_value`` case below). The port now mirrors that.

Honest divergence (NOT compared cross-side, asserted Python-only): a generic
``add_simple_property`` for a field name *not declared* on the structured type
raises ``NullPointerException`` upstream (``getPropertyType(name)`` returns null
and ``.type()`` NPEs); pypdfbox is intentionally lenient and defaults the type
to ``Text``.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox.type.array_property import ArrayProperty, Cardinality
from pypdfbox.xmpbox.type.dimensions_type import DimensionsType
from pypdfbox.xmpbox.type.job_type import JobType
from pypdfbox.xmpbox.type.text_type import TextType
from pypdfbox.xmpbox.type.thumbnail_type import ThumbnailType
from pypdfbox.xmpbox.type.type_mapping import TypeMapping
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
from tests.oracle.harness import requires_oracle, run_probe_text

_US = chr(0x1F)
_NS = "http://ns.example/"
_PFX = "ex"


# --- Python case runner -------------------------------------------------
#
# Each runner returns the SAME ``key=value`` payload the Java probe emits (or
# the literal ``"ERR"`` sentinel when the matching Java call throws — see the
# per-case mapping below). The cross-side comparison normalises any payload that
# *starts with* ``ERR`` so the differing exception-class names don't matter.


def _meta() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def _text(meta: XMPMetadata, value: str) -> TextType:
    # rdf:li children carry the structure-array element local name "li".
    return TextType(meta, _NS, _PFX, "li", value)


def _bag(meta: XMPMetadata) -> ArrayProperty:
    return ArrayProperty(meta, _NS, _PFX, "arr", Cardinality.Bag)


def _seq(meta: XMPMetadata) -> ArrayProperty:
    return ArrayProperty(meta, _NS, _PFX, "arr", Cardinality.Seq)


def _alt(meta: XMPMetadata) -> ArrayProperty:
    return ArrayProperty(meta, _NS, _PFX, "arr", Cardinality.Alt)


def _join(items: list[str]) -> str:
    return ",".join(items)


def _by_name(result: list | None) -> str:
    return "null" if result is None else f"size={len(result)}"


def _py_case(case: str) -> str:  # noqa: C901 - flat switch mirrors the probe
    meta = _meta()
    if case == "arr_bag_kind":
        return f"type={_bag(meta).get_array_type().value}"
    if case == "arr_seq_kind":
        return f"type={_seq(meta).get_array_type().value}"
    if case == "arr_alt_kind":
        return f"type={_alt(meta).get_array_type().value}"

    if case == "arr_empty_elems":
        a = _bag(meta)
        return f"size={len(a.get_all_properties())}{_US}elems={_join(a.get_elements_as_string())}"
    if case == "arr_add_elems":
        a = _seq(meta)
        for v in ("one", "two", "three"):
            a.add_property(_text(meta, v))
        return f"size={len(a.get_all_properties())}{_US}elems={_join(a.get_elements_as_string())}"
    if case == "arr_add_dup":
        a = _bag(meta)
        a.add_property(_text(meta, "x"))
        a.add_property(_text(meta, "x"))
        return f"size={len(a.get_all_properties())}{_US}elems={_join(a.get_elements_as_string())}"
    if case == "arr_add_empty_str":
        a = _bag(meta)
        a.add_property(_text(meta, ""))
        return f"size={len(a.get_all_properties())}{_US}elems={_join(a.get_elements_as_string())}"

    if case == "arr_byname_miss":
        a = _bag(meta)
        a.add_property(_text(meta, "v"))
        return f"r={_by_name(a.get_properties_by_local_name('nope'))}"
    if case == "arr_byname_hit":
        a = _bag(meta)
        a.add_property(_text(meta, "v1"))
        a.add_property(_text(meta, "v2"))
        return f"r={_by_name(a.get_properties_by_local_name('li'))}"

    if case == "arr_remove_prop":
        a = _seq(meta)
        keep = _text(meta, "keep")
        drop = _text(meta, "drop")
        a.add_property(keep)
        a.add_property(drop)
        a.remove_property(drop)
        return f"size={len(a.get_all_properties())}{_US}elems={_join(a.get_elements_as_string())}"
    if case == "arr_remove_byname":
        a = _seq(meta)
        a.add_property(_text(meta, "a"))
        a.add_property(_text(meta, "b"))
        a.remove_properties_by_name("li")
        return f"size={len(a.get_all_properties())}"

    if case == "arr_contains_same_value":
        a = _bag(meta)
        a.add_property(_text(meta, "dup"))
        return f"c={str(a.contains_property(_text(meta, 'dup'))).lower()}"
    if case == "arr_contains_diff_value":
        a = _bag(meta)
        a.add_property(_text(meta, "one"))
        return f"c={str(a.contains_property(_text(meta, 'two'))).lower()}"

    if case == "struct_get_absent":
        j = JobType(meta)
        return f"p={'null' if j.get_property(JobType.ID) is None else 'obj'}"
    if case == "struct_add_get":
        j = JobType(meta)
        j.add_simple_property(JobType.ID, "J7")
        found = j.get_property(JobType.ID) is not None
        val = j.get_property_value_as_string(JobType.ID)
        return f"found={str(found).lower()}{_US}val={val}"
    if case == "struct_add_twice_replaces":
        j = JobType(meta)
        j.add_simple_property(JobType.ID, "first")
        j.add_simple_property(JobType.ID, "second")
        val = j.get_property_value_as_string(JobType.ID)
        return f"size={len(j.get_all_properties())}{_US}val={val}"
    if case == "struct_remove_present":
        j = JobType(meta)
        j.add_simple_property(JobType.ID, "X")
        j.remove_property(j.get_property(JobType.ID))
        return f"size={len(j.get_all_properties())}"
    if case == "struct_value_as_string_absent":
        # Absent field -> None; render it as Java's String.valueOf(null) = "null".
        j = JobType(meta)
        value = j.get_property_value_as_string(JobType.ID)
        return f"v={'null' if value is None else value}"
    if case == "struct_wrong_type_cast":
        d = DimensionsType(meta)
        try:
            d.add_simple_property(DimensionsType.W, "not-a-real")
        except (ValueError, TypeError):
            return "ERR"
        return f"w={d.get_w()}"
    if case == "struct_int_wrong_type_cast":
        t = ThumbnailType(meta)
        try:
            t.add_simple_property(ThumbnailType.HEIGHT, "not-an-int")
        except (ValueError, TypeError):
            return "ERR"
        return f"h={t.get_height()}"

    if case == "tm_simple_text":
        tm = TypeMapping(meta)
        f = tm.instanciate_simple_property(_NS, _PFX, "p", "hello", "Text")
        return f"cls={type(f).__name__}{_US}v={f.get_string_value()}"
    if case == "tm_simple_integer_ok":
        tm = TypeMapping(meta)
        f = tm.instanciate_simple_property(_NS, _PFX, "p", "42", "Integer")
        return f"cls={type(f).__name__}{_US}v={f.get_string_value()}"
    if case == "tm_simple_integer_bad":
        tm = TypeMapping(meta)
        try:
            tm.instanciate_simple_property(_NS, _PFX, "p", "abc", "Integer")
        except (ValueError, TypeError):
            return "ERR"
        return "OK"
    if case == "tm_simple_structured_type":
        tm = TypeMapping(meta)
        try:
            tm.instanciate_simple_property(_NS, _PFX, "p", "x", "Dimensions")
        except (ValueError, TypeError):
            return "ERR"
        return "OK"

    if case == "tm_struct_known":
        tm = TypeMapping(meta)
        s = tm.instanciate_structured_type("Dimensions", "p")
        return f"cls={type(s).__name__}{_US}name={s.get_property_name()}"
    if case == "tm_struct_simple_name":
        tm = TypeMapping(meta)
        try:
            tm.instanciate_structured_type("Text", "p")
        except Exception:  # noqa: BLE001 - upstream raises a structured-type error
            return "ERR"
        return "OK"

    raise AssertionError(f"unknown case {case!r}")


# (case_id, python_class_simple_name_remap). The second tuple element maps a Java
# class simple-name to the pypdfbox one when both sides succeed AND the probe
# emits a ``cls=`` key — needed because the projected class names are identical
# here (TextType / IntegerType / DimensionsType) so no remap is required, but we
# keep the comparison string-exact for the OK cases.
_CASES: list[str] = [
    "arr_bag_kind",
    "arr_seq_kind",
    "arr_alt_kind",
    "arr_empty_elems",
    "arr_add_elems",
    "arr_add_dup",
    "arr_add_empty_str",
    "arr_byname_miss",
    "arr_byname_hit",
    "arr_remove_prop",
    "arr_remove_byname",
    "arr_contains_same_value",
    "arr_contains_diff_value",
    "struct_get_absent",
    "struct_add_get",
    "struct_add_twice_replaces",
    "struct_remove_present",
    "struct_value_as_string_absent",
    "struct_wrong_type_cast",
    "struct_int_wrong_type_cast",
    "tm_simple_text",
    "tm_simple_integer_ok",
    "tm_simple_integer_bad",
    "tm_simple_structured_type",
    "tm_struct_known",
    "tm_struct_simple_name",
]


def _java_outcome(case: str) -> str:
    raw = run_probe_text("XmpTypeSystemFuzzProbe", case).rstrip("\n")
    if raw.startswith("ERR"):
        return "ERR"
    return raw


def _py_outcome(case: str) -> str:
    raw = _py_case(case)
    if raw.startswith("ERR"):
        return "ERR"
    return raw


@requires_oracle
@pytest.mark.parametrize("case", _CASES, ids=_CASES)
def test_type_system_matches_xmpbox(case: str) -> None:
    java = _java_outcome(case)
    py = _py_outcome(case)
    assert py == java, f"type-system divergence for {case}: java={java!r} py={py!r}"


# --- Honest divergences pinned Python-only (NOT compared to Java) -------


def test_add_simple_property_unknown_field_is_lenient() -> None:
    """Upstream NPEs on an undeclared field name (``getPropertyType`` is null);
    pypdfbox is intentionally lenient and defaults the unknown field to a Text
    property. Confirmed against the ``struct_add_unknown_field`` probe case,
    which the live oracle reports as ``ERR<US>NullPointerException``."""
    meta = _meta()
    j = JobType(meta)
    j.add_simple_property("undeclared", "v")
    assert len(j.get_all_properties()) == 1
    assert j.get_property_value_as_string("undeclared") == "v"


def test_is_same_property_identity_not_value() -> None:
    """Regression pin for the wave 1564 fix: identity, not value, decides
    sameness (matches Apache xmpbox, which has no ``equals`` override)."""
    meta = _meta()
    a = _bag(meta)
    one = _text(meta, "dup")
    a.add_property(one)
    assert a.is_same_property(one, one) is True
    assert a.is_same_property(one, _text(meta, "dup")) is False
    assert a.contains_property(one) is True
    assert a.contains_property(_text(meta, "dup")) is False
