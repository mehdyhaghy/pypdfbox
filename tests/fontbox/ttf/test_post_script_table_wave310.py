from __future__ import annotations

from pypdfbox.fontbox.ttf.post_script_table import PostScriptTable


def test_java_style_scalar_aliases_round_trip_wave310() -> None:
    table = PostScriptTable()

    table.setFormatType(2.5)
    table.setItalicAngle(-11.25)
    table.setUnderlinePosition(-90)
    table.setUnderlineThickness(35)
    table.setIsFixedPitch(1)
    table.setMinMemType42(10)
    table.setMaxMemType42(20)
    table.setMinMemType1(30)
    table.setMaxMemType1(40)

    assert table.getFormatType() == table.get_format_type() == 2.5
    assert table.getItalicAngle() == table.get_italic_angle() == -11.25
    assert table.getUnderlinePosition() == table.get_underline_position() == -90
    assert table.getUnderlineThickness() == table.get_underline_thickness() == 35
    assert table.getIsFixedPitch() == table.get_is_fixed_pitch() == 1
    assert table.getMinMemType42() == table.get_min_mem_type42() == 10
    assert table.getMaxMemType42() == table.get_max_mem_type42() == 20
    assert table.getMinMemType1() == table.get_min_mem_type1() == 30
    assert table.getMimMemType1() == table.get_min_mem_type1() == 30
    assert table.getMaxMemType1() == table.get_max_mem_type1() == 40

    table.setMimMemType1(31)
    assert table.getMimMemType1() == table.getMinMemType1() == 31


def test_java_style_glyph_name_aliases_wave310() -> None:
    table = PostScriptTable()

    table.setGlyphNames([".notdef", "A"])
    assert table.getGlyphNames() == table.get_glyph_names() == [".notdef", "A"]
    assert table.getName(1) == table.get_name(1) == "A"
    assert table.getName(2) is None

