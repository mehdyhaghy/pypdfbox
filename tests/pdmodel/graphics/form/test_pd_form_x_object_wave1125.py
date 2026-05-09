from __future__ import annotations

import pytest

import tests.pdmodel.graphics.form.test_pd_form_x_object as form_tests


class _MatrixAcceptingForm:
    def set_matrix(self, matrix: object) -> None:
        self.matrix = matrix


def test_matrix_rejects_wrong_length_fallback_assertion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(form_tests, "_new_form", _MatrixAcceptingForm)

    with pytest.raises(
        AssertionError,
        match="set_matrix should reject non-6-element sequences",
    ):
        form_tests.test_matrix_rejects_wrong_length()
