"""Ported from
``pdfbox/src/test/java/org/apache/pdfbox/multipdf/TestLayerUtility.java``
(PDFBox trunk).

The upstream JUnit class drives a save-then-reload round-trip with two
small generated PDFs (one text body, one rotated overlay caption). That
relies on Standard14 type-1 font wiring, ``PDPageContentStream``'s text
operators, and ``CompressParameters.NO_COMPRESSION`` — none of which
have landed in the same shape yet (the lite content-stream surface
covers BT/ET + showText, but Standard14 fonts aren't ported yet, and
the writer doesn't expose the upstream ``CompressParameters`` knob).

We translate the core assertions from ``testLayerImport`` to operate
purely on ``COSDocument`` graphs (no font / no save round-trip), since
the per-class clusters above already cover the byte-level layer of the
operations:

- catalog ``/OCProperties`` contains the ``"overlay"`` layer after
  ``append_form_as_layer``;
- page resources expose a ``/Properties`` entry pointing at the same
  OCG;
- a second LayerUtility on the same document successfully imports a
  page as a form (PDFBOX-5232 — never-ended marked-content section).
"""

from __future__ import annotations

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.multipdf import LayerUtility
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)


def _make_main_pdf() -> PDDocument:
    """Tiny stand-in for upstream's ``createMainPDF`` — a single Letter
    page with a non-empty content stream."""
    doc = PDDocument()
    page = PDPage()
    stream = COSStream()
    stream.set_raw_data(b"% main page body\nq 1 0 0 1 0 0 cm Q\n")
    page.set_contents(stream)
    doc.add_page(page)
    return doc


def _make_overlay_pdf() -> PDDocument:
    """Stand-in for upstream's ``createOverlay1`` — page with a tiny
    placeholder content stream."""
    doc = PDDocument()
    page = PDPage()
    stream = COSStream()
    stream.set_raw_data(b"% overlay caption goes here\n")
    page.set_contents(stream)
    doc.add_page(page)
    return doc


def test_layer_import() -> None:
    """Translation of upstream ``testLayerImport``: import a page as a
    form, wrap the target page in q/Q, append the form as an "overlay"
    layer, and verify the resulting OCG is reachable via both the page's
    /Resources/Properties and the catalog's /OCProperties.

    Notes on simplifications:
    - Upstream saves to disk and re-loads to assert the OCG name; we
      assert directly on the in-memory dictionaries (the COSWriter
      round-trip is covered separately under ``tests/pdfwriter``).
    - Upstream checks ``doc.getVersion() == 1.5`` after save (OCGs
      require PDF 1.5+). The catalog version-bump on
      ``append_form_as_layer`` is a writer concern and lives outside
      this cluster, so we don't assert it here.
    """
    target_doc = _make_main_pdf()
    overlay_doc = _make_overlay_pdf()

    layer_util = LayerUtility(target_doc)
    form = layer_util.import_page_as_form(overlay_doc, 0)
    target_page = target_doc.get_page(0)
    layer_util.wrap_in_save_restore(target_page)
    layer = layer_util.append_form_as_layer(target_page, form, None, "overlay")

    # /OCProperties layer reachable via the catalog.
    catalog = target_doc.get_document_catalog()
    oc_props = catalog.get_oc_properties()
    overlay = oc_props.get_group("overlay")
    assert overlay is not None
    assert overlay.get_name() == layer.get_name() == "overlay"

    # The page's /Resources/Properties carries an OCG entry whose dict is
    # the same object as the catalog-side OCG (mirrors upstream's
    # ``page.getResources().getProperties(COSName.getPDFName("oc1"))``
    # — the resource key is auto-allocated as ``MC<n>`` in our port, so
    # we walk the /Properties dict instead of hard-coding a key name).
    res_dict = target_page.get_resources().get_cos_object()
    props = res_dict.get_dictionary_object(COSName.get_pdf_name("Properties"))
    assert isinstance(props, COSDictionary)
    found: PDOptionalContentGroup | None = None
    for key in props.key_set():
        entry = props.get_dictionary_object(key)
        if isinstance(entry, COSDictionary) and entry is layer.get_cos_object():
            found = PDOptionalContentGroup(entry)
            break
    assert found is not None
    assert found.get_name() == "overlay"

    # PDFBOX-5232: a fresh LayerUtility on the same target document can
    # still import a page as a form (the previous BDC...EMC marked-
    # content block was correctly closed; there are no unended sections
    # leaking into a follow-on import).
    LayerUtility(target_doc).import_page_as_form(target_doc, 0)

    target_doc.close()
    overlay_doc.close()


