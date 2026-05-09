from __future__ import annotations

import types

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def test_wave974_image_factory_import_hook_allows_unrelated_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pypdfbox.pdmodel.pd_page_content_stream as pcs

    imports: list[str] = []
    original_import = pcs.importlib.import_module

    def fake_import(name: str):
        imports.append(name)
        if name.endswith("jpeg_factory"):
            return types.SimpleNamespace(
                JPEGFactory=types.SimpleNamespace(
                    create_from_byte_array=lambda document, data: None
                )
            )
        if name.endswith("lossless_factory"):
            return types.SimpleNamespace()
        return original_import(name)

    monkeypatch.setattr(pcs.importlib, "import_module", fake_import)

    doc = PDDocument()
    try:
        with pytest.raises(NotImplementedError, match="LosslessFactory"):
            PDPageContentStream._coerce_to_image_xobject(b"not-jpeg", doc)
    finally:
        doc.close()

    assert "pypdfbox.pdmodel.graphics.image.lossless_factory" in imports
