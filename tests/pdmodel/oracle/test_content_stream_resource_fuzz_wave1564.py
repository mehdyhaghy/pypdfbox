"""Live PDFBox differential parity for PDPageContentStream RESOURCE-NAME
allocation + reuse (wave 1564).

ResourceCreateKeyProbe (wave 1509) already pins ``PDResources.add`` /
``createKey`` in isolation. This wave drives the *content-stream writer*
end-to-end — ``set_font`` / ``draw_image`` / ``set_graphics_state_parameters``
/ ``begin_marked_content_with_dict`` — and projects the names actually emitted
into the content stream operands PLUS the final ``/Resources`` sub-dict keys,
so the reuse-vs-new-key decisions and the collision-avoidance walk (appending
to a page that already carries ``/Font F1`` / ``/XObject Im1``) are pinned the
same way Apache PDFBox 3.0.7 makes them.

Findings pinned against PDFBox 3.0.7 (probe
``oracle/probes/ContentStreamResourceFuzzProbe.java``):

- ``set_font(f, ...)`` twice with the SAME font COS object -> one ``/Font``
  key (``F1``), reused; two different fonts -> ``F1`` + ``F2``.
- ``draw_image(img, ...)`` twice with the SAME image -> one ``/XObject`` key
  (``Im1``); two different images -> ``Im1`` + ``Im2``.
- ``set_graphics_state_parameters(gs)`` twice with the SAME state -> ``gs1``;
  two different states -> ``gs1`` + ``gs2``.
- A multi-key property list registers under ``/Resources/Properties`` as
  ``Prop1`` (upstream prefix is ``Prop``, NOT ``MC``). pypdfbox splits the
  upstream ``beginMarkedContent(COSName, PDPropertyList)`` overload into the
  inline ``begin_marked_content_with_mcid`` (writes ``<</MCID n>>``, no
  resource entry) and ``begin_marked_content_with_dict`` (always registers);
  this test pins the *registering* path, which matches the upstream branch
  taken for a property list with more than a bare ``/MCID``.
- Appending to a page already holding ``/Font F1`` -> the new font seeds from
  ``keySet().size()`` (=1), pre-increments, and lands on ``F2`` (NOT the
  lowest-free ``F0``/``F1``); same for ``/XObject Im1`` -> ``Im2``.
- Emitted operand-name order for a gs/font/image sequence is
  ``[/gs1, /F1, /Im1]``.

Naming-scheme note: pypdfbox mints the same 1-based ``F``/``Im``/``gs``/``Prop``
prefixes as upstream, so the name STRINGS are byte-identical here (no
divergence). The reuse/collision behaviour is the load-bearing pin.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from pypdfbox.pdmodel import PDResources
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream
from tests.oracle.harness import requires_oracle, run_probe_text


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _keys(page: PDPage, kind: COSName) -> str:
    sub = page.get_resources().get_cos_object().get_dictionary_object(kind)
    if not isinstance(sub, COSDictionary):
        return "<none>"
    return ",".join(sorted(k.get_name() for k in sub.key_set()))


def _make_image() -> PDImageXObject:
    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    stream.set_int(COSName.get_pdf_name("Width"), 2)
    stream.set_int(COSName.get_pdf_name("Height"), 2)
    stream.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    return PDImageXObject(stream, None)


def _emitted_names(page: PDPage) -> list[str]:
    tokens = PDFStreamParser.from_bytes(page.get_contents()).parse()
    return ["/" + t.get_name() for t in tokens if isinstance(t, COSName)]


def _reproduce() -> dict[str, str]:
    """Rebuild every ContentStreamResourceFuzzProbe scenario in pypdfbox and
    return the same ``label -> value`` mapping the Java probe prints."""
    out: dict[str, str] = {}

    # setFont twice, SAME font object -> one /Font key reused.
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        font = PDType1Font()
        cs = PDPageContentStream(doc, page)
        cs.begin_text()
        cs.set_font(font, 12)
        cs.set_font(font, 14)
        cs.end_text()
        cs.close()
        out["same_font_twice.font_keys"] = _keys(page, PDResources.FONT)

    # setFont with two DIFFERENT fonts -> F1, F2.
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        cs = PDPageContentStream(doc, page)
        cs.begin_text()
        cs.set_font(PDType1Font(), 12)
        cs.set_font(PDType1Font(), 14)
        cs.end_text()
        cs.close()
        out["two_fonts.font_keys"] = _keys(page, PDResources.FONT)

    # drawImage SAME image twice -> one /XObject key.
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        img = _make_image()
        cs = PDPageContentStream(doc, page)
        cs.draw_image(img, 0, 0, 10, 10)
        cs.draw_image(img, 20, 20, 10, 10)
        cs.close()
        out["same_image_twice.xobject_keys"] = _keys(page, PDResources.XOBJECT)

    # drawImage two DIFFERENT images -> Im1, Im2.
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        cs = PDPageContentStream(doc, page)
        cs.draw_image(_make_image(), 0, 0, 10, 10)
        cs.draw_image(_make_image(), 20, 20, 10, 10)
        cs.close()
        out["two_images.xobject_keys"] = _keys(page, PDResources.XOBJECT)

    # setGraphicsStateParameters SAME state twice -> gs1.
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        gs = PDExtendedGraphicsState()
        cs = PDPageContentStream(doc, page)
        cs.set_graphics_state_parameters(gs)
        cs.set_graphics_state_parameters(gs)
        cs.close()
        out["same_gs_twice.extgstate_keys"] = _keys(page, PDResources.EXT_G_STATE)

    # setGraphicsStateParameters two DIFFERENT states -> gs1, gs2.
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        cs = PDPageContentStream(doc, page)
        cs.set_graphics_state_parameters(PDExtendedGraphicsState())
        cs.set_graphics_state_parameters(PDExtendedGraphicsState())
        cs.close()
        out["two_gs.extgstate_keys"] = _keys(page, PDResources.EXT_G_STATE)

    # Multi-key property list -> registered as Prop1; emits /Span /Prop1.
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        mc = COSDictionary()
        mc.set_int(_name("MCID"), 0)
        mc.set_name(_name("Alt"), "extra")
        props = PDPropertyList.create(mc)
        cs = PDPageContentStream(doc, page)
        cs.begin_marked_content_with_dict(_name("Span"), props)
        cs.end_marked_content()
        cs.close()
        out["mc_props.properties_keys"] = _keys(page, PDResources.PROPERTIES)
        out["mc_props.emitted_names"] = str(_emitted_names(page))

    # Bare MCID-only property list -> inlined, no /Properties entry.
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        mc = COSDictionary()
        mc.set_int(_name("MCID"), 0)
        cs = PDPageContentStream(doc, page)
        cs.begin_marked_content_with_mcid(_name("Span"), 0)
        cs.end_marked_content()
        cs.close()
        out["mc_mcid_only.properties_keys"] = _keys(page, PDResources.PROPERTIES)

    # Append to a page already holding /Font F1 -> new font lands on F2.
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        res = PDResources()
        font_sub = COSDictionary()
        font_sub.set_item(_name("F1"), COSDictionary())
        res.get_cos_object().set_item(PDResources.FONT, font_sub)
        page.set_resources(res)
        cs = PDPageContentStream(doc, page, AppendMode.APPEND, False)
        cs.begin_text()
        cs.set_font(PDType1Font(), 12)
        cs.end_text()
        cs.close()
        out["append_existing_font.font_keys"] = _keys(page, PDResources.FONT)

    # Append to a page already holding /XObject Im1 -> new image lands on Im2.
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        res = PDResources()
        x_sub = COSDictionary()
        x_sub.set_item(_name("Im1"), COSDictionary())
        res.get_cos_object().set_item(PDResources.XOBJECT, x_sub)
        page.set_resources(res)
        cs = PDPageContentStream(doc, page, AppendMode.APPEND, False)
        cs.draw_image(_make_image(), 0, 0, 10, 10)
        cs.close()
        out["append_existing_image.xobject_keys"] = _keys(page, PDResources.XOBJECT)

    # Mixed gs/font/image sequence -> keys + emitted operand-name order.
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        font = PDType1Font()
        img = _make_image()
        gs = PDExtendedGraphicsState()
        cs = PDPageContentStream(doc, page)
        cs.set_graphics_state_parameters(gs)
        cs.begin_text()
        cs.set_font(font, 12)
        cs.end_text()
        cs.draw_image(img, 0, 0, 10, 10)
        cs.close()
        out["mixed.font_keys"] = _keys(page, PDResources.FONT)
        out["mixed.xobject_keys"] = _keys(page, PDResources.XOBJECT)
        out["mixed.extgstate_keys"] = _keys(page, PDResources.EXT_G_STATE)
        out["mixed.emitted_names"] = str(_emitted_names(page))

    return out


# PDFBox 3.0.7 expected values (probe output, pinned standalone so the suite is
# self-contained when the live jar is absent).
_EXPECTED: dict[str, str] = {
    "same_font_twice.font_keys": "F1",
    "two_fonts.font_keys": "F1,F2",
    "same_image_twice.xobject_keys": "Im1",
    "two_images.xobject_keys": "Im1,Im2",
    "same_gs_twice.extgstate_keys": "gs1",
    "two_gs.extgstate_keys": "gs1,gs2",
    "mc_props.properties_keys": "Prop1",
    "mc_props.emitted_names": "['/Span', '/Prop1']",
    "mc_mcid_only.properties_keys": "<none>",
    "append_existing_font.font_keys": "F1,F2",
    "append_existing_image.xobject_keys": "Im1,Im2",
    "mixed.font_keys": "F1",
    "mixed.xobject_keys": "Im1",
    "mixed.extgstate_keys": "gs1",
    "mixed.emitted_names": "['/gs1', '/F1', '/Im1']",
}


def test_content_stream_resource_allocation_matches_pdfbox() -> None:
    assert _reproduce() == _EXPECTED


def _parse_probe(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.strip().splitlines():
        if "=" in line:
            label, value = line.split("=", 1)
            result[label.strip()] = value.strip()
    return result


def _normalise_java_list(value: str) -> str:
    """Java's ``[/gs1, /F1]`` -> Python repr ``['/gs1', '/F1']`` so emitted
    name-order lines compare across the language boundary."""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return "[]"
        items = [piece.strip() for piece in inner.split(",")]
        return "[" + ", ".join(f"'{item}'" for item in items) + "]"
    return value


@requires_oracle
def test_content_stream_resource_allocation_matches_live_oracle() -> None:
    java = _parse_probe(run_probe_text("ContentStreamResourceFuzzProbe"))
    java = {k: _normalise_java_list(v) for k, v in java.items()}
    assert _reproduce() == java
