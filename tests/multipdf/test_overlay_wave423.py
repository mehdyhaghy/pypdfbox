from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObject, COSStream
from pypdfbox.multipdf.overlay import Overlay, Position, _LayoutPage
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle

_OPEN_DOCS: list[PDDocument] = []


@pytest.fixture(autouse=True)
def _close_test_documents():
    yield
    while _OPEN_DOCS:
        doc = _OPEN_DOCS.pop()
        if not doc.is_closed():
            doc.close()


def _doc_with_pages(count: int) -> PDDocument:
    doc = PDDocument()
    _OPEN_DOCS.append(doc)
    for _ in range(count):
        doc.add_page(PDPage(PDRectangle.from_width_height(300.0, 400.0)))
    return doc


def _single_page_overlay(
    *,
    rotation: int = 0,
    media_box: PDRectangle | None = None,
) -> PDDocument:
    doc = PDDocument()
    _OPEN_DOCS.append(doc)
    page = PDPage(media_box or PDRectangle.from_width_height(100.0, 120.0))
    page.set_rotation(rotation)
    doc.add_page(page)
    return doc


def _stream(text: str) -> COSStream:
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(text.encode("latin-1"))
    return stream


def _decoded(stream: COSStream) -> bytes:
    with stream.create_input_stream() as src:
        return src.read()


def test_create_content_stream_list_flattens_arrays_and_indirect_objects() -> None:
    first = _stream("first\n")
    second = _stream("second\n")
    wrapped = COSObject(423, 0, resolved=second)
    contents = COSArray([first, COSArray([wrapped])])

    assert Overlay._create_content_stream_list(contents) == [first, second]  # noqa: SLF001


def test_create_content_stream_list_rejects_unknown_content_type() -> None:
    with pytest.raises(OSError, match="Unknown content type: COSDictionary"):
        Overlay._create_content_stream_list(COSDictionary())  # noqa: SLF001


def test_create_combined_content_stream_copies_all_decoded_stream_bodies() -> None:
    base = _doc_with_pages(1)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    contents = COSArray([_stream("one\n"), COSObject(424, 0, resolved=_stream("two\n"))])

    combined = overlay._create_combined_content_stream(contents)  # noqa: SLF001

    assert _decoded(combined) == b"one\ntwo\n"
    assert combined.has_filter(COSName.get_pdf_name("FlateDecode"))


def test_add_original_content_appends_array_entries_without_resolving_refs() -> None:
    first = _stream("a")
    second = COSObject(1, 0, resolved=_stream("b"))
    original = COSArray([first, second])
    target = COSArray()

    Overlay._add_original_content(original, target)  # noqa: SLF001

    assert target.to_list() == [first, second]


def test_add_original_content_rejects_unknown_content_type() -> None:
    with pytest.raises(OSError, match="Unknown content type: COSDictionary"):
        Overlay._add_original_content(COSDictionary(), COSArray())  # noqa: SLF001


def test_all_pages_overlay_cycles_after_specific_overlays_are_disabled() -> None:
    base = _doc_with_pages(5)
    all_pages = _single_page_overlay()
    all_pages.add_page(PDPage(PDRectangle.from_width_height(150.0, 160.0)))
    explicit = _single_page_overlay()

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_all_pages_overlay_pdf(all_pages)
    overlay.set_specific_page_overlay_pdf({2: explicit})
    overlay._load_pdfs()  # noqa: SLF001

    first = overlay._specific_page_overlay_layout[0]  # noqa: SLF001
    second = overlay._specific_page_overlay_layout[1]  # noqa: SLF001
    assert overlay._get_layout_page(1, 5) is first  # noqa: SLF001
    assert overlay._get_layout_page(2, 5) is second  # noqa: SLF001
    assert overlay._get_layout_page(3, 5) is first  # noqa: SLF001


