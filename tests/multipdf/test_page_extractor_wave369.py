from __future__ import annotations

import pytest

import pypdfbox.pdmodel.pd_document as pd_document_module
from pypdfbox import PDDocument, PDPage
from pypdfbox.multipdf import PageExtractor
from pypdfbox.pdmodel.pd_viewer_preferences import PDViewerPreferences


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n_pages):
        doc.add_page(PDPage())
    return doc


def test_wave369_extract_start_past_document_returns_empty_metadata_copy() -> None:
    src = _make_doc(2)
    info = src.get_document_information()
    info.set_title("wave369 title")
    prefs = PDViewerPreferences()
    prefs.set_hide_menubar(True)
    src.get_document_catalog().set_viewer_preferences(prefs)

    result = PageExtractor(src, 9, 9).extract()

    assert result.get_number_of_pages() == 0
    assert result.get_document_information().get_title() == "wave369 title"
    out_prefs = result.get_document_catalog().get_viewer_preferences()
    assert out_prefs is not None
    assert out_prefs.hide_menubar() is True

    src.close()
    result.close()


class _FailingMetadataSource:
    def get_number_of_pages(self) -> int:
        return 0

    def get_document_information(self) -> object:
        raise RuntimeError("broken info")

    def get_document_catalog(self) -> object:
        raise RuntimeError("broken catalog")


def test_wave369_extract_swallowing_metadata_failures_still_returns_doc() -> None:
    result = PageExtractor(_FailingMetadataSource(), 1, 1).extract()  # type: ignore[arg-type]

    assert result.get_number_of_pages() == 0

    result.close()


class _InfoSource:
    def __init__(self, info: object) -> None:
        self.info = info

    def get_number_of_pages(self) -> int:
        return 0

    def get_document_information(self) -> object:
        return self.info


class _RejectingInfoTarget:
    def __init__(self) -> None:
        self.seen_info: object | None = None

    def set_document_information(self, info: object) -> None:
        self.seen_info = info
        raise RuntimeError("target rejected info")


def test_wave369_copy_document_information_ignores_target_rejection() -> None:
    info = object()
    target = _RejectingInfoTarget()
    extractor = PageExtractor(_InfoSource(info), 1, 1)  # type: ignore[arg-type]

    extractor._copy_document_information(target)  # type: ignore[arg-type]  # noqa: SLF001

    assert target.seen_info is info


def test_wave369_extract_ignores_imported_page_setter_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = _make_doc(1)
    calls: list[str] = []

    class RejectingImportedPage:
        def set_crop_box(self, _value: object) -> None:
            calls.append("crop")
            raise RuntimeError("crop failed")

        def set_media_box(self, _value: object) -> None:
            calls.append("media")
            raise RuntimeError("media failed")

        def set_resources(self, _value: object) -> None:
            calls.append("resources")
            raise RuntimeError("resources failed")

        def set_rotation(self, _value: object) -> None:
            calls.append("rotation")
            raise RuntimeError("rotation failed")

    class TargetCatalog:
        def set_viewer_preferences(self, _prefs: object) -> None:
            pass

    class TargetDocument:
        def __init__(self) -> None:
            self.imported = RejectingImportedPage()

        def set_document_information(self, _info: object) -> None:
            pass

        def get_document_catalog(self) -> TargetCatalog:
            return TargetCatalog()

        def import_page(self, _page: PDPage) -> RejectingImportedPage:
            return self.imported

    monkeypatch.setattr(pd_document_module, "PDDocument", TargetDocument)

    result = PageExtractor(src, 1, 1).extract()

    assert isinstance(result, TargetDocument)
    assert calls == ["crop", "media", "resources", "rotation"]

    src.close()
