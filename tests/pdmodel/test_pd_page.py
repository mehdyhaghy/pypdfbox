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
from pypdfbox.pdmodel.interactive.annotation import PDAnnotation
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
    # ``get_actions`` auto-creates an empty /AA dict on first read (matches
    # upstream PDPage.getActions on line 723); verify the wrapper type
    # rather than a None return.
    assert page.get_actions() is not None


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
        page.set_viewports(["not-a-viewport"])


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


# ---------- get_matrix / random-access content ----------


def test_get_matrix_returns_identity() -> None:
    """Upstream ``PDPage.getMatrix()`` returns ``new Matrix()`` — identity."""
    page = PDPage()
    assert page.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_get_matrix_independent_of_rotation_and_user_unit() -> None:
    """Upstream's ``getMatrix`` ignores ``/Rotate`` and ``/UserUnit`` (the
    upstream ``// todo:`` comment flags this as a known limitation). Verify
    we mirror that exact behaviour rather than helpfully composing them in."""
    page = PDPage()
    page.set_rotation(90)
    page.set_user_unit(2.0)
    assert page.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_get_contents_for_random_access_empty_when_absent() -> None:
    page = PDPage()
    rar = page.get_contents_for_random_access()
    assert rar.length() == 0


def test_get_contents_for_random_access_single_stream() -> None:
    page = PDPage()
    stream = COSStream()
    stream.set_raw_data(b"q 1 0 0 1 0 0 cm Q")
    page.set_contents(stream)
    rar = page.get_contents_for_random_access()
    buf = bytearray(rar.length())
    assert rar.read_into(buf) == len(buf)
    assert bytes(buf) == b"q 1 0 0 1 0 0 cm Q"


def test_get_contents_for_random_access_array_uses_newline_delimiter() -> None:
    """Mirrors upstream's ``DELIMITER = new byte[] { '\\n' }`` between array
    entries — adjacent content streams must not merge their token runs."""
    page = PDPage()
    s1 = COSStream()
    s1.set_raw_data(b"q")
    s2 = COSStream()
    s2.set_raw_data(b"Q")
    arr = COSArray([s1, s2])
    page.get_cos_object().set_item(COSName.CONTENTS, arr)  # type: ignore[attr-defined]
    rar = page.get_contents_for_random_access()
    buf = bytearray(rar.length())
    rar.read_into(buf)
    assert bytes(buf) == b"q\nQ"


def test_get_contents_for_stream_parsing_delegates_to_random_access() -> None:
    """Default ``getContentsForStreamParsing`` shares bytes with
    ``getContentsForRandomAccess``; only upstream's flate-fast-path differs,
    and we don't bypass the filter chain."""
    page = PDPage()
    stream = COSStream()
    stream.set_raw_data(b"BT ET")
    page.set_contents(stream)
    rar = page.get_contents_for_stream_parsing()
    buf = bytearray(rar.length())
    rar.read_into(buf)
    assert bytes(buf) == b"BT ET"


# ---------- clip-to-media-box ----------


def test_get_crop_box_clipped_to_media_box() -> None:
    """Upstream ``PDPage.getCropBox`` runs the ``clipToMediaBox`` step —
    a /CropBox that overhangs the /MediaBox is trimmed to the media bounds
    on read (the stored array is left untouched)."""
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 200.0))
    # CropBox extends past the media box on every side.
    page.set_crop_box(PDRectangle(-50.0, -25.0, 150.0, 250.0))
    cb = page.get_crop_box()
    assert (cb.lower_left_x, cb.lower_left_y, cb.upper_right_x, cb.upper_right_y) == (
        0.0,
        0.0,
        100.0,
        200.0,
    )
    # Stored COS entry is unmodified — clipping is a read-time projection.
    raw = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("CropBox"))
    assert isinstance(raw, COSArray)
    stored = PDRectangle.from_cos_array(raw)
    assert (stored.lower_left_x, stored.upper_right_x) == (-50.0, 150.0)


