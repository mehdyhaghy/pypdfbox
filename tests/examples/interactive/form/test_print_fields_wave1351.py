"""Wave 1351 coverage-boost tests for :class:`PrintFields`.

Targets the ``except Exception`` branch inside
:meth:`PrintFields.process_field` (lines 56-57). The existing
``test_process_field_handles_value_exception`` test monkeypatches the
bound method on an instance, but ``PDAcroForm.get_fields()`` rebuilds a
fresh wrapper from the COS tree so the monkeypatch is dropped and the
exception branch is never exercised. Here we call ``process_field``
directly with a stand-in field whose ``get_value_as_string`` raises.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pypdfbox.examples.interactive.form.print_fields import PrintFields
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField


def test_process_field_swallows_get_value_exception(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``process_field`` must catch any exception raised by
    ``get_value_as_string`` and emit an empty value instead."""
    field = Mock(spec=PDTextField)
    field.get_partial_name.return_value = "BadField"
    field.get_value_as_string.side_effect = RuntimeError("boom")

    PrintFields().process_field(field, "|--", "Parent")
    out = capsys.readouterr().out
    # Empty value (no text between ``= `` and ``,``) — exception path
    # supplied ``""`` as the substitute.
    assert "= ,  type=" in out
    assert "BadField" in out
    assert "Parent" in out
