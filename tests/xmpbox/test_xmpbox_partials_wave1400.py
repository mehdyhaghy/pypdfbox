"""Wave 1400 — close residual branch partials across xmpbox.

Each test targets a single uncovered branch flagged by
``pytest --cov=pypdfbox.xmpbox --cov-branch`` after wave 1399. They
all exercise live code paths (no monkeypatching of production
methods unless the input shape needed for the branch is otherwise
unreachable through the public API).

Closed partials:

* ``date_converter.py:1294->1297`` — split-at-tz handler accepts a
  pre-fmt + post-fmt parse but the TZ blob isn't a recognised JVM
  name → ``parse_t_zoffset`` returns ``False`` → handler returns
  ``(cal, len(text))`` without applying a TZ offset.
* ``pdfa_identification_schema.py:84->86`` — ``_read_integer``
  falls through to ``get_unqualified_text_property_value`` because
  ``_properties`` holds a non-string/non-int/non-AbstractSimple
  value, and the fallback lookup returns a string that ``int()``
  can parse.
* ``type/abstract_structured_type.py:112->116`` — ``add_property``
  receives a field whose ``get_property_name()`` returns ``None``
  → skip the duplicate-name dedupe filter; the property is
  appended without filtering.
* ``type/type_mapping.py:381->exit`` — ``add_new_name_space`` is
  called for a namespace already registered in
  ``_schema_factories``: skip the factory-insert branch and exit
  the method.
* ``xmp_metadata.py:186->184`` — ``get_about`` iterates two
  schemas where the first has an empty ``rdf:about`` (falsy value)
  → the loop continues to the second schema.
* ``dublin_core_schema.py:148->151`` — ``_build_lang_alt`` for a
  LangAlt dict that has no ``x-default`` key: the reorder block
  is skipped and we drop straight into the per-language loop.
* ``exif_schema.py:335->338`` — same x-default-missing branch on
  ``get_user_comment_property``.
* ``tiff_schema.py:261->264`` — same x-default-missing branch on
  ``_build_lang_alt``.
* ``type/array_property.py:191->190`` — ``get_elements_as_string``
  skips a child that isn't an ``AbstractSimpleProperty`` (e.g. a
  nested ``ArrayProperty``).
* ``type/lang_alt.py:79->exit`` — ``remove_language`` walks every
  child without finding a matching language attribute → loop
  exits cleanly (no removal).
* ``type/layer_type.py:95-96`` — ``set_layer_text_property`` with
  a non-None ``TextType`` value installs it via ``add_property``
  after stamping the local name.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.date_converter import _make_handler_locale_split_at_tz
from pypdfbox.xmpbox.pdfa_identification_schema import PDFAIdentificationSchema
from pypdfbox.xmpbox.type import (
    AbstractStructuredType,
    TextType,
    TypeMapping,
)
from pypdfbox.xmpbox.xmp_schema import XMPSchema

# ----------------------------------------------------------------------------
# date_converter.py:1294->1297 — split-at-tz handler with unknown TZ blob
# ----------------------------------------------------------------------------


def test_split_at_tz_handler_succeeds_when_tz_blob_unrecognised() -> None:
    """``parse_t_zoffset`` rejects the TZ blob (not numeric, not a known
    name) → the cal is returned without any TZ offset applied (default
    zone) but the parse still 'succeeds' from the caller's perspective:
    ``cal is not None`` and ``consumed == len(text)``.

    Without this case the success-path branch at line 1294 → 1297 (the
    'parse_t_zoffset returned False, fall through to return') was
    unexercised — every test reaching the handler also fed it a
    well-formed JVM tz blob (``GMT+08:00`` etc).
    """
    handler = _make_handler_locale_split_at_tz("EEEE MMM dd HH:mm:ss z yy")
    # "XYZQQ" is not a known TZ name and has no leading digits, so
    # parse_t_zoffset's named-tz fallback rejects it and returns False.
    cal, consumed = handler("Fri Jan 01 00:00:00 XYZQQ 25")
    assert cal is not None
    assert consumed == len("Fri Jan 01 00:00:00 XYZQQ 25")
    # Cal carries the parsed wall clock; TZ stays unset (zone_offset 0).
    assert cal.zone_offset == 0


# ----------------------------------------------------------------------------
# pdfa_identification_schema.py:84->86 — _read_integer fallback path
# ----------------------------------------------------------------------------


def test_pdfa_identification_read_integer_falls_through_unknown_typed() -> None:
    """``_properties`` holds a value that's not an ``AbstractSimpleProperty``,
    ``int``, or ``str`` (here: a plain ``list``), so the typed branches
    skip and we hit ``get_unqualified_text_property_value``. The
    fallback iterates list storage and returns the first string entry
    → ``"3"`` → int parse → ``3``. Exercises the ``text is None`` *false*
    arm of the branch at line 84.
    """
    meta = XMPMetadata.create_xmp_metadata()
    schema = PDFAIdentificationSchema(meta)
    # A list with a single parseable string mirrors how a sloppy parser
    # might land an ``int``-typed slot: ``get_unqualified_text_property_value``
    # surfaces the first list item when it's a string (see XMPSchema
    # lines 243-245).
    schema._properties["part"] = ["3"]
    # The list shape lands us in the ``else`` branch on line 82-83;
    # the text fallback returns "3" → int parse → 3.
    assert schema.get_part() == 3


def test_pdfa_identification_read_integer_returns_none_when_fallback_missing() -> None:
    """Branch sibling: ``text is None`` *true* arm — when the unqualified
    fallback yields nothing the method short-circuits to ``None``.
    Already covered elsewhere but kept as a sanity guard so both arms
    appear in a single module."""
    meta = XMPMetadata.create_xmp_metadata()
    schema = PDFAIdentificationSchema(meta)
    schema._properties["part"] = object()  # neither typed nor text
    assert schema.get_part() is None


# ----------------------------------------------------------------------------
# type/abstract_structured_type.py:112->116 — add_property with no name
# ----------------------------------------------------------------------------


class _StructUnderTest(AbstractStructuredType):
    """Concrete subclass so we can instantiate the abstract base."""


def test_add_property_skips_dedupe_when_field_name_is_none() -> None:
    """``add_property`` only filters by name when the incoming field
    actually carries one. A field with ``property_name == None`` skips
    the list-comprehension dedupe (line 112 false branch) and is
    appended directly. Real-world trigger: pre-flight parsing
    constructs an attribute-only ``TextType`` with no local name
    before the surrounding namespace assigns one.
    """
    meta = XMPMetadata.create_xmp_metadata()
    struct = _StructUnderTest(
        meta, "http://www.apache.org/ns/", "ap", "pn"
    )
    # Seed a named property so the structure is non-empty.
    named = TextType(meta, "http://www.apache.org/ns/", "ap", "named", "v1")
    struct.add_property(named)
    assert len(struct.get_all_properties()) == 1

    # Append an *un*-named field; the dedupe filter must NOT run.
    unnamed = TextType(
        meta, "http://www.apache.org/ns/", "ap", "named", "v2"
    )
    unnamed.set_property_name(None)  # exercise the branch
    struct.add_property(unnamed)
    # Both fields survive — the dedupe didn't fire because incoming
    # name was None.
    props = struct.get_all_properties()
    assert len(props) == 2
    assert named in props
    assert unnamed in props


# ----------------------------------------------------------------------------
# type/type_mapping.py:381->exit — add_new_name_space for known namespace
# ----------------------------------------------------------------------------


def test_add_new_name_space_no_op_when_factory_already_present() -> None:
    """Calling ``add_new_name_space`` for a namespace that's already in
    ``_schema_factories`` updates ``_defined_namespaces`` (line 380)
    but the factory-insert branch (lines 382-384) is skipped → branch
    381 exits the method directly.
    """
    meta = XMPMetadata.create_xmp_metadata()
    tm = TypeMapping(meta)
    ns = "http://example.invalid/custom#"
    tm.add_new_name_space(ns, "ex")
    # Snapshot the factory so we can prove the second call doesn't
    # replace it.
    first_factory = tm._schema_factories[ns]
    # Second call with the same namespace must short-circuit.
    tm.add_new_name_space(ns, "ex2")
    # Prefix update did land:
    assert tm._defined_namespaces[ns] == "ex2"
    # Factory identity is preserved (skip-branch reached):
    assert tm._schema_factories[ns] is first_factory


# ----------------------------------------------------------------------------
# xmp_metadata.py:186->184 — get_about continues past empty-about schemas
# ----------------------------------------------------------------------------


def test_get_about_continues_past_schemas_with_empty_about() -> None:
    """``get_about`` returns the first schema's ``rdf:about`` value that
    is truthy. When the first schema has no ``about`` set (empty
    string), the loop falls through to the next schema — the
    ``if value:`` branch goes false → continue → eventually we
    return the populated second schema's value.
    """
    meta = XMPMetadata.create_xmp_metadata()
    s1 = XMPSchema(meta, "http://example.invalid/s1#", "s1")
    s2 = XMPSchema(meta, "http://example.invalid/s2#", "s2")
    s2.set_about("https://example.invalid/about")
    meta.add_schema(s1)
    meta.add_schema(s2)
    # s1 has empty about → branch 186 false → loop continues → s2 hits.
    assert meta.get_about() == "https://example.invalid/about"


def test_get_about_returns_none_when_no_schema_has_about() -> None:
    """Sibling: every schema has an empty ``about`` → both arms of the
    branch are exercised in this module, and the method returns None.
    """
    meta = XMPMetadata.create_xmp_metadata()
    meta.add_schema(XMPSchema(meta, "http://example.invalid/a#", "a"))
    meta.add_schema(XMPSchema(meta, "http://example.invalid/b#", "b"))
    assert meta.get_about() is None


@pytest.mark.parametrize(
    "first_about,expected",
    [("https://first/", "https://first/"), ("", "https://second/")],
)
def test_get_about_priority_first_non_empty_wins(
    first_about: str, expected: str
) -> None:
    """Parametric pair: when the first schema's about is non-empty the
    branch returns immediately (186 true); when empty it skips to the
    next (186 false). Exercises both branch arms in one parametric
    test."""
    meta = XMPMetadata.create_xmp_metadata()
    s1 = XMPSchema(meta, "http://example.invalid/x#", "x")
    s2 = XMPSchema(meta, "http://example.invalid/y#", "y")
    if first_about:
        s1.set_about(first_about)
    s2.set_about("https://second/")
    meta.add_schema(s1)
    meta.add_schema(s2)
    assert meta.get_about() == expected


# ----------------------------------------------------------------------------
# dublin_core_schema.py:148->151, exif_schema.py:335->338, tiff_schema.py:261->264
# — LangAlt build with no x-default key
# ----------------------------------------------------------------------------


def test_dublin_core_build_lang_alt_without_x_default() -> None:
    """``_build_lang_alt`` consumes a dict whose keys do NOT include
    ``x-default`` — the reorder block (148-150) is skipped and the
    loop proceeds with the original key ordering.
    """
    from pypdfbox.xmpbox.dublin_core_schema import DublinCoreSchema

    meta = XMPMetadata.create_xmp_metadata()
    schema = DublinCoreSchema(meta)
    # Stuff a dict with explicit language keys but no x-default.
    schema._properties["title"] = {"en-US": "Hello", "fr-FR": "Bonjour"}
    la = schema.get_title_property()
    assert la is not None
    langs = sorted(la.get_languages())
    assert langs == ["en-US", "fr-FR"]


def test_exif_user_comment_lang_alt_without_x_default() -> None:
    """Same x-default-missing reorder skip on
    ``ExifSchema.get_user_comment_property``.
    """
    from pypdfbox.xmpbox.exif_schema import ExifSchema

    meta = XMPMetadata.create_xmp_metadata()
    schema = ExifSchema(meta)
    schema._properties[ExifSchema.USER_COMMENT] = {
        "de-DE": "Kommentar",
        "ja-JP": "コメント",
    }
    la = schema.get_user_comment_property()
    assert la is not None
    assert sorted(la.get_languages()) == ["de-DE", "ja-JP"]


def test_tiff_build_lang_alt_without_x_default() -> None:
    """Same x-default-missing reorder skip on TiffSchema's
    ``_build_lang_alt`` — uses the ``Copyright`` LangAlt slot.
    """
    from pypdfbox.xmpbox.tiff_schema import TiffSchema

    meta = XMPMetadata.create_xmp_metadata()
    schema = TiffSchema(meta)
    schema._properties[TiffSchema.COPYRIGHT] = {
        "en-GB": "(c) Author",
        "it-IT": "(c) Autore",
    }
    la = schema.get_copyright_property()
    assert la is not None
    langs = sorted(la.get_languages())
    assert langs == ["en-GB", "it-IT"]


# ----------------------------------------------------------------------------
# type/array_property.py:191->190 — child that isn't AbstractSimpleProperty
# ----------------------------------------------------------------------------


def test_array_property_get_elements_as_string_skips_non_simple_children() -> None:
    """``get_elements_as_string`` walks children but only the
    ``AbstractSimpleProperty`` ones contribute. Adding a nested
    ``ArrayProperty`` exercises the ``isinstance`` branch's false arm
    (191->190 continue).
    """
    from pypdfbox.xmpbox.type import ArrayProperty, Cardinality

    meta = XMPMetadata.create_xmp_metadata()
    arr = ArrayProperty(
        meta,
        "http://example.invalid/a#",
        "ex",
        "items",
        Cardinality.Bag,
    )
    # Add one simple child.
    txt = TextType(meta, "http://example.invalid/a#", "ex", "rdf:li", "alpha")
    arr.add_property(txt)
    # Add a complex (non-simple) child: a nested ArrayProperty.
    nested = ArrayProperty(
        meta,
        "http://example.invalid/a#",
        "ex",
        "rdf:li",
        Cardinality.Seq,
    )
    arr.add_property(nested)
    # Only the simple one shows up in the string serialisation —
    # the nested array is silently skipped (branch 191->190 closed).
    assert arr.get_elements_as_string() == ["alpha"]


# ----------------------------------------------------------------------------
# type/lang_alt.py:79->exit — remove_language with no matching lang
# ----------------------------------------------------------------------------


def test_lang_alt_remove_language_no_match_exits_cleanly() -> None:
    """``remove_language`` walks every child looking for a matching
    language attribute. When none match the loop exits without
    removing anything (branch 79->exit closed).
    """
    from pypdfbox.xmpbox.type.lang_alt import X_DEFAULT, LangAlt

    meta = XMPMetadata.create_xmp_metadata()
    la = LangAlt(meta, "http://example.invalid/", "ex", "title")
    # Seed two languages via the public setter — neither is "zh-CN".
    la.set_language_value("en-US", "Hello")
    la.set_language_value("fr-FR", "Bonjour")
    before = sorted(la.get_languages())
    # Request removal of a language that isn't present — no-op.
    la.remove_language("zh-CN")
    after = sorted(la.get_languages())
    assert before == after
    # Sanity: x-default isn't in the set; passing None aliases to
    # x-default, also a miss → still a no-op.
    assert X_DEFAULT not in before
    la.remove_language(None)
    assert sorted(la.get_languages()) == before


# ----------------------------------------------------------------------------
# type/layer_type.py:95-96 — set_layer_text_property with non-None value
# ----------------------------------------------------------------------------


def test_layer_type_set_layer_text_property_installs_value() -> None:
    """``set_layer_text_property(value)`` with a real ``TextType`` stamps
    the local name and installs the field via ``add_property``. Lines
    95-96 had no test that passed a non-None value (the no-arg /
    None-clear path was covered by existing wave 1170-era tests).
    """
    from pypdfbox.xmpbox.type import LayerType

    meta = XMPMetadata.create_xmp_metadata()
    layer = LayerType(meta)
    txt = TextType(
        meta,
        LayerType.NAMESPACE,
        LayerType.PREFERRED_PREFIX,
        "tmp",
        "captured layer",
    )
    layer.set_layer_text_property(txt)
    # The property is now retrievable through the typed accessor.
    fetched = layer.get_layer_text_property()
    assert fetched is txt
    # Local name was stamped by the setter (95).
    assert txt.get_property_name() == LayerType.LAYER_TEXT
