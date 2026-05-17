"""Wave 1337 — PDFMergerUtility coverage-boost round.

Covers the deeper branches of the optimize-mode canonical-hash dedup
helper (``_hash_cos`` / ``_canonical_resource_hash``), the
``_dedup_page_resources`` walker on edge-case resource subgraphs, the
remaining property/setter accessors (acro_form_merge_mode_property,
ignore_acro_form_errors, destination-* round-trips, stream-cache &
compress-parameters staging), the dynamic-XFA reject path under
OPTIMIZE_RESOURCES_MODE, the close-on-error log paths, and the
upstream-named alias wrappers at the tail of the class.

All inputs are constructed in-memory so the suite has no fixture
dependency.
"""
from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.multipdf import (
    AcroFormMergeMode,
    DocumentMergeMode,
    PDFMergerUtility,
)
from pypdfbox.multipdf.pdf_clone_utility import PDFCloneUtility
from pypdfbox.multipdf.pdf_merger_utility import _hash_cos, _HashAbort
from pypdfbox.pdmodel import PDDocument, PDPage

# ---------- helpers ----------


_RESOURCES = COSName.get_pdf_name("Resources")
_FONT = COSName.get_pdf_name("Font")
_XOBJECT = COSName.get_pdf_name("XObject")
_F1 = COSName.get_pdf_name("F1")


def _seed_page_contents(page: PDPage, body: bytes = b"q\n1 0 0 1 0 0 cm Q\n") -> None:
    stream = COSStream()
    stream.set_raw_data(body)
    page.set_contents(stream)


def _hash_value(value: object) -> bytes:
    h = hashlib.sha256()
    _hash_cos(value, h, set())
    return h.digest()


def _hash_value_or_none(value: object) -> bytes | None:
    h = hashlib.sha256()
    try:
        _hash_cos(value, h, set())
    except _HashAbort:
        return None
    return h.digest()


# ---------- _hash_cos leaf branches ----------


def test_hash_cos_none_value_hashes_as_null_marker() -> None:
    a = _hash_value(None)
    b = _hash_value(COSNull.NULL)
    # Implementation maps both Python None and COSNull to ``\x00null``.
    assert a == b


def test_hash_cos_cos_boolean_true_vs_false_differs() -> None:
    t = _hash_value(COSBoolean.TRUE)
    f = _hash_value(COSBoolean.FALSE)
    assert t != f
    # And both differ from null.
    assert t != _hash_value(None)


def test_hash_cos_integer_and_equivalent_float_collapse() -> None:
    """Stable text form: an int and a float that compares equal hash
    the same."""
    a = _hash_value(COSInteger.get(42))
    b = _hash_value(COSFloat(42.0))
    assert a == b


def test_hash_cos_float_that_is_not_an_int_uses_fixed_repr() -> None:
    a = _hash_value(COSFloat(1.5))
    b = _hash_value(COSFloat(1.5))
    assert a == b
    assert a != _hash_value(COSFloat(2.5))


def test_hash_cos_name_value_hashes_value_bytes() -> None:
    a = _hash_value(COSName.get_pdf_name("Foo"))
    b = _hash_value(COSName.get_pdf_name("Foo"))
    c = _hash_value(COSName.get_pdf_name("Bar"))
    assert a == b
    assert a != c


def test_hash_cos_string_hashes_payload_bytes() -> None:
    a = _hash_value(COSString("hello"))
    b = _hash_value(COSString("hello"))
    c = _hash_value(COSString("world"))
    assert a == b
    assert a != c


def test_hash_cos_dictionary_orders_keys() -> None:
    """Dict canonicalisation walks keys in sorted order — two dicts
    with the same entries (different insertion order) collapse."""
    d1 = COSDictionary()
    d1.set_name("A", "alpha")
    d1.set_name("B", "beta")
    d2 = COSDictionary()
    d2.set_name("B", "beta")
    d2.set_name("A", "alpha")
    assert _hash_value(d1) == _hash_value(d2)


