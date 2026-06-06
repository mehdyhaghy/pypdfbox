from __future__ import annotations

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.multipdf import PageExtractor
from pypdfbox.pdmodel.pd_viewer_preferences import PDViewerPreferences


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n_pages):
        doc.add_page(PDPage())
    return doc


def test_wave369_extract_start_past_document_raises_like_upstream() -> None:
    """A range entirely past the document (``start=9, end=9`` on a 2-page
    source) raises, mirroring upstream.

    The raw-span guard ``end - start + 1 = 1 > 0`` passes, so upstream
    builds a ``Splitter`` with ``setStartPage(max(9, 1) = 9)`` and
    ``setEndPage(min(9, 2) = 2)``. ``Splitter.setEndPage`` rejects
    ``end < startPage`` with ``IllegalArgumentException`` — the Python
    port raises the analogous ``ValueError``. Wave 369 originally pinned
    the bespoke page-walk's lenient "return empty doc with metadata
    copied" behaviour; wave 1505 retargets it to the upstream contract
    now that ``extract`` delegates to the ported ``Splitter`` (verified
    against PDFBox 3.0.7: ``IllegalArgumentException: End page is smaller
    than startPage``)."""
    src = _make_doc(2)
    info = src.get_document_information()
    info.set_title("wave369 title")
    prefs = PDViewerPreferences()
    prefs.set_hide_menubar(True)
    src.get_document_catalog().set_viewer_preferences(prefs)

    with pytest.raises(ValueError, match="End page is smaller than startPage"):
        PageExtractor(src, 9, 9).extract()

    src.close()


def test_wave369_extract_zero_page_source_raises_like_upstream() -> None:
    """Extracting ``[1..1]`` from a zero-page document raises, mirroring
    upstream.

    The raw-span guard ``1 - 1 + 1 = 1 > 0`` passes; upstream then calls
    ``setEndPage(min(1, 0) = 0)`` which ``Splitter.setEndPage`` rejects
    (``IllegalArgumentException: End page is smaller than one``). The port
    raises the analogous ``ValueError``. Wave 369 originally pinned the
    bespoke walk's lenient empty-doc return; retargeted in wave 1505 to
    the upstream contract."""
    empty = _make_doc(0)
    with pytest.raises(ValueError, match="End page is smaller than one"):
        PageExtractor(empty, 1, 1).extract()
    empty.close()


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


def test_wave369_extract_delegates_to_splitter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``extract`` delegates to a single ``Splitter.split`` covering the
    clamped window and returns its first part.

    Wave 369 originally pinned the bespoke page-walk's per-page setter
    re-application (``set_crop_box`` / ``set_media_box`` / ``set_resources``
    / ``set_rotation`` in that order) via a monkeypatched ``PDDocument``.
    That walk was removed in wave 1505 when ``extract`` was switched to
    delegate to the ported ``Splitter`` (upstream parity). This test now
    pins the delegation contract: the configured ``Splitter`` is driven
    with ``set_start_page(max(start, 1))`` /
    ``set_end_page(min(end, N))`` / ``set_split_at_page(end - start + 1)``
    and ``extract`` returns ``split()[0]``."""
    import pypdfbox.multipdf.splitter as splitter_module

    src = _make_doc(5)
    recorded: dict[str, object] = {}
    real_split = splitter_module.Splitter.split

    def spy_split(self: object, document: object) -> list[object]:
        recorded["start"] = self.get_start_page()  # type: ignore[attr-defined]
        recorded["end"] = self.get_end_page()  # type: ignore[attr-defined]
        recorded["split_at"] = self.get_split_at_page()  # type: ignore[attr-defined]
        recorded["document"] = document
        return real_split(self, document)  # type: ignore[arg-type]

    monkeypatch.setattr(splitter_module.Splitter, "split", spy_split)

    result = PageExtractor(src, 2, 4).extract()

    assert recorded["document"] is src
    assert recorded["start"] == 2
    assert recorded["end"] == 4
    assert recorded["split_at"] == 3  # 4 - 2 + 1
    assert result.get_number_of_pages() == 3

    src.close()
    result.close()
