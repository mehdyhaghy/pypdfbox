from __future__ import annotations

import pytest

import tests.pdmodel.test_pd_page_content_stream_wave250 as wave250


def test_wave889_shading_fill_stub_materializes_dummy_cos_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def shading_fill(self, shading) -> None:  # noqa: ANN001
        shading_dict = shading.get_cos_object()
        assert shading_dict.get_int("ShadingType") == 2
        raise RuntimeError("shading_fill is not allowed within a text block")

    monkeypatch.setattr(wave250.PDPageContentStream, "shading_fill", shading_fill)

    wave250.test_shading_fill_rejected_inside_text_block()
