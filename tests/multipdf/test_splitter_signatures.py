"""Hand-written tests for :class:`pypdfbox.multipdf.Splitter`'s signature
handling. Split documents have a different byte range than the source so
any signature carried into a chunk would be invalid; the splitter must
drop signature widgets and clear ``/SigFlags`` from any inherited
``/AcroForm``.
"""
from __future__ import annotations

import io

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName
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


def _make_widget(subtype: str = "Widget", **extras: object) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, COSName.get_pdf_name("Annot"))
    d.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))
    for k, v in extras.items():
        d.set_item(COSName.get_pdf_name(k), v)
    return d


def _make_page_with_annots(*annots: COSDictionary) -> PDPage:
    page = PDPage()
    arr = COSArray()
    for a in annots:
        arr.add(a)
    page.get_cos_object().set_item(_ANNOTS, arr)
    return page


# ---------- signature widget detection ----------


def test_merged_signature_widget_dropped() -> None:
    """A widget that carries /FT=Sig directly (merged widget+field) must
    not survive into the split chunk."""
    sig_widget = _make_widget(FT=COSName.get_pdf_name("Sig"))
    text_widget = _make_widget(FT=COSName.get_pdf_name("Tx"))
    page = _make_page_with_annots(sig_widget, text_widget)

    src = PDDocument()
    src.add_page(page)

    splitter = Splitter()
    chunks = splitter.split(src)
    assert len(chunks) == 1
    chunk = chunks[0]
    chunk_page = chunk.get_pages().get(0)
    annots = chunk_page.get_cos_object().get_dictionary_object(_ANNOTS)
    assert isinstance(annots, COSArray)
    # Sig widget gone, text widget survives.
    surviving_subtypes = [
        annots.get_object(i).get_name(_FT) for i in range(annots.size())
    ]
    assert "Sig" not in surviving_subtypes
    assert "Tx" in surviving_subtypes
    chunk.close()
    src.close()


def test_widget_with_sig_field_parent_dropped() -> None:
    """A widget whose /Parent chain ends in /FT=Sig is a sig widget."""
    sig_field = COSDictionary()
    sig_field.set_item(_FT, COSName.get_pdf_name("Sig"))
    widget = _make_widget()
    widget.set_item(_PARENT, sig_field)
    page = _make_page_with_annots(widget)

    src = PDDocument()
    src.add_page(page)

    splitter = Splitter()
    chunks = splitter.split(src)
    chunk_page = chunks[0].get_pages().get(0)
    annots = chunk_page.get_cos_object().get_dictionary_object(_ANNOTS)
    assert annots is None or annots.size() == 0
    chunks[0].close()
    src.close()


def test_widget_with_text_parent_kept() -> None:
    """A widget whose /Parent is /FT=Tx must NOT be classified as a sig
    widget — only /Parent removal happens."""
    tx_field = COSDictionary()
    tx_field.set_item(_FT, COSName.get_pdf_name("Tx"))
    widget = _make_widget()
    widget.set_item(_PARENT, tx_field)
    page = _make_page_with_annots(widget)

    src = PDDocument()
    src.add_page(page)

    splitter = Splitter()
    chunks = splitter.split(src)
    chunk_page = chunks[0].get_pages().get(0)
    annots = chunk_page.get_cos_object().get_dictionary_object(_ANNOTS)
    assert isinstance(annots, COSArray) and annots.size() == 1
    surviving = annots.get_object(0)
    # /Parent stripped from cloned widget per upstream processAnnotations.
    assert not surviving.contains_key(_PARENT)
    chunks[0].close()
    src.close()


def test_widget_with_signature_value_dictionary_dropped() -> None:
    """Widget with /V containing /Type=/Sig is a signature widget even
    without a /FT entry."""
    v_dict = COSDictionary()
    v_dict.set_item(_TYPE, COSName.get_pdf_name("Sig"))
    widget = _make_widget()
    widget.set_item(_V, v_dict)
    page = _make_page_with_annots(widget)

    src = PDDocument()
    src.add_page(page)

    splitter = Splitter()
    chunks = splitter.split(src)
    chunk_page = chunks[0].get_pages().get(0)
    annots = chunk_page.get_cos_object().get_dictionary_object(_ANNOTS)
    assert annots is None or annots.size() == 0
    chunks[0].close()
    src.close()


def test_widget_with_v_byterange_dropped() -> None:
    """/V with /ByteRange (signature artifact) classifies as sig widget."""
    from pypdfbox.cos import COSInteger

    v_dict = COSDictionary()
    br = COSArray()
    for n in (0, 100, 200, 300):
        br.add(COSInteger.get(n))
    v_dict.set_item(_BYTERANGE, br)
    widget = _make_widget()
    widget.set_item(_V, v_dict)
    page = _make_page_with_annots(widget)

    src = PDDocument()
    src.add_page(page)

    splitter = Splitter()
    chunks = splitter.split(src)
    chunk_page = chunks[0].get_pages().get(0)
    annots = chunk_page.get_cos_object().get_dictionary_object(_ANNOTS)
    assert annots is None or annots.size() == 0
    chunks[0].close()
    src.close()