def test_get_bleed_trim_art_clipped_to_media_box() -> None:
    """All four supplemental boxes (bleed/trim/art) honour ``clipToMediaBox``
    just like the crop box — boxes that overhang the media box are trimmed
    on read."""
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 300.0))
    # Each box overhangs on a different side so we can spot incorrect snapping.
    page.set_bleed_box(PDRectangle(-10.0, 0.0, 50.0, 50.0))
    page.set_trim_box(PDRectangle(0.0, -20.0, 50.0, 50.0))
    page.set_art_box(PDRectangle(150.0, 250.0, 250.0, 350.0))

    bb = page.get_bleed_box()
    assert bb.lower_left_x == 0.0  # snapped from -10
    assert bb.upper_right_x == 50.0

    tb = page.get_trim_box()
    assert tb.lower_left_y == 0.0  # snapped from -20
    assert tb.upper_right_y == 50.0

    ab = page.get_art_box()
    assert ab.upper_right_x == 200.0  # snapped from 250
    assert ab.upper_right_y == 300.0  # snapped from 350


def test_get_crop_box_unaffected_when_inside_media_box() -> None:
    """When the crop box lies entirely within the media box, clipping is
    a no-op — the returned rectangle matches the stored one byte-for-byte."""
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    page.set_crop_box(PDRectangle(36.0, 36.0, 576.0, 756.0))
    cb = page.get_crop_box()
    assert (cb.lower_left_x, cb.lower_left_y, cb.upper_right_x, cb.upper_right_y) == (
        36.0,
        36.0,
        576.0,
        756.0,
    )


# ---------- Wave 200: rotation gate + annotation_filter ----------


def test_get_rotation_non_multiple_of_90_returns_zero() -> None:
    """Upstream gate: ``rotationAngle % 90 == 0`` — anything else
    (45, 89, 271) is treated as not-set and returns 0."""
    page = PDPage()
    page.get_cos_object().set_int(COSName.get_pdf_name("Rotate"), 45)
    assert page.get_rotation() == 0
    page.get_cos_object().set_int(COSName.get_pdf_name("Rotate"), 89)
    assert page.get_rotation() == 0
    page.get_cos_object().set_int(COSName.get_pdf_name("Rotate"), 271)
    assert page.get_rotation() == 0


def test_get_rotation_negative_multiple_of_90_wraps_to_positive() -> None:
    """Upstream wraps via ``(angle % 360 + 360) % 360`` so negatives stay
    on the 0/90/180/270 axis."""
    page = PDPage()
    page.get_cos_object().set_int(COSName.get_pdf_name("Rotate"), -90)
    assert page.get_rotation() == 270
    page.get_cos_object().set_int(COSName.get_pdf_name("Rotate"), -360)
    assert page.get_rotation() == 0
    page.get_cos_object().set_int(COSName.get_pdf_name("Rotate"), -450)
    assert page.get_rotation() == 270


def test_get_rotation_large_multiple_of_90() -> None:
    """Multiples of 90 above 360 still reduce mod 360."""
    page = PDPage()
    page.get_cos_object().set_int(COSName.get_pdf_name("Rotate"), 720)
    assert page.get_rotation() == 0
    page.get_cos_object().set_int(COSName.get_pdf_name("Rotate"), 810)
    assert page.get_rotation() == 90


def test_get_rotation_non_numeric_returns_zero() -> None:
    """A non-COSNumber ``/Rotate`` (e.g. accidental name) → 0."""
    page = PDPage()
    page.get_cos_object().set_item(
        COSName.get_pdf_name("Rotate"),
        COSName.get_pdf_name("Foo"),
    )
    assert page.get_rotation() == 0


def test_get_annotations_with_filter_keeps_only_accepted() -> None:
    """``annotation_filter`` mirrors upstream's ``AnnotationFilter`` —
    only annotations the callable returns truthy for are kept."""
    page = PDPage()
    arr = COSArray()
    for subtype in ("Link", "Text", "Link"):
        ann = COSDictionary()
        ann.set_item(
            COSName.get_pdf_name("Subtype"),
            COSName.get_pdf_name(subtype),
        )
        arr.add(ann)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), arr)

    def keep_links(annotation: PDAnnotation) -> bool:
        subtype = annotation.get_cos_object().get_name(COSName.get_pdf_name("Subtype"))
        return subtype == "Link"

    filtered = page.get_annotations(keep_links)
    assert len(filtered) == 2
    for ann in filtered:
        assert ann.get_cos_object().get_name(
            COSName.get_pdf_name("Subtype")
        ) == "Link"


