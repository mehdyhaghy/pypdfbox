from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
    _open_embedded_pdf,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageFitDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument


def test_wave519_resolve_target_without_target_returns_explicit_destination() -> None:
    document = PDDocument()
    try:
        destination = PDPageFitDestination()
        destination.set_page_number(3)
        action = PDActionEmbeddedGoTo()
        action.set_destination(destination)

        result = action.resolve_target(document)

        assert result is not None
        resolved_document, resolved_destination = result
        assert resolved_document is document
        assert isinstance(resolved_destination, PDPageFitDestination)
        assert resolved_destination.get_page_number() == 3
    finally:
        document.close()


def test_wave519_resolve_named_destination_from_legacy_catalog_dests() -> None:
    document = PDDocument()
    try:
        destination = PDPageFitDestination()
        destination.set_page_number(5)
        legacy_dests = COSDictionary()
        legacy_dests.set_item(COSName.get_pdf_name("chapter"), destination.get_cos_object())
        document.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("Dests"),
            legacy_dests,
        )

        action = PDActionEmbeddedGoTo()
        action.set_destination(PDNamedDestination("chapter"))

        result = action.resolve_target(document)

        assert result is not None
        resolved_document, resolved_destination = result
        assert resolved_document is document
        assert isinstance(resolved_destination, PDPageFitDestination)
        assert resolved_destination.get_page_number() == 5
    finally:
        document.close()


def test_wave519_resolve_named_destination_returns_none_for_non_page_destination() -> None:
    document = PDDocument()
    try:
        action = PDActionEmbeddedGoTo()
        action.set_destination(PDNamedDestination("missing"))

        assert action.resolve_target(document) is None
    finally:
        document.close()


def test_wave519_open_embedded_pdf_uses_unicode_embedded_file_fallback(
    monkeypatch,
) -> None:
    loaded = PDDocument()

    class Embedded:
        def to_byte_array(self) -> bytes:
            return b"%PDF from UF"

    raw_spec = COSDictionary()

    class FileSpecLike:
        def get_cos_object(self) -> COSDictionary:
            return raw_spec

    class EmbeddedFiles:
        def get_value(self, name: str) -> FileSpecLike | None:
            return FileSpecLike() if name == "unicode.pdf" else None

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
        lambda self: None,
    )
    monkeypatch.setattr(
        "pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to."
        "PDComplexFileSpecification.get_embedded_file_unicode",
        lambda self: Embedded(),
    )

    class Loader:
        @staticmethod
        def load(data: bytes) -> PDDocument:
            assert data == b"%PDF from UF"
            return loaded

    try:
        assert _open_embedded_pdf(Scope(), "unicode.pdf", Loader) is loaded
    finally:
        loaded.close()


def test_wave519_open_embedded_pdf_soft_fails_when_names_are_absent() -> None:
    class Catalog:
        def get_names(self) -> None:
            return None

    class Scope:
        def get_document_catalog(self) -> Catalog:
            return Catalog()

    assert _open_embedded_pdf(Scope(), "missing.pdf", PDDocument) is None
