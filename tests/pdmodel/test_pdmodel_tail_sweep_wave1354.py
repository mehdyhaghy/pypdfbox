"""Wave 1354 tail-sweep tests for pdmodel/** (excl. graphics).

Each file in this module targets a single 1-3 missing-line gap surfaced by
``--cov=pypdfbox/pdmodel`` against ``tests/pdmodel/`` (graphics tree
excluded — owned by agent B in this wave).

The tests pin the upstream-named alias / Java-style helper / typed-factory
shim / setter type-error / static-wrapper / dispatch fall-through that
the existing test suite was leaving uncovered.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)

# ---------------------------------------------------------------------------
# common/function/type4/bitwise_operators.py line 83 — applyfor_integer alias
# ---------------------------------------------------------------------------


def test_bitwise_applyfor_integer_alias_forwards_to_canonical() -> None:
    """The lowercase-``f`` upstream alias delegates to ``apply_for_integer``."""
    from pypdfbox.pdmodel.common.function.type4.bitwise_operators import (
        And,
        Or,
        Xor,
    )

    # And/Or/Xor each implement apply_for_integer; applyfor_integer must mirror.
    assert And().applyfor_integer(0b1010, 0b1100) == 0b1000
    assert Or().applyfor_integer(0b1010, 0b0101) == 0b1111
    assert Xor().applyfor_integer(0b1100, 0b1010) == 0b0110


# ---------------------------------------------------------------------------
# common/function/type4/instruction_sequence_builder.py line 68
#   — get_current_sequence (public mirror of _get_current_sequence)
# ---------------------------------------------------------------------------


def test_instruction_sequence_builder_get_current_sequence_returns_top() -> None:
    from pypdfbox.pdmodel.common.function.type4.instruction_sequence_builder import (
        InstructionSequenceBuilder,
    )

    builder = InstructionSequenceBuilder()
    main = builder.get_instruction_sequence()
    # With no nested procs, current == main.
    assert builder.get_current_sequence() is main


# ---------------------------------------------------------------------------
# common/function/type4/relational_operators.py line 105
#   — AbstractNumberComparisonOperator.compare raises NotImplementedError
# ---------------------------------------------------------------------------


def test_abstract_number_comparison_operator_compare_is_abstract() -> None:
    from pypdfbox.pdmodel.common.function.type4.relational_operators import (
        AbstractNumberComparisonOperator,
    )

    op = AbstractNumberComparisonOperator()
    with pytest.raises(NotImplementedError):
        op.compare(1.0, 2.0)


# ---------------------------------------------------------------------------
# common/label_generator.py line 39 — remove() raises NotImplementedError
# ---------------------------------------------------------------------------


def test_label_generator_remove_unsupported() -> None:
    from pypdfbox.pdmodel.common.label_generator import LabelGenerator
    from pypdfbox.pdmodel.pd_page_label_range import PDPageLabelRange

    gen = LabelGenerator(PDPageLabelRange(), 3)
    with pytest.raises(NotImplementedError):
        gen.remove()


# ---------------------------------------------------------------------------
# common/pd_stream.py line 383 — internal_get_decode_params raises on a
# non-dictionary, non-null entry inside a COSArray decode-params chain.
# ---------------------------------------------------------------------------


def test_pd_stream_internal_get_decode_params_skips_bogus_entry() -> None:
    # Wave 1529 aligned PDStream.internal_get_decode_params with upstream
    # leniency: a non-dict/non-null /DecodeParms array element is SKIPPED
    # (upstream logs and ignores it), not rejected. The list is therefore
    # intentionally not index-aligned with /Filter on such holes.
    from pypdfbox.cos.cos_stream import COSStream
    from pypdfbox.pdmodel.common.pd_stream import PDStream

    cs = COSStream()
    # Build a /DecodeParms array with a stray non-dict/non-null entry.
    arr = COSArray()
    good = COSDictionary()
    arr.add(good)
    arr.add(COSInteger(42))  # not a dict and not COSNull → skipped, not raised
    cs.set_item(COSName.get_pdf_name("DecodeParms"), arr)

    pdstream = PDStream(cs)
    params = pdstream.internal_get_decode_params(
        COSName.get_pdf_name("DecodeParms"),
        COSName.get_pdf_name("DP"),
    )
    # The bogus COSInteger entry is dropped; only the dict survives.
    assert [type(p).__name__ for p in params] == ["COSDictionary"]


# ---------------------------------------------------------------------------
# documentinterchange/logicalstructure/pd_structure_tree_root.py line 587
#   — _to_cos returns a raw COSBase when value has no get_cos_object()
# ---------------------------------------------------------------------------


def test_structure_element_number_tree_node_convert_value_to_cos_passthrough() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
        PDStructureElementNumberTreeNode,
    )

    node = PDStructureElementNumberTreeNode(COSDictionary())
    # COSInteger is a COSBase but has get_cos_object (it returns self).
    # Force the "no get_cos_object" branch via a bare COSBase-like sentinel —
    # because the helper's contract is "passthrough when no get_cos_object",
    # the cast-to-COSBase happens regardless. Easiest reachable input: a
    # COSInteger after stripping the attribute via a wrapper.
    class _Bare:
        """Stand-in COSBase with no get_cos_object — mirrors raw passthrough."""

    bare = _Bare()
    # Internal helper is the only code path that exercises line 587; route via
    # convert_value_to_cos which delegates to _to_cos.
    result = node.convert_value_to_cos(bare)  # type: ignore[arg-type]
    assert result is bare


# ---------------------------------------------------------------------------
# encryption/security_handler.py line 620 — _decrypt_array uses ``set`` setter
# when the array exposes it (COSArray does), and the element changed.
# ---------------------------------------------------------------------------


def test_security_handler_decrypt_array_uses_set_method_on_change() -> None:
    """Exercise the COSArray.set() branch of _decrypt_array.

    We subclass SecurityHandler so :meth:`decrypt` always returns a fresh
    object (forces the ``replaced is not elem`` branch to True), and we
    keep ``set`` callable so line 620 fires (rather than the fallback
    ``__setitem__`` branch).
    """
    from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler

    class _ReplacingHandler(SecurityHandler):
        def prepare_document(self, doc: object) -> None:  # pragma: no cover
            pass

        def prepare_for_decryption(self, *args: object, **kw: object) -> None:  # pragma: no cover
            pass

        def decrypt(self, obj: object, obj_num: int, gen_num: int) -> object:
            # Return a new COSString every time → triggers replacement.
            return COSString(b"X")

    handler = _ReplacingHandler()
    arr = COSArray()
    arr.add(COSString(b"a"))
    arr.add(COSString(b"b"))
    handler._decrypt_array(arr, 1, 0)
    # Both slots were swapped with the fresh COSStrings.
    assert all(isinstance(arr.get(i), COSString) for i in range(arr.size()))
    assert arr.get(0).get_string() == "X"
    assert arr.get(1).get_string() == "X"


# ---------------------------------------------------------------------------
# fdf/fdf_annotation_ink.py line 59 — get_ink_list emits [] for non-array entry
# ---------------------------------------------------------------------------


def test_fdf_annotation_ink_get_ink_list_skips_non_array_entries() -> None:
    from pypdfbox.pdmodel.fdf.fdf_annotation_ink import FDFAnnotationInk

    annot = COSDictionary()
    ink_list = COSArray()
    # First entry is a proper path; second is a stray non-array → maps to [].
    good = COSArray()
    good.add(COSFloat(1.0))
    good.add(COSFloat(2.0))
    ink_list.add(good)
    ink_list.add(COSString(b"not-a-path"))
    annot.set_item(COSName.get_pdf_name("InkList"), ink_list)

    fdf = FDFAnnotationInk(annot)
    paths = fdf.get_ink_list()
    assert paths == [[1.0, 2.0], []]


# ---------------------------------------------------------------------------
# fdf/fdf_annotation_stamp.py line 103 — parse_dict_element early-returns the
# empty result when the element has no ``iter`` attribute.
# ---------------------------------------------------------------------------


def test_fdf_annotation_stamp_parse_dict_element_no_iter_returns_empty() -> None:
    from pypdfbox.pdmodel.fdf.fdf_annotation_stamp import FDFAnnotationStamp

    stamp = FDFAnnotationStamp(COSDictionary())

    # An object without ``iter`` triggers the ``children is None`` early return.
    class _NoIter:
        pass

    result = stamp.parse_dict_element(_NoIter())
    assert isinstance(result, COSDictionary)
    assert result.size() == 0


# ---------------------------------------------------------------------------
# font/font_mapper_impl.py lines 204-206 — get_provider lazy-installs the
# FileSystemFontProvider when none has been set.
# ---------------------------------------------------------------------------


def test_font_mapper_impl_get_provider_lazy_installs_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force a fresh FontMapperImpl, then call get_provider() with no
    pre-installed provider. The default FileSystemFontProvider must be
    constructed via the lazy import branch (lines 204-206)."""
    from pypdfbox.pdmodel.font import font_mapper_impl as fmi_module

    # Stub FileSystemFontProvider so we don't scan the host's fonts.
    class _FakeProvider:
        def __init__(self, cache: object) -> None:
            self._cache = cache

        def get_font_info(self) -> list[object]:
            # set_provider iterates this; an empty list satisfies the contract.
            return []

    # Patch the module that the lazy import goes through.
    import pypdfbox.pdmodel.font.file_system_font_provider as fsfp

    monkeypatch.setattr(fsfp, "FileSystemFontProvider", _FakeProvider)

    impl = fmi_module.FontMapperImpl()
    # Force the cached singleton state to "no provider yet".
    impl._font_provider = None
    provider = impl.get_provider()
    assert isinstance(provider, _FakeProvider)


