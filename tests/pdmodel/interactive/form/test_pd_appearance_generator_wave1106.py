from __future__ import annotations

from contextlib import suppress

from pypdfbox.pdmodel.interactive.form import PDAppearanceGenerator
from tests.pdmodel.interactive.form import test_pd_appearance_generator_wave418


def test_wave1106_choice_fallback_helper_exercises_get_options_cleanup(
    monkeypatch,
) -> None:
    class GeneratorThatProbesOptions:
        def generate(self, field: object) -> None:
            with suppress(RuntimeError):
                field.get_options()
            PDAppearanceGenerator().generate(field)

    monkeypatch.setattr(
        test_pd_appearance_generator_wave418,
        "PDAppearanceGenerator",
        GeneratorThatProbesOptions,
    )

    test_pd_appearance_generator_wave418.test_choice_option_lookup_failure_falls_back_to_selected_values()
