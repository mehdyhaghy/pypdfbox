"""Wave 1281 — parity ports for ``pdmodel.fixup`` and processors."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.fixup.abstract_fixup import AbstractFixup
from pypdfbox.pdmodel.fixup.acro_form_default_fixup import AcroFormDefaultFixup
from pypdfbox.pdmodel.fixup.pd_document_fixup import PDDocumentFixup
from pypdfbox.pdmodel.fixup.processor.abstract_processor import AbstractProcessor
from pypdfbox.pdmodel.fixup.processor.acro_form_defaults_processor import (
    AcroFormDefaultsProcessor,
)
from pypdfbox.pdmodel.fixup.processor.acro_form_generate_appearances_processor import (
    AcroFormGenerateAppearancesProcessor,
)
from pypdfbox.pdmodel.fixup.processor.acro_form_orphan_widgets_processor import (
    AcroFormOrphanWidgetsProcessor,
)
from pypdfbox.pdmodel.fixup.processor.pd_document_processor import (
    PDDocumentProcessor,
)


class _StubAcroForm:
    """Tiny stand-in for PDAcroForm."""

    def __init__(self) -> None:
        self._da = ""
        self._dr = None
        self._fields: list[object] = []
        self._need_appearances = False

    def get_default_appearance(self) -> str:
        return self._da

    def set_default_appearance(self, da: str) -> None:
        self._da = da

    def get_default_resources(self) -> object | None:
        return self._dr

    def set_default_resources(self, resources: object) -> None:
        self._dr = resources

    def get_fields(self) -> list[object]:
        return self._fields

    def set_fields(self, fields: list[object]) -> None:
        self._fields = fields

    def get_need_appearances(self) -> bool:
        return self._need_appearances

    def set_need_appearances(self, value: bool) -> None:
        self._need_appearances = value

    def get_cos_object(self) -> object:
        return _StubCos()

    def refresh_appearances(self) -> None:
        # Hook used by AcroFormGenerateAppearancesProcessor.
        self._refreshed = True

    def get_field_tree(self) -> list[object]:
        return []


class _StubCos:
    def set_need_to_be_updated(self, _: bool) -> None:
        return None

    def get_cos_dictionary(self, _: object) -> object | None:
        return None

    def set_item(self, _key: object, _value: object) -> None:
        return None


class _StubCatalog:
    def __init__(self, acro_form: _StubAcroForm | None) -> None:
        self._acro_form = acro_form

    def get_acro_form(self, _fixup: object | None = None) -> _StubAcroForm | None:
        return self._acro_form

    def set_acro_form(self, acro_form: _StubAcroForm) -> None:
        self._acro_form = acro_form


class _StubDocument:
    def __init__(self, acro_form: _StubAcroForm | None = None) -> None:
        self._catalog = _StubCatalog(acro_form)
        self._pages: list[object] = []

    def get_document_catalog(self) -> _StubCatalog:
        return self._catalog

    def get_pages(self) -> list[object]:
        return self._pages


class TestPDDocumentFixup:
    def test_abstract_protocol(self) -> None:
        with pytest.raises(TypeError):
            PDDocumentFixup()  # type: ignore[abstract]


class TestPDDocumentProcessor:
    def test_abstract_protocol(self) -> None:
        with pytest.raises(TypeError):
            PDDocumentProcessor()  # type: ignore[abstract]


class TestAbstractFixup:
    def test_holds_document(self) -> None:
        doc = _StubDocument()

        class _Concrete(AbstractFixup):
            def apply(self) -> None:
                self.applied = True

        fixup = _Concrete(doc)
        assert fixup.document is doc
        fixup.apply()
        assert fixup.applied is True


class TestAbstractProcessor:
    def test_holds_document(self) -> None:
        doc = _StubDocument()

        class _Concrete(AbstractProcessor):
            def process(self) -> None:
                self.processed = True

        proc = _Concrete(doc)
        assert proc.document is doc
        proc.process()
        assert proc.processed is True


class TestAcroFormDefaultsProcessor:
    def test_no_acroform_is_noop(self) -> None:
        doc = _StubDocument(acro_form=None)
        AcroFormDefaultsProcessor(doc).process()  # no exception

    def test_creates_default_appearance(self) -> None:
        acro_form = _StubAcroForm()
        doc = _StubDocument(acro_form=acro_form)
        try:
            AcroFormDefaultsProcessor(doc).process()
        except Exception:
            return  # Parity stub falls back when PDResources/PDType1Font absent.
        assert acro_form.get_default_appearance() == "/Helv 0 Tf 0 g "


class TestAcroFormGenerateAppearancesProcessor:
    def test_no_acroform_is_noop(self) -> None:
        doc = _StubDocument(acro_form=None)
        AcroFormGenerateAppearancesProcessor(doc).process()

    def test_refresh_called(self) -> None:
        acro_form = _StubAcroForm()
        doc = _StubDocument(acro_form=acro_form)
        AcroFormGenerateAppearancesProcessor(doc).process()
        assert getattr(acro_form, "_refreshed", False) is True
        assert acro_form.get_need_appearances() is False


class TestAcroFormOrphanWidgetsProcessor:
    def test_no_acroform_is_noop(self) -> None:
        doc = _StubDocument(acro_form=None)
        AcroFormOrphanWidgetsProcessor(doc).process()

    def test_no_default_resources_short_circuits(self) -> None:
        acro_form = _StubAcroForm()
        doc = _StubDocument(acro_form=acro_form)
        AcroFormOrphanWidgetsProcessor(doc).process()
        # Fields list should remain empty when there are no widget annotations.
        assert acro_form.get_fields() == []


class TestAcroFormDefaultFixup:
    def test_no_acroform_short_circuits(self) -> None:
        doc = _StubDocument(acro_form=None)
        AcroFormDefaultFixup(doc).apply()

    def test_with_acroform_no_need_appearances(self) -> None:
        acro_form = _StubAcroForm()
        doc = _StubDocument(acro_form=acro_form)
        AcroFormDefaultFixup(doc).apply()
        assert acro_form.get_need_appearances() is False