# ---------- AcroForm /SigFlags scrub ----------


def test_acroform_sigflags_cleared_when_signature_dropped() -> None:
    """If a sig widget is dropped, any /AcroForm in the chunk catalog
    must have /SigFlags removed."""
    sig_widget = _make_widget(FT=COSName.get_pdf_name("Sig"))
    page = _make_page_with_annots(sig_widget)

    src = PDDocument()
    src.add_page(page)

    splitter = Splitter()

    # Subclass that injects an /AcroForm with /SigFlags into the
    # destination catalog so the scrub pass has something to clean.
    class AcroFormSplitter(Splitter):
        def create_new_document(self):
            doc = super().create_new_document()
            from pypdfbox.cos import COSInteger as _COSInt

            af = COSDictionary()
            af.set_item(_SIG_FLAGS, _COSInt.get(3))
            doc.get_document_catalog().get_cos_object().set_item(_ACROFORM, af)
            return doc

    splitter = AcroFormSplitter()
    chunks = splitter.split(src)
    chunk_catalog = chunks[0].get_document_catalog().get_cos_object()
    af = chunk_catalog.get_dictionary_object(_ACROFORM)
    if af is not None:
        # Either fully removed (preferred when empty) or /SigFlags gone.
        assert not af.contains_key(_SIG_FLAGS)
    chunks[0].close()
    src.close()


def test_acroform_sig_field_removed_from_fields_array() -> None:
    """A signature-typed field in /AcroForm/Fields must be filtered out."""
    page = _make_page_with_annots(
        _make_widget(FT=COSName.get_pdf_name("Sig"))
    )
    src = PDDocument()
    src.add_page(page)

    sig_field = COSDictionary()
    sig_field.set_item(_FT, COSName.get_pdf_name("Sig"))
    tx_field = COSDictionary()
    tx_field.set_item(_FT, COSName.get_pdf_name("Tx"))

    class AcroFormSplitter(Splitter):
        def create_new_document(self):
            doc = super().create_new_document()
            af = COSDictionary()
            fields = COSArray()
            fields.add(sig_field)
            fields.add(tx_field)
            af.set_item(_FIELDS, fields)
            doc.get_document_catalog().get_cos_object().set_item(_ACROFORM, af)
            return doc

    chunks = AcroFormSplitter().split(src)
    chunk_catalog = chunks[0].get_document_catalog().get_cos_object()
    af = chunk_catalog.get_dictionary_object(_ACROFORM)
    assert isinstance(af, COSDictionary)
    fields = af.get_dictionary_object(_FIELDS)
    assert isinstance(fields, COSArray)
    fts = [fields.get_object(i).get_name(_FT) for i in range(fields.size())]
    assert "Sig" not in fts
    assert "Tx" in fts
    chunks[0].close()
    src.close()


# ---------- default chunk catalog has no AcroForm ----------


def test_default_chunk_does_not_carry_acroform() -> None:
    """``create_new_document`` whitelists catalog entries — AcroForm is
    not on that whitelist, mirroring upstream Splitter."""
    src = PDDocument()
    src.add_page(PDPage())
    src_catalog = src.get_document_catalog().get_cos_object()
    af = COSDictionary()
    af.set_item(_SIG_FLAGS, COSName.get_pdf_name("Sig"))  # any value
    src_catalog.set_item(_ACROFORM, af)

    chunks = Splitter().split(src)
    chunk_catalog = chunks[0].get_document_catalog().get_cos_object()
    assert not chunk_catalog.contains_key(_ACROFORM)
    chunks[0].close()
    src.close()


# ---------- round-trip: split + reload ----------


def test_split_with_sig_widget_round_trips() -> None:
    """Save the chunk to bytes and reload — the absence of the sig widget
    must persist through the writer."""
    sig_widget = _make_widget(FT=COSName.get_pdf_name("Sig"))
    text_widget = _make_widget(FT=COSName.get_pdf_name("Tx"))
    page = _make_page_with_annots(sig_widget, text_widget)
    src = PDDocument()
    src.add_page(page)

    chunks = Splitter().split(src)
    sink = io.BytesIO()
    chunks[0].save(sink)
    chunks[0].close()
    src.close()

    with PDDocument.load(sink.getvalue()) as reloaded:
        assert reloaded.get_number_of_pages() == 1
        annots = reloaded.get_pages().get(0).get_cos_object().get_dictionary_object(
            _ANNOTS
        )
        if annots is not None:
            for i in range(annots.size()):
                ft = annots.get_object(i).get_name(_FT)
                assert ft != "Sig"
