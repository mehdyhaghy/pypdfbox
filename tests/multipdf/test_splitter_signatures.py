"""Hand-written tests for how :class:`pypdfbox.multipdf.Splitter` treats
signature widgets.

Upstream ``Splitter`` has no signature special case: every annotation,
signature widgets included, is shallow-cloned onto the imported page, a
widget's ``/Parent`` field reference is dropped, and no ``/AcroForm`` is
created in the split documents (so no ``/SigFlags`` either).
"""

import io

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.multipdf import Splitter

_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_FT = COSName.get_pdf_name("FT")
_PARENT = COSName.get_pdf_name("Parent")
_ANNOTS = COSName.get_pdf_name("Annots")
_ACROFORM = COSName.get_pdf_name("AcroForm")
_SIG_FLAGS = COSName.get_pdf_name("SigFlags")
_FIELDS = COSName.get_pdf_name("Fields")
_V = COSName.get_pdf_name("V")
_BYTERANGE = COSName.get_pdf_name("ByteRange")


def _make_widget(**extras: object) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, COSName.get_pdf_name("Annot"))
    d.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    for k, v in extras.items():
        d.set_item(COSName.get_pdf_name(k), v)
    return d


def _signed_source() -> tuple[PDDocument, COSDictionary, COSDictionary]:
    """One page carrying a merged signature widget and a signature widget
    whose field is its ``/Parent``; the source has an ``/AcroForm`` with
    ``/SigFlags``."""
    sig_value = COSDictionary()
    sig_value.set_item(_TYPE, COSName.get_pdf_name("Sig"))
    byte_range = COSArray()
    for n in (0, 10, 20, 30):
        byte_range.add(COSInteger.get(n))
    sig_value.set_item(_BYTERANGE, byte_range)
    merged = _make_widget(FT=COSName.get_pdf_name("Sig"), V=sig_value)
    field = COSDictionary()
    field.set_item(_FT, COSName.get_pdf_name("Sig"))
    kid = _make_widget(Parent=field)
    kids = COSArray()
    kids.add(kid)
    field.set_item(COSName.get_pdf_name("Kids"), kids)

    page = PDPage()
    annots = COSArray()
    annots.add(merged)
    annots.add(kid)
    page.get_cos_object().set_item(_ANNOTS, annots)
    src = PDDocument()
    src.add_page(page)
    acroform = COSDictionary()
    fields = COSArray()
    fields.add(merged)
    fields.add(field)
    acroform.set_item(_FIELDS, fields)
    acroform.set_int(_SIG_FLAGS, 3)
    src.get_document_catalog().get_cos_object().set_item(_ACROFORM, acroform)
    return src, merged, kid


def test_signature_widgets_are_shallow_cloned_like_any_annotation() -> None:
    src, merged, kid = _signed_source()
    chunk = Splitter().split(src)[0]
    annots = chunk.get_page(0).get_cos_object().get_dictionary_object(_ANNOTS)
    assert isinstance(annots, COSArray)
    assert annots.size() == 2
    cloned_merged = annots.get_object(0)
    cloned_kid = annots.get_object(1)
    # clones, not the source dictionaries
    assert cloned_merged is not merged
    assert cloned_kid is not kid
    # the merged widget keeps its field entries (shared values)
    assert cloned_merged.get_name(_FT) == "Sig"
    assert cloned_merged.get_dictionary_object(_V) is merged.get_dictionary_object(_V)
    # a widget's /Parent is removed on the clone only
    assert not cloned_kid.contains_key(_PARENT)
    assert kid.contains_key(_PARENT)
    chunk.close()
    src.close()


def test_split_document_has_no_acroform() -> None:
    src, _, _ = _signed_source()
    chunk = Splitter().split(src)[0]
    catalog = chunk.get_document_catalog().get_cos_object()
    assert not catalog.contains_key(_ACROFORM)
    # the source form is untouched
    src_form = src.get_document_catalog().get_cos_object().get_dictionary_object(
        _ACROFORM
    )
    assert src_form.get_int(_SIG_FLAGS) == 3
    assert src_form.get_dictionary_object(_FIELDS).size() == 2
    chunk.close()
    src.close()


def test_split_with_sig_widget_round_trips() -> None:
    src, _, _ = _signed_source()
    chunks = Splitter().split(src)
    sink = io.BytesIO()
    chunks[0].save(sink)
    chunks[0].close()
    src.close()

    with PDDocument.load(sink.getvalue()) as reloaded:
        assert reloaded.get_number_of_pages() == 1
        annots = reloaded.get_page(0).get_cos_object().get_dictionary_object(_ANNOTS)
        assert annots.size() == 2
        assert annots.get_object(0).get_name(_FT) == "Sig"
        assert not reloaded.get_document_catalog().get_cos_object().contains_key(
            _ACROFORM
        )