def test_get_document_returns_target() -> None:
    """``getDocument()`` returns the same ``PDDocument`` passed to the
    constructor. Mirrors upstream LayerUtility.java:77.
    """
    doc = PDDocument()
    layer_util = LayerUtility(doc)
    assert layer_util.get_document() is doc
    doc.close()


def test_wrap_in_save_restore_with_array_contents() -> None:
    """``wrapInSaveRestore`` prepends ``q`` and appends ``Q`` when the
    page's ``/Contents`` is already a ``COSArray``. Mirrors upstream
    LayerUtility.java:118-124.
    """
    doc = PDDocument()
    page = PDPage()
    arr = COSArray()
    s1 = COSStream()
    s1.set_raw_data(b"% body 1\n")
    s2 = COSStream()
    s2.set_raw_data(b"% body 2\n")
    arr.add(s1)
    arr.add(s2)
    page.get_cos_object().set_item(COSName.CONTENTS, arr)
    doc.add_page(page)

    LayerUtility(doc).wrap_in_save_restore(page)
    contents = page.get_cos_object().get_dictionary_object(COSName.CONTENTS)
    assert isinstance(contents, COSArray)
    # Original two streams flanked by q + Q streams = 4 entries.
    assert contents.size() == 4
    doc.close()


def test_transfer_dict_copies_filtered_keys() -> None:
    """``transferDict`` (private upstream, public on the port) copies
    the listed keys from one dict to another, cloning values through
    the bound ``PDFCloneUtility``. Mirrors LayerUtility.java:288-299.
    """
    doc = PDDocument()
    layer_util = LayerUtility(doc)

    src = COSDictionary()
    last_modified = COSName.get_pdf_name("LastModified")
    metadata_key = COSName.get_pdf_name("Metadata")
    skipped = COSName.get_pdf_name("Resources")
    metadata_stream = COSStream()
    metadata_stream.set_raw_data(b"<rdf:RDF/>")
    src.set_item(last_modified, COSName.get_pdf_name("D:20240101"))
    src.set_item(metadata_key, metadata_stream)
    src.set_item(skipped, COSName.get_pdf_name("dont-copy"))

    dst = COSDictionary()
    layer_util.transfer_dict(src, dst, frozenset({"LastModified", "Metadata"}))

    assert dst.get_dictionary_object(last_modified) is not None
    assert dst.get_dictionary_object(metadata_key) is not None
    assert dst.get_dictionary_object(skipped) is None
    doc.close()


def test_import_oc_properties_noop_when_source_empty() -> None:
    """``importOcProperties`` is a no-op when the source has no
    ``/OCProperties``. Mirrors LayerUtility.java:312-315.
    """
    src = PDDocument()
    dst = PDDocument()
    LayerUtility(dst).import_oc_properties(src)
    assert dst.get_document_catalog().get_oc_properties() is None
    src.close()
    dst.close()


def test_import_oc_properties_clones_from_source() -> None:
    """``importOcProperties`` clones the source ``/OCProperties`` into
    the target catalog when the target has none of its own. Mirrors
    LayerUtility.java:317-324.
    """
    src = PDDocument()
    src_oc = PDOptionalContentProperties()
    src_oc.add_group(PDOptionalContentGroup("layer-from-src"))
    src.get_document_catalog().set_oc_properties(src_oc)

    dst = PDDocument()
    LayerUtility(dst).import_oc_properties(src)

    dst_oc = dst.get_document_catalog().get_oc_properties()
    assert dst_oc is not None
    assert dst_oc.has_group("layer-from-src")
    src.close()
    dst.close()