# ---------------------------------------------------------------------------
# font/pd_type1_font_embedder.py lines 136-137 — width-computation fallback
# when get_type1_width raises.
# ---------------------------------------------------------------------------


def test_pd_type1_font_embedder_width_fallback_on_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drive the constructor's per-glyph width loop through a Type1 stub
    whose ``getGlyphSet`` raises ValueError — the embedder must catch the
    error and substitute width=0 (lines 136-137).
    """
    import io as _io

    import fontTools.t1Lib as _t1mod

    # Defensive: embedder references these as static-attribute constants
    # on COSName; ``cos_name.py`` does not pre-register them, so other
    # embedder tests register them on import (see
    # tests/pdmodel/font/test_pd_true_type_font_embedder_coverage.py).
    # Mirror that registration here to keep this test self-contained.
    if not hasattr(COSName, "BASE_FONT"):
        COSName.BASE_FONT = COSName.get_pdf_name("BaseFont")  # type: ignore[attr-defined]
    if not hasattr(COSName, "ENCODING"):
        COSName.ENCODING = COSName.get_pdf_name("Encoding")  # type: ignore[attr-defined]
    if not hasattr(COSName, "FONT_DESC"):
        COSName.FONT_DESC = COSName.get_pdf_name("FontDescriptor")  # type: ignore[attr-defined]

    from pypdfbox.pdmodel.font.pd_type1_font_embedder import PDType1FontEmbedder
    from pypdfbox.pdmodel.pd_document import PDDocument

    class _StubT1:
        """Stub T1Font that synthesises a font dict but blows up on widths."""

        def __init__(self, _stream: object) -> None:
            # FontName + 256-element Encoding so the loop reaches the
            # ``name and name != ".notdef"`` width path. FontBBox keeps
            # build_font_descriptor happy.
            self.font = {
                "FontName": "Stub",
                "FontBBox": [0, 0, 1000, 1000],
                "Encoding": ["A"] + [".notdef"] * 255,
            }

        def getGlyphSet(self) -> object:  # noqa: N802 — fontTools API
            raise ValueError("forced width-lookup failure")

    monkeypatch.setattr(_t1mod, "T1Font", _StubT1)

    # Minimal valid PFB byte layout (markers + segment lengths).
    seg1 = b"%!PS"
    seg2 = b"bin"
    seg3 = b"end"
    pfb = (
        b"\x80\x01" + len(seg1).to_bytes(4, "little") + seg1
        + b"\x80\x02" + len(seg2).to_bytes(4, "little") + seg2
        + b"\x80\x01" + len(seg3).to_bytes(4, "little") + seg3
        + b"\x80\x03"
    )

    doc = PDDocument()
    try:
        target = COSDictionary()
        PDType1FontEmbedder(doc, target, _io.BytesIO(pfb), None)
        widths = target.get_dictionary_object(COSName.WIDTHS)
        assert isinstance(widths, COSArray)
        # Every code falls back to 0 because getGlyphSet raised.
        assert all(int(w.int_value()) == 0 for w in widths)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# interactive/action/pd_action_factory.py line 44 — return None when /S
# subtype is absent.
# ---------------------------------------------------------------------------


def test_pd_action_factory_create_action_returns_none_when_subtype_missing() -> None:
    from pypdfbox.pdmodel.interactive.action.pd_action_factory import (
        PDActionFactory,
    )

    # An action dict with no /S subtype → factory returns None (line 44).
    blank = COSDictionary()
    assert PDActionFactory.create_action(blank) is None


# ---------------------------------------------------------------------------
# interactive/annotation/handlers/pd_ink_appearance_handler.py line 67 — early
# return when annotation has no /Rect.
# ---------------------------------------------------------------------------


def test_pd_ink_appearance_handler_no_rect_short_circuits() -> None:
    """When the annotation has no /Rect, the handler returns without writing
    an appearance stream (line 67)."""
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_ink_appearance_handler import (
        PDInkAppearanceHandler,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_ink import (
        PDAnnotationInk,
    )

    # Build an ink annotation with a color, /BS, and an ink list — but
    # explicitly *no* /Rect. The handler must reach the rect check (line 65)
    # and return on line 67 without raising.
    ink_dict = COSDictionary()
    # /C — stroke color (DeviceRGB black).
    color = COSArray()
    color.add(COSFloat(0.0))
    color.add(COSFloat(0.0))
    color.add(COSFloat(0.0))
    ink_dict.set_item(COSName.get_pdf_name("C"), color)
    # /BS — border style with width=1 so AnnotationBorder.get_annotation_border
    # returns ab.width != 0 and the flow proceeds past line 39-40.
    bs = COSDictionary()
    bs.set_item(COSName.get_pdf_name("W"), COSFloat(1.0))
    ink_dict.set_item(COSName.get_pdf_name("BS"), bs)
    # /InkList — one stroke path with two points.
    ink_list = COSArray()
    path = COSArray()
    path.add(COSFloat(10.0))
    path.add(COSFloat(10.0))
    path.add(COSFloat(20.0))
    path.add(COSFloat(20.0))
    ink_list.add(path)
    ink_dict.set_item(COSName.get_pdf_name("InkList"), ink_list)
    annot = PDAnnotationInk(ink_dict)
    # Sanity check that /Rect really is absent.
    assert annot.get_rectangle() is None

    handler = PDInkAppearanceHandler(annot)
    # generate_normal_appearance must not raise even though /Rect is None.
    handler.generate_normal_appearance()


# ---------------------------------------------------------------------------
# interactive/annotation/pd_annotation_screen.py line 33 — _as_cos_dictionary
# raises TypeError for a non-wrapper, non-dict value.
# ---------------------------------------------------------------------------


def test_pd_annotation_screen_set_action_rejects_arbitrary_value() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_screen import (
        PDAnnotationScreen,
    )

    screen = PDAnnotationScreen()
    with pytest.raises(TypeError, match="set_action expects"):
        # ``42`` is not a COSDictionary and has no ``get_cos_object`` —
        # hits the final-branch raise at line 33-36.
        screen.set_action(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# interactive/annotation/pd_annotation_watermark.py line 62 — set_fixed_print
# raises on a value with neither COSDictionary nor get_cos_object().
# ---------------------------------------------------------------------------


def test_pd_annotation_watermark_set_fixed_print_rejects_unknown_value() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_watermark import (
        PDAnnotationWatermark,
    )

    wm = PDAnnotationWatermark()
    with pytest.raises(TypeError, match="set_fixed_print expects"):
        wm.set_fixed_print("not a dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# interactive/annotation/pd_appearance_stream_name_tree_node.py line 53
#   — convert_cos_to_pd routes through convert_cos_to_value.
# ---------------------------------------------------------------------------


def test_pd_appearance_stream_name_tree_node_convert_cos_to_pd() -> None:
    from pypdfbox.cos.cos_stream import COSStream
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
        PDAppearanceStream,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream_name_tree_node import (
        PDAppearanceStreamNameTreeNode,
    )

    node = PDAppearanceStreamNameTreeNode(COSDictionary())
    stream = COSStream()
    pd = node.convert_cos_to_pd(stream)
    assert isinstance(pd, PDAppearanceStream)


# ---------------------------------------------------------------------------
# interactive/annotation/pd_external_data_dictionary.py line 23 — preserve a
# caller-supplied COSDictionary instead of allocating a new one.
# ---------------------------------------------------------------------------


def test_pd_external_data_dictionary_preserves_caller_dict() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_external_data_dictionary import (
        PDExternalDataDictionary,
    )

    backing = COSDictionary()
    backing.set_name(COSName.SUBTYPE, "Markup3D")
    ext = PDExternalDataDictionary(backing)
    # The wrapper must reuse the caller's dict (line 23), not allocate.
    assert ext.get_cos_object() is backing
    assert ext.get_subtype() == "Markup3D"


# ---------------------------------------------------------------------------
# interactive/form/pd_variable_text.py line 88 — get_default_appearance_string
# returns None when the AcroForm has no /DR resources.
# ---------------------------------------------------------------------------


def test_pd_variable_text_get_default_appearance_string_returns_none_without_dr(
    tmp_path,
) -> None:
    """If the field's inheritable /DA is set but the parent AcroForm exposes
    no /DR resources, the wrapper returns ``None`` (line 88)."""
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
    from pypdfbox.pdmodel.pd_document import PDDocument

    with PDDocument() as doc:
        acro = PDAcroForm(doc)
        # Field with explicit /DA but parent AcroForm without /DR.
        field_dict = COSDictionary()
        field_dict.set_item(
            COSName.get_pdf_name("DA"), COSString(b"/Helv 12 Tf 0 g")
        )
        field = PDTextField(acro, field_dict, None)
        # Sanity: parent acro form has no default-resources dict.
        assert acro.get_default_resources() is None
        assert field.get_default_appearance_string() is None


# ---------------------------------------------------------------------------
# pd_document_name_dictionary.py line 408 — get_ap_raw returns None when /AP
# is absent on the names dictionary.
# ---------------------------------------------------------------------------


def test_pd_document_name_dictionary_get_ap_raw_returns_none_when_absent() -> None:
    from pypdfbox.pdmodel.pd_document_name_dictionary import (
        PDDocumentNameDictionary,
    )

    names = PDDocumentNameDictionary(None, COSDictionary())
    assert names.get_ap_raw() is None


# ---------------------------------------------------------------------------
# resource_cache.py line 35 — ResourceCache.put dispatches PDXObject (non-form)
# to put_x_object.
# ---------------------------------------------------------------------------


def test_resource_cache_put_dispatches_plain_pdxobject() -> None:
    """Cover ``ResourceCache.put`` line 35: PDXObject branch (not PDFormXObject).

    ``ResourceCache`` is the upstream-named alias subclass of the abstract
    :class:`PDResourceCache`. To get a concrete instance we route through
    :class:`DefaultResourceCache` which fills in the abstract methods.
    """
    from pypdfbox.cos.cos_object import COSObject
    from pypdfbox.cos.cos_stream import COSStream
    from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
    from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache
    from pypdfbox.pdmodel.resource_cache import ResourceCache

    class _ConcreteResourceCache(ResourceCache, DefaultResourceCache):
        """Concrete cache combining the upstream-named alias's ``put`` and
        the default-impl's abstract method bodies."""

    class _PlainXObject(PDXObject):
        """Bare PDXObject subclass that is *not* a PDFormXObject."""

    cache = _ConcreteResourceCache()
    stream = COSStream()
    indirect = COSObject(1, 0, resolved=stream)
    plain = _PlainXObject(stream, COSName.IMAGE)
    # Triggers the PDXObject branch (line 34-35), not the PDFormXObject one.
    cache.put(indirect, plain)
    assert cache.get_x_object(indirect) is plain


# ---------------------------------------------------------------------------
# interactive/digitalsignature/pd_seed_value_certificate.py lines 465, 475 —
# static convert / get list-of-byte-array helpers.
# ---------------------------------------------------------------------------


def test_pd_seed_value_certificate_byte_array_static_helpers() -> None:
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value_certificate import (
        PDSeedValueCertificate,
    )

    payload = [b"\x01\x02", b"\xff\xee"]
    arr = PDSeedValueCertificate.convert_list_of_byte_arrays_to_cos_array(
        payload
    )
    assert isinstance(arr, COSArray)
    # Round-trip via the public unpack wrapper (line 475).
    out = PDSeedValueCertificate.get_list_of_byte_arrays_from_cos_array(arr)
    assert out == payload
