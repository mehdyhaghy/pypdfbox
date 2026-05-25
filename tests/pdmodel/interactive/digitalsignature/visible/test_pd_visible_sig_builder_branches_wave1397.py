"""Wave 1397 branch-coverage tests for ``PDVisibleSigBuilder``.

Closes False-branch arrows where the builder probes the surrounding
pdmodel objects for optional setters / closers and bails out cleanly
when they're absent:

* ``inject_proc_set_array`` 279->273 — resources with no ``set_proc_set``
* ``create_visual_signature`` 305->exit — template with no ``get_document``
* ``close_template`` 319->exit — template with no ``close``
"""

from __future__ import annotations

from typing import Any

from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sig_builder import (
    PDVisibleSigBuilder,
)


def _builder() -> PDVisibleSigBuilder:
    return PDVisibleSigBuilder()


class _ResourcesWithoutSetProcSet:
    """Resources stub that intentionally lacks ``set_proc_set``."""


class _TemplateWithoutGetDocument:
    """Template stub that lacks ``get_document``."""


class _TemplateWithoutClose:
    """Template stub that lacks ``close``."""


def test_inject_proc_set_array_skips_resources_without_setter() -> None:
    """Closes 279->273: a resources stub with no ``set_proc_set``
    falls through the loop iteration without raising."""
    builder = _builder()
    bare = _ResourcesWithoutSetProcSet()
    # The loop iterates over inner_form_resources, image_form_resources,
    # holder_form_resources — pass the bare stub three times.
    builder.inject_proc_set_array(None, None, bare, bare, bare, ["PDF"])


def test_create_visual_signature_noop_when_template_lacks_get_document() -> None:
    """Closes 305->exit: a template with no ``get_document`` skips
    the ``set_visual_signature`` dispatch."""
    builder = _builder()
    # Capture what _pdf_structure receives — should be nothing.
    received: list[Any] = []
    builder._pdf_structure.set_visual_signature = lambda v: received.append(v)  # type: ignore[assignment]
    builder.create_visual_signature(_TemplateWithoutGetDocument())
    assert received == []


def test_close_template_skips_when_template_lacks_close() -> None:
    """Closes 319->exit: a template without a ``close`` method is
    silently ignored."""
    builder = _builder()
    # Should not raise.
    builder.close_template(_TemplateWithoutClose())
