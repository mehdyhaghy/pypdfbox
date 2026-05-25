"""Branch coverage for ``MarkedContentPointWithProperties`` (``DP``) — wave 1400.

Closes residual partial branches in
``pypdfbox/contentstream/operator/markedcontent/marked_content_point_with_properties.py``:

* Context returns ``None`` from ``get_resources`` — the resource-lookup
  block is skipped (branch 34 → 42).
* Context lacks the ``marked_content_point`` hook entirely (branch 45 → 21).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.markedcontent import (
    MarkedContentPointWithProperties,
)
from pypdfbox.cos import COSDictionary, COSName


class _EngineWithoutHook(PDFStreamEngine):
    """Stream engine that has no ``marked_content_point`` hook so
    ``getattr(context, 'marked_content_point', None)`` is None."""


# Strip the inherited hook if PDFStreamEngine ever adds one.
if hasattr(_EngineWithoutHook, "marked_content_point"):
    _EngineWithoutHook.marked_content_point = None  # type: ignore[assignment]


class _EngineNullResources(PDFStreamEngine):
    """Stream engine whose ``get_resources`` returns None."""

    def get_resources(self) -> Any:  # type: ignore[override]
        return None


def test_named_operand_with_null_resources_skips_lookup() -> None:
    """``op1`` is a ``COSName`` but ``context.get_resources()`` is None
    — the inner lookup block is skipped and ``prop_dict`` stays None,
    so the hook is never invoked.

    Closes branch (34 → 42)."""
    engine = _EngineNullResources()
    op = MarkedContentPointWithProperties(engine)
    # Should not raise; the early return at ``if prop_dict is None``
    # kicks in.
    op.process(
        Operator.get_operator("DP"),
        [COSName.get_pdf_name("Tag"), COSName.get_pdf_name("MyProps")],
    )


def test_inline_dict_with_engine_missing_hook_is_noop() -> None:
    """Context lacks ``marked_content_point`` — the helper resolves
    ``prop_dict`` to the inline operand but the hook block is skipped.

    Closes branch (45 → 21)."""
    engine = _EngineWithoutHook()
    op = MarkedContentPointWithProperties(engine)
    # Inline dict path → prop_dict is set, hook lookup yields None.
    op.process(
        Operator.get_operator("DP"),
        [COSName.get_pdf_name("Tag"), COSDictionary()],
    )