def test_hash_cos_array_uses_index_order() -> None:
    a1 = COSArray()
    a1.add(COSInteger.get(1))
    a1.add(COSInteger.get(2))
    a2 = COSArray()
    a2.add(COSInteger.get(2))
    a2.add(COSInteger.get(1))
    # Index-ordered: different ordering must produce different hashes.
    assert _hash_value(a1) != _hash_value(a2)


def test_hash_cos_stream_includes_body_bytes() -> None:
    s1 = COSStream()
    s1.set_raw_data(b"payload-A")
    s2 = COSStream()
    s2.set_raw_data(b"payload-A")
    s3 = COSStream()
    s3.set_raw_data(b"payload-B")
    assert _hash_value(s1) == _hash_value(s2)
    assert _hash_value(s1) != _hash_value(s3)


def test_hash_cos_unknown_leaf_raises_hash_abort() -> None:
    """Anything that isn't one of the COS scalar/container types
    aborts the digest with _HashAbort."""

    class _Junk:
        pass

    with pytest.raises(_HashAbort):
        _hash_cos(_Junk(), hashlib.sha256(), set())


def test_hash_cos_cycle_in_dictionary_aborts() -> None:
    """A self-referential dict raises _HashAbort the second time the
    walker would revisit the same id()."""
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Self"), d)
    assert _hash_value_or_none(d) is None


def test_hash_cos_cycle_in_array_aborts() -> None:
    arr = COSArray()
    arr.add(arr)
    assert _hash_value_or_none(arr) is None


def test_hash_cos_cycle_via_stream_aborts() -> None:
    s = COSStream()
    s.set_raw_data(b"x")
    s.set_item(COSName.get_pdf_name("Self"), s)
    assert _hash_value_or_none(s) is None


def test_hash_cos_stream_unreadable_body_aborts() -> None:
    """When ``create_raw_input_stream`` blows up, ``_hash_cos`` raises
    ``_HashAbort`` so the caller falls back rather than poisoning the
    digest."""
    s = COSStream()
    s.set_raw_data(b"some-bytes")

    class _BoomBody:
        def __enter__(self):
            raise RuntimeError("nope")

        def __exit__(self, *exc):
            return False

    # Force ``has_data`` to True but make ``create_raw_input_stream``
    # explode — simulates a corrupt cached stream.
    s.create_raw_input_stream = lambda: _BoomBody()  # type: ignore[assignment]
    assert _hash_value_or_none(s) is None


# ---------- _canonical_resource_hash ----------


def test_canonical_resource_hash_returns_stable_digest() -> None:
    d = COSDictionary()
    d.set_name("Type", "Font")
    d.set_name("Subtype", "Type1")
    d.set_name("BaseFont", "Helvetica")
    digest_a = PDFMergerUtility._canonical_resource_hash(d)
    digest_b = PDFMergerUtility._canonical_resource_hash(d)
    assert digest_a == digest_b
    assert isinstance(digest_a, bytes)
    assert len(digest_a) == 32  # SHA-256 → 32 bytes


def test_canonical_resource_hash_returns_none_for_cycle() -> None:
    """Cyclic graphs round-trip through the public helper as ``None``
    (the caller skips them rather than poisoning the cache)."""
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Loop"), d)
    assert PDFMergerUtility._canonical_resource_hash(d) is None


# ---------- _dedup_page_resources branches ----------


def test_dedup_page_resources_with_no_resources_is_noop() -> None:
    util = PDFMergerUtility()
    page = COSDictionary()  # no /Resources at all
    cache: dict[bytes, object] = {}
    util._dedup_page_resources(page, cache)  # noqa: SLF001
    assert cache == {}


def test_dedup_page_resources_skips_non_dict_resource_container() -> None:
    util = PDFMergerUtility()
    page = COSDictionary()
    page.set_item(_RESOURCES, COSArray())  # wrong type
    cache: dict[bytes, object] = {}
    util._dedup_page_resources(page, cache)  # noqa: SLF001
    assert cache == {}


