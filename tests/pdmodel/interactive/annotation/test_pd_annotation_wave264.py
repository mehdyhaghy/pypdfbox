"""Wave 264 — pdmodel/interactive/annotation small parity gaps for the
``PDAnnotation`` base class.

Covers:
- upstream-canonical ``get_appearance`` / ``set_appearance`` aliases
  for the historical pypdfbox ``get_appearance_dictionary`` /
  ``set_appearance_dictionary`` spelling (Java
  :code:`PDAnnotation.getAppearance()` is the canonical name upstream).
- ``set_appearance_state`` accepting :class:`COSName` directly,
  mirroring upstream's ``setAppearanceState(COSName)`` overload.
- ``set_color`` accepting a typed :class:`PDColor` via duck-typed
  ``to_cos_array()``, mirroring upstream's
  ``setColor(PDColor)`` while keeping the looser pypdfbox surface.
- own-dictionary ``has_*`` predicates: ``has_appearance`` /
  ``has_rectangle`` / ``has_color`` / ``has_contents``. Cheaper than
  the corresponding ``get_*() is not None`` idioms and mean callers
  don't have to construct typed wrappers just to test for entry
  presence.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationLink,
    PDAnnotationText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)

# ---------- get_appearance / set_appearance aliases ----------


def test_get_appearance_alias_returns_same_as_get_appearance_dictionary() -> None:
    """Java :code:`getAppearance()` is the canonical name; we expose
    both spellings."""
    annot = PDAnnotationLink()
    ap_dict = COSDictionary()
    annot.get_cos_object().set_item(COSName.get_pdf_name("AP"), ap_dict)

    via_alias = annot.get_appearance()
    via_long = annot.get_appearance_dictionary()
    assert via_alias is not None
    assert via_long is not None
    assert isinstance(via_alias, PDAppearanceDictionary)
    # Both wrappers must point at the same backing dictionary.
    assert via_alias.get_cos_object() is via_long.get_cos_object()


def test_get_appearance_returns_none_when_ap_absent() -> None:
    annot = PDAnnotationLink()
    assert annot.get_appearance() is None


def test_get_appearance_returns_none_when_ap_not_a_dict() -> None:
    annot = PDAnnotationLink()
    annot.get_cos_object().set_item(
        COSName.get_pdf_name("AP"), COSArray([COSInteger.get(1)])
    )
    assert annot.get_appearance() is None


def test_set_appearance_writes_ap_entry() -> None:
    annot = PDAnnotationText()
    ap = PDAppearanceDictionary()
    annot.set_appearance(ap)
    stored = annot.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("AP")
    )
    assert stored is ap.get_cos_object()


def test_set_appearance_none_removes_entry() -> None:
    annot = PDAnnotationText()
    annot.set_appearance(PDAppearanceDictionary())
    assert annot.has_appearance()
    annot.set_appearance(None)
    assert not annot.has_appearance()
    assert (
        annot.get_cos_object().get_dictionary_object(COSName.get_pdf_name("AP"))
        is None
    )


def test_set_appearance_accepts_raw_cos_dictionary() -> None:
    annot = PDAnnotationLink()
    raw = COSDictionary()
    annot.set_appearance(raw)
    assert (
        annot.get_cos_object().get_dictionary_object(COSName.get_pdf_name("AP"))
        is raw
    )


# ---------- has_appearance ----------


def test_has_appearance_default_false() -> None:
    assert not PDAnnotationLink().has_appearance()


def test_has_appearance_true_when_ap_set() -> None:
    annot = PDAnnotationLink()
    annot.set_appearance(PDAppearanceDictionary())
    assert annot.has_appearance()


def test_has_appearance_ignores_non_dict_value() -> None:
    """A malformed ``/AP`` (e.g. an array) must not count as having
    an appearance."""
    annot = PDAnnotationLink()
    annot.get_cos_object().set_item(COSName.get_pdf_name("AP"), COSArray())
    assert not annot.has_appearance()


def test_has_appearance_false_after_clear() -> None:
    annot = PDAnnotationLink()
    annot.set_appearance(PDAppearanceDictionary())
    annot.set_appearance(None)
    assert not annot.has_appearance()


# ---------- set_appearance_state(COSName) overload ----------


def test_set_appearance_state_accepts_cos_name() -> None:
    """Mirror upstream's ``setAppearanceState(COSName)`` overload."""
    annot = PDAnnotationText()
    annot.set_appearance_state(COSName.get_pdf_name("On"))
    assert annot.get_appearance_state() == "On"


def test_set_appearance_state_string_still_works() -> None:
    annot = PDAnnotationText()
    annot.set_appearance_state("Off")
    assert annot.get_appearance_state() == "Off"


def test_set_appearance_state_cos_name_writes_name_object() -> None:
    """The stored value must be a ``COSName`` object — not a COS string —
    even when the caller passes a ``COSName`` directly."""
    annot = PDAnnotationText()
    annot.set_appearance_state(COSName.get_pdf_name("Yes"))
    raw = annot.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("AS")
    )
    assert isinstance(raw, COSName)
    assert raw.name == "Yes"


def test_set_appearance_state_none_removes_entry() -> None:
    annot = PDAnnotationText()
    annot.set_appearance_state(COSName.get_pdf_name("On"))
    annot.set_appearance_state(None)
    assert annot.get_appearance_state() is None


