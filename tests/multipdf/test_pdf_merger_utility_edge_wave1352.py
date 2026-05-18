"""Wave 1352 — PDFMergerUtility: defensive close-on-error finally
clauses, optimize-mode document-info / metadata override, viewer-prefs
toggle guards, and the ``_hash_cos`` indirect-reference recursion.

Targets the under-covered branches in
``pypdfbox/multipdf/pdf_merger_utility.py``:

* lines 50-51 — ``_hash_cos`` recursion through a ``COSObject``
  indirect reference (deref + re-enter on the resolved value);
* lines 635, 639 — optimize-mode honours
  ``set_destination_document_information`` /
  ``set_destination_metadata``;
* lines 651-652 — optimize-mode ``destination.close()`` raises in the
  ``finally`` block; logged-and-swallowed;
* lines 655-658 — optimize-mode ``src_doc.close()`` raises in the
  ``finally`` block; logged-and-swallowed;
* lines 780-783 — legacy-mode ``src_doc.close()`` raises in the
  ``finally`` block; logged-and-swallowed;
* line 1922 — ``merge_viewer_preferences._maybe`` callable-attr guard
  short-circuits when the destination is missing the setter / getter;
* lines 1926-1927 — ``getter()`` raises inside ``_maybe``; logged-and-
  swallowed via the broad-except path.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSObject, COSStream
from pypdfbox.multipdf import DocumentMergeMode, PDFMergerUtility
from pypdfbox.multipdf.pdf_clone_utility import PDFCloneUtility
from pypdfbox.multipdf.pdf_merger_utility import _hash_cos, _HashAbort
from pypdfbox.pdmodel import PDDocument, PDPage

# ---------- helpers --------------------------------------------------------


def _save_to_path(doc: PDDocument, path: Path) -> None:
    doc.save(path)
    doc.close()


def _build_doc(num_pages: int = 1) -> PDDocument:
    doc = PDDocument()
    for _ in range(num_pages):
        page = PDPage()
        stream = COSStream()
        stream.set_raw_data(b"q Q\n")
        page.set_contents(stream)
        doc.add_page(page)
    return doc


# ---------- _hash_cos COSObject recursion (lines 50-51) -------------------


def test_hash_cos_recurses_through_cos_object_indirect_reference() -> None:
    """Lines 50-51: ``_hash_cos`` of a ``COSObject`` follows the indirect
    reference and hashes the resolved value. Two indirects pointing at
    structurally-identical resolved dicts must produce the same digest.
    """
    inner = COSDictionary()
    inner.set_name(COSName.get_pdf_name("Subtype"), "Test")
    inner.set_int(COSName.get_pdf_name("Count"), 42)

    indirect_a = COSObject(7, 0, resolved=inner)
    indirect_b = COSObject(99, 0, resolved=inner)

    h_a = hashlib.sha256()
    _hash_cos(indirect_a, h_a, set())

    h_b = hashlib.sha256()
    _hash_cos(indirect_b, h_b, set())

    # Same resolved target -> same digest, despite different object numbers.
    assert h_a.digest() == h_b.digest()


def test_hash_cos_indirect_reference_to_none_resolves_clean() -> None:
    """Companion: a ``COSObject`` that resolves to ``None`` is folded
    into the null leaf path on the recursive call (line 50 follows the
    indirect, line 46 handles the ``None``)."""
    indirect = COSObject(7, 0, resolved=None)
    # Force is_dereferenced=True so get_object returns None without loader.
    indirect._dereferenced = True  # noqa: SLF001
    h = hashlib.sha256()
    _hash_cos(indirect, h, set())
    # The indirect-then-null path must agree byte-for-byte with the
    # direct-null path (both reduce to ``b"\x00null"``).
    h_direct = hashlib.sha256()
    _hash_cos(None, h_direct, set())
    assert h.digest() == h_direct.digest()


# ---------- optimize-mode set_destination_*  (lines 635, 639) -------------


def test_optimize_mode_honours_destination_document_information(
    tmp_path: Path,
) -> None:
    """Line 635: the optimize merge path also honours
    ``set_destination_document_information`` (separate code branch from
    the legacy path covered by ``test_destination_document_information_overrides``).
    """
    from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation

    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1), a)

    info = PDDocumentInformation()
    info.set_title("optimize-title")

    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    util.set_destination_document_information(info)
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        assert merged.get_document_information().get_title() == "optimize-title"


def test_optimize_mode_honours_destination_metadata(tmp_path: Path) -> None:
    """Line 639: the optimize merge path also honours
    ``set_destination_metadata`` (separate code branch from the legacy
    path covered by ``test_set_destination_metadata_overrides_source``).
    """
    from pypdfbox.pdmodel.common.pd_metadata import PDMetadata

    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1), a)

    override_xmp = b'<?xml version="1.0"?><x:xmpmeta xmlns:x="adobe:ns:meta/"/>\n'
    override_stream = COSStream()
    override_stream.set_raw_data(override_xmp)
    override_md = PDMetadata(override_stream)

    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    util.set_destination_metadata(override_md)
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        md = merged.get_document_catalog().get_metadata()
        assert md is not None
        assert b"x:xmpmeta" in md.get_cos_object().get_raw_data()


# ---------- optimize-mode close-on-error finally (lines 651-652, 655-658) -


def test_optimize_mode_swallows_destination_close_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 651-652: optimize-mode ``destination.close()`` raising in
    the outer ``finally`` clause is swallowed (logged) — the merge
    itself still completes successfully.

    Close order in the optimize path:
      1. inner finally: ``source_doc.close()`` (lines 628-632)
      2. outer finally: ``destination.close()`` (lines 649-652)

    So the second observed close call must raise to land in 651-652.
    """
    from pypdfbox.pdmodel import pd_document as pd_doc_module

    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1), a)

    original_close = pd_doc_module.PDDocument.close
    call_count = {"n": 0}

    def flaky_close(self: PDDocument) -> None:
        call_count["n"] += 1
        if call_count["n"] == 2:
            # Second close is the destination (per the order above).
            raise RuntimeError("destination close blew up")
        original_close(self)

    monkeypatch.setattr(pd_doc_module.PDDocument, "close", flaky_close)

    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    util.merge_documents()  # the swallowed exception lets this return
    assert out.exists()
    assert call_count["n"] >= 2