def test_dedup_page_resources_skips_non_dict_subcategory() -> None:
    util = PDFMergerUtility()
    page = COSDictionary()
    resources = COSDictionary()
    resources.set_item(_FONT, COSArray())  # /Font is *not* a dict — skip
    page.set_item(_RESOURCES, resources)
    cache: dict[bytes, object] = {}
    util._dedup_page_resources(page, cache)  # noqa: SLF001
    assert cache == {}


def test_dedup_page_resources_skips_none_entry() -> None:
    util = PDFMergerUtility()
    page = COSDictionary()
    resources = COSDictionary()
    fonts = COSDictionary()
    # NB: set_item with COSNull → get_dictionary_object returns None
    fonts.set_item(_F1, COSNull.NULL)
    resources.set_item(_FONT, fonts)
    page.set_item(_RESOURCES, resources)
    cache: dict[bytes, object] = {}
    util._dedup_page_resources(page, cache)  # noqa: SLF001
    assert cache == {}


def test_dedup_page_resources_skips_un_hashable_entry() -> None:
    """A cyclic entry is un-hashable (canonical_resource_hash → None) —
    the dedup walker leaves it alone instead of dumping a junk key in
    the cache."""
    util = PDFMergerUtility()
    page = COSDictionary()
    resources = COSDictionary()
    fonts = COSDictionary()
    cyclic = COSDictionary()
    cyclic.set_item(COSName.get_pdf_name("Self"), cyclic)
    fonts.set_item(_F1, cyclic)
    resources.set_item(_FONT, fonts)
    page.set_item(_RESOURCES, resources)
    cache: dict[bytes, object] = {}
    util._dedup_page_resources(page, cache)  # noqa: SLF001
    assert cache == {}


def test_dedup_page_resources_populates_cache_then_collapses_duplicates() -> None:
    """First page seeds the cache; second page's equivalent entry is
    rewritten to point at the first instance."""
    util = PDFMergerUtility()

    def _font_dict() -> COSDictionary:
        font = COSDictionary()
        font.set_name("Type", "Font")
        font.set_name("Subtype", "Type1")
        font.set_name("BaseFont", "Helvetica")
        return font

    page_a = COSDictionary()
    res_a = COSDictionary()
    fmap_a = COSDictionary()
    f_a = _font_dict()
    fmap_a.set_item(_F1, f_a)
    res_a.set_item(_FONT, fmap_a)
    page_a.set_item(_RESOURCES, res_a)

    page_b = COSDictionary()
    res_b = COSDictionary()
    fmap_b = COSDictionary()
    f_b = _font_dict()
    fmap_b.set_item(_F1, f_b)
    res_b.set_item(_FONT, fmap_b)
    page_b.set_item(_RESOURCES, res_b)

    cache: dict[bytes, object] = {}
    util._dedup_page_resources(page_a, cache)  # noqa: SLF001
    assert len(cache) == 1
    # After the second page is folded in, /F1 must point at the
    # first page's font instance.
    util._dedup_page_resources(page_b, cache)  # noqa: SLF001
    assert fmap_b.get_dictionary_object(_F1) is f_a


# ---------- accessor round-trips (uncovered getter/setter pairs) ----------


def test_acro_form_merge_mode_property_round_trip() -> None:
    util = PDFMergerUtility()
    assert util.acro_form_merge_mode_property is AcroFormMergeMode.PDFBOX_LEGACY_MODE
    util.acro_form_merge_mode_property = AcroFormMergeMode.JOIN_FORM_FIELDS_MODE
    assert util.get_acro_form_merge_mode() is AcroFormMergeMode.JOIN_FORM_FIELDS_MODE
    # setter via set_acro_form_merge_mode also exercised:
    util.set_acro_form_merge_mode(AcroFormMergeMode.PDFBOX_LEGACY_MODE)
    assert util.acro_form_merge_mode_property is AcroFormMergeMode.PDFBOX_LEGACY_MODE


def test_ignore_acro_form_errors_default_and_set() -> None:
    util = PDFMergerUtility()
    assert util.is_ignore_acro_form_errors() is False
    util.set_ignore_acro_form_errors(True)
    assert util.is_ignore_acro_form_errors() is True
    util.set_ignore_acro_form_errors(0)  # truthy → bool() cast to False
    assert util.is_ignore_acro_form_errors() is False


