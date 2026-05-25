"""Branch coverage for ``DrawObject`` (``Do``) — wave 1400.

Closes residual partial branches in
``pypdfbox/contentstream/operator/draw_object.py``:

* Context lacks ``show_transparency_group`` — the dispatch is skipped
  (branch 64 → 71).
* Context lacks ``show_form`` — the dispatch is skipped (branch 68 → 71).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.draw_object import DrawObject
from pypdfbox.cos import COSName


class _StubResources:
    def __init__(self, x_object: object) -> None:
        self._x = x_object

    def is_image_x_object(self, name: COSName) -> bool:
        del name
        return False

    def get_x_object(self, name: COSName) -> Any:
        del name
        return self._x


class _FormXObject:
    is_form_xobject = True


class _PDTransparencyGroup:
    is_form_xobject = True


# Force class name so DrawObject._is_transparency_group recognises it.
_PDTransparencyGroup.__name__ = "PDTransparencyGroup"


class _EngineWithoutShowForm(PDFStreamEngine):
    """Engine that lacks ``show_form`` — the regular form dispatch is
    skipped (branch 68 → 71)."""

    def __init__(self, resources: _StubResources) -> None:
        super().__init__()
        self._resources = resources


# Remove inherited show_form to make getattr return None.
_EngineWithoutShowForm.show_form = None  # type: ignore[assignment]


class _EngineWithoutShowTransparency(PDFStreamEngine):
    """Engine that lacks ``show_transparency_group`` — transparency
    dispatch is skipped (branch 64 → 71)."""

    def __init__(self, resources: _StubResources) -> None:
        super().__init__()
        self._resources = resources

    def show_form(self, form: Any) -> None:  # type: ignore[override]
        del form  # noqa: F841 — recorded via spy


_EngineWithoutShowTransparency.show_transparency_group = None  # type: ignore[assignment]


def test_draw_object_form_dispatch_skipped_when_show_form_missing() -> None:
    """Engine lacking ``show_form`` must not raise — DrawObject just
    skips the dispatch.

    Closes branch (68 → 71)."""
    form = _FormXObject()
    engine = _EngineWithoutShowForm(_StubResources(form))
    op = DrawObject(engine)
    # Must not raise; the finally still runs.
    op.process(Operator.get_operator("Do"), [COSName.get_pdf_name("Fm0")])
    # Engine level was increased then decreased.
    assert engine.get_level() == 0


def test_draw_object_transparency_dispatch_skipped_when_hook_missing() -> None:
    """Engine lacking ``show_transparency_group`` must not raise — the
    transparency dispatch is skipped.

    Closes branch (64 → 71)."""
    group = _PDTransparencyGroup()
    engine = _EngineWithoutShowTransparency(_StubResources(group))
    op = DrawObject(engine)
    op.process(Operator.get_operator("Do"), [COSName.get_pdf_name("Fm1")])
    assert engine.get_level() == 0
