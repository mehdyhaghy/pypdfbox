from __future__ import annotations

from pypdfbox.fontbox.font_mapper import FontMapper
from pypdfbox.fontbox.font_mappers import FontMappers


class _Wave857Mapper(FontMapper):
    def get_true_type_font(self, base_font, font_descriptor):  # type: ignore[override]
        return (base_font, font_descriptor, "ttf")

    def get_open_type_font(self, base_font, font_descriptor):  # type: ignore[override]
        return (base_font, font_descriptor, "otf")

    def get_font_box_font(self, base_font, font_descriptor):  # type: ignore[override]
        return (base_font, font_descriptor, "fontbox")


def test_wave857_mapper_stub_branches_return_distinct_sentinels() -> None:
    mapper = _Wave857Mapper()
    descriptor = object()

    assert mapper.get_true_type_font("Base", descriptor) == ("Base", descriptor, "ttf")
    assert mapper.get_open_type_font("Base", descriptor) == ("Base", descriptor, "otf")
    assert mapper.get_font_box_font("Base", descriptor) == (
        "Base",
        descriptor,
        "fontbox",
    )
    assert mapper.get_cid_font("Base", descriptor, object()) is None


def test_wave857_font_mappers_reset_fixture_shape_uses_custom_mapper() -> None:
    mapper = _Wave857Mapper()
    try:
        FontMappers.set(mapper)
        assert FontMappers.instance() is mapper
    finally:
        FontMappers.reset()

    assert FontMappers.instance() is not mapper