def test_set_appearance_state_cos_name_overwrites_string_state() -> None:
    annot = PDAnnotationText()
    annot.set_appearance_state("Off")
    annot.set_appearance_state(COSName.get_pdf_name("On"))
    assert annot.get_appearance_state() == "On"


# ---------- set_color(PDColor) ----------


def test_set_color_accepts_pd_color() -> None:
    """Mirror upstream's ``setColor(PDColor)`` — duck-typed via
    ``to_cos_array()`` to keep the rendering cluster out of the
    annotation import graph."""
    annot = PDAnnotationLink()
    color = PDColor([1.0, 0.5, 0.25], PDDeviceRGB.INSTANCE)
    annot.set_color(color)
    cos = annot.get_color()
    assert cos is not None
    assert cos.size() == 3
    assert cos.get(0).value == pytest.approx(1.0)
    assert cos.get(1).value == pytest.approx(0.5)
    assert cos.get(2).value == pytest.approx(0.25)


def test_set_color_pd_color_components_are_cos_floats() -> None:
    annot = PDAnnotationLink()
    annot.set_color(PDColor([0.0, 0.0, 0.0], PDDeviceRGB.INSTANCE))
    cos = annot.get_color()
    assert cos is not None
    for i in range(cos.size()):
        assert isinstance(cos.get(i), COSFloat)


def test_set_color_pd_color_overwrites_existing_array() -> None:
    annot = PDAnnotationLink()
    annot.set_color([0.1, 0.2, 0.3])
    annot.set_color(PDColor([0.9, 0.8, 0.7], PDDeviceRGB.INSTANCE))
    cos = annot.get_color()
    assert cos is not None
    assert cos.size() == 3
    assert cos.get(0).value == pytest.approx(0.9)


def test_set_color_rejects_unknown_object_type() -> None:
    annot = PDAnnotationLink()

    class _NotAColor:
        pass

    with pytest.raises(TypeError):
        annot.set_color(_NotAColor())  # type: ignore[arg-type]


def test_set_color_rejects_object_with_non_cos_array_to_cos_array() -> None:
    """Duck-typed ``to_cos_array()`` returning a non-COSArray must be
    rejected — otherwise we'd silently corrupt ``/C``."""
    annot = PDAnnotationLink()

    class _Bogus:
        def to_cos_array(self) -> object:
            return "not a cos array"

    with pytest.raises(TypeError):
        annot.set_color(_Bogus())  # type: ignore[arg-type]


# ---------- has_rectangle ----------


def test_has_rectangle_default_false() -> None:
    assert not PDAnnotationLink().has_rectangle()


def test_has_rectangle_true_when_rect_present() -> None:
    annot = PDAnnotationLink()
    annot.get_cos_object().set_item(
        COSName.get_pdf_name("Rect"),
        COSArray([COSFloat(0.0), COSFloat(0.0), COSFloat(100.0), COSFloat(50.0)]),
    )
    assert annot.has_rectangle()


def test_has_rectangle_false_for_short_array() -> None:
    """Upstream rejects rectangles with fewer than 4 numbers — our
    predicate must match."""
    annot = PDAnnotationLink()
    annot.get_cos_object().set_item(
        COSName.get_pdf_name("Rect"),
        COSArray([COSFloat(0.0), COSFloat(0.0)]),
    )
    assert not annot.has_rectangle()


# ---------- has_color ----------


def test_has_color_default_false() -> None:
    assert not PDAnnotationLink().has_color()


def test_has_color_true_when_c_set_via_list() -> None:
    annot = PDAnnotationLink()
    annot.set_color([1.0, 0.0, 0.0])
    assert annot.has_color()


def test_has_color_false_after_clear() -> None:
    annot = PDAnnotationLink()
    annot.set_color([1.0, 0.0, 0.0])
    annot.set_color(None)
    assert not annot.has_color()


def test_has_color_ignores_non_array_value() -> None:
    """A malformed ``/C`` (e.g. a number) must not count as having
    a color."""
    annot = PDAnnotationLink()
    annot.get_cos_object().set_item(COSName.get_pdf_name("C"), COSInteger.get(0))
    assert not annot.has_color()


# ---------- has_contents ----------


def test_has_contents_default_false() -> None:
    assert not PDAnnotationLink().has_contents()


def test_has_contents_true_after_set() -> None:
    annot = PDAnnotationLink()
    annot.set_contents("hello")
    assert annot.has_contents()


def test_has_contents_false_for_empty_string() -> None:
    """Empty ``/Contents`` is treated as 'no contents' by the predicate
    — saves callers an extra equality check."""
    annot = PDAnnotationLink()
    annot.set_contents("")
    assert not annot.has_contents()


def test_has_contents_false_after_clear() -> None:
    annot = PDAnnotationLink()
    annot.set_contents("note")
    annot.set_contents(None)
    assert not annot.has_contents()


# ---------- aliases preserve no-camelCase rule ----------


def test_pd_annotation_has_no_camelcase_aliases() -> None:
    """Wave 264 must not introduce ``getAppearance``/``setAppearance``
    Java-name aliases — only snake_case is allowed (project memory)."""
    members = dir(PDAnnotation)
    for forbidden in (
        "getAppearance",
        "setAppearance",
        "getRectangle",
        "setRectangle",
        "getColor",
        "setColor",
        "getAppearanceState",
        "setAppearanceState",
        "hasAppearance",
        "hasRectangle",
        "hasColor",
        "hasContents",
    ):
        assert forbidden not in members, (
            f"PDAnnotation must not expose camelCase alias {forbidden!r}"
        )
