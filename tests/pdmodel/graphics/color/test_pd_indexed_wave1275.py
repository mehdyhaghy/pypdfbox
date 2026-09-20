"""Wave 1275 round-out, re-shaped for the PDFBox 4.0 surface.

The original file exercised ``PDIndexed.set_high_value``. PDFBox 3.0.x
marks ``setHighValue`` ``@Deprecated ... will be removed in 4.0`` and
trunk deletes it outright; pypdfbox 2.0.0 adopts the removal.

The *behaviour* that file pinned is still pinned here, reached through
the surviving API (``set_hival`` plus the :meth:`PDIndexed.create`
factory):

* writing the slot at array position 2 round-trips through the getter;
* there is no setter-side clamp — the read side clamps to 255;
* the removed 3.x name is really gone.
"""

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSNull
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed


def _default_indexed() -> PDIndexed:
    """Build ``[/Indexed /DeviceRGB 255 null]`` — the array PDFBox 3.x's
    no-arg ``PDIndexed()`` produced before 4.0 privatised it."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(255))
    arr.add(COSNull.NULL)
    return PDIndexed(arr)


def test_set_hival_round_trips_through_get_hival() -> None:
    cs = _default_indexed()
    cs.set_hival(7)
    # Same slot upstream's removed ``setHighValue`` wrote: array index 2.
    assert cs.get_hival() == 7
    assert cs.get_cos_object().get_int(2, -1) == 7


def test_set_hival_clamps_via_get_hival_to_255() -> None:
    cs = _default_indexed()
    # No setter-side clamp — the getter clamps on read, exactly as
    # upstream's ``array.set(2, high)`` + ``getHival()`` pair did.
    cs.set_hival(1000)
    assert cs.get_hival() == 255
    assert cs.get_cos_object().get_int(2, -1) == 1000


@pytest.mark.parametrize("value", [0, 1, 15, 64, 255])
def test_set_hival_round_trips_every_legal_value(value: int) -> None:
    a = _default_indexed()
    b = _default_indexed()
    a.set_hival(value)
    b.set_hival(value)
    assert a.get_hival() == b.get_hival() == value


def test_create_factory_fixes_hival_without_any_setter() -> None:
    # The 4.0-shaped construction path: hival is supplied up front.
    cs = PDIndexed.create(PDDeviceRGB.INSTANCE, 1, b"\xff\x00\x00\x00\xff\x00")
    assert cs.get_hival() == 1


def test_set_high_value_is_removed_in_4_0() -> None:
    """``setHighValue`` is gone on trunk; pypdfbox 2.0.0 follows."""
    assert not hasattr(_default_indexed(), "set_high_value")
    assert not hasattr(PDIndexed, "set_high_value")
