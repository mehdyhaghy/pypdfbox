from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.graphics.color import PDOutputIntent
from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead
from pypdfbox.pdmodel.pd_page import _unwrap_page_dict


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave626_catalog_requirements_needs_rendering_and_base_uri_lifecycle() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        requirement = COSDictionary()

        assert catalog.has_requirements() is False
        catalog.add_requirement(requirement)

        assert catalog.get_requirements() == [requirement]
        assert catalog.has_requirements() is True

        with pytest.raises(TypeError, match="add_requirement expected COSDictionary"):
            catalog.add_requirement(object())  # type: ignore[arg-type]

        catalog.set_base_uri("https://example.test/root/")
        catalog.set_needs_rendering(True)

        assert catalog.get_base_uri() == "https://example.test/root/"
        assert catalog.has_base_uri() is True
        assert catalog.is_needs_rendering() is True
        assert catalog.has_needs_rendering() is True

        catalog.clear_base_uri()
        catalog.clear_requirements()
        catalog.clear_needs_rendering()

        assert catalog.get_base_uri() is None
        assert catalog.has_base_uri() is False
        assert catalog.has_uri() is False
        assert catalog.get_requirements() == []
        assert catalog.is_needs_rendering() is False
        assert catalog.has_needs_rendering() is False


def test_wave626_catalog_output_intents_threads_and_open_action_shape_predicates() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        intent = PDOutputIntent()
        malformed = COSArray([COSInteger.get(1)])
        catalog.get_cos_object().set_item(_name("OutputIntents"), malformed)

        assert catalog.get_output_intents() == []
        assert catalog.has_output_intents() is False

        catalog.set_output_intents([intent])

        assert catalog.get_output_intents()[0].get_cos_object() is intent.get_cos_object()
        assert catalog.has_output_intents() is True

        with pytest.raises(TypeError, match="set_output_intents entries"):
            catalog.set_output_intents([COSDictionary()])  # type: ignore[list-item]

        assert catalog.has_threads() is False
        assert catalog.get_threads() == []
        assert catalog.has_threads() is False

        with pytest.raises(TypeError, match="set_threads entries"):
            catalog.set_threads([COSDictionary()])  # type: ignore[list-item]

        catalog.set_open_action(COSArray())
        assert catalog.has_open_action() is True
        catalog.clear_open_action()
        assert catalog.has_open_action() is False


def test_wave626_page_user_unit_tab_order_contents_validation_and_unwrap() -> None:
    page = PDPage()
    stream = COSStream()
    wrapper = type("StreamWrapper", (), {"get_cos_object": lambda self: stream})()

    page.set_user_unit(2.5)
    assert page.get_user_unit() == 2.5
    page.get_cos_object().set_item(_name("UserUnit"), COSFloat(-1.0))
    assert page.get_user_unit() == 1.0

    with pytest.raises(ValueError, match="user_unit must be positive"):
        page.set_user_unit(0)

    page.set_tab_order(PDPage.TAB_ORDER_STRUCTURE)
    assert page.get_tab_order() == "S"
    assert page.has_tab_order() is True

    page.set_contents([wrapper])
    stored = page.get_cos_object().get_dictionary_object(_name("Contents"))
    assert isinstance(stored, COSArray)
    assert stored.get_object(0) is stream

    with pytest.raises(TypeError, match="COSStream-like"):
        page.set_contents([object()])  # type: ignore[list-item]
    with pytest.raises(TypeError, match="expected None, COSStream, COSArray"):
        page.set_contents(object())  # type: ignore[arg-type]

    assert _unwrap_page_dict(page) is page.get_cos_object()
    assert _unwrap_page_dict(page.get_cos_object()) is page.get_cos_object()
    with pytest.raises(TypeError, match="expected PDPage"):
        _unwrap_page_dict(object())  # type: ignore[arg-type]


def test_wave626_page_thread_beads_group_and_viewport_presence_are_shape_aware() -> None:
    page = PDPage()
    bead = PDThreadBead()
    page.get_cos_object().set_item(_name("B"), COSArray([COSInteger.get(7)]))

    assert page.has_thread_beads() is True
    assert page.get_thread_beads() == [None]

    page.set_thread_beads([bead])
    assert page.get_thread_beads()[0].get_cos_object() is bead.get_cos_object()

    with pytest.raises(TypeError, match="set_thread_beads entries"):
        page.set_thread_beads([COSDictionary()])  # type: ignore[list-item]

    page.get_cos_object().set_item(_name("Group"), COSInteger.get(1))
    assert page.has_group() is True
    assert page.get_group() is None

    with pytest.raises(TypeError, match="set_group expected COSDictionary"):
        page.set_group(COSInteger.get(1))

    page.get_cos_object().set_item(_name("VP"), COSArray([COSInteger.get(1)]))
    assert page.has_viewports() is True
    assert page.get_viewports() == []
