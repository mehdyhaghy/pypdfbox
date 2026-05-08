from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.pagenavigation import PDThread, PDThreadBead


def test_wave305_thread_constructor_sets_thread_and_circular_links() -> None:
    thread = PDThread()

    bead = PDThreadBead(thread)

    assert bead.get_cos_object().get_name(COSName.get_pdf_name("Type")) == "Bead"
    assert bead.get_thread() == thread
    assert bead.is_first_bead() is True
    assert bead.is_singleton() is True
    assert bead.get_cos_object().get_dictionary_object(COSName.get_pdf_name("T")) is (
        thread.get_cos_object()
    )
    assert bead.get_cos_object().get_dictionary_object(COSName.get_pdf_name("N")) is (
        bead.get_cos_object()
    )
    assert bead.get_cos_object().get_dictionary_object(COSName.get_pdf_name("V")) is (
        bead.get_cos_object()
    )


def test_wave305_dictionary_constructor_still_preserves_identity() -> None:
    raw = COSDictionary()

    bead = PDThreadBead(raw)

    assert bead.get_cos_object() is raw


def test_wave305_constructor_rejects_unknown_backing_object() -> None:
    with pytest.raises(TypeError, match="COSDictionary, PDThread, or None"):
        PDThreadBead(object())  # type: ignore[arg-type]
