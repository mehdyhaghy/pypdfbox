"""Additional branch coverage for ``DrawObject`` — wave 1400.

Closes branch (52 → 53) — resources lacking ``get_x_object`` short-
circuits with a return.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.draw_object import DrawObject
from pypdfbox.cos import COSName


class _ResourcesWithoutGetX:
    """Resources stand-in lacking ``get_x_object`` so the
    ``getattr(..., None) is None`` guard fires."""

    def is_image_x_object(self, name: COSName) -> bool:
        del name
        return False


class _EngineWithStubResources(PDFStreamEngine):
    def __init__(self, resources: Any) -> None:
        super().__init__()
        self._resources = resources


def test_draw_object_returns_when_get_x_object_missing() -> None:
    """When the resources object lacks ``get_x_object`` (e.g. mocked
    resources or a partial stub), DrawObject must silently return.

    Closes branch (52 → 53)."""
    engine = _EngineWithStubResources(_ResourcesWithoutGetX())
    op = DrawObject(engine)
    # Must not raise.
    op.process(Operator.get_operator("Do"), [COSName.get_pdf_name("Fm0")])
