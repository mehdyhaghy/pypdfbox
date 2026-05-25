"""Wave 1403 branch round-out for ``field_triggers``.

Closes ``82->71``: when a trigger setter is absent from the additional-actions
object, ``getattr(annotation_actions, setter, None)`` is None so the
``if fn is not None`` guard takes its False arc and the loop advances to the
next trigger without applying that one.

A real ``PDAnnotationAdditionalActions`` exposes all six setters, so this arc
is only reachable by substituting an object missing one of them — which the
test does via monkeypatch.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.field_triggers import FieldTriggers
from pypdfbox.pdmodel.interactive.action import (
    pd_annotation_additional_actions as _aa_mod,
)
from pypdfbox.pdmodel.pd_document import PDDocument


def test_attach_triggers_skips_absent_setter(
    tmp_path: Path, monkeypatch,
) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "triggered.pdf"

    real_cls = _aa_mod.PDAnnotationAdditionalActions

    class _MissingBlur(real_cls):  # type: ignore[misc, valid-type]
        """Drop one trigger setter so ``getattr`` returns None for it."""

        set_bl = None  # type: ignore[assignment]

    monkeypatch.setattr(
        _aa_mod, "PDAnnotationAdditionalActions", _MissingBlur,
    )

    # The five remaining setters apply; the missing one (set_bl) hits the
    # ``fn is not None`` False arc (82->71) and is skipped.
    FieldTriggers.attach_triggers(str(src), str(dst), "SampleField")
    assert dst.exists()
    with PDDocument.load(str(dst)) as doc:
        assert doc.get_document_catalog().get_acro_form() is not None