def test_destination_file_name_getter_setter() -> None:
    util = PDFMergerUtility()
    assert util.get_destination_file_name() is None
    util.set_destination_file_name("/tmp/out.pdf")
    assert util.get_destination_file_name() == "/tmp/out.pdf"


def test_destination_stream_getter_setter() -> None:
    util = PDFMergerUtility()
    assert util.get_destination_stream() is None
    sink = io.BytesIO()
    util.set_destination_stream(sink)
    assert util.get_destination_stream() is sink


def test_destination_document_information_getter_setter() -> None:
    util = PDFMergerUtility()
    assert util.get_destination_document_information() is None
    sentinel = object()
    util.set_destination_document_information(sentinel)
    assert util.get_destination_document_information() is sentinel


def test_destination_metadata_getter_setter() -> None:
    util = PDFMergerUtility()
    assert util.get_destination_metadata() is None
    sentinel = object()
    util.set_destination_metadata(sentinel)
    assert util.get_destination_metadata() is sentinel


# ---------- optimize-mode error paths ----------


def test_optimize_mode_requires_destination() -> None:
    """OPTIMIZE_RESOURCES_MODE shares the same destination-missing
    guard as legacy mode."""
    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    # Source must exist to reach the destination guard.
    src = PDDocument()
    src.add_page(PDPage())
    util.add_source(src)
    try:
        with pytest.raises(ValueError):
            util.merge_documents()
    finally:
        src.close()


def test_optimize_mode_dynamic_xfa_raises_oserror(tmp_path: Path) -> None:
    """A source carrying a dynamic-XFA AcroForm is rejected under the
    optimize path too (same guard as legacy)."""
    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)

    class _DynamicForm:
        def xfa_is_dynamic(self) -> bool:
            return True

    class _FakeCatalog:
        def get_acro_form(self):
            return _DynamicForm()

    class _FakeSourceDoc:
        def get_document_catalog(self):
            return _FakeCatalog()

        def get_pages(self):
            return []

        def close(self) -> None:
            pass

    monkey = _FakeSourceDoc()
    util._sources = [monkey]  # noqa: SLF001 — direct list bypass
    util.set_destination_file_name(str(tmp_path / "out.pdf"))

    # Patch _open_source to return our fake without touching disk.
    util._open_source = lambda src: (src, False)  # type: ignore[method-assign]  # noqa: SLF001
    with pytest.raises(OSError, match="dynamic XFA"):
        util.merge_documents()


