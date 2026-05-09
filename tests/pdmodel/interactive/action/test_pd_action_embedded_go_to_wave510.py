from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
    _open_embedded_pdf,
)
from pypdfbox.pdmodel.interactive.action.pd_target_directory import (
    PDTargetDirectory,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestinationNameTreeNode,
    PDNamedDestination,
    PDPageFitDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from pypdfbox.pdmodel.pd_page import PDPage


def test_wave510_set_destination_rejects_page_object_destinations() -> None:
    document = PDDocument()
    try:
        page = PDPage()
        document.add_page(page)
        destination = PDPageFitDestination()
        destination.set_page(page)
        action = PDActionEmbeddedGoTo()

        with pytest.raises(ValueError, match="must be an integer"):
            action.set_destination(destination)
    finally:
        document.close()


def test_wave510_set_destination_accepts_fresh_page_destination_placeholder() -> None:
    action = PDActionEmbeddedGoTo()
    destination = PDPageFitDestination()

    action.set_destination(destination)

    assert action.get_destination() is not None


def test_wave510_parent_target_without_parent_document_soft_fails() -> None:
    source = PDDocument()
    try:
        target = PDTargetDirectory()
        target.set_relationship("P")
        target.set_target_filename("parent.pdf")
        action = PDActionEmbeddedGoTo()
        action.set_target_directory(target)
        action.set_destination(PDNamedDestination("ParentDest"))

        assert action.resolve_target(source) is None
    finally:
        source.close()


def test_wave510_parent_target_resolves_named_destination_in_parent_document() -> None:
    source = PDDocument()
    parent = PDDocument()
    try:
        names = PDDocumentNameDictionary(catalog=parent.get_document_catalog())
        dests = PDDestinationNameTreeNode()
        destination = PDPageFitDestination()
        destination.set_page_number(0)
        dests.set_value("ParentDest", destination)
        names.set_dests(dests)

        target = PDTargetDirectory()
        target.set_relationship("P")
        target.set_target_filename("parent.pdf")
        action = PDActionEmbeddedGoTo()
        action.set_target_directory(target)
        action.set_destination(PDNamedDestination("ParentDest"))

        result = action.resolve_target(source, parent)

        assert result is not None
        final_doc, final_dest = result
        assert final_doc is parent
        assert isinstance(final_dest, PDPageFitDestination)
        assert final_dest.get_page_number() == 0
    finally:
        source.close()
        parent.close()


def test_wave510_open_embedded_pdf_wraps_raw_cos_file_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded = PDDocument()

    class Embedded:
        def to_byte_array(self) -> bytes:
            return b"%PDF bytes"

    raw_spec = COSDictionary()
    raw_spec.set_item(COSName.get_pdf_name("EF"), COSDictionary())

    class FileSpecLike:
        def get_cos_object(self) -> COSDictionary:
            return raw_spec

    class EmbeddedFiles:
        def get_value(self, name: str) -> FileSpecLike | None:
            return FileSpecLike() if name == "child.pdf" else None

    class Names:
        def get_embedded_files(self) -> EmbeddedFiles:
            return EmbeddedFiles()

    class Catalog:
        def get_names(self) -> Names:
            return Names()

    class Scope:
        def get_document_catalog(self) -> Catalog:
            return Catalog()

    monkeypatch.setattr(
        "pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to."
        "PDComplexFileSpecification.get_embedded_file",
        lambda self: Embedded(),
    )

    class Loader:
        @staticmethod
        def load(data: bytes) -> PDDocument:
            assert data == b"%PDF bytes"
            return loaded

    try:
        assert _open_embedded_pdf(Scope(), "child.pdf", Loader) is loaded
    finally:
        loaded.close()


def test_wave510_open_embedded_pdf_soft_fails_when_stream_read_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_spec = COSDictionary()

    class BrokenEmbedded:
        def to_byte_array(self) -> bytes:
            raise OSError("broken stream")

    class FileSpecLike:
        def get_cos_object(self) -> COSDictionary:
            return raw_spec

    class EmbeddedFiles:
        def get_value(self, name: str) -> FileSpecLike | None:
            return FileSpecLike() if name == "broken.pdf" else None

    class Names:
        def get_embedded_files(self) -> EmbeddedFiles:
            return EmbeddedFiles()

    class Catalog:
        def get_names(self) -> Names:
            return Names()

    class Scope:
        def get_document_catalog(self) -> Catalog:
            return Catalog()

    monkeypatch.setattr(
        "pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to."
        "PDComplexFileSpecification.get_embedded_file",
        lambda self: BrokenEmbedded(),
    )

    assert _open_embedded_pdf(Scope(), "broken.pdf", PDDocument) is None
