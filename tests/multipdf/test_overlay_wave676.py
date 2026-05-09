from __future__ import annotations

import builtins
import logging
from typing import Any

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.multipdf import Overlay, Position
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle


def _blank_doc() -> PDDocument:
    doc = PDDocument()
    doc.add_page(PDPage(PDRectangle.from_width_height(200.0, 100.0)))
    return doc


class _NoResourcePage:
    def __init__(self) -> None:
        self._dict = COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_resources(self) -> None:
        return None

    def get_media_box(self) -> PDRectangle:
        return PDRectangle.from_width_height(25.0, 50.0)

    def get_rotation(self) -> int:
        return 0


def test_wave676_create_layout_page_supplies_empty_resources_when_page_has_none() -> None:
    base = _blank_doc()
    overlay = Overlay()
    overlay.set_input_pdf(base)

    try:
        layout = overlay._create_layout_page(_NoResourcePage())  # type: ignore[arg-type]  # noqa: SLF001,E501
    finally:
        base.close()

    assert isinstance(layout.overlay_resources, COSDictionary)
    assert list(layout.overlay_resources.key_set()) == []


def test_wave676_make_cloner_falls_back_to_document_deep_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def blocked_import(
        name: str,
        globals_: dict[str, Any] | None = None,
        locals_: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if level == 1 and name == "pdf_clone_utility":
            raise ImportError("force fallback")
        return real_import(name, globals_, locals_, fromlist, level)

    doc = _blank_doc()
    source = COSDictionary()
    source.set_item(COSName.get_pdf_name("Marker"), COSName.get_pdf_name("Value"))
    monkeypatch.setattr(builtins, "__import__", blocked_import)

    try:
        cloner = Overlay._make_cloner(doc)  # noqa: SLF001
        cloned = cloner.clone_for_new_document(source)
    finally:
        doc.close()

    assert isinstance(cloned, COSDictionary)
    assert cloned is not source
    assert cloned.get_name(COSName.get_pdf_name("Marker")) == "Value"


def test_wave676_calculate_affine_transform_logs_debug_position(
    caplog: pytest.LogCaptureFixture,
) -> None:
    doc = _blank_doc()
    page = doc.get_page(0)
    overlay_box = PDRectangle(10.0, 20.0, 60.0, 40.0)
    overlay = Overlay()

    caplog.set_level(logging.DEBUG, logger="pypdfbox.multipdf.overlay")
    try:
        matrix = overlay.calculate_affine_transform(page, overlay_box)
    finally:
        doc.close()

    assert matrix == [1.0, 0.0, 0.0, 1.0, 65.0, 20.0]
    assert "Overlay position: (65.0,20.0)" in caplog.text


def test_wave676_position_value_of_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="No Position constant"):
        Position.value_of("foreground")
