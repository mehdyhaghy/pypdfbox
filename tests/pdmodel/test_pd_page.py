from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.interactive.action import PDActionURI, PDPageAdditionalActions
from pypdfbox.pdmodel.interactive.pagenavigation import PDTransition


def test_default_constructor_us_letter_media_box() -> None:
    page = PDPage()
    mb = page.get_media_box()
    assert mb.width == 612.0
    assert mb.height == 792.0
    # Type entry must be /Page so the writer treats it as a leaf.
    assert page.get_cos_object().get_name(COSName.TYPE) == "Page"  # type: ignore[attr-defined]


def test_constructor_with_pd_rectangle() -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 200.0))
    mb = page.get_media_box()
    assert (mb.lower_left_x, mb.lower_left_y, mb.upper_right_x, mb.upper_right_y) == (
        0.0,
        0.0,
        100.0,
        200.0,
    )


def test_constructor_wraps_existing_dict() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    page = PDPage(raw)
    assert page.get_cos_object() is raw


def test_set_media_box_round_trip() -> None:
    page = PDPage()
    page.set_media_box(PDRectangle(10.0, 20.0, 410.0, 620.0))
    mb = page.get_media_box()
    assert mb.width == 400.0
    assert mb.height == 600.0


def test_get_rotation_default_zero() -> None:
    page = PDPage()
    assert page.get_rotation() == 0


def test_set_rotation() -> None:
    page = PDPage()
    page.set_rotation(90)
    assert page.get_rotation() == 90
    page.set_rotation(450)  # normalised
    assert page.get_rotation() == 90


def test_rotation_inherited_from_parent() -> None:
    parent = COSDictionary()
    parent.set_int(COSName.get_pdf_name("Rotate"), 180)
    child_dict = COSDictionary()
    child_dict.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    child_dict.set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]
    page = PDPage(child_dict)
    assert page.get_rotation() == 180


def test_resources_inherited_from_parent() -> None:
    parent_res = COSDictionary()
    parent = COSDictionary()
    parent.set_item(COSName.RESOURCES, parent_res)  # type: ignore[attr-defined]
    child_dict = COSDictionary()
    child_dict.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    child_dict.set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]
    page = PDPage(child_dict)
    assert page.get_resources().get_cos_object() is parent_res


def test_set_resources_replaces_dict() -> None:
    page = PDPage()
    new_res = COSDictionary()
    page.set_resources(new_res)
    assert page.get_resources().get_cos_object() is new_res


def test_get_contents_empty_when_absent() -> None:
    page = PDPage()
    assert page.get_contents() == b""


def test_get_contents_single_stream() -> None:
    page = PDPage()
    stream = COSStream()
    stream.set_raw_data(b"BT /F0 12 Tf ET")
    page.set_contents(stream)
    assert page.get_contents() == b"BT /F0 12 Tf ET"


def test_get_contents_array_of_streams() -> None:
    page = PDPage()
    s1 = COSStream()
    s1.set_raw_data(b"q")
    s2 = COSStream()
    s2.set_raw_data(b"Q")
    arr = COSArray([s1, s2])
    page.get_cos_object().set_item(COSName.CONTENTS, arr)  # type: ignore[attr-defined]
    assert page.get_contents() == b"q\nQ"


def test_crop_box_falls_back_to_media_box() -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 200.0))
    cb = page.get_crop_box()
    assert cb.width == 100.0
    assert cb.height == 200.0


def test_set_crop_box_overrides_media_box() -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    page.set_crop_box(PDRectangle(10.0, 10.0, 100.0, 100.0))
    cb = page.get_crop_box()
    assert cb.width == 90.0


def test_bleed_trim_art_fall_back_to_crop_box() -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 200.0))
    page.set_crop_box(PDRectangle(5.0, 5.0, 95.0, 195.0))
    for getter in (page.get_bleed_box, page.get_trim_box, page.get_art_box):
        box = getter()
        assert box.width == 90.0
        assert box.height == 190.0


def test_user_unit_default_one() -> None:
    page = PDPage()
    assert page.get_user_unit() == 1.0


def test_user_unit_round_trip() -> None:
    page = PDPage()
    page.set_user_unit(2.5)
    assert page.get_user_unit() == 2.5


def test_stub_methods_raise() -> None:
    page = PDPage()
    assert page.get_annotations() == []
    assert page.get_thumb() is None
    assert page.get_transition() is None
    assert page.get_actions() is None


