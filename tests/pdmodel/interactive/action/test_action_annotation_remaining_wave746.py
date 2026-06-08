from __future__ import annotations

import logging
from typing import Any

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.interactive.action import PDAction
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
    _open_embedded_pdf,
    _resolve_named_destination,
)
from pypdfbox.pdmodel.interactive.action.pd_action_sound import PDActionSound
from pypdfbox.pdmodel.interactive.action.pd_action_transition import (
    PDActionTransition,
)
from pypdfbox.pdmodel.interactive.action.pd_target_directory import (
    PDTargetDirectory,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageFitDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument


def _action_dict(subtype: str) -> COSDictionary:
    action = COSDictionary()
    action.set_name(COSName.get_pdf_name("S"), subtype)
    return action


def test_wave746_action_create_handles_none_type_errors_and_remaining_dispatches() -> None:
    assert PDAction.create(None) is None

    with pytest.raises(TypeError, match="expects COSDictionary"):
        PDAction.create(COSString("not-a-dict"))  # type: ignore[arg-type]

    assert isinstance(PDAction.create(_action_dict("Sound")), PDActionSound)
    assert isinstance(PDAction.create(_action_dict("Trans")), PDActionTransition)
    assert isinstance(PDAction.create(_action_dict("GoToE")), PDActionEmbeddedGoTo)


def test_wave746_action_get_next_ignores_invalid_next_shape() -> None:
    action = PDAction()
    action.get_cos_object().set_item(COSName.get_pdf_name("Next"), COSString("bad"))

    assert action.get_next() is None


def test_wave746_embedded_goto_resolve_target_logs_close_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = PDDocument()

    class ChildDocument:
        def close(self) -> None:
            raise RuntimeError("close failed")

    def open_child(
        scope: PDDocument,
        name: str,
        pddocument_cls: type[PDDocument],
    ) -> ChildDocument:
        assert scope is source
        assert name == "child.pdf"
        assert pddocument_cls is PDDocument
        return ChildDocument()

    root = PDTargetDirectory()
    root.set_relationship("C")
    root.set_target_filename("child.pdf")
    root.set_target(PDTargetDirectory())

    action = PDActionEmbeddedGoTo()
    action.set_target_directory(root)

    monkeypatch.setattr(
        "pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to."
        "_open_embedded_pdf",
        open_child,
    )

    try:
        with caplog.at_level(
            logging.DEBUG,
            logger="pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to",
        ):
            assert action.resolve_target(source) is None
        assert "Failed to close embedded PDDocument" in caplog.text
    finally:
        source.close()


def test_wave746_embedded_goto_final_destination_absent_and_empty_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action = PDActionEmbeddedGoTo()

    assert action._resolve_final_destination(PDDocument()) is None  # noqa: SLF001

    empty_named = PDNamedDestination()
    monkeypatch.setattr(action, "get_d", lambda: empty_named)
    scope = PDDocument()
    try:
        assert action._resolve_final_destination(scope) is None  # noqa: SLF001
    finally:
        scope.close()


def test_wave746_open_embedded_pdf_rejects_filespec_without_embedded_stream() -> None:
    file_spec = PDComplexFileSpecification()

    class EmbeddedFiles:
        def get_value(self, name: str) -> PDComplexFileSpecification | None:
            return file_spec if name == "empty.pdf" else None

    class Names:
        def get_embedded_files(self) -> EmbeddedFiles:
            return EmbeddedFiles()

    class Catalog:
        def get_names(self) -> Names:
            return Names()

    class Scope:
        def get_document_catalog(self) -> Catalog:
            return Catalog()

    assert _open_embedded_pdf(Scope(), "empty.pdf", PDDocument) is None  # type: ignore[arg-type]


def test_wave746_resolve_named_destination_uses_legacy_catalog_dests() -> None:
    # Wave 1515: get_dests now returns a PDDocumentNameDestinationDictionary
    # whose lookup method is get_destination (matching the upstream type).
    destination = PDPageFitDestination()
    destination.set_page_number(2)

    class LegacyDests:
        def get_destination(self, name: str) -> PDPageFitDestination | None:
            return destination if name == "legacy" else None

    class Catalog:
        def get_names(self) -> None:
            return None

        def get_dests(self) -> LegacyDests:
            return LegacyDests()

    class Scope:
        def get_document_catalog(self) -> Catalog:
            return Catalog()

    assert _resolve_named_destination(Scope(), "legacy") is destination  # type: ignore[arg-type]


def test_wave746_resolve_named_destination_falls_back_from_non_destination_legacy_value() -> None:
    # Wave 1515: legacy get_dests().get_destination returns a non-destination,
    # so the isinstance arm is False and resolution returns None.
    class LegacyDests:
        def get_destination(self, name: str) -> Any:
            assert name == "missing"
            return object()

    class Catalog:
        def get_names(self) -> None:
            return None

        def get_dests(self) -> LegacyDests:
            return LegacyDests()

    class Scope:
        def get_document_catalog(self) -> Catalog:
            return Catalog()

    assert _resolve_named_destination(Scope(), "missing") is None  # type: ignore[arg-type]
