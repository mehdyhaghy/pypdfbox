from __future__ import annotations

from importlib import resources


def test_core_afm_resource_package_exposes_helvetica_metrics() -> None:
    text = (
        resources.files("pypdfbox.pdmodel.font.afm")
        .joinpath("Helvetica.afm")
        .read_text(encoding="latin-1")
    )

    assert "FontName Helvetica" in text
    assert "StartCharMetrics" in text
