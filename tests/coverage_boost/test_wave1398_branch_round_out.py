"""Wave 1398 branch-coverage round-out.

Targets the residual partial-branch arrows surfaced by the wave 1398
audit. Each test hits a False-arm that the existing suite never reached.
Branches that are clearly defensive (mirroring upstream Java guards
that can't be reproduced in Python) are pragma'd in source rather than
exercised through tests.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)

# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/interactive/annotation/handlers/annotation_border.py
# 38->42 (size < 3 short-circuit) and 44->55 (size > 3 but slot 3 not array)
# -----------------------------------------------------------------------------


class _StubAnnotation:
    def __init__(self, border: COSArray | None) -> None:
        self._border = border

    def get_border(self) -> COSArray | None:
        return self._border


def test_annotation_border_legacy_border_too_short() -> None:
    """Border with size<3 leaves width=0; covers the 38->42 short-circuit."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.annotation_border import (
        AnnotationBorder,
    )

    border = COSArray()
    border.add(COSFloat(0.0))
    border.add(COSFloat(0.0))
    ab = AnnotationBorder.get_annotation_border(_StubAnnotation(border), None)
    assert ab.width == 0.0
    assert ab.dash_array is None


def test_annotation_border_legacy_dash_slot_not_array() -> None:
    """Border slot 3 not a COSArray skips dash assignment; covers 44->55."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.annotation_border import (
        AnnotationBorder,
    )

    border = COSArray()
    border.add(COSFloat(0.0))
    border.add(COSFloat(0.0))
    border.add(COSFloat(1.5))
    border.add(COSInteger.get(7))  # not a COSArray — should be skipped
    ab = AnnotationBorder.get_annotation_border(_StubAnnotation(border), None)
    assert ab.width == 1.5
    assert ab.dash_array is None


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/interactive/action/pd_action.py
# 143->141 (entry not COSDictionary), 145->141 (PDAction.create returns None)
# -----------------------------------------------------------------------------


def test_pd_action_get_next_array_mixed_entries() -> None:
    """A /Next array containing non-dict entries and an unsupported /S
    dict triggers both 143->141 and 145->141."""
    from pypdfbox.pdmodel.interactive.action import PDActionNamed

    parent = COSDictionary()
    parent.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Named"))
    nxt = COSArray()
    # 143->141: non-dict entry skipped
    nxt.add(COSInteger.get(0))
    # 145->141: a dict whose /S is not a recognised action subtype
    unsupported = COSDictionary()
    unsupported.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("BogusActionType")
    )
    nxt.add(unsupported)
    # Plus one valid entry so we still return non-empty
    valid = COSDictionary()
    valid.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Named"))
    valid.set_item(COSName.get_pdf_name("N"), COSName.get_pdf_name("NextPage"))
    nxt.add(valid)
    parent.set_item(COSName.get_pdf_name("Next"), nxt)

    action = PDActionNamed(parent)
    results = action.get_next()
    assert results is not None
    # both bogus entries are skipped; only the valid named action survives
    assert len(results) >= 1


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/pd_abstract_content_stream.py
# 202->204 (resources is None branch in set_font)
# -----------------------------------------------------------------------------


def test_abstract_content_stream_set_font_with_no_resources() -> None:
    """set_font when self._resources is None skips the resources.add call.

    PDPageContentStream and PDAppearanceContentStream both override
    set_font with a resource-key-allocating variant, so we drive the
    bare PDAbstractContentStream branch directly via an ad-hoc subclass.
    """
    import io as _io

    from pypdfbox.pdmodel.font import PDType1Font
    from pypdfbox.pdmodel.pd_abstract_content_stream import (
        PDAbstractContentStream,
    )

    out = _io.BytesIO()
    # Pass None for both document and resources to exercise the no-resources branch
    cs = PDAbstractContentStream(None, out, None)
    font = PDType1Font()
    font.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), PDType1Font.HELVETICA
    )
    font.get_cos_object().set_name(COSName.get_pdf_name("Subtype"), "Type1")
    # When resources is None set_font should still write the operand
    cs.set_font(font, 10.0)
    # call again to exercise the pop+append branch as well
    cs.set_font(font, 12.0)
    assert b"Tf" in out.getvalue()


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/font/pd_cid_font.py
# 230->232 (w2 is None branch in read_vertical_displacements)
# -----------------------------------------------------------------------------


def test_pd_cid_font_read_vertical_displacements_no_w2() -> None:
    """When /W2 is absent, read_vertical_displacements skips the parse
    and just returns an empty dict (covers 230->232)."""
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    cid_dict = COSDictionary()
    cid_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    cid_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("CIDFontType2")
    )
    cid_dict.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("ArialMT")
    )
    cidsys = COSDictionary()
    cidsys.set_item(COSName.get_pdf_name("Registry"), COSString("Adobe"))
    cidsys.set_item(COSName.get_pdf_name("Ordering"), COSString("Identity"))
    cidsys.set_item(COSName.get_pdf_name("Supplement"), COSInteger.get(0))
    cid_dict.set_item(COSName.get_pdf_name("CIDSystemInfo"), cidsys)

    # PDCIDFontType2 signature varies — call .__new__ + set _dict to skip
    font = object.__new__(PDCIDFontType2)
    font._dict = cid_dict  # type: ignore[attr-defined]
    font._widths = None  # type: ignore[attr-defined]
    font._widths2 = None  # type: ignore[attr-defined]
    font._w_ranges = None  # type: ignore[attr-defined]
    font._w2_ranges = None  # type: ignore[attr-defined]
    widths = font.read_vertical_displacements()
    assert widths == {}


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/font/pd_font.py
# 215->214 (non-numeric entry in /Widths skipped)
# -----------------------------------------------------------------------------


def test_pd_font_widths_skip_non_numeric_entries() -> None:
    """Non-numeric /Widths entries are kept as None in place (index-aligned),
    matching upstream COSArray.toCOSNumberFloatList (wave 1469)."""
    from pypdfbox.pdmodel.font import PDType1Font

    font = PDType1Font()
    font.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), PDType1Font.HELVETICA
    )
    font.get_cos_object().set_name(COSName.get_pdf_name("Subtype"), "Type1")
    cos = font.get_cos_object()
    arr = COSArray()
    arr.add(COSInteger.get(500))
    arr.add(COSName.get_pdf_name("BogusEntry"))  # non-numeric — kept as None
    arr.add(COSFloat(600.0))
    cos.set_item(COSName.get_pdf_name("Widths"), arr)
    try:
        widths = font.get_widths()
        assert widths == [500.0, None, 600.0]
    finally:
        cos.remove_item(COSName.get_pdf_name("Widths"))


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/interactive/measurement/pd_selector_rendition.py
# 31->29 (entry not COSDictionary), 33->29 (PDRendition.create returns None)
# -----------------------------------------------------------------------------


def test_pd_selector_rendition_get_r_skips_invalid_entries() -> None:
    """Non-dict and unwrappable entries in /R are skipped."""
    from pypdfbox.pdmodel.interactive.measurement.pd_selector_rendition import (
        PDSelectorRendition,
    )

    selector = PDSelectorRendition()
    cos = selector.get_cos_object()
    arr = COSArray()
    arr.add(COSInteger.get(0))  # not a dict — covers 31->29
    # A dict without /S so PDRendition.create returns None — covers 33->29
    unsupported = COSDictionary()
    unsupported.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Rendition")
    )
    arr.add(unsupported)
    cos.set_item(COSName.get_pdf_name("R"), arr)
    assert selector.get_r() == []


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/fdf/fdf_document.py
# 289->293 (_owns_document False — close() doesn't touch self._document)
# -----------------------------------------------------------------------------


def test_fdf_document_close_does_not_close_borrowed_cos_document() -> None:
    """When the FDFDocument is constructed over a borrowed COSDocument
    (owns_document=False), close() must not close it. Covers 289->293."""
    from pypdfbox.cos.cos_document import COSDocument
    from pypdfbox.pdmodel.fdf.fdf_document import FDFDocument

    cos_doc = COSDocument()
    fdf = FDFDocument(cos_doc)
    # FDFDocument owns the cos_doc by default; force the not-owns branch
    fdf._owns_document = False
    fdf.close()
    # COSDocument should still be usable
    cos_doc.set_trailer(COSDictionary())
    cos_doc.close()


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/interactive/digitalsignature/sig_utils.py
# 146->149 (perms already exists path)
# -----------------------------------------------------------------------------


def test_sig_utils_set_mdp_permission_reuses_existing_perms() -> None:
    """When the catalog already has a /Perms dict, set_mdp_permission
    must reuse it rather than allocating a new one (covers 146->149)."""
    from pypdfbox.pdmodel import PDDocument
    from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature
    from pypdfbox.pdmodel.interactive.digitalsignature.sig_utils import (
        set_mdp_permission,
    )

    doc = PDDocument()
    catalog = doc.get_document_catalog()
    existing_perms = COSDictionary()
    existing_perms.set_item(
        COSName.get_pdf_name("UR3"), COSDictionary()
    )  # unrelated to /DocMDP
    catalog.set_perms(existing_perms)
    sig = PDSignature()
    set_mdp_permission(doc, sig, 1)
    # The Perms dict should still carry the original UR3 entry plus the
    # newly added DocMDP entry (reuse path).
    perms_after = catalog.get_perms()
    assert perms_after is not None
    assert perms_after.get_dictionary_object(
        COSName.get_pdf_name("UR3")
    ) is not None
    doc.close()


# -----------------------------------------------------------------------------
# pypdfbox/pdfparser/pdf_object_stream_parser.py
# 63->66 (stream_object is None branch)
# -----------------------------------------------------------------------------


def test_pdf_object_stream_parser_parse_object_returns_none_for_missing() -> None:
    """Parsing a non-existent object number should return None — covers
    the 63->66 stream_object-is-None arm in parse_object."""
    from pypdfbox.cos.cos_document import COSDocument
    from pypdfbox.cos.cos_stream import COSStream
    from pypdfbox.pdfparser.pdf_object_stream_parser import (
        PDFObjectStreamParser,
    )

    # Minimal object stream with /N 0 (no compressed objects)
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("N"), 0)
    stream.set_int(COSName.get_pdf_name("First"), 0)
    stream.set_raw_data(b"")

    cos_doc = COSDocument()
    parser = PDFObjectStreamParser(stream, cos_doc)
    # object number not present in offsets table -> returns None
    assert parser.parse_object(99) is None
    cos_doc.close()


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/font/file_system_font_provider.py
# 379->372 (suffix not matching any known font type)
# -----------------------------------------------------------------------------


def test_file_system_font_provider_unknown_suffix_is_skipped(tmp_path) -> None:
    """A file with an unknown suffix is silently skipped — covers
    379->372 (else branch falls back to next iteration)."""
    import threading

    from pypdfbox.pdmodel.font.file_system_font_provider import (
        FileSystemFontProvider,
    )

    # Construct a bare provider and feed it a file with .xyz suffix.
    provider = FileSystemFontProvider.__new__(FileSystemFontProvider)
    provider._font_info_by_name = {}  # type: ignore[attr-defined]
    provider._font_info_list = []  # type: ignore[attr-defined]
    provider._lock = threading.RLock()  # type: ignore[attr-defined]
    bogus = tmp_path / "not_a_font.xyz"
    bogus.write_bytes(b"junk")
    # Should not raise — silently skipped
    provider._scan_fonts([bogus])  # type: ignore[attr-defined]


# -----------------------------------------------------------------------------
# pypdfbox/xmpbox/exif_schema.py
# 335->338 (X_DEFAULT not in keys — list stays as-is)
# -----------------------------------------------------------------------------


def test_exif_schema_get_user_comment_property_without_x_default() -> None:
    """get_user_comment_property when the recorded value map has no
    x-default key — covers 335->338 (False arm of the X_DEFAULT-in-keys check)."""
    from pypdfbox.xmpbox import XMPMetadata
    from pypdfbox.xmpbox.exif_schema import ExifSchema

    metadata = XMPMetadata.create_xmp_metadata()
    exif = metadata.create_and_add_exif_schema()
    # Manually inject a LangAlt-shaped raw payload missing 'x-default'.
    exif._properties[ExifSchema.USER_COMMENT] = {"en": "hello", "fr": "bonjour"}
    la = exif.get_user_comment_property()
    assert la is not None


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/font/pd_type0_font.py
# 1125->1127 (descendant lacks encode_glyph_id method)
# -----------------------------------------------------------------------------


def test_pd_type0_encode_glyph_id_fallback_to_manual_be_encoding() -> None:
    """When the descendant font has no encode_glyph_id method, the code
    falls through to the manual big-endian 2-byte encoding — covers 1125->1127."""
    from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

    cos = COSDictionary()
    cos.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    cos.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type0"))
    cos.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("StubBase"))
    cos.set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("Identity-H")
    )

    f = object.__new__(PDType0Font)
    f._dict = cos  # type: ignore[attr-defined]

    class _StubDescendantNoEncoder:
        def get_cos_object(self) -> COSDictionary:
            return COSDictionary()

    f.get_descendant_font = lambda: _StubDescendantNoEncoder()  # type: ignore[assignment]
    out = f.encode_glyph_id(0x1234)
    assert out == b"\x12\x34"


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/interactive/digitalsignature/sig_utils.py — 110->104
# (existing signature is a DocTimeStamp -> continue without raising)
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/interactive/annotation/pd_ink_list.py
# 30->28 (entry not COSArray)
# -----------------------------------------------------------------------------


def test_pd_ink_list_skips_non_array_entries() -> None:
    """get_paths skips non-COSArray /InkList entries — covers 30->28."""
    from pypdfbox.pdmodel.interactive.annotation.pd_ink_list import PDInkList

    arr = COSArray()
    # A path
    path1 = COSArray()
    path1.add(COSFloat(0.0))
    path1.add(COSFloat(0.0))
    arr.add(path1)
    # Garbage entry
    arr.add(COSInteger.get(0))
    ink_list = PDInkList(arr)
    paths = ink_list.get_paths()
    assert len(paths) == 1


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/interactive/annotation/pd_appearance_characteristics_dictionary.py
# 45->47 (cos() returns non-stream)
# -----------------------------------------------------------------------------


def test_appearance_characteristics_set_icon_rejects_bogus_cos() -> None:
    """A duck-typed object whose get_cos_object returns a non-stream is
    rejected via TypeError — covers 45->47."""
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
        PDAppearanceCharacteristicsDictionary,
    )

    appc = PDAppearanceCharacteristicsDictionary(COSDictionary())

    class _BogusIconHolder:
        def get_cos_object(self):
            return COSDictionary()  # not a stream

    import pytest as _pytest

    with _pytest.raises(TypeError):
        appc.set_normal_icon(_BogusIconHolder())


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/interactive/digitalsignature/pd_document_security_store.py
# 96->94 (resolved is not a COSStream)
# -----------------------------------------------------------------------------


def test_document_security_store_skips_non_stream_entries() -> None:
    """_array_to_byte_blobs ignores non-COSStream entries — covers 96->94."""
    from pypdfbox.cos.cos_stream import COSStream
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_document_security_store import (
        _array_to_byte_blobs,
    )

    arr = COSArray()
    arr.add(COSInteger.get(1))  # not a stream — skipped
    s = COSStream()
    s.set_raw_data(b"hello")
    arr.add(s)
    out = _array_to_byte_blobs(arr)
    assert out == [b"hello"]


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/font/encoding/dictionary_encoding.py
# 125->exit (diffs is None — apply_differences returns without doing work)
# -----------------------------------------------------------------------------


def test_dictionary_encoding_apply_differences_when_diffs_absent() -> None:
    """Apply differences on an encoding with no /Differences array
    short-circuits without raising — covers 125->exit."""
    from pypdfbox.pdmodel.font.encoding.dictionary_encoding import (
        DictionaryEncoding,
    )

    # font_encoding kw -> reader path; non-symbolic so base falls back to
    # StandardEncoding even without /BaseEncoding.
    cos = COSDictionary()
    cos.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=cos, is_non_symbolic=True)
    enc.apply_differences()  # no /Differences -> safe no-op


# -----------------------------------------------------------------------------
# pypdfbox/xmpbox/type/array_property.py 191->190
# (skip non-simple child in get_elements_as_string)
# -----------------------------------------------------------------------------


def test_array_property_get_elements_as_string_skips_complex_child() -> None:
    """A non-simple child in an ArrayProperty is skipped — covers 191->190."""
    from pypdfbox.xmpbox import XMPMetadata
    from pypdfbox.xmpbox.type.array_property import ArrayProperty, Cardinality
    from pypdfbox.xmpbox.type.text_type import TextType
    from pypdfbox.xmpbox.xmp_metadata import RDF_NAMESPACE

    metadata = XMPMetadata.create_xmp_metadata()
    arr = ArrayProperty(metadata, RDF_NAMESPACE, "rdf", "Bag", Cardinality.Bag)
    # one simple child
    arr.add_property(TextType(metadata, RDF_NAMESPACE, "rdf", "li", "hello"))
    # one complex child (a nested ArrayProperty)
    nested = ArrayProperty(metadata, RDF_NAMESPACE, "rdf", "li", Cardinality.Bag)
    arr.add_property(nested)
    out = arr.get_elements_as_string()
    assert out == ["hello"]


# -----------------------------------------------------------------------------
# pypdfbox/xmpbox/type/abstract_complex_property.py 41->43
# (ArrayProperty skips the dedupe step)
# -----------------------------------------------------------------------------


# abstract_complex_property.py 41->43 is unreachable from regular call sites:
# ArrayProperty overrides add_property entirely and never calls super(), so the
# `if not isinstance(self, ArrayProperty)` False arm in the parent method has
# no live caller. Pragma'd in source as a defensive guard mirroring upstream.


# -----------------------------------------------------------------------------
# pypdfbox/xmpbox/dublin_core_schema.py 148->151 (X_DEFAULT absent path)
# -----------------------------------------------------------------------------


def test_dublin_core_build_lang_alt_without_x_default() -> None:
    """Build a LangAlt from a Dublin Core lang dict missing x-default —
    covers 148->151."""
    from pypdfbox.xmpbox import XMPMetadata

    metadata = XMPMetadata.create_xmp_metadata()
    dc = metadata.create_and_add_dublin_core_schema()
    # The schema stores localized values keyed by language. Inject a raw
    # mapping that doesn't include the x-default key.
    dc._properties["title"] = {"en": "hello", "fr": "bonjour"}
    la = dc.get_title_property()
    assert la is not None


# -----------------------------------------------------------------------------
# pypdfbox/xmpbox/tiff_schema.py 261->264 (X_DEFAULT absent path)
# -----------------------------------------------------------------------------


def test_tiff_schema_build_lang_alt_without_x_default() -> None:
    """A TIFF LangAlt-shaped raw map missing x-default — covers 261->264."""
    from pypdfbox.xmpbox import XMPMetadata

    metadata = XMPMetadata.create_xmp_metadata()
    tiff = metadata.create_and_add_tiff_schema()
    tiff._properties["Artist"] = {"en": "alice"}
    la = tiff._build_lang_alt("Artist")
    assert la is not None


# -----------------------------------------------------------------------------
# pypdfbox/xmpbox/pdfa_identification_schema.py 84->86
# -----------------------------------------------------------------------------


def test_pdfa_identification_schema_int_get_string_payload() -> None:
    """When the stored Part value is a string (e.g. loaded from XMP),
    _int_get parses it via int(text.strip()) — covers 84->86."""
    from pypdfbox.xmpbox import XMPMetadata

    metadata = XMPMetadata.create_xmp_metadata()
    pdfa = metadata.create_and_add_pdfa_identification_schema()
    # Inject a string-shaped Part value directly into properties so
    # _int_get hits the str branch (text != None -> int(text)).
    pdfa._properties["part"] = "2"
    assert pdfa.get_part() == 2


# -----------------------------------------------------------------------------
# pypdfbox/xmpbox/type/lang_alt.py 79->exit
# -----------------------------------------------------------------------------


def test_lang_alt_remove_language_on_empty_container() -> None:
    """Remove a language on a LangAlt with no properties — covers 79->exit."""
    from pypdfbox.xmpbox import XMPMetadata
    from pypdfbox.xmpbox.type.lang_alt import LangAlt
    from pypdfbox.xmpbox.xmp_metadata import RDF_NAMESPACE

    metadata = XMPMetadata.create_xmp_metadata()
    la = LangAlt(metadata, RDF_NAMESPACE, "rdf", "Foo")
    la.remove_language("en")  # no children — loop exits without removing


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/interactive/digitalsignature/pd_signature_lock.py 187->190
# (defensive guard: when has_p True, get_p never returns None)
# -----------------------------------------------------------------------------


# Pragma'd in source — has_p() True guarantees get_p() returns an int.


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/fdf/fdf_page.py 42->40
# pypdfbox/pdmodel/fdf/fdf_template.py 68->66
# pypdfbox/pdmodel/fdf/fdf_dictionary.py 62->60
# All three: skip non-COSDictionary entries in /Templates / /Fields walk.
# -----------------------------------------------------------------------------


def test_fdf_page_skips_non_dict_template_entries() -> None:
    """A /Templates array containing a non-dict entry skips it — covers 42->40."""
    from pypdfbox.pdmodel.fdf.fdf_page import FDFPage

    cos = COSDictionary()
    arr = COSArray()
    arr.add(COSInteger.get(0))  # not a dict — skipped
    dict_entry = COSDictionary()
    arr.add(dict_entry)
    cos.set_item(COSName.get_pdf_name("Templates"), arr)
    page = FDFPage(cos)
    templates = page.get_templates()
    assert templates is not None
    assert len(templates) == 1


def test_fdf_template_skips_non_dict_field_entries() -> None:
    """A /Fields array containing a non-dict entry skips it — covers 68->66."""
    from pypdfbox.pdmodel.fdf.fdf_template import FDFTemplate

    cos = COSDictionary()
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSDictionary())
    cos.set_item(COSName.get_pdf_name("Fields"), arr)
    tpl = FDFTemplate(cos)
    fields = tpl.get_fields()
    assert fields is not None
    assert len(fields) == 1


def test_fdf_dictionary_skips_non_dict_field_entries() -> None:
    """A /Fields entry that resolves to a non-dict is skipped — covers 62->60."""
    from pypdfbox.pdmodel.fdf.fdf_dictionary import FDFDictionary

    cos = COSDictionary()
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSDictionary())
    cos.set_item(COSName.get_pdf_name("Fields"), arr)
    fdf = FDFDictionary(cos)
    fields = fdf.get_fields()
    assert fields is not None
    assert len(fields) == 1


# -----------------------------------------------------------------------------
# pypdfbox/pdmodel/documentinterchange/logicalstructure/revisions.py 129->131
# -----------------------------------------------------------------------------


def test_revisions_remove_skips_revision_offset_when_absent() -> None:
    """remove_at on a Revisions entry with no revision slot — covers 129->131."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.revisions import (
        Revisions,
    )

    arr = COSArray()
    # Single object entry with no revision slot
    arr.add(COSDictionary())
    revs = Revisions(arr)
    revs.remove_at(0)
    assert arr.size() == 0