def test_layout_page_selection_precedence_specific_first_last_odd_even_default() -> None:
    overlay = Overlay()
    specific = _LayoutPage(PDRectangle(), COSStream(), COSDictionary(), 0)
    first = _LayoutPage(PDRectangle(), COSStream(), COSDictionary(), 0)
    last = _LayoutPage(PDRectangle(), COSStream(), COSDictionary(), 0)
    odd = _LayoutPage(PDRectangle(), COSStream(), COSDictionary(), 0)
    even = _LayoutPage(PDRectangle(), COSStream(), COSDictionary(), 0)
    default = _LayoutPage(PDRectangle(), COSStream(), COSDictionary(), 0)
    overlay._specific_page_overlay_layout[3] = specific  # noqa: SLF001
    overlay._first_page_overlay_page = first  # noqa: SLF001
    overlay._last_page_overlay_page = last  # noqa: SLF001
    overlay._odd_page_overlay_page = odd  # noqa: SLF001
    overlay._even_page_overlay_page = even  # noqa: SLF001
    overlay._default_overlay_page = default  # noqa: SLF001

    assert overlay._get_layout_page(1, 6) is first  # noqa: SLF001
    assert overlay._get_layout_page(6, 6) is last  # noqa: SLF001
    assert overlay._get_layout_page(3, 6) is specific  # noqa: SLF001
    assert overlay._get_layout_page(5, 6) is odd  # noqa: SLF001
    assert overlay._get_layout_page(4, 6) is even  # noqa: SLF001


def test_adjust_rotation_reuses_cached_rotated_default_layout() -> None:
    base = _doc_with_pages(1)
    base.get_page(0).set_rotation(90)
    overlay_doc = _single_page_overlay(rotation=270)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(overlay_doc)
    overlay.set_adjust_rotation(True)
    overlay._load_pdfs()  # noqa: SLF001

    adjusted = overlay._get_layout_page(1, 1)  # noqa: SLF001
    same_adjusted = overlay._get_layout_page(1, 1)  # noqa: SLF001

    assert adjusted is same_adjusted
    assert adjusted is not None
    assert adjusted.overlay_rotation == 180


@pytest.mark.parametrize(
    ("rotation", "expected"),
    [
        (90, [0.0, -1.0, 1.0, 0.0, 0.0, 20.0]),
        (180, [-1.0, 0.0, 0.0, -1.0, 20.0, 30.0]),
        (270, [0.0, 1.0, -1.0, 0.0, 30.0, 0.0]),
        (450, [0.0, -1.0, 1.0, 0.0, 0.0, 20.0]),
        (45, [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]),
    ],
)
def test_rotation_matrix_handles_quadrants_and_other_angles(
    rotation: int, expected: list[float]
) -> None:
    layout = _LayoutPage(
        PDRectangle.from_width_height(20.0, 30.0),
        COSStream(),
        COSDictionary(),
        rotation,
    )

    assert Overlay._rotation_matrix(layout) == expected  # noqa: SLF001


def test_create_overlay_stream_swaps_media_box_for_rotated_overlay() -> None:
    base = _doc_with_pages(1)
    page = base.get_page(0)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    layout = _LayoutPage(
        PDRectangle(10.0, 20.0, 110.0, 220.0),
        COSStream(),
        COSDictionary(),
        90,
    )

    stream = overlay._create_overlay_stream(  # noqa: SLF001
        page, layout, COSName.get_pdf_name("OL0")
    )

    assert b"1.0 0.0 0.0 1.0 30.0 140.0  cm\n /OL0 Do" in _decoded(stream)


def test_create_stream_only_compresses_long_content_and_float_formatting() -> None:
    base = _doc_with_pages(1)
    overlay = Overlay()
    overlay.set_input_pdf(base)

    short = overlay._create_stream("short\n")  # noqa: SLF001
    long = overlay._create_stream("x" * 21)  # noqa: SLF001

    assert short.get_filters() is None
    assert long.has_filter(COSName.get_pdf_name("FlateDecode"))
    assert Overlay._float_to_string(1.0) == "1.0"  # noqa: SLF001
    assert Overlay._float_to_string(1.25) == "1.25"  # noqa: SLF001
    assert Overlay._float_to_string(0.000001) == "0.000001"  # noqa: SLF001


def test_process_pages_rejects_unknown_overlay_position() -> None:
    base = _doc_with_pages(1)
    overlay_doc = _single_page_overlay()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(overlay_doc)
    overlay._position = "SIDEWAYS"  # type: ignore[assignment]  # noqa: SLF001

    with pytest.raises(OSError, match="Unknown type of position"):
        overlay.overlay({})


def test_position_value_of_is_case_sensitive() -> None:
    assert Position.value_of("FOREGROUND") is Position.FOREGROUND
    with pytest.raises(ValueError, match="No Position constant"):
        Position.value_of("foreground")