def test_get_annotations_with_filter_none_is_accept_all() -> None:
    """Passing ``None`` (or omitting) matches the upstream no-arg overload."""
    page = PDPage()
    arr = COSArray()
    for subtype in ("Link", "Text", "FreeText"):
        ann = COSDictionary()
        ann.set_item(
            COSName.get_pdf_name("Subtype"),
            COSName.get_pdf_name(subtype),
        )
        arr.add(ann)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), arr)
    assert len(page.get_annotations()) == 3
    assert len(page.get_annotations(None)) == 3
    # Accept-all callable is equivalent.
    assert len(page.get_annotations(lambda _a: True)) == 3
    # Reject-all leaves an empty list.
    assert page.get_annotations(lambda _a: False) == []


def test_get_annotations_skips_null_entries() -> None:
    """Upstream's ``if (item == null) continue;`` defensive skip — we must
    not crash when a /Annots entry resolves to null."""
    from pypdfbox.cos import COSNull

    page = PDPage()
    arr = COSArray()
    arr.add(COSNull.NULL)
    legit = COSDictionary()
    legit.set_item(
        COSName.get_pdf_name("Subtype"),
        COSName.get_pdf_name("Link"),
    )
    arr.add(legit)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), arr)
    result = page.get_annotations()
    assert len(result) == 1


# ---------- Wave 230: get_actions auto-create + has_* + duration ----------


def test_get_actions_auto_creates_empty_aa() -> None:
    """Upstream ``PDPage.getActions`` (line 723) materialises an empty
    ``/AA`` dictionary in place when the entry is absent, so subsequent
    callers can attach trigger actions without having to wire the
    sub-dictionary themselves."""
    page = PDPage()
    # Sanity: /AA absent before first call.
    assert page.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("AA")
    ) is None

    actions = page.get_actions()
    assert actions is not None
    # /AA was materialised in place — and the wrapper points at it.
    aa = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("AA"))
    assert isinstance(aa, COSDictionary)
    assert actions.get_cos_object() is aa

    # Calling again returns the same underlying dict (idempotent).
    again = page.get_actions()
    assert again.get_cos_object() is aa


def test_get_actions_does_not_overwrite_existing_aa() -> None:
    """If ``/AA`` already exists the auto-create path is skipped — the
    existing dict is wrapped verbatim."""
    page = PDPage()
    existing_aa = COSDictionary()
    existing_aa.set_item(
        COSName.get_pdf_name("O"),
        COSDictionary(),
    )
    page.get_cos_object().set_item(COSName.get_pdf_name("AA"), existing_aa)

    resolved = page.get_actions()
    assert resolved.get_cos_object() is existing_aa


def test_get_duration_default_none() -> None:
    page = PDPage()
    assert page.get_duration() is None


def test_set_duration_round_trip() -> None:
    page = PDPage()
    page.set_duration(3.0)
    assert page.get_duration() == pytest.approx(3.0)
    # ``None`` removes the entry.
    page.set_duration(None)
    assert page.get_duration() is None
    assert page.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Dur")
    ) is None


def test_get_duration_reads_integer_dur() -> None:
    """``/Dur`` may be stored as an integer too (PDF spec: number) — the
    getter must coerce to float rather than crash."""
    page = PDPage()
    page.get_cos_object().set_item(
        COSName.get_pdf_name("Dur"),
        COSInteger.get(5),
    )
    assert page.get_duration() == 5.0


def test_set_transition_with_duration_then_read_back() -> None:
    """``set_transition(transition, duration)`` writes /Dur — the new
    ``get_duration`` getter reads it back."""
    page = PDPage()
    page.set_transition(PDTransition(style="Fade"), 2.25)
    assert page.get_duration() == pytest.approx(2.25)


def test_has_metadata() -> None:
    page = PDPage()
    assert page.has_metadata() is False
    metadata_stream = COSStream()
    page.get_cos_object().set_item(COSName.get_pdf_name("Metadata"), metadata_stream)
    assert page.has_metadata() is True


def test_has_thumb() -> None:
    page = PDPage()
    assert page.has_thumb() is False
    page.set_thumb(PDImageXObject(COSStream()))
    assert page.has_thumb() is True


