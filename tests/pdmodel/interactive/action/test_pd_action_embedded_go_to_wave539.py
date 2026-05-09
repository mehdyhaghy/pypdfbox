from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
    _open_embedded_pdf,
    _resolve_named_destination,
)
from pypdfbox.pdmodel.interactive.action.pd_target_directory import (
    PDTargetDirectory,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument


def test_wave539_resolve_target_closes_opened_child_when_nested_chain_breaks(
    monkeypatch,
) -> None:
    source = PDDocument()
    closed: list[str] = []

    class ChildDocument:
        def close(self) -> None:
            closed.append("child")

    child = ChildDocument()

    def open_child(
        scope: PDDocument,
        name: str,
        pddocument_cls: type[PDDocument],
    ) -> ChildDocument:
        assert scope is source
        assert name == "child.pdf"
        assert pddocument_cls is PDDocument
        return child

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
        assert action.resolve_target(source) is None
        assert closed == ["child"]
    finally:
        source.close()


def test_wave539_open_embedded_pdf_rejects_non_filespec_like_value() -> None:
    class EmbeddedFiles:
        def get_value(self, name: str) -> object:
            assert name == "not-a-spec.pdf"
            return object()

    class Names:
        def get_embedded_files(self) -> EmbeddedFiles:
            return EmbeddedFiles()

    class Catalog:
        def get_names(self) -> Names:
            return Names()

    class Scope:
        def get_document_catalog(self) -> Catalog:
            return Catalog()

    assert _open_embedded_pdf(Scope(), "not-a-spec.pdf", PDDocument) is None  # type: ignore[arg-type]


def test_wave539_resolve_named_destination_uses_names_dests_get_destination() -> None:
    destination = PDPageFitDestination()
    destination.set_page_number(7)

    class FlatDests:
        def get_destination(self, name: str) -> PDPageFitDestination | None:
            return destination if name == "chapter" else None

    class Names:
        def get_cos_object(self) -> COSDictionary:
            return COSDictionary()

        def get_dests(self) -> FlatDests:
            return FlatDests()

    class Catalog:
        def get_names(self) -> Names:
            return Names()

        def get_dests(self) -> None:
            return None

    class Scope:
        def get_document_catalog(self) -> Catalog:
            return Catalog()

    assert _resolve_named_destination(Scope(), "chapter") is destination  # type: ignore[arg-type]


def test_wave539_resolve_named_destination_ignores_non_destination_flat_value() -> None:
    raw_names = COSDictionary()
    raw_names.set_item(COSName.get_pdf_name("Dests"), COSDictionary())

    class FlatDests:
        def get_value(self, name: str) -> Any:
            assert name == "chapter"
            return object()

    class Names:
        def get_cos_object(self) -> COSDictionary:
            return raw_names

        def get_dests(self) -> FlatDests:
            return FlatDests()

    class Catalog:
        def get_names(self) -> Names:
            return Names()

        def get_dests(self) -> None:
            return None

    class Scope:
        def get_document_catalog(self) -> Catalog:
            return Catalog()

    assert _resolve_named_destination(Scope(), "chapter") is None  # type: ignore[arg-type]