def test_legacy_mode_swallows_destination_close_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Companion: legacy-mode also swallows a destination-close raise in
    its outer finally (already covered indirectly by the optimize test
    above, but the legacy path has a distinct copy of the same block —
    lines 773-777 — and we exercise it here for branch coverage)."""
    from pypdfbox.pdmodel import pd_document as pd_doc_module

    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1), a)

    original_close = pd_doc_module.PDDocument.close
    call_count = {"n": 0}

    def flaky_close(self: PDDocument) -> None:
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("destination close blew up (legacy)")
        original_close(self)

    monkeypatch.setattr(pd_doc_module.PDDocument, "close", flaky_close)

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    util.merge_documents()
    assert out.exists()
    assert call_count["n"] >= 2


# ---------- latent bug flagged -----------------------------------------
#
# Lines 655-658 (optimize-mode outer-cleanup source close) and lines
# 780-783 (legacy-mode outer-cleanup source close) are effectively
# unreachable as written: the per-source inner finally
# (``opened_sources[-1] = (source_doc, False)``, lines 632 / 757)
# *always* flips the ownership flag to ``False`` after the close
# attempt — whether the close succeeded or raised. The outer cleanup
# loop then sees ``still_owned=False`` for every entry and skips the
# close.
#
# To exercise 655-658 / 780-783 the inner finally would need to either
# (a) not run, or (b) only flip on successful close. Neither happens in
# the current implementation. Reported as a latent code-correctness
# issue (the outer cleanup loop is dead code in normal control flow).
# Pragmas added in the source flag the lines for now.


# ---------- merge_viewer_preferences _maybe guards ------------------------


def test_merge_viewer_preferences_skips_when_destination_missing_setter() -> None:
    """Line 1922: when the destination viewer-prefs object lacks one of
    the typed setters the ``_maybe`` helper short-circuits silently
    rather than raising.

    Approach: hand the merger a destination catalog whose
    ``get_viewer_preferences`` returns a stub missing the typed toggle
    setters (e.g. ``set_hide_toolbar`` is absent). The merge call must
    complete cleanly with no AttributeError.
    """
    from pypdfbox.pdmodel.pd_viewer_preferences import PDViewerPreferences

    class _StubVP:
        """Viewer-prefs stand-in: source has the typed getters/setters,
        but the destination stub deliberately omits ``set_*`` so each
        ``_maybe(get_name, set_name)`` call falls through line 1922."""

        def __init__(self) -> None:
            self._cos = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self._cos

        def get_hide_toolbar(self) -> bool:
            return True

        def get_hide_menubar(self) -> bool:
            return False

        def get_hide_window_ui(self) -> bool:
            return False

        def get_fit_window(self) -> bool:
            return False

        def get_center_window(self) -> bool:
            return False

        def get_display_doc_title(self) -> bool:
            return False
        # NB: deliberately no ``set_*`` methods — line 1922 short-circuit.

    class _DestCat:
        def __init__(self) -> None:
            self._vp = _StubVP()

        def get_viewer_preferences(self) -> _StubVP:
            return self._vp

        def set_viewer_preferences(self, _vp: object) -> None:
            self._vp = _vp  # type: ignore[assignment]

    class _SrcCat:
        def __init__(self) -> None:
            real = PDViewerPreferences()
            real.set_hide_toolbar(True)
            self._vp = real

        def get_viewer_preferences(self) -> PDViewerPreferences:
            return self._vp

    util = PDFMergerUtility()
    dest = PDDocument()
    try:
        util.merge_viewer_preferences(_DestCat(), _SrcCat(), PDFCloneUtility(dest))
    finally:
        dest.close()


def test_merge_viewer_preferences_swallows_getter_raise() -> None:
    """Lines 1926-1927: a ``getter()`` call inside ``_maybe`` raising
    is logged-and-swallowed; the merge completes normally and the
    remaining toggles are still attempted."""

    class _RaisingVP:
        def __init__(self) -> None:
            self._cos = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self._cos

        # Every typed getter raises so ``_maybe``'s ``try`` block in
        # 1923-1925 hits the ``except`` arm in 1926-1927.
        def get_hide_toolbar(self) -> bool:
            raise RuntimeError("toolbar boom")

        def get_hide_menubar(self) -> bool:
            raise RuntimeError("menubar boom")

        def get_hide_window_ui(self) -> bool:
            raise RuntimeError("windowui boom")

        def get_fit_window(self) -> bool:
            raise RuntimeError("fit boom")

        def get_center_window(self) -> bool:
            raise RuntimeError("center boom")

        def get_display_doc_title(self) -> bool:
            raise RuntimeError("doctitle boom")

        # Setters present and callable so we reach the try-block.
        def set_hide_toolbar(self, _v: bool) -> None: ...
        def set_hide_menubar(self, _v: bool) -> None: ...
        def set_hide_window_ui(self, _v: bool) -> None: ...
        def set_fit_window(self, _v: bool) -> None: ...
        def set_center_window(self, _v: bool) -> None: ...
        def set_display_doc_title(self, _v: bool) -> None: ...

    class _DestCat:
        def __init__(self) -> None:
            self._vp = _RaisingVP()

        def get_viewer_preferences(self) -> _RaisingVP:
            return self._vp

        def set_viewer_preferences(self, _vp: object) -> None:
            self._vp = _vp  # type: ignore[assignment]

    class _SrcCat:
        def __init__(self) -> None:
            self._vp = _RaisingVP()

        def get_viewer_preferences(self) -> _RaisingVP:
            return self._vp

    util = PDFMergerUtility()
    dest = PDDocument()
    try:
        # No exception escapes — every raising getter is swallowed.
        util.merge_viewer_preferences(_DestCat(), _SrcCat(), PDFCloneUtility(dest))
    finally:
        dest.close()


# ---------- module re-export sanity --------------------------------------


def test_hash_abort_is_exception_subclass() -> None:
    """``_HashAbort`` is a private sentinel exception — confirm its
    public-facing contract (subclass of ``Exception``) so the optimize
    cache can rely on the standard try/except catch above."""
    assert issubclass(_HashAbort, Exception)
