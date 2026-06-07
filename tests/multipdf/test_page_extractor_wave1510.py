"""Wave 1510 coverage round-out for the retained ``PageExtractor`` copy shims.

``PageExtractor._copy_document_information`` / ``_copy_viewer_preferences`` are
pypdfbox-specific best-effort compatibility shims (upstream
``PageExtractor.extract`` performs the ``setDocumentInformation`` /
``setViewerPreferences`` copy inline; pypdfbox factored the copy into these two
no-longer-internally-called helpers — see the class docstring). The defensive
``except`` branches that swallow source-side fetch failures and the
``prefs is None`` short-circuit were the only uncovered spans after wave 1505
delegated ``extract`` to ``Splitter``. These tests drive each remaining branch.
"""

from __future__ import annotations

from types import SimpleNamespace

from pypdfbox import PDDocument
from pypdfbox.multipdf import PageExtractor


def _extractor() -> PageExtractor:
    # ``end_page=0`` keeps the constructor from calling ``get_number_of_pages``
    # on the stub; ``_source_document`` is reassigned per branch below.
    return PageExtractor(SimpleNamespace(get_number_of_pages=lambda: 0), 1, 0)


def _raise(exc: Exception):
    def _thrower(*_args: object, **_kwargs: object):
        raise exc

    return _thrower


def test_copy_document_information_swallows_source_fetch_failure() -> None:
    """A source whose ``get_document_information`` itself raises is tolerated
    (the helper logs at debug and returns without touching the target)."""
    extractor = _extractor()
    extractor._source_document = SimpleNamespace(  # noqa: SLF001
        get_document_information=_raise(RuntimeError("source info exploded")),
    )
    target = PDDocument()
    try:
        # Must not propagate; an extracted doc without /Info is still well-formed.
        extractor._copy_document_information(target)  # noqa: SLF001
    finally:
        target.close()


def test_copy_viewer_preferences_swallows_catalog_fetch_failure() -> None:
    """A source whose ``get_document_catalog`` raises is tolerated — the helper
    returns before ever touching the target catalog."""
    extractor = _extractor()
    extractor._source_document = SimpleNamespace(  # noqa: SLF001
        get_document_catalog=_raise(RuntimeError("source catalog exploded")),
    )
    target = PDDocument()
    try:
        extractor._copy_viewer_preferences(target)  # noqa: SLF001
    finally:
        target.close()


def test_copy_viewer_preferences_no_op_when_source_prefs_absent() -> None:
    """When the source catalog has no ``/ViewerPreferences`` (returns ``None``)
    the helper short-circuits and never calls the target's setter."""
    set_calls: list[object] = []
    source_catalog = SimpleNamespace(get_viewer_preferences=lambda: None)
    target_catalog = SimpleNamespace(
        set_viewer_preferences=lambda prefs: set_calls.append(prefs)
    )
    extractor = _extractor()
    extractor._source_document = SimpleNamespace(  # noqa: SLF001
        get_document_catalog=lambda: source_catalog,
    )
    target = SimpleNamespace(get_document_catalog=lambda: target_catalog)

    extractor._copy_viewer_preferences(target)  # type: ignore[arg-type]  # noqa: SLF001

    assert set_calls == []
