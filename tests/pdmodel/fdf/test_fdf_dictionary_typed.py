from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.fdf import (
    FDFDictionary,
    FDFJavaScript,
    FDFPage,
    FDFPageInfo,
    FDFTemplate,
)


def test_get_pages_returns_typed_fdf_page_list() -> None:
    """``get_pages`` wraps each ``/Pages`` entry in :class:`FDFPage`,
    matching upstream ``FDFDictionary.getPages() -> List<FDFPage>``."""
    fdf = FDFDictionary()
    p1 = FDFPage()
    p2 = FDFPage()
    fdf.set_pages([p1, p2])
    pages = fdf.get_pages()
    assert pages is not None
    assert len(pages) == 2
    assert all(isinstance(page, FDFPage) for page in pages)
    # identity is preserved at the COS-dictionary level (the typed wrapper
    # may be re-instantiated on each call, but the underlying dict is the
    # same instance)
    assert pages[0].get_cos_object() is p1.get_cos_object()
    assert pages[1].get_cos_object() is p2.get_cos_object()


def test_get_pages_preserves_nested_attributes() -> None:
    """Verify a round-tripped page still carries its ``/Templates`` and
    ``/Info`` sub-entries — confirming we wrap the same dictionary, not a
    fresh copy."""
    fdf = FDFDictionary()
    page = FDFPage()
    tpl = FDFTemplate()
    tpl.set_rename(True)
    page.set_templates([tpl])
    info = FDFPageInfo()
    info.get_cos_object().set_string(
        COSName.get_pdf_name("Custom"), "marker"
    )
    page.set_page_info(info)
    fdf.set_pages([page])
    out = fdf.get_pages()
    assert out is not None and len(out) == 1
    templates = out[0].get_templates()
    assert templates is not None and len(templates) == 1
    assert templates[0].should_rename() is True
    out_info = out[0].get_page_info()
    assert out_info is not None
    assert (
        out_info.get_cos_object().get_string(COSName.get_pdf_name("Custom"))
        == "marker"
    )


def test_set_pages_writes_cos_array_of_cos_dicts() -> None:
    """The raw COS form must remain a ``COSArray`` of ``COSDictionary`` so
    parser / writer code that operates on raw COS still works."""
    fdf = FDFDictionary()
    p1 = FDFPage()
    p2 = FDFPage()
    fdf.set_pages([p1, p2])
    raw = fdf.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Pages"))
    assert isinstance(raw, COSArray)
    assert raw.size() == 2
    assert isinstance(raw.get_object(0), COSDictionary)
    assert isinstance(raw.get_object(1), COSDictionary)


def test_get_pages_none_when_entry_missing() -> None:
    fdf = FDFDictionary()
    assert fdf.get_pages() is None
    assert fdf.get_pages_cos_array() is None


def test_get_pages_none_when_entry_wrong_type() -> None:
    """Non-array ``/Pages`` value must yield ``None``, mirroring the typed
    cast behaviour upstream."""
    fdf = FDFDictionary()
    fdf.get_cos_object().set_item(COSName.get_pdf_name("Pages"), COSDictionary())
    assert fdf.get_pages() is None
    assert fdf.get_pages_cos_array() is None


def test_get_pages_skips_non_dict_entries() -> None:
    """If a ``/Pages`` array somehow contains a non-dict element we skip
    over it, matching the defensive ``COSDictionary`` cast upstream."""
    fdf = FDFDictionary()
    arr = COSArray()
    arr.add(COSDictionary())
    arr.add(COSName.get_pdf_name("Bogus"))  # non-dict — should be skipped
    arr.add(COSDictionary())
    fdf.get_cos_object().set_item(COSName.get_pdf_name("Pages"), arr)
    pages = fdf.get_pages()
    assert pages is not None
    assert len(pages) == 2


def test_set_pages_none_drops_entry() -> None:
    fdf = FDFDictionary()
    fdf.set_pages([FDFPage()])
    assert fdf.get_pages() is not None
    fdf.set_pages(None)
    assert fdf.get_pages() is None
    assert COSName.get_pdf_name("Pages") not in fdf.get_cos_object()


def test_get_pages_cos_array_back_compat() -> None:
    """``get_pages_cos_array`` returns the raw ``COSArray`` for legacy
    callers that need direct COS access."""
    fdf = FDFDictionary()
    fdf.set_pages([FDFPage(), FDFPage()])
    raw = fdf.get_pages_cos_array()
    assert isinstance(raw, COSArray)
    assert raw.size() == 2


def test_get_javascript_returns_typed_wrapper() -> None:
    """``get_javascript`` wraps the ``/JavaScript`` entry in
    :class:`FDFJavaScript`, matching upstream
    ``FDFDictionary.getJavaScript() -> FDFJavaScript``."""
    fdf = FDFDictionary()
    js = FDFJavaScript()
    js.set_before("app.alert('hi');")
    js.set_after("app.alert('bye');")
    fdf.set_javascript(js)
    got = fdf.get_javascript()
    assert isinstance(got, FDFJavaScript)
    assert got.get_cos_object() is js.get_cos_object()
    # Round-trip preserves the /Before and /After values.
    assert got.get_before() == "app.alert('hi');"
    assert got.get_after() == "app.alert('bye');"


def test_get_javascript_none_when_entry_missing() -> None:
    fdf = FDFDictionary()
    assert fdf.get_javascript() is None
    assert fdf.get_javascript_cos_dictionary() is None


def test_get_javascript_none_when_entry_wrong_type() -> None:
    fdf = FDFDictionary()
    fdf.get_cos_object().set_item(COSName.get_pdf_name("JavaScript"), COSArray())
    assert fdf.get_javascript() is None
    assert fdf.get_javascript_cos_dictionary() is None


def test_set_javascript_none_drops_entry() -> None:
    fdf = FDFDictionary()
    fdf.set_javascript(FDFJavaScript())
    assert fdf.get_javascript() is not None
    fdf.set_javascript(None)
    assert fdf.get_javascript() is None
    assert COSName.get_pdf_name("JavaScript") not in fdf.get_cos_object()


def test_get_javascript_cos_dictionary_back_compat() -> None:
    """``get_javascript_cos_dictionary`` returns the raw ``COSDictionary``
    for legacy callers."""
    fdf = FDFDictionary()
    js = FDFJavaScript()
    fdf.set_javascript(js)
    raw = fdf.get_javascript_cos_dictionary()
    assert isinstance(raw, COSDictionary)
    assert raw is js.get_cos_object()


def test_set_javascript_writes_cos_dictionary() -> None:
    """The raw ``/JavaScript`` value must be a ``COSDictionary`` so parser /
    writer code that operates on raw COS still works."""
    fdf = FDFDictionary()
    js = FDFJavaScript()
    js.set_before("noop;")
    fdf.set_javascript(js)
    raw = fdf.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("JavaScript")
    )
    assert isinstance(raw, COSDictionary)


def test_java_script_strict_alias_typed() -> None:
    """The mechanical ``get_java_script`` / ``set_java_script`` aliases
    must return typed :class:`FDFJavaScript` wrappers too."""
    fdf = FDFDictionary()
    js = FDFJavaScript()
    fdf.set_java_script(js)
    got = fdf.get_java_script()
    assert isinstance(got, FDFJavaScript)
    assert got.get_cos_object() is js.get_cos_object()
