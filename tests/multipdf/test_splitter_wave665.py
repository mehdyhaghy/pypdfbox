from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.documentnavigation.destination import PDDestination
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
    PDPageDestination,
)


def test_wave665_process_annotations_tolerates_subtype_lookup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SourceAnnotation:
        def __init__(self) -> None:
            self._dict = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self._dict

    class AnnotationWrapper:
        def __init__(self, cos_dict: COSDictionary) -> None:
            self._dict = cos_dict

        def get_cos_object(self) -> COSDictionary:
            return self._dict

    class ImportedPage:
        def __init__(self) -> None:
            self.annotations: list[Any] = [SourceAnnotation()]
            self.rewritten: list[Any] | None = None

        def get_annotations(self) -> list[Any]:
            return self.annotations

        def set_annotations(self, annotations: list[Any]) -> None:
            self.rewritten = annotations

    def raise_attribute_error(self: COSDictionary, key: COSName) -> str | None:
        raise AttributeError("subtype unavailable")

    monkeypatch.setattr(
        Splitter,
        "_is_signature_widget",
        staticmethod(lambda ann_dict: False),
    )
    monkeypatch.setattr(
        PDAnnotation,
        "create",
        staticmethod(lambda cos_dict: AnnotationWrapper(cos_dict)),
    )
    monkeypatch.setattr(COSDictionary, "get_name", raise_attribute_error)

    imported = ImportedPage()

    Splitter()._process_annotations(object(), imported)  # type: ignore[arg-type]  # noqa: SLF001,E501

    assert imported.rewritten is not None
    assert len(imported.rewritten) == 1


def test_wave665_stage_link_destination_clears_broken_goto_action() -> None:
    class BrokenGoTo(PDActionGoTo):
        def __init__(self) -> None:
            pass

        def get_destination(self) -> PDDestination | str | None:
            raise OSError("broken action destination")

    class Link:
        def __init__(self) -> None:
            self.action: PDActionGoTo | None = BrokenGoTo()

        def get_destination(self) -> None:
            return None

        def get_action(self) -> PDActionGoTo | None:
            return self.action

        def set_action(self, action: PDActionGoTo | None) -> None:
            self.action = action

    link = Link()

    Splitter()._stage_link_destination(link, COSDictionary())  # noqa: SLF001

    assert link.action is None


def test_wave665_stage_link_destination_ignores_factory_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest_array = COSArray()
    dest_array.add(COSDictionary())
    dest_array.add(COSName.get_pdf_name("XYZ"))

    class Link:
        def get_destination(self) -> PDPageDestination:
            return PDPageDestination(dest_array)

    monkeypatch.setattr(
        PDDestination,
        "create",
        staticmethod(lambda base: None),
    )

    splitter = Splitter()

    splitter._stage_link_destination(Link(), COSDictionary())  # type: ignore[arg-type]  # noqa: SLF001,E501

    assert splitter._dest_to_fix == []  # noqa: SLF001


def test_wave665_signature_widget_false_when_name_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_attribute_error(self: COSDictionary, key: COSName) -> str | None:
        raise AttributeError("name table unavailable")

    monkeypatch.setattr(COSDictionary, "get_name", raise_attribute_error)

    assert not Splitter._is_signature_widget(COSDictionary())  # noqa: SLF001
