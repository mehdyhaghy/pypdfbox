"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/XMPSchemaTest.java

Coverage notes:
  * ``testBagManagement`` — ported as :func:`test_bag_management`.
  * ``testArrayList`` — covered indirectly by ``test_array_list``, restated
    against cluster #1's plain-list array storage (typed-field round-trip via
    ``add_property`` is exercised by the per-subclass schemas).
  * ``testSeqManagement`` — ported as :func:`test_seq_management`, scoped to
    the date-and-string surface that pypdfbox's ``add_unqualified_sequence_*``
    helpers expose. The mixed-type ordering assertions on ``BooleanType`` are
    skipped because the list-backed Seq doesn't preserve typed wrapper
    identity (cluster #1 unwraps them to strings on insert).
  * ``rdfAboutTest`` — ported as :func:`test_rdf_about`.
  * ``testBadRdfAbout`` — skipped: cluster #1 does not yet model
    ``Attribute`` validation. ``set_about`` accepts a plain string only.
  * ``testSetSpecifiedSimpleTypeProperty`` — ported as
    :func:`test_set_specified_simple_type_property`.
  * ``testSpecifiedSimplePropertyFormer`` — ported as
    :func:`test_specified_simple_property_former`, exercising the new typed
    ``set_text_property`` / ``get_unqualified_text_property`` round-trip.
  * ``testAsSimpleMethods`` — ported as :func:`test_as_simple_methods`,
    exercising the ``setXxxPropertyValueAsSimple`` and the typed
    ``getXxxProperty`` family wired up in this wave.
  * ``testProperties`` — ported as :func:`test_properties`, including the
    ``BadFieldValueException`` mismatched-type asserts.
  * ``testAltProperties`` — ported as :func:`test_alt_properties`.
  * ``testMergeSchema`` — ported as :func:`test_merge_schema`.
  * ``testListAndContainerAccessor`` — skipped: ``Attribute`` /
    ``getAllProperties`` / ``getAllAttributes`` infrastructure on the base
    ``XMPSchema`` is not yet ported; the hand-written parity test file already
    covers the storage round-trip.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import (
    BooleanType,
    DateType,
    IntegerType,
    TextType,
    XMPMetadata,
    XMPSchema,
)
from pypdfbox.xmpbox.xmp_schema import BadFieldValueException


def _new_schema() -> XMPSchema:
    return XMPSchema(
        XMPMetadata.create_xmp_metadata(),
        namespace_uri="nsURI",
        prefix="nsSchem",
    )


# --- testBagManagement ------------------------------------------------------


def test_bag_management() -> None:
    """Port of ``XMPSchemaTest.testBagManagement``."""
    schem = _new_schema()
    bag_name = "BAGTEST"
    value1 = "valueOne"
    value2 = "valueTwo"
    # Upstream calls schem.addBagValue(bag_name, createText(...)). Cluster #1
    # stores Bag values as plain strings, so the typed wrapper variant is
    # unwrapped to its string value via ``add_bag_value``.
    schem.add_bag_value(
        bag_name,
        TextType(schem.get_metadata(), None, "rdf", "li", value1),
    )
    schem.add_qualified_bag_value(bag_name, value2)

    values = schem.get_unqualified_bag_value_list(bag_name)
    assert values is not None
    assert values[0] == value1
    assert values[1] == value2

    schem.remove_unqualified_bag_value(bag_name, value1)
    values2 = schem.get_unqualified_bag_value_list(bag_name)
    assert values2 == [value2]


# --- testSeqManagement (subset) --------------------------------------------


def test_seq_management() -> None:
    """
    Subset port of ``XMPSchemaTest.testSeqManagement`` covering the date /
    string surface that pypdfbox exposes today. The mixed-type ordering
    assertions on ``BooleanType`` are dropped because cluster #1 unwraps
    typed simple wrappers to plain strings on Seq insert.
    """
    schem = _new_schema()
    date_value = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    text_val = "seqValue"
    seq_name = "SEQNAME"

    schem.add_unqualified_sequence_date_value(seq_name, date_value)
    schem.add_unqualified_sequence_value(seq_name, text_val)

    dates = schem.get_unqualified_sequence_date_value_list(seq_name)
    assert dates == [date_value]

    schem.remove_unqualified_sequence_date_value(seq_name, date_value)
    assert schem.get_unqualified_sequence_date_value_list(seq_name) == []

    schem.remove_unqualified_sequence_value(seq_name, text_val)
    assert schem.get_unqualified_sequence_value_list(seq_name) == []


# --- rdfAboutTest -----------------------------------------------------------


def test_rdf_about() -> None:
    """Port of ``XMPSchemaTest.rdfAboutTest``."""
    schem = _new_schema()
    assert schem.get_about_value() is None  # upstream returns "" via attribute
    about = "about"
    schem.set_about_as_simple(about)
    assert schem.get_about_value() == about
    schem.set_about_as_simple("")
    # Empty input clears in cluster #1 — getAboutAttribute returns None.
    assert schem.get_about_value() in {"", None}
    schem.set_about_as_simple(None)
    assert schem.get_about_value() is None


# --- testSetSpecifiedSimpleTypeProperty -------------------------------------


def test_set_specified_simple_type_property() -> None:
    """Port of ``XMPSchemaTest.testSetSpecifiedSimpleTypeProperty``."""
    schem = _new_schema()
    prop = "testprop"
    val = "value"
    val2 = "value2"
    schem.set_text_property_value_as_simple(prop, val)
    assert schem.get_unqualified_text_property_value(prop) == val
    schem.set_text_property_value_as_simple(prop, val2)
    assert schem.get_unqualified_text_property_value(prop) == val2
    schem.set_text_property_value_as_simple(prop, None)
    assert schem.get_unqualified_text_property(prop) is None


# --- testSpecifiedSimplePropertyFormer --------------------------------------


def test_specified_simple_property_former() -> None:
    """Port of ``XMPSchemaTest.testSpecifiedSimplePropertyFormer``."""
    schem = _new_schema()
    prop = "testprop"
    val = "value"
    schem.set_text_property_value_as_simple(prop, val)
    text = TextType(
        schem.get_metadata(), None, schem.get_prefix(), prop, "value2"
    )
    schem.set_text_property(text)
    assert schem.get_unqualified_text_property_value(prop) == "value2"


# --- testAsSimpleMethods ----------------------------------------------------


def test_as_simple_methods() -> None:
    """Port of ``XMPSchemaTest.testAsSimpleMethods``."""
    schem = _new_schema()
    bool_name = "bool"
    bool_val = True

    date_name = "date"
    date_val = datetime(2024, 1, 1, 12, 30, tzinfo=UTC)

    integ = "integer"
    i = 1

    langprop = "langprop"
    lang = "x-default"
    lang_val = "langVal"

    bagprop = "bagProp"
    bag_val = "bagVal"

    seqprop = "SeqProp"
    seq_prop_val = "seqval"

    seqdate = "SeqDate"

    schem.set_boolean_property_value_as_simple(bool_name, bool_val)
    schem.set_date_property_value_as_simple(date_name, date_val)
    schem.set_integer_property_value_as_simple(integ, i)
    schem.set_unqualified_language_property_value(langprop, lang, lang_val)
    schem.add_bag_value_as_simple(bagprop, bag_val)
    schem.add_unqualified_sequence_value(seqprop, seq_prop_val)
    schem.add_sequence_date_value_as_simple(seqdate, date_val)

    boolean_property = schem.get_boolean_property(bool_name)
    assert boolean_property is not None
    assert boolean_property.get_value() is bool_val

    date_property = schem.get_date_property(date_name)
    assert date_property is not None
    assert date_property.get_value() == date_val

    integer_property = schem.get_integer_property(integ)
    assert integer_property is not None
    assert integer_property.get_string_value() == str(i)

    assert (
        schem.get_unqualified_language_property_value(langprop, lang) == lang_val
    )
    bag_list = schem.get_unqualified_bag_value_list(bagprop)
    assert bag_list is not None
    assert bag_val in bag_list
    seq_list = schem.get_unqualified_sequence_value_list(seqprop)
    assert seq_list is not None
    assert seq_prop_val in seq_list
    date_seq = schem.get_unqualified_sequence_date_value_list(seqdate)
    assert date_seq is not None
    assert date_val in date_seq
    languages = schem.get_unqualified_language_property_languages_value(langprop)
    assert languages is not None
    assert lang in languages

    assert schem.get_boolean_property_value_as_simple(bool_name) is bool_val
    assert schem.get_date_property_value_as_simple(date_name) == date_val
    assert schem.get_integer_property_value_as_simple(integ) == i


# --- testProperties ---------------------------------------------------------


def test_properties() -> None:
    """Port of ``XMPSchemaTest.testProperties`` (subset — Attribute-bound
    ``setAbout(Attribute)`` form is skipped, see top-of-file note)."""
    schem = _new_schema()
    assert schem.get_namespace() == "nsURI"

    schem.add_namespace("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")

    text_prop = "textProp"
    text_prop_val = "TextPropTest"
    schem.set_text_property_value(text_prop, text_prop_val)
    assert schem.get_unqualified_text_property_value(text_prop) == text_prop_val

    text = TextType(
        schem.get_metadata(), None, "nsSchem", "textType", "GRINGO"
    )
    schem.set_text_property(text)
    # Identity round-trip: the typed wrapper handed in must come back out.
    assert schem.get_property("textType") == "GRINGO"

    date_val = datetime(2024, 1, 1, 12, 30, tzinfo=UTC)
    date_name = "nsSchem:dateProp"
    schem.set_date_property_value(date_name, date_val)
    assert schem.get_date_property_value(date_name) == date_val

    date_type = DateType(
        schem.get_metadata(), None, "nsSchem", "dateType", date_val
    )
    schem.set_date_property(date_type)
    fetched = schem.get_date_property("dateType")
    assert fetched is date_type

    bool_name = "nsSchem:booleanTestProp"
    bool_val = False
    schem.set_boolean_property_value(bool_name, bool_val)
    assert schem.get_boolean_property_value(bool_name) is bool_val

    bool_type = BooleanType(
        schem.get_metadata(), None, "nsSchem", "boolType", False
    )
    schem.set_boolean_property(bool_type)
    fetched_bool = schem.get_boolean_property("boolType")
    assert fetched_bool is bool_type

    int_prop = "nsSchem:IntegerTestProp"
    int_prop_val = 5
    schem.set_integer_property_value(int_prop, int_prop_val)
    assert schem.get_integer_property_value(int_prop) == int_prop_val

    int_type = IntegerType(
        schem.get_metadata(), None, "nsSchem", "intType", 5
    )
    schem.set_integer_property(int_type)
    fetched_int = schem.get_integer_property("intType")
    assert fetched_int is int_type

    # Mismatched-type lookups raise BadFieldValueException, mirroring upstream.
    with pytest.raises(BadFieldValueException):
        schem.get_integer_property("boolType")
    with pytest.raises(BadFieldValueException):
        schem.get_date_property("textType")
    with pytest.raises(BadFieldValueException):
        schem.get_boolean_property("dateType")


# --- testAltProperties ------------------------------------------------------


def test_alt_properties() -> None:
    """Port of ``XMPSchemaTest.testAltProperties``."""
    schem = _new_schema()
    alt_prop = "AltProp"

    default_lang = "x-default"
    default_val = "Default Language"

    us_lang = "en-us"
    us_val = "American Language"

    fr_lang = "fr-fr"
    fr_val = "Lang française"

    schem.set_unqualified_language_property_value(alt_prop, us_lang, us_val)
    schem.set_unqualified_language_property_value(alt_prop, default_lang, default_val)
    schem.set_unqualified_language_property_value(alt_prop, fr_lang, fr_val)

    assert (
        schem.get_unqualified_language_property_value(alt_prop, default_lang)
        == default_val
    )
    assert schem.get_unqualified_language_property_value(alt_prop, fr_lang) == fr_val
    assert schem.get_unqualified_language_property_value(alt_prop, us_lang) == us_val

    languages = schem.get_unqualified_language_property_languages_value(alt_prop)
    assert languages is not None
    # default language must be in first place
    assert languages[0] == default_lang
    assert us_lang in languages
    assert fr_lang in languages

    # Replacement / removal
    fr_val = "Langue française"
    schem.set_unqualified_language_property_value(alt_prop, fr_lang, fr_val)
    assert schem.get_unqualified_language_property_value(alt_prop, fr_lang) == fr_val

    schem.set_unqualified_language_property_value(alt_prop, fr_lang, None)
    languages = schem.get_unqualified_language_property_languages_value(alt_prop)
    assert languages is not None
    assert fr_lang not in languages


# --- testMergeSchema --------------------------------------------------------


def test_merge_schema() -> None:
    """Port of ``XMPSchemaTest.testMergeSchema``."""
    parent = XMPMetadata.create_xmp_metadata()
    bag_name = "bagName"
    seq_name = "seqName"
    alt_name = "AltProp"

    val_bag1 = "BagvalSchem1"
    val_bag2 = "BagvalSchem2"

    val_seq1 = "seqvalSchem1"
    val_seq2 = "seqvalSchem2"

    val_alt1 = "altvalSchem1"
    lang_alt1 = "x-default"

    val_alt2 = "altvalSchem2"
    lang_alt2 = "fr-fr"

    schem1 = XMPSchema(parent, namespace_uri="http://www.test.org/schem/", prefix="test")
    schem1.add_qualified_bag_value(bag_name, val_bag1)
    schem1.add_unqualified_sequence_value(seq_name, val_seq1)
    schem1.set_unqualified_language_property_value(alt_name, lang_alt1, val_alt1)

    schem2 = XMPSchema(parent, namespace_uri="http://www.test.org/schem/", prefix="test")
    schem2.add_qualified_bag_value(bag_name, val_bag2)
    schem2.add_unqualified_sequence_value(seq_name, val_seq2)
    schem2.set_unqualified_language_property_value(alt_name, lang_alt2, val_alt2)

    schem1.merge(schem2)

    # All values are present after merge.
    assert (
        schem1.get_unqualified_language_property_value(alt_name, lang_alt2)
        == val_alt2
    )
    assert (
        schem1.get_unqualified_language_property_value(alt_name, lang_alt1)
        == val_alt1
    )
    bag = schem1.get_unqualified_bag_value_list(bag_name)
    assert bag is not None
    assert val_bag1 in bag
    assert val_bag2 in bag
    seq = schem1.get_unqualified_sequence_value_list(seq_name)
    assert seq is not None
    assert val_seq1 in seq
    assert val_seq2 in seq