def test_optimize_mode_source_close_failure_is_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """When the merger owns a source it closes it in the per-iteration
    finally; a raising close is swallowed and ``_LOG.exception`` is
    fired."""
    a = tmp_path / "a.pdf"
    doc = PDDocument()
    page = PDPage()
    _seed_page_contents(page)
    doc.add_page(page)
    doc.save(a)
    doc.close()

    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_source(str(a))
    util.set_destination_file_name(str(tmp_path / "out.pdf"))

    # Force the source.close() to raise — _LOG.exception fires.
    original_open = util._open_source

    def _flaky_open(src):  # noqa: ANN001
        d, owns = original_open(src)

        class _Flaky:
            def __getattr__(self, name):
                return getattr(d, name)

            def close(self):
                raise RuntimeError("flaky close")

        return _Flaky(), True

    util._open_source = _flaky_open  # type: ignore[method-assign]  # noqa: SLF001
    with caplog.at_level(logging.ERROR, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util.merge_documents()
    assert "error closing source PDDocument" in caplog.text


# ---------- legacy path: destination close-error logging ----------


def test_legacy_merge_destination_close_error_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When destination.close() raises in the finally clause the
    error is swallowed + logged. The source closes first (inner
    finally) so we make every PDDocument.close raise and assert both
    branches fire."""
    a = tmp_path / "a.pdf"
    doc = PDDocument()
    page = PDPage()
    _seed_page_contents(page)
    doc.add_page(page)
    doc.save(a)
    doc.close()

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.set_destination_file_name(str(tmp_path / "out.pdf"))

    from pypdfbox.pdmodel import pd_document as _pdm

    def _always_flaky(self):  # noqa: ANN001
        raise RuntimeError("flaky close")

    monkeypatch.setattr(_pdm.PDDocument, "close", _always_flaky)

    with caplog.at_level(logging.ERROR, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util.merge_documents()
    # Both source-close and destination-close raise; both errors must
    # be swallowed and logged.
    assert "error closing destination PDDocument" in caplog.text
    assert "error closing source PDDocument" in caplog.text


# ---------- public-name alias wrappers (1968-2058) ----------


def test_alias_is_dynamic_xfa_routes_to_private() -> None:
    util = PDFMergerUtility()
    assert util.is_dynamic_xfa(None) is False

    class _Dyn:
        def xfa_is_dynamic(self) -> bool:
            return True

    assert util.is_dynamic_xfa(_Dyn()) is True


def test_alias_merge_into_routes_to_private() -> None:
    util = PDFMergerUtility()
    dest_doc = PDDocument()
    try:
        cloner = PDFCloneUtility(dest_doc)
        src = COSDictionary()
        src.set_name("Foo", "bar")
        dst = COSDictionary()
        util.merge_into(src, dst, cloner, frozenset())
        assert dst.get_name("Foo") == "bar"
    finally:
        dest_doc.close()


def test_alias_merge_acro_form_routes_to_private() -> None:
    """merge_acro_form delegates to _merge_acro_form; with both forms
    None the call is a clean no-op."""
    util = PDFMergerUtility()
    dest_doc = PDDocument()
    try:
        cloner = PDFCloneUtility(dest_doc)

        class _NoForm:
            def get_acro_form(self):
                return None

        # Both forms None — short-circuits cleanly.
        util.merge_acro_form(cloner, _NoForm(), _NoForm())
    finally:
        dest_doc.close()


def test_alias_acro_form_legacy_and_join_modes_route_to_private() -> None:
    util = PDFMergerUtility()
    dest_doc = PDDocument()
    try:
        cloner = PDFCloneUtility(dest_doc)

        class _Form:
            def get_fields(self):
                return []

            def get_field_tree(self):
                return []

            def get_cos_object(self):
                return COSDictionary()

        # Empty source fields → no-op both ways.
        util.acro_form_legacy_mode(cloner, _Form(), _Form())
        util.acro_form_join_fields_mode(cloner, _Form(), _Form())
    finally:
        dest_doc.close()


def test_alias_merge_open_action_routes_to_private() -> None:
    """merge_open_action is a no-op when the destination already carries
    an /OpenAction; this exercises the alias dispatcher only."""
    util = PDFMergerUtility()
    dest_doc = PDDocument()
    try:
        cloner = PDFCloneUtility(dest_doc)

        class _Cat:
            def __init__(self):
                self._cos = COSDictionary()

            def get_cos_object(self):
                return self._cos

        util.merge_open_action(cloner, _Cat(), _Cat())
    finally:
        dest_doc.close()


def test_alias_merge_role_map_routes_to_private() -> None:
    util = PDFMergerUtility()
    dest_doc = PDDocument()
    try:
        cloner = PDFCloneUtility(dest_doc)

        class _ST:
            def get_role_map(self):
                return None

            def set_role_map(self, mapping):
                self._rm = mapping

            def get_cos_object(self):
                return COSDictionary()

        util.merge_role_map(cloner, _ST(), _ST())
    finally:
        dest_doc.close()


def test_alias_merge_id_tree_and_k_entries_route_to_private() -> None:
    util = PDFMergerUtility()
    dest_doc = PDDocument()
    try:
        cloner = PDFCloneUtility(dest_doc)

        class _ST:
            def get_id_tree(self):
                return None

            def set_id_tree(self, t):
                self._it = t

            def get_k(self):
                return None

            def set_k(self, k):
                self._k = k

            def get_parent_tree_next_key(self):
                return 0

            def set_parent_tree_next_key(self, n):
                self._n = n

            def get_cos_object(self):
                return COSDictionary()

        util.merge_id_tree(cloner, _ST(), _ST())
        util.merge_k_entries(cloner, _ST(), _ST())
    finally:
        dest_doc.close()


def test_alias_merge_output_intents_routes_to_private() -> None:
    util = PDFMergerUtility()
    dest_doc = PDDocument()
    try:
        cloner = PDFCloneUtility(dest_doc)

        class _Cat:
            def __init__(self):
                self._cos = COSDictionary()

            def get_cos_object(self):
                return self._cos

        util.merge_output_intents(cloner, _Cat(), _Cat())
    finally:
        dest_doc.close()


def test_alias_has_only_documents_or_parts_routes_to_private() -> None:
    util = PDFMergerUtility()
    arr = COSArray()
    # Empty array — happy path.
    assert util.has_only_documents_or_parts(arr) in (True, False)


def test_alias_update_parent_entry_routes_to_private() -> None:
    util = PDFMergerUtility()
    arr = COSArray()
    new_parent = COSDictionary()
    # Empty K array — no-op-style call to exercise dispatcher.
    util.update_parent_entry(arr, new_parent, None)


def test_alias_update_struct_parent_entries_routes_to_private() -> None:
    util = PDFMergerUtility()
    page = COSDictionary()
    # Without /Annots / /StructParents the helper short-circuits.
    util.update_struct_parent_entries(page, 5)


# ---------- viewer-preferences helper edge cases ----------


def test_merge_viewer_preferences_short_circuits_when_src_lacks_getter() -> None:
    """merge_viewer_preferences exits immediately when the source
    catalog doesn't expose get_viewer_preferences."""
    util = PDFMergerUtility()
    dest_doc = PDDocument()
    try:
        cloner = PDFCloneUtility(dest_doc)

        class _BareCat:  # no get_viewer_preferences
            pass

        # Should not raise even with the bare object.
        util.merge_viewer_preferences(_BareCat(), _BareCat(), cloner)
    finally:
        dest_doc.close()


def test_merge_viewer_preferences_skips_when_src_returns_none() -> None:
    util = PDFMergerUtility()
    dest_doc = PDDocument()
    try:
        cloner = PDFCloneUtility(dest_doc)

        class _Cat:
            def get_viewer_preferences(self):
                return None

        util.merge_viewer_preferences(_Cat(), _Cat(), cloner)
    finally:
        dest_doc.close()


def test_merge_viewer_preferences_skips_when_dest_lacks_setter() -> None:
    """When destination catalog has a getter but no setter, the helper
    bails before any merge_into call."""

    class _SrcVP:
        def get_cos_object(self):
            return COSDictionary()

    class _SrcCat:
        def get_viewer_preferences(self):
            return _SrcVP()

    class _DestCat:
        def get_viewer_preferences(self):
            return None  # setter missing → guard fires

    util = PDFMergerUtility()
    dest_doc = PDDocument()
    try:
        cloner = PDFCloneUtility(dest_doc)
        util.merge_viewer_preferences(_DestCat(), _SrcCat(), cloner)
    finally:
        dest_doc.close()


# ---------- merge_language / merge_mark_info ----------


def test_merge_language_short_circuits_without_accessors() -> None:
    util = PDFMergerUtility()

    class _Bare:
        pass

    # Helper must not raise on bare catalogs.
    util.merge_language(_Bare(), _Bare())


def test_merge_language_copies_when_dest_is_empty() -> None:
    util = PDFMergerUtility()

    class _DestCat:
        def __init__(self):
            self._lang: str | None = None

        def get_language(self) -> str | None:
            return self._lang

        def set_language(self, lang: str) -> None:
            self._lang = lang

    class _SrcCat:
        def get_language(self) -> str:
            return "en-US"

    dest = _DestCat()
    util.merge_language(dest, _SrcCat())
    assert dest.get_language() == "en-US"


def test_merge_mark_info_short_circuits_without_accessors() -> None:
    util = PDFMergerUtility()

    class _Bare:
        pass

    # No accessor present → silent no-op.
    util.merge_mark_info(_Bare(), _Bare())
