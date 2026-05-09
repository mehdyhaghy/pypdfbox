from __future__ import annotations

import pytest

from pypdfbox.multipdf import PDFMergerUtility
from tests.multipdf import test_pdf_merger_utility_wave454 as wave454


def test_wave1175_legacy_empty_fields_helper_get_field_tree_executes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def exercise_dest_field_tree(
        self: object,
        cloner: object,
        dest_form: object,
        src_form: object,
    ) -> None:
        assert dest_form.get_field_tree() == []

    monkeypatch.setattr(
        PDFMergerUtility,
        "_acro_form_legacy_mode",
        exercise_dest_field_tree,
    )

    wave454.test_wave454_acroform_legacy_mode_empty_source_fields_is_noop()