def test_set_thumb_round_trip() -> None:
    page = PDPage()
    stream = COSStream()
    stream.set_raw_data(b"fake-image-data")
    thumb = PDImageXObject(stream)
    page.set_thumb(thumb)
    resolved = page.get_thumb()
    assert isinstance(resolved, PDImageXObject)
    assert resolved.get_cos_object() is stream
    page.set_thumb(None)
    assert page.get_thumb() is None


def test_set_transition_round_trip() -> None:
    page = PDPage()
    trans = PDTransition(style="Split")
    page.set_transition(trans)
    resolved = page.get_transition()
    assert isinstance(resolved, PDTransition)
    assert resolved.get_style() == "Split"
    page.set_transition(None)
    assert page.get_transition() is None


def test_page_additional_actions_round_trip() -> None:
    page = PDPage()
    actions = PDPageAdditionalActions()
    open_action = PDActionURI()
    open_action.set_uri("https://example.test/open")
    actions.set_o(open_action)

    page.set_actions(actions)
    resolved = page.get_actions()

    assert isinstance(resolved, PDPageAdditionalActions)
    resolved_open = resolved.get_o()
    assert isinstance(resolved_open, PDActionURI)
    assert resolved_open.get_uri() == "https://example.test/open"


def test_constructor_rejects_bad_type() -> None:
    with pytest.raises(TypeError):
        PDPage("nope")  # type: ignore[arg-type]


def test_unwrap_via_cos_integer_rotation() -> None:
    """COSInteger rotation values return ints — guards against accidental
    COSFloat-only handling."""
    page = PDPage()
    page.get_cos_object().set_item(COSName.get_pdf_name("Rotate"), COSInteger.get(270))
    assert page.get_rotation() == 270


def test_set_transition_with_duration_writes_dur() -> None:
    """``set_transition(transition, duration)`` mirrors upstream's
    two-argument overload by also setting ``/Dur`` on the page dict."""
    from pypdfbox.cos import COSFloat

    page = PDPage()
    trans = PDTransition(style="Wipe")
    page.set_transition(trans, 4.5)
    dur = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Dur"))
    assert isinstance(dur, COSFloat)
    assert dur.value == pytest.approx(4.5)
    # And /Trans is still in place.
    resolved = page.get_transition()
    assert isinstance(resolved, PDTransition)
    assert resolved.get_style() == "Wipe"


def test_set_transition_default_duration_omits_dur() -> None:
    """Single-argument ``set_transition`` must not write ``/Dur`` —
    mirrors the upstream one-argument overload exactly."""
    page = PDPage()
    page.set_transition(PDTransition(style="Box"))
    assert page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Dur")) is None


def test_set_viewports_round_trip() -> None:
    """``set_viewports`` accepts ``PDViewportDictionary`` instances and
    is mirrored by ``get_viewports``; ``None`` removes the entry."""
    from pypdfbox.pdmodel.interactive.measurement.pd_viewport_dictionary import (
        PDViewportDictionary,
    )

    page = PDPage()
    vp1 = PDViewportDictionary()
    vp1.get_cos_object().set_name(COSName.get_pdf_name("Name"), "vp1")
    vp2 = PDViewportDictionary()
    vp2.get_cos_object().set_name(COSName.get_pdf_name("Name"), "vp2")
    page.set_viewports([vp1, vp2])

    resolved = page.get_viewports()
    assert resolved is not None
    assert len(resolved) == 2
    assert {vp.get_cos_object().get_name(COSName.get_pdf_name("Name")) for vp in resolved} == {
        "vp1",
        "vp2",
    }

    page.set_viewports(None)
    assert page.get_viewports() is None


def test_set_viewports_rejects_bad_entry() -> None:
    page = PDPage()
    with pytest.raises(TypeError):
        page.set_viewports(["not-a-viewport"])  # type: ignore[list-item]


def test_get_resource_cache_default_none() -> None:
    """A freshly constructed page has no resource cache attached."""
    page = PDPage()
    assert page.get_resource_cache() is None


def test_set_resource_cache_round_trip() -> None:
    """``set_resource_cache`` stores the cache and ``get_resource_cache``
    returns it verbatim; ``None`` detaches."""
    page = PDPage()
    sentinel = object()
    page.set_resource_cache(sentinel)
    assert page.get_resource_cache() is sentinel
    page.set_resource_cache(None)
    assert page.get_resource_cache() is None


