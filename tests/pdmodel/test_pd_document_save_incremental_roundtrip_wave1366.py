"""``PDDocument.save_incremental`` round-trip fuzz (wave 1366, agent E).

Complements ``tests/pdmodel/test_save_incremental.py``: that file pins the
byte-prefix / /Prev / startxref contract. This one drives the higher-level
"mutate → save_incremental → reload → assert structural equivalence" loop
across several mutation shapes (info dict updates, multi-round chaining,
``objects_to_write`` set form) and verifies the final reload sees the
mutated state.

No upstream JUnit counterpart — pypdfbox-specific suite around the
``saveIncremental(OutputStream, Set<COSDictionary>)`` overload (PDFBox
3.0.x ``PDDocument.java`` ~ line 1010).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSDictionary, COSName, COSString


def _seed_pdf() -> bytes:
    """Single-page PDF with /Info already populated so an indirect /Info
    object exists in the source xref (avoids the incremental path having
    to invent it)."""
    sink = io.BytesIO()
    with PDDocument() as src:
        src.add_page(PDPage())
        src.get_document_information().set_title("seed")
        src.save(sink)
    return sink.getvalue()


def test_incremental_save_then_reload_sees_mutated_title() -> None:
    """Mutating /Info and incrementally saving — the reloaded document
    must see the new title."""
    src = _seed_pdf()
    with PDDocument.load(src) as loaded:
        info = loaded.get_document_information()
        info.set_title("after-increment")
        info.get_cos_object().set_needs_to_be_updated(True)
        sink = io.BytesIO()
        loaded.save_incremental(sink)

    with PDDocument.load(sink.getvalue()) as reloaded:
        # When the incremental tail reuses the source's /Info dict slot,
        # the new title overrides the original via the appended xref.
        assert reloaded.get_document_information().get_title() == "after-increment"


def test_two_chained_increments_preserve_first_revision_in_prev() -> None:
    """Chained incremental saves: each save's /Prev must point at the
    previous startxref, and the final reload must reflect the latest
    mutation."""
    src = _seed_pdf()
    with PDDocument.load(src) as loaded:
        loaded.get_document_information().set_title("rev1")
        loaded.get_document_information().get_cos_object().set_needs_to_be_updated(True)
        sink1 = io.BytesIO()
        loaded.save_incremental(sink1)
    revision1 = sink1.getvalue()
    assert revision1.startswith(src)

    with PDDocument.load(revision1) as loaded2:
        loaded2.get_document_information().set_title("rev2")
        loaded2.get_document_information().get_cos_object().set_needs_to_be_updated(
            True
        )
        sink2 = io.BytesIO()
        loaded2.save_incremental(sink2)
    revision2 = sink2.getvalue()
    assert revision2.startswith(revision1)

    with PDDocument.load(revision2) as final:
        assert final.get_document_information().get_title() == "rev2"


def test_incremental_save_with_objects_to_write_set() -> None:
    """``save_incremental(target, objects_to_write={dict})`` force-stamps
    every entry as ``needs_to_be_updated`` even when the dirty walk would
    have skipped them. The reloaded document must see the new dictionary."""
    src = _seed_pdf()
    with PDDocument.load(src) as loaded:
        # Attach a fresh COSDictionary that is NOT marked dirty via the
        # normal path. The set form must force its inclusion anyway.
        new_dict = COSDictionary()
        new_dict.set_item(COSName.get_pdf_name("Marker"), COSString("force-included"))
        # Splice the new dict into the catalog so it's reachable; the
        # catalog itself needs to be marked so the writer queues both.
        cat_cos = loaded.get_document_catalog().get_cos_object()
        cat_cos.set_item(COSName.get_pdf_name("FuzzExtra"), new_dict)
        cat_cos.set_needs_to_be_updated(True)

        sink = io.BytesIO()
        loaded.save_incremental(sink, objects_to_write={new_dict})

    with PDDocument.load(sink.getvalue()) as reloaded:
        marker = reloaded.get_document_catalog().get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("FuzzExtra")
        )
        assert isinstance(marker, COSDictionary)
        v = marker.get_dictionary_object(COSName.get_pdf_name("Marker"))
        assert isinstance(v, COSString)
        assert v.get_string() == "force-included"


def test_save_incremental_rejects_non_dictionary_in_set() -> None:
    """``objects_to_write`` must contain only ``COSDictionary`` instances —
    other COS shapes raise ``TypeError`` before any bytes are produced."""
    src = _seed_pdf()
    with PDDocument.load(src) as loaded:
        sink = io.BytesIO()
        with pytest.raises(TypeError, match="COSDictionary"):
            # The set form filters by type; a non-dict entry must raise.
            loaded.save_incremental(sink, objects_to_write={"not-a-dict"})  # type: ignore[arg-type]


def test_save_incremental_requires_source() -> None:
    """A synthesised (non-loaded) document has no source — incremental
    save raises ``RuntimeError`` (wave 1486: mirrors upstream
    ``IllegalStateException("document was not loaded from a file or a
    stream")``, PDDocument.java L1089)."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        sink = io.BytesIO()
        with pytest.raises(RuntimeError, match="was not loaded from a file or a stream"):
            doc.save_incremental(sink)


def test_save_incremental_to_path(tmp_path: Path) -> None:
    """Path target for incremental save: must write the source prefix
    verbatim and reload with the mutation visible."""
    src = _seed_pdf()
    seed_path = tmp_path / "seed.pdf"
    seed_path.write_bytes(src)

    target = tmp_path / "after.pdf"
    with PDDocument.load(seed_path) as loaded:
        loaded.get_document_information().set_title("path-target")
        loaded.get_document_information().get_cos_object().set_needs_to_be_updated(True)
        loaded.save_incremental(target)

    final_bytes = target.read_bytes()
    assert final_bytes.startswith(src)
    with PDDocument.load(target) as reloaded:
        assert reloaded.get_document_information().get_title() == "path-target"


def test_save_incremental_with_no_dirty_objects_still_succeeds() -> None:
    """Calling ``save_incremental`` when no object is dirty produces a
    PDF that's still well-formed and reloads — just with no observable
    mutation. (Upstream tolerates this silently.)"""
    src = _seed_pdf()
    with PDDocument.load(src) as loaded:
        sink = io.BytesIO()
        # No dirty marking — incremental save must still succeed.
        loaded.save_incremental(sink)
    out = sink.getvalue()
    assert out.startswith(src)
    with PDDocument.load(out) as reloaded:
        # Title is unchanged from the seed.
        assert reloaded.get_document_information().get_title() == "seed"
