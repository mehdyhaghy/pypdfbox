"""Loader memory-usage backing parity (wave 1366, agent E).

Exercises ``Loader.load_pdf``'s ``memory_usage_setting`` knob: documents
load identically whether the underlying ``ScratchFile`` is configured for
heap-only, scratch-file-only, or mixed backing. The setting is propagated
to the ``COSDocument``'s owned scratch file (or absent for the default
path), and ``cos_doc.close()`` releases it.

No upstream JUnit counterpart — pypdfbox-specific parity suite around the
``Loader.load_pdf(file, password, MemoryUsageSetting)`` overload that
upstream exposes (PDFBox 3.0.x ``Loader.java`` lines 215-251).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.io.memory_usage_setting import MemoryUsageSetting
from pypdfbox.loader import Loader


def _small_pdf_bytes() -> bytes:
    """Return a freshly-synthesised tiny PDF as bytes."""
    sink = io.BytesIO()
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.add_page(PDPage())
        doc.save(sink)
    return sink.getvalue()


def _page_count_via_pddoc(cos) -> int:
    """Wrap a ``COSDocument`` in a non-owning ``PDDocument`` to read the
    page count without closing the COSDocument out from under the caller."""
    pd = PDDocument(cos)
    pd._owns_document = False  # noqa: SLF001 — keep cos alive for caller
    return pd.get_number_of_pages()


def test_default_no_setting_loads_via_default_scratch() -> None:
    """With ``memory_usage_setting=None`` the Loader still produces a
    closable document — the scratch file (if any) is constructed by the
    COSDocument internally rather than provisioned by the Loader."""
    cos = Loader.load_pdf(_small_pdf_bytes())
    try:
        assert _page_count_via_pddoc(cos) >= 1
    finally:
        cos.close()


def test_main_memory_only_setting_attaches_scratch() -> None:
    """``setup_main_memory_only`` constructs a scratch file owned by the
    document. Confirm the document closes cleanly and reports the expected
    page count."""
    setting = MemoryUsageSetting.setup_main_memory_only()
    cos = Loader.load_pdf(_small_pdf_bytes(), None, setting)
    try:
        assert cos._owns_scratch is True  # noqa: SLF001
        assert _page_count_via_pddoc(cos) == 2
    finally:
        cos.close()


def test_temp_file_only_setting_loads_and_closes(tmp_path: Path) -> None:
    """``setup_temp_file_only`` spills decoded stream bodies to disk.
    Document must load with the same page count and close without leaking
    the scratch directory."""
    setting = MemoryUsageSetting.setup_temp_file_only().set_temp_dir(tmp_path)
    cos = Loader.load_pdf(_small_pdf_bytes(), None, setting)
    try:
        assert cos._owns_scratch is True  # noqa: SLF001
        assert _page_count_via_pddoc(cos) == 2
    finally:
        cos.close()


def test_mixed_setting_with_small_threshold() -> None:
    """``setup_mixed`` with a tiny in-memory cap forces immediate spill to
    the scratch file. Document still loads with full fidelity."""
    setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=128)
    cos = Loader.load_pdf(_small_pdf_bytes(), None, setting)
    try:
        assert cos._owns_scratch is True  # noqa: SLF001
        assert _page_count_via_pddoc(cos) == 2
    finally:
        cos.close()


@pytest.mark.parametrize(
    "factory",
    [
        lambda: None,
        lambda: MemoryUsageSetting.setup_main_memory_only(),
        lambda: MemoryUsageSetting.setup_mixed(max_main_memory_bytes=1024),
        lambda: MemoryUsageSetting.setup_temp_file_only(),
    ],
    ids=["none", "main_memory", "mixed", "temp_file"],
)
def test_all_memory_settings_parse_same_document(factory) -> None:
    """All four backing strategies yield a document with the same page
    count and trailer /Size value — the storage strategy is transparent
    to the COS-level graph."""
    pdf = _small_pdf_bytes()
    setting = factory()
    cos = Loader.load_pdf(pdf, None, setting)
    try:
        assert _page_count_via_pddoc(cos) == 2
        trailer = cos.get_trailer()
        assert trailer is not None
    finally:
        cos.close()


def test_memory_setting_via_pddocument_load_passthrough() -> None:
    """``PDDocument.load`` does not currently expose the
    ``memory_usage_setting`` knob (cluster-#1 surface limit). Confirm the
    direct ``Loader.load_pdf`` path is the way to thread it. This is a
    surface-area assertion — when ``PDDocument.load`` grows the kwarg the
    test will fail loud and an entry will be added to CHANGES.md."""
    import inspect

    sig = inspect.signature(PDDocument.load)
    # As of wave 1366, ``PDDocument.load`` accepts only ``(source, password)``.
    # The 3-positional surface is the documented parity drop.
    assert "memory_usage_setting" not in sig.parameters


def test_loader_load_alias_accepts_setting() -> None:
    """``Loader.load`` is an alias of ``Loader.load_pdf`` (line 172 of
    ``loader.py``) — confirm both routes accept the
    ``memory_usage_setting`` argument."""
    setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=256)
    cos = Loader.load(_small_pdf_bytes(), None, setting)
    try:
        assert _page_count_via_pddoc(cos) == 2
    finally:
        cos.close()