def test_has_transition() -> None:
    page = PDPage()
    assert page.has_transition() is False
    page.set_transition(PDTransition(style="Box"))
    assert page.has_transition() is True
    page.set_transition(None)
    assert page.has_transition() is False


def test_has_actions_does_not_auto_materialise() -> None:
    """``has_actions`` is a read-only probe — calling it on a page
    without /AA must not write an empty /AA dict (would mutate the
    page on every probe and break differential round-trips)."""
    page = PDPage()
    assert page.has_actions() is False
    # Verify no accidental write.
    assert page.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("AA")
    ) is None

    # Empty /AA still reports True: has_* helpers are direct key-presence
    # checks and do not inspect the action triggers.
    page.get_cos_object().set_item(
        COSName.get_pdf_name("AA"), COSDictionary()
    )
    assert page.has_actions() is True

    # Populated /AA reports True.
    aa = COSDictionary()
    aa.set_item(COSName.get_pdf_name("O"), COSDictionary())
    page.get_cos_object().set_item(COSName.get_pdf_name("AA"), aa)
    assert page.has_actions() is True


def test_has_annotations() -> None:
    page = PDPage()
    assert page.has_annotations() is False
    # Empty array still reports True: has_* helpers are direct key-presence
    # checks and do not inspect typed contents.
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), COSArray())
    assert page.has_annotations() is True
    # Populated array — True.
    arr = COSArray()
    ann = COSDictionary()
    ann.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Link")
    )
    arr.add(ann)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), arr)
    assert page.has_annotations() is True


def test_has_thread_beads() -> None:
    from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead

    page = PDPage()
    assert page.has_thread_beads() is False
    page.set_thread_beads([PDThreadBead(COSDictionary())])
    assert page.has_thread_beads() is True
    page.set_thread_beads(None)
    assert page.has_thread_beads() is False


def test_has_viewports() -> None:
    from pypdfbox.pdmodel.interactive.measurement.pd_viewport_dictionary import (
        PDViewportDictionary,
    )

    page = PDPage()
    assert page.has_viewports() is False
    page.set_viewports([PDViewportDictionary()])
    assert page.has_viewports() is True
    page.set_viewports(None)
    assert page.has_viewports() is False


def test_has_group() -> None:
    page = PDPage()
    assert page.has_group() is False
    page.set_group(COSDictionary())
    assert page.has_group() is True
    page.set_group(None)
    assert page.has_group() is False


def test_has_tab_order() -> None:
    page = PDPage()
    assert page.has_tab_order() is False
    page.set_tab_order("R")
    assert page.has_tab_order() is True
    page.set_tab_order(None)
    assert page.has_tab_order() is False


# ---------- TAB_ORDER_* class constants ----------


def test_tab_order_constants_exposed_on_class() -> None:
    # Class-level access (no instantiation needed).
    assert PDPage.TAB_ORDER_ROW == "R"
    assert PDPage.TAB_ORDER_COLUMN == "C"
    assert PDPage.TAB_ORDER_STRUCTURE == "S"
    assert PDPage.TAB_ORDER_ANNOTATIONS_ARRAY == "A"
    assert PDPage.TAB_ORDER_WIDGETS == "W"


def test_tab_order_constants_exposed_on_instance() -> None:
    page = PDPage()
    # Instance access mirrors class access — Python doesn't need an explicit
    # static modifier but PDFBox-style ``page.TAB_ORDER_ROW`` should work.
    assert page.TAB_ORDER_ROW == "R"
    assert page.TAB_ORDER_COLUMN == "C"
    assert page.TAB_ORDER_STRUCTURE == "S"
    assert page.TAB_ORDER_ANNOTATIONS_ARRAY == "A"
    assert page.TAB_ORDER_WIDGETS == "W"


def test_tab_order_constants_round_trip_through_set_get() -> None:
    page = PDPage()
    for code in (
        PDPage.TAB_ORDER_ROW,
        PDPage.TAB_ORDER_COLUMN,
        PDPage.TAB_ORDER_STRUCTURE,
        PDPage.TAB_ORDER_ANNOTATIONS_ARRAY,
        PDPage.TAB_ORDER_WIDGETS,
    ):
        page.set_tab_order(code)
        assert page.get_tab_order() == code


