"""Wave 1403 branch round-out for
``AcroFormOrphanWidgetsProcessor.resolve_fields_from_widgets``.

Closes the False-branch arrow in
``pypdfbox/pdmodel/fixup/processor/acro_form_orphan_widgets_processor.py``:

* 79->78 — a field yielded by ``get_field_tree()`` has no
  ``get_default_appearance`` attribute, so the ``if hasattr(...)`` arm is
  False and the loop advances to the next field without calling
  ``ensure_font_resources``.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.pdmodel.fixup.processor.acro_form_orphan_widgets_processor import (
    AcroFormOrphanWidgetsProcessor,
)


class _Resources:
    """Default-resources stub (non-None so the early return is skipped)."""


class _FieldWithoutDA:
    """Terminal-field stub that intentionally lacks
    ``get_default_appearance`` so the hasattr check is False."""


class _AcroForm:
    def __init__(self) -> None:
        self.set_fields_calls: list[Any] = []

    def get_default_resources(self) -> object:
        return _Resources()

    def set_fields(self, fields: list[Any]) -> None:
        self.set_fields_calls.append(fields)

    def get_field_tree(self) -> list[Any]:
        # One field that does NOT expose get_default_appearance.
        return [_FieldWithoutDA()]


class _StubDoc:
    def get_pages(self) -> list[Any]:
        return []


def test_resolve_fields_skips_field_without_default_appearance() -> None:
    """Closes 79->78: the lone field has no ``get_default_appearance`` so
    ``ensure_font_resources`` is never invoked and the loop just advances.
    The processor must not raise."""
    proc = AcroFormOrphanWidgetsProcessor.__new__(AcroFormOrphanWidgetsProcessor)
    proc.document = _StubDoc()  # type: ignore[assignment]

    acro = _AcroForm()
    proc.resolve_fields_from_widgets(acro)

    # set_fields ran with the (empty) collected list; no exception.
    assert acro.set_fields_calls == [[]]
