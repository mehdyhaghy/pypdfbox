from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import ColorantType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    c = ColorantType(metadata)
    assert c.get_namespace() == "http://ns.adobe.com/xap/1.0/g/"
    assert c.get_prefix() == "xmpG"


def test_field_constants() -> None:
    assert ColorantType.A == "A"
    assert ColorantType.B == "B"
    assert ColorantType.L == "L"
    assert ColorantType.BLACK == "black"
    assert ColorantType.CYAN == "cyan"
    assert ColorantType.MAGENTA == "magenta"
    assert ColorantType.YELLOW == "yellow"
    assert ColorantType.BLUE == "blue"
    assert ColorantType.GREEN == "green"
    assert ColorantType.RED == "red"
    assert ColorantType.MODE == "mode"
    assert ColorantType.SWATCH_NAME == "swatchName"
    assert ColorantType.TYPE == "type"


def test_set_and_get_cmyk(metadata: XMPMetadata) -> None:
    c = ColorantType(metadata)
    c.add_simple_property(ColorantType.CYAN, 0.1)
    c.add_simple_property(ColorantType.MAGENTA, 0.2)
    c.add_simple_property(ColorantType.YELLOW, 0.3)
    c.add_simple_property(ColorantType.BLACK, 0.4)
    assert c.get_property_value_as_string(ColorantType.CYAN) == "0.1"
    assert c.get_property_value_as_string(ColorantType.BLACK) == "0.4"


def test_set_and_get_rgb(metadata: XMPMetadata) -> None:
    c = ColorantType(metadata)
    c.add_simple_property(ColorantType.RED, 255)
    c.add_simple_property(ColorantType.GREEN, 128)
    c.add_simple_property(ColorantType.BLUE, 64)
    assert c.get_property_value_as_string(ColorantType.RED) == "255"
    assert c.get_property_value_as_string(ColorantType.GREEN) == "128"
    assert c.get_property_value_as_string(ColorantType.BLUE) == "64"


def test_set_and_get_lab(metadata: XMPMetadata) -> None:
    c = ColorantType(metadata)
    c.add_simple_property(ColorantType.L, 50.0)
    c.add_simple_property(ColorantType.A, 12)
    c.add_simple_property(ColorantType.B, -34)
    assert c.get_property_value_as_string(ColorantType.L) == "50.0"
    assert c.get_property_value_as_string(ColorantType.A) == "12"
    assert c.get_property_value_as_string(ColorantType.B) == "-34"


def test_set_and_get_descriptive(metadata: XMPMetadata) -> None:
    c = ColorantType(metadata)
    c.add_simple_property(ColorantType.SWATCH_NAME, "MySwatch")
    c.add_simple_property(ColorantType.MODE, "RGB")
    c.add_simple_property(ColorantType.TYPE, "PROCESS")
    assert c.get_property_value_as_string(ColorantType.SWATCH_NAME) == "MySwatch"
    assert c.get_property_value_as_string(ColorantType.MODE) == "RGB"
    assert c.get_property_value_as_string(ColorantType.TYPE) == "PROCESS"


def test_typed_lab_accessors(metadata: XMPMetadata) -> None:
    c = ColorantType(metadata)
    c.set_l(50.0)
    c.set_a(12)
    c.set_b(-34)
    assert c.get_l() == pytest.approx(50.0)
    assert c.get_a() == 12
    assert c.get_b() == -34


def test_typed_cmyk_accessors(metadata: XMPMetadata) -> None:
    c = ColorantType(metadata)
    c.set_cyan(0.1)
    c.set_magenta(0.2)
    c.set_yellow(0.3)
    c.set_black(0.4)
    assert c.get_cyan() == pytest.approx(0.1)
    assert c.get_magenta() == pytest.approx(0.2)
    assert c.get_yellow() == pytest.approx(0.3)
    assert c.get_black() == pytest.approx(0.4)


def test_typed_rgb_accessors(metadata: XMPMetadata) -> None:
    c = ColorantType(metadata)
    c.set_red(255)
    c.set_green(128)
    c.set_blue(64)
    assert c.get_red() == 255
    assert c.get_green() == 128
    assert c.get_blue() == 64


def test_typed_descriptive_accessors(metadata: XMPMetadata) -> None:
    c = ColorantType(metadata)
    c.set_swatch_name("MySwatch")
    c.set_mode("RGB")
    c.set_type("PROCESS")
    assert c.get_swatch_name() == "MySwatch"
    assert c.get_mode() == "RGB"
    assert c.get_type() == "PROCESS"


def test_typed_initial_none(metadata: XMPMetadata) -> None:
    c = ColorantType(metadata)
    assert c.get_l() is None
    assert c.get_a() is None
    assert c.get_b() is None
    assert c.get_cyan() is None
    assert c.get_magenta() is None
    assert c.get_yellow() is None
    assert c.get_black() is None
    assert c.get_red() is None
    assert c.get_green() is None
    assert c.get_blue() is None
    assert c.get_mode() is None
    assert c.get_swatch_name() is None
    assert c.get_type() is None