def test_tab_order_constants_are_unique() -> None:
    codes = {
        PDPage.TAB_ORDER_ROW,
        PDPage.TAB_ORDER_COLUMN,
        PDPage.TAB_ORDER_STRUCTURE,
        PDPage.TAB_ORDER_ANNOTATIONS_ARRAY,
        PDPage.TAB_ORDER_WIDGETS,
    }
    assert len(codes) == 5


# ---------- is_rotated() ----------


def test_is_rotated_default_false() -> None:
    page = PDPage()
    assert page.is_rotated() is False


def test_is_rotated_true_after_set() -> None:
    page = PDPage()
    page.set_rotation(90)
    assert page.is_rotated() is True
    page.set_rotation(180)
    assert page.is_rotated() is True
    page.set_rotation(270)
    assert page.is_rotated() is True


def test_is_rotated_false_after_zero() -> None:
    page = PDPage()
    page.set_rotation(0)
    assert page.is_rotated() is False


def test_is_rotated_false_for_full_turn() -> None:
    # 360 normalises to 0 in get_rotation().
    page = PDPage()
    page.set_rotation(360)
    assert page.get_rotation() == 0
    assert page.is_rotated() is False


def test_is_rotated_handles_negative_rotation() -> None:
    page = PDPage()
    page.set_rotation(-90)
    # -90 normalises to 270, not 0.
    assert page.get_rotation() == 270
    assert page.is_rotated() is True


def test_is_rotated_inherits_from_parent() -> None:
    parent = COSDictionary()
    parent.set_int(COSName.get_pdf_name("Rotate"), 270)
    child = COSDictionary()
    child.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    child.set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]
    page = PDPage(child)
    assert page.is_rotated() is True


def test_is_rotated_false_for_off_axis_rotation() -> None:
    # 45 is not a multiple of 90; get_rotation() reports 0, so is_rotated()
    # must follow suit.
    page = PDPage()
    page.get_cos_object().set_int(COSName.get_pdf_name("Rotate"), 45)
    assert page.get_rotation() == 0
    assert page.is_rotated() is False


# ---------- get_rotation_in_radians() ----------


def test_get_rotation_in_radians_default_zero() -> None:
    import math

    page = PDPage()
    assert page.get_rotation_in_radians() == pytest.approx(0.0)
    assert page.get_rotation_in_radians() == math.radians(0)


def test_get_rotation_in_radians_quadrants() -> None:
    import math

    page = PDPage()
    page.set_rotation(90)
    assert page.get_rotation_in_radians() == pytest.approx(math.pi / 2)
    page.set_rotation(180)
    assert page.get_rotation_in_radians() == pytest.approx(math.pi)
    page.set_rotation(270)
    assert page.get_rotation_in_radians() == pytest.approx(3 * math.pi / 2)


def test_get_rotation_in_radians_normalises_through_get_rotation() -> None:
    import math

    # 450 → normalised to 90 → π/2 rad.
    page = PDPage()
    page.set_rotation(450)
    assert page.get_rotation() == 90
    assert page.get_rotation_in_radians() == pytest.approx(math.pi / 2)


def test_get_rotation_in_radians_full_turn_zero() -> None:
    page = PDPage()
    page.set_rotation(360)
    assert page.get_rotation_in_radians() == pytest.approx(0.0)


def test_get_rotation_in_radians_off_axis_returns_zero() -> None:
    # Same rule as is_rotated — off-axis falls through to 0 rad.
    page = PDPage()
    page.get_cos_object().set_int(COSName.get_pdf_name("Rotate"), 33)
    assert page.get_rotation_in_radians() == pytest.approx(0.0)


def test_get_rotation_in_radians_inherits_from_parent() -> None:
    import math

    parent = COSDictionary()
    parent.set_int(COSName.get_pdf_name("Rotate"), 180)
    child = COSDictionary()
    child.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    child.set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]
    page = PDPage(child)
    assert page.get_rotation_in_radians() == pytest.approx(math.pi)


def test_get_rotation_in_radians_returns_float() -> None:
    page = PDPage()
    page.set_rotation(90)
    value = page.get_rotation_in_radians()
    assert isinstance(value, float)
