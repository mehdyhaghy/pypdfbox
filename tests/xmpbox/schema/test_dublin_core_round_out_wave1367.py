"""Branch-coverage round-out (wave 1367) for ``DublinCoreSchema``.

Exercises LangAlt round-trip on title/description/rights, Bag/Seq
cardinality enforcement and remove semantics, and the
typed-property accessors that build :class:`ArrayProperty` /
:class:`LangAlt` instances on demand.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox.dublin_core_schema import DublinCoreSchema
from pypdfbox.xmpbox.type import ArrayProperty, Cardinality, LangAlt
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


@pytest.fixture()
def schema() -> DublinCoreSchema:
    return DublinCoreSchema(XMPMetadata.create_xmp_metadata())


def test_title_lang_alt_round_trip_with_x_default(schema: DublinCoreSchema) -> None:
    schema.set_title("Default Title")
    schema.set_title_lang("fr", "Titre")
    schema.set_title_lang("de", "Titel")
    assert schema.get_title() == "Default Title"
    assert schema.get_title("fr") == "Titre"
    assert schema.get_title("de") == "Titel"
    langs = schema.get_title_languages()
    assert langs is not None
    # x-default must be first per LangAlt reorganisation contract.
    assert langs[0] == "x-default"
    assert set(langs) == {"x-default", "fr", "de"}


def test_title_typed_property_builds_lang_alt(schema: DublinCoreSchema) -> None:
    schema.set_title("English")
    schema.set_title_lang("fr", "Francais")
    la = schema.get_title_property()
    assert isinstance(la, LangAlt)
    assert la.get_property_name() == "title"
    # Container has at least the x-default plus the fr entry.
    children = la.get_all_properties()
    assert len(children) == 2


def test_description_round_trip_via_typed_setter(schema: DublinCoreSchema) -> None:
    la = LangAlt(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        DublinCoreSchema.DESCRIPTION,
    )
    la.set_language_value("x-default", "Default text")
    la.set_language_value("es", "Texto")
    schema.set_description_property(la)
    assert schema.get_description() == "Default text"
    assert schema.get_description("es") == "Texto"


def test_set_creators_property_replaces_seq(schema: DublinCoreSchema) -> None:
    schema.add_creator("Alpha")
    schema.add_creator("Beta")
    array = schema.get_creators_property()
    assert isinstance(array, ArrayProperty)
    # Build a fresh ArrayProperty and feed it back through the typed setter.
    replacement = ArrayProperty(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        DublinCoreSchema.CREATOR,
        Cardinality.Seq,
    )
    from pypdfbox.xmpbox.type import ProperNameType

    replacement.add_property(
        ProperNameType(
            schema.get_metadata(),
            schema.get_namespace(),
            schema.get_prefix(),
            DublinCoreSchema.CREATOR,
            "Replacement",
        )
    )
    schema.set_creators_property(replacement)
    assert schema.get_creators() == ["Replacement"]


def test_subject_bag_add_and_remove(schema: DublinCoreSchema) -> None:
    schema.add_subject("alpha")
    schema.add_subject("beta")
    schema.add_subject("gamma")
    assert schema.get_subjects() == ["alpha", "beta", "gamma"]
    schema.remove_subject("beta")
    assert schema.get_subjects() == ["alpha", "gamma"]
    # Removing absent entry is a no-op.
    schema.remove_subject("does-not-exist")
    assert schema.get_subjects() == ["alpha", "gamma"]


def test_date_seq_iso_round_trip(schema: DublinCoreSchema) -> None:
    when = datetime(2024, 7, 15, 12, 0, 0, tzinfo=UTC)
    schema.add_date(when)
    schema.add_date("2025-01-01T00:00:00Z")
    dates = schema.get_dates()
    assert dates is not None
    assert len(dates) == 2
    assert dates[0] == when


def test_add_date_rejects_unknown_type(schema: DublinCoreSchema) -> None:
    with pytest.raises(TypeError):
        schema.add_date(12345)  # type: ignore[arg-type]


def test_remove_publisher_clears_match(schema: DublinCoreSchema) -> None:
    schema.add_publisher("One")
    schema.add_publisher("Two")
    schema.remove_publisher("One")
    assert schema.get_publishers() == ["Two"]


def test_typed_setter_for_subjects_round_trips(schema: DublinCoreSchema) -> None:
    from pypdfbox.xmpbox.type import TextType

    array = ArrayProperty(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        DublinCoreSchema.SUBJECT,
        Cardinality.Bag,
    )
    for value in ("python", "pdf", "xmp"):
        array.add_property(
            TextType(
                schema.get_metadata(),
                schema.get_namespace(),
                schema.get_prefix(),
                DublinCoreSchema.SUBJECT,
                value,
            )
        )
    schema.set_subjects_property(array)
    assert schema.get_subjects() == ["python", "pdf", "xmp"]


def test_rights_lang_alt_languages_listing(schema: DublinCoreSchema) -> None:
    schema.set_rights("All rights reserved")
    schema.add_rights("fr", "Tous droits reserves")
    langs = schema.get_rights_languages()
    assert langs is not None
    assert "x-default" in langs
    assert "fr" in langs


def test_coverage_typed_setter_accepts_string_text(schema: DublinCoreSchema) -> None:
    from pypdfbox.xmpbox.type import TextType

    text = TextType(
        schema.get_metadata(),
        schema.get_namespace(),
        schema.get_prefix(),
        DublinCoreSchema.COVERAGE,
        "Worldwide",
    )
    schema.set_coverage_property(text)
    assert schema.get_coverage() == "Worldwide"
    cov_prop = schema.get_coverage_property()
    assert cov_prop is not None
    assert cov_prop.get_string_value() == "Worldwide"
