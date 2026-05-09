from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.common.function import PDFunction
from pypdfbox.rendering.pdf_renderer import PDFRenderer


class _RaisesDomain:
    def get_domain(self) -> Any:
        raise RuntimeError("domain unavailable")


class _BadDomain:
    def get_domain(self) -> Any:
        class Domain:
            def to_float_array(self) -> list[float]:
                raise RuntimeError("bad domain")

        return Domain()


class _BadExtend:
    def get_extend(self) -> object:
        return object()


def test_blend_channel_short_circuits_none_mode_and_clamps_outputs(
    monkeypatch: Any,
) -> None:
    backdrop = Image.new("L", (1, 1), 120)
    source = Image.new("L", (1, 1), 40)

    assert PDFRenderer._blend_channel(backdrop, source, None) is backdrop  # noqa: SLF001

    monkeypatch.setattr(
        PDFRenderer,
        "_blend_scalar",
        staticmethod(lambda _b, _s, _mode: -0.25),
    )
    low = PDFRenderer._blend_channel(backdrop, source, "Synthetic")  # noqa: SLF001
    assert low.getpixel((0, 0)) == 0

    monkeypatch.setattr(
        PDFRenderer,
        "_blend_scalar",
        staticmethod(lambda _b, _s, _mode: 1.25),
    )
    high = PDFRenderer._blend_channel(backdrop, source, "Synthetic")  # noqa: SLF001
    assert high.getpixel((0, 0)) == 255


def test_hsl_helpers_cover_equal_component_fallbacks() -> None:
    assert PDFRenderer._hsl_clip_color(-0.25, -0.25, -0.25) == (  # noqa: SLF001
        0.0,
        0.0,
        0.0,
    )
    assert PDFRenderer._hsl_clip_color(1.25, 1.25, 1.25) == (  # noqa: SLF001
        1.0,
        1.0,
        1.0,
    )
    assert PDFRenderer._hsl_set_sat(0.4, 0.4, 0.4, 0.8) == (  # noqa: SLF001
        0.0,
        0.0,
        0.0,
    )


def test_build_transfer_lookup_handles_factory_none_and_empty_outputs(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(PDFunction, "create", staticmethod(lambda _tr: None))
    assert PDFRenderer._build_transfer_lookup(object()) is None  # noqa: SLF001

    class EmptyThenHalf:
        def eval(self, values: list[float]) -> list[float]:
            if values == [0.0]:
                return []
            return [0.5]

    monkeypatch.setattr(
        PDFunction,
        "create",
        staticmethod(lambda _tr: EmptyThenHalf()),
    )

    lookup = PDFRenderer._build_transfer_lookup(COSName.get_pdf_name("TR"))  # noqa: SLF001

    assert lookup is not None
    assert lookup[0] == 0
    assert lookup[1] == 128


def test_shading_domain_and_extend_malformed_values_default() -> None:
    assert PDFRenderer._shading_domain(_RaisesDomain()) == (0.0, 1.0)  # noqa: SLF001
    assert PDFRenderer._shading_domain(_BadDomain()) == (0.0, 1.0)  # noqa: SLF001
    assert PDFRenderer._shading_extend(_BadExtend()) == (False, False)  # noqa: SLF001