def test_sig_utils_set_mdp_skips_doc_timestamp_signature() -> None:
    """An existing DocTimeStamp signature must not block adding a DocMDP —
    covers the 110->104 'continue' arm in the dictionaries loop."""
    from pypdfbox.pdmodel import PDDocument
    from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature
    from pypdfbox.pdmodel.interactive.digitalsignature.sig_utils import (
        set_mdp_permission,
    )
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm

    doc = PDDocument()
    catalog = doc.get_document_catalog()
    # Build an AcroForm with a /Sig field whose /V is a DocTimeStamp sig
    acro = PDAcroForm(doc)
    catalog.set_acro_form(acro)
    fields = COSArray()
    sig_field = COSDictionary()
    sig_field.set_item(
        COSName.get_pdf_name("FT"), COSName.get_pdf_name("Sig")
    )
    timestamp_sig = COSDictionary()
    timestamp_sig.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("DocTimeStamp")
    )
    timestamp_sig.set_item(
        COSName.get_pdf_name("Contents"),
        COSString("placeholder"),
    )
    sig_field.set_item(COSName.get_pdf_name("V"), timestamp_sig)
    fields.add(sig_field)
    acro.get_cos_object().set_item(COSName.get_pdf_name("Fields"), fields)

    # Now add a new approval signature; should succeed (DocTimeStamp ignored)
    new_sig = PDSignature()
    set_mdp_permission(doc, new_sig, 1)
    doc.close()
