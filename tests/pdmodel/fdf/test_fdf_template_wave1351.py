"""Wave 1351 coverage boost: ``FDFTemplate.set_fields`` None-clears path.

Targets lines 78-79 of ``pypdfbox/pdmodel/fdf/fdf_template.py`` —
``set_fields(None)`` removes the ``/Fields`` entry and returns
without building a new array.
"""

from __future__ import annotations

from pypdfbox.pdmodel.fdf import FDFField, FDFTemplate


def test_set_fields_none_clears_existing_entry() -> None:
    """Covers lines 78-79: passing ``None`` removes ``/Fields``."""
    template = FDFTemplate()
    template.set_fields([FDFField()])
    assert template.get_fields() is not None
    template.set_fields(None)
    assert template.get_fields() is None


def test_set_fields_none_when_already_absent_is_safe() -> None:
    """Calling ``set_fields(None)`` against a fresh template is a no-op."""
    template = FDFTemplate()
    template.set_fields(None)
    assert template.get_fields() is None