def test_inheritable_walks_via_p_alias() -> None:
    """Upstream PDFBox falls back to ``/P`` when ``/Parent`` is absent
    (``COSDictionary.getCOSDictionary(PARENT, P)``); inheritable lookups
    must traverse that legacy short form too."""
    grandparent = COSDictionary()
    grandparent.set_int(COSName.get_pdf_name("Rotate"), 90)
    parent = COSDictionary()
    # Legacy /P short form, not /Parent.
    parent.set_item(COSName.get_pdf_name("P"), grandparent)
    child_dict = COSDictionary()
    child_dict.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    child_dict.set_item(COSName.get_pdf_name("P"), parent)
    page = PDPage(child_dict)
    assert page.get_rotation() == 90


def test_remove_page_resource_from_cache_no_cache_is_noop() -> None:
    """Without a resource cache attached, ``remove_page_resource_from_cache``
    must silently return — mirrors upstream's early-out."""
    page = PDPage()
    # Should not raise even though there's no /Resources and no cache.
    page.remove_page_resource_from_cache()


def test_remove_page_resource_from_cache_purges_indirect_objects() -> None:
    """Indirect resource entries are forwarded to the cache's typed
    removers; direct entries are skipped."""
    from pypdfbox.cos import COSObject

    class _CountingCache:
        def __init__(self) -> None:
            self.removed_xobjects: list[COSObject] = []
            self.removed_fonts: list[COSObject] = []
            self.removed_color_spaces: list[COSObject] = []

        def remove_x_object(self, obj: COSObject) -> None:
            self.removed_xobjects.append(obj)

        def remove_font(self, obj: COSObject) -> None:
            self.removed_fonts.append(obj)

        def remove_color_space(self, obj: COSObject) -> None:
            self.removed_color_spaces.append(obj)

    page = PDPage()
    cache = _CountingCache()
    page.set_resource_cache(cache)

    # Build /Resources with both indirect and direct entries.
    resources = COSDictionary()
    page.get_cos_object().set_item(COSName.RESOURCES, resources)  # type: ignore[attr-defined]

    xobject_dict = COSDictionary()
    indirect_xobject = COSObject(7, resolved=COSStream())
    xobject_dict.set_item(COSName.get_pdf_name("Im0"), indirect_xobject)
    # Direct entry — should be skipped (no remover invocation).
    xobject_dict.set_item(COSName.get_pdf_name("Im1"), COSStream())
    resources.set_item(COSName.get_pdf_name("XObject"), xobject_dict)

    font_dict = COSDictionary()
    indirect_font = COSObject(8, resolved=COSDictionary())
    font_dict.set_item(COSName.get_pdf_name("F0"), indirect_font)
    resources.set_item(COSName.get_pdf_name("Font"), font_dict)

    page.remove_page_resource_from_cache()
    assert cache.removed_xobjects == [indirect_xobject]
    assert cache.removed_fonts == [indirect_font]
    # No /ColorSpace entry — remover never called.
    assert cache.removed_color_spaces == []


def test_remove_page_resource_from_cache_skips_inherited_resources() -> None:
    """Inherited (parent-owned) /Resources must not be purged — upstream
    explicitly limits the purge to ``page.getCOSDictionary(RESOURCES)``,
    *not* the inheritable lookup."""
    from pypdfbox.cos import COSObject

    class _CountingCache:
        def __init__(self) -> None:
            self.calls = 0

        def remove_x_object(self, obj: COSObject) -> None:  # noqa: ARG002
            self.calls += 1

    parent = COSDictionary()
    parent_resources = COSDictionary()
    parent_xobject_dict = COSDictionary()
    parent_xobject_dict.set_item(
        COSName.get_pdf_name("Im0"),
        COSObject(9, resolved=COSStream()),
    )
    parent_resources.set_item(COSName.get_pdf_name("XObject"), parent_xobject_dict)
    parent.set_item(COSName.RESOURCES, parent_resources)  # type: ignore[attr-defined]

    child_dict = COSDictionary()
    child_dict.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    child_dict.set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]
    page = PDPage(child_dict)
    cache = _CountingCache()
    page.set_resource_cache(cache)

    page.remove_page_resource_from_cache()
    # Parent resources are inherited; the purge must not reach them.
    assert cache.calls == 0
