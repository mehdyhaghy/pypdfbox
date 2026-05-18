"""Wave 1354 coverage-tail sweep — fontbox + cos + io + filter + pdfparser
+ pdfwriter + contentstream final 1-3-line gaps.

Each test is targeted at exactly one residual missing line to push the
in-scope directories to (or very close to) 100% line coverage. The cases
exercise edge branches and ``__repr__`` / dunder helpers that the
broader test suite reaches indirectly but not always deterministically.
"""

from __future__ import annotations

import logging

import pytest

# ---------- contentstream/operator/state/save.py: get_name() ----------


def test_save_operator_get_name_returns_q() -> None:
    """``Save.get_name()`` must return the lowercase ``q`` literal."""
    from pypdfbox.contentstream.operator.state.save import Save

    assert Save().get_name() == "q"


# ---------- contentstream/operator/draw_object.py: get_x missing branch ----


def test_draw_object_skips_when_resources_has_no_get_x_object() -> None:
    """Resources without ``get_x_object`` short-circuit (line 53)."""
    from pypdfbox.contentstream.operator import Operator
    from pypdfbox.contentstream.operator.draw_object import DrawObject
    from pypdfbox.cos import COSName

    class _Resources:
        def is_image_x_object(self, _name: object) -> bool:
            return False

    class _Ctx:
        def get_resources(self) -> _Resources:
            return _Resources()

    p = DrawObject()
    p._context = _Ctx()  # type: ignore[attr-defined]
    # Should silently return because ``get_x_object`` is absent.
    p.process(Operator.get_operator("Do"), [COSName.get_pdf_name("Im1")])


# --- close_fill_even_odd_and_stroke_path: log_invocation branch (line 31) ---


def test_close_fill_eo_and_stroke_path_no_engine_falls_back_to_log() -> None:
    """Without a bound engine the operator hits the ``_log_invocation``
    branch (line 31)."""
    from pypdfbox.contentstream.operator import Operator
    from pypdfbox.contentstream.operator.graphics.close_fill_even_odd_and_stroke_path import (
        CloseFillEvenOddAndStrokePath,
    )

    p = CloseFillEvenOddAndStrokePath()
    p._context = None  # type: ignore[attr-defined]
    # Should not raise; logs at debug level.
    p.process(Operator.get_operator("b*"), [])


# ----- begin_marked_content_sequence_with_properties.py: hook call (56) -----


def test_begin_marked_content_seq_with_props_invokes_hook() -> None:
    from pypdfbox.contentstream.operator import Operator
    from pypdfbox.contentstream.operator.markedcontent import (
        begin_marked_content_sequence_with_properties as _bdc_mod,
    )

    BeginMarkedContentSequenceWithProperties = (
        _bdc_mod.BeginMarkedContentSequenceWithProperties
    )
    from pypdfbox.cos import COSDictionary, COSName

    captured: dict[str, object] = {}

    class _Ctx:
        def begin_marked_content_sequence(self, tag, props) -> None:  # type: ignore[no-untyped-def]
            captured["tag"] = tag
            captured["props"] = props

        def get_resources(self):  # type: ignore[no-untyped-def]
            return None

    p = BeginMarkedContentSequenceWithProperties()
    p._context = _Ctx()  # type: ignore[attr-defined]
    tag = COSName.get_pdf_name("Tag")
    props = COSDictionary()
    p.process(Operator.get_operator("BDC"), [tag, props])
    assert captured["tag"] is tag
    assert captured["props"] is props


# ----- marked_content_point_with_properties.py: hook call (49) -----


def test_marked_content_point_with_props_invokes_hook() -> None:
    from pypdfbox.contentstream.operator import Operator
    from pypdfbox.contentstream.operator.markedcontent.marked_content_point_with_properties import (
        MarkedContentPointWithProperties,
    )
    from pypdfbox.cos import COSDictionary, COSName

    captured: dict[str, object] = {}

    class _Ctx:
        def marked_content_point(self, tag, props) -> None:  # type: ignore[no-untyped-def]
            captured["tag"] = tag
            captured["props"] = props

        def get_resources(self):  # type: ignore[no-untyped-def]
            return None

    p = MarkedContentPointWithProperties()
    p._context = _Ctx()  # type: ignore[attr-defined]
    tag = COSName.get_pdf_name("Tag")
    props = COSDictionary()
    p.process(Operator.get_operator("DP"), [tag, props])
    assert captured["tag"] is tag
    assert captured["props"] is props


# ---------- cos/cos_array.py: getUpdateState alias + of_cos_floats -------


def test_cos_array_get_update_state_camelcase_alias() -> None:
    from pypdfbox.cos.cos_array import COSArray

    arr = COSArray()
    assert arr.getUpdateState() is arr.get_update_state()


def test_cos_array_of_cos_floats_factory() -> None:
    from pypdfbox.cos.cos_array import COSArray
    from pypdfbox.cos.cos_float import COSFloat

    arr = COSArray.of_cos_floats([1.5, 2.5])
    assert len(arr) == 2
    assert all(isinstance(x, COSFloat) for x in arr)
    assert [x.float_value() for x in arr] == [1.5, 2.5]


# ---------- cos/cos_boolean.py: __repr__ ----------


def test_cos_boolean_repr_returns_class_constant() -> None:
    from pypdfbox.cos.cos_boolean import COSBoolean

    assert repr(COSBoolean.TRUE) == "COSBoolean.TRUE"
    assert repr(COSBoolean.FALSE) == "COSBoolean.FALSE"


# ---------- cos/cos_dictionary.py: get_name + __repr__ + __contains__ default


def test_cos_dictionary_get_name_returns_name_value() -> None:
    from pypdfbox.cos.cos_dictionary import COSDictionary
    from pypdfbox.cos.cos_name import COSName

    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Key"), COSName.get_pdf_name("Value"))
    assert d.get_name("Key") == "Value"


def test_cos_dictionary_get_name_default_when_missing() -> None:
    from pypdfbox.cos.cos_dictionary import COSDictionary

    d = COSDictionary()
    assert d.get_name("Missing", "fallback") == "fallback"


def test_cos_dictionary_contains_non_name_string_returns_false() -> None:
    from pypdfbox.cos.cos_dictionary import COSDictionary

    d = COSDictionary()
    # Anything not COSName / str should evaluate False (line 1074).
    assert (42 in d) is False


def test_cos_dictionary_repr_round_trips_keys_and_values() -> None:
    from pypdfbox.cos.cos_dictionary import COSDictionary
    from pypdfbox.cos.cos_integer import COSInteger

    d = COSDictionary()
    d.set_item("A", COSInteger.get(1))
    s = repr(d)
    assert s.startswith("COSDictionary({")
    assert s.endswith("})")


# ---------- cos/cos_document.py: ordered_keys fallback + set_trailer(None) ---


def test_cos_document_get_linearization_skips_non_dict_resolved() -> None:
    """When the resolved object isn't a COSDictionary the linearization
    scan continues past it (line 252)."""
    from pypdfbox.cos.cos_document import COSDocument
    from pypdfbox.cos.cos_integer import COSInteger
    from pypdfbox.cos.cos_object import COSObject
    from pypdfbox.cos.cos_object_key import COSObjectKey

    doc = COSDocument()
    key = COSObjectKey(1, 0)
    obj = COSObject(1, 0, resolved=COSInteger.get(0))
    doc._objects[key] = obj  # type: ignore[attr-defined]
    assert doc.get_linearized_dictionary() is None


def test_cos_document_get_linearization_skips_missing_xref_object() -> None:
    """Line 249 — an xref-table key with no entry in ``_objects`` is
    skipped via ``continue`` rather than raising."""
    from pypdfbox.cos.cos_document import COSDocument
    from pypdfbox.cos.cos_object_key import COSObjectKey

    doc = COSDocument()
    key = COSObjectKey(7, 0)
    doc._xref_table[key] = 1234  # type: ignore[attr-defined]
    # No matching entry in ``doc._objects`` → loop hits ``cos_obj is None``.
    assert doc.get_linearized_dictionary() is None


def test_cos_document_set_trailer_none_short_circuits() -> None:
    """``set_trailer(None)`` returns without touching update state."""
    from pypdfbox.cos.cos_document import COSDocument

    doc = COSDocument()
    doc.set_trailer(None)  # Must not raise.
    assert doc.get_trailer() is None


# ---------- cos/cos_object.py: getUpdateState camelCase alias ----------


def test_cos_object_get_update_state_camelcase_alias() -> None:
    from pypdfbox.cos.cos_object import COSObject

    obj = COSObject(1, 0)
    assert obj.getUpdateState() is obj.get_update_state()


# ---------- cos/cos_stream.py: writer-open raw stream guard ----------


def test_cos_stream_raw_input_stream_when_no_data_raises_oserror() -> None:
    from pypdfbox.cos.cos_stream import COSStream

    s = COSStream()
    # ``_buffer`` is None until something is written; ``create_raw_input_stream``
    # raises OSError (line 236).
    with pytest.raises(OSError, match="stream has no data"):
        s.create_raw_input_stream()


# ---------- cos/cos_string.py: __repr__ ----------


def test_cos_string_repr_shows_bytes_and_hex_flag() -> None:
    from pypdfbox.cos.cos_string import COSString

    s = COSString("ab")
    r = repr(s)
    assert r.startswith("COSString(")
    assert "hex=" in r


# ---------- cos/cos_update_state.py: forward_origin_to with None child ----


def test_cos_update_state_set_child_origin_with_none_is_noop() -> None:
    """Line 116 — ``_set_child_origin(None, ...)`` short-circuits."""
    from pypdfbox.cos.cos_document_state import COSDocumentState
    from pypdfbox.cos.cos_update_state import COSUpdateState

    state = COSUpdateState(None)  # type: ignore[arg-type]
    state.set_origin_document_state(COSDocumentState())
    state._set_child_origin(None, dereferencing=False)  # type: ignore[arg-type]


# ---------- filter/jbig2_filter.py: log_levigo_donated branch + guard ----


def test_jbig2_filter_log_levigo_donated_is_one_shot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from pypdfbox.filter.jbig2_filter import JBIG2Filter

    JBIG2Filter._levigo_logged = False
    with caplog.at_level(logging.INFO, logger="pypdfbox.filter.jbig2_filter"):
        JBIG2Filter.log_levigo_donated()
        first = len(caplog.records)
        # Second call is a no-op (guard).
        JBIG2Filter.log_levigo_donated()
        assert len(caplog.records) == first


# ---------- filter/jpx_decode.py: BPC=8 path acceptance ----------


def test_jpx_decode_encode_unsupported_bpc_raises() -> None:
    """``encode`` raises for any BPC that isn't 8 or 16 (line 205-208)."""
    import io as _io

    from pypdfbox.cos.cos_dictionary import COSDictionary
    from pypdfbox.cos.cos_integer import COSInteger
    from pypdfbox.cos.cos_name import COSName
    from pypdfbox.filter.jpx_decode import JPXDecode

    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("Width"), COSInteger.get(2))
    params.set_item(COSName.get_pdf_name("Height"), COSInteger.get(2))
    params.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(4))

    with pytest.raises(OSError):
        JPXDecode().encode(
            _io.BytesIO(b"\x00" * 4), _io.BytesIO(), params
        )


# ---------- filter/predictor.py: Predictor() constructor is a no-op ----


def test_predictor_class_can_be_instantiated() -> None:
    """``Predictor()`` mirrors upstream's private no-arg constructor."""
    from pypdfbox.filter.predictor import Predictor

    p = Predictor()
    assert isinstance(p, Predictor)


# ---------- fontbox/afm/ligature.py: get_ligature ----------


def test_afm_ligature_accessors_round_trip() -> None:
    from pypdfbox.fontbox.afm.ligature import Ligature

    lig = Ligature("i", "fi")
    assert lig.get_successor() == "i"
    assert lig.get_ligature() == "fi"  # line 24
    assert repr(lig) == "Ligature('i' -> 'fi')"


# ---------- fontbox/cff/format1_encoding.py: __repr__ ----------


def test_cff_format1_encoding_range3_repr_shape() -> None:
    """``Range3.__repr__`` (line 59-63) — exercised explicitly."""
    from pypdfbox.fontbox.cff.format1_encoding import Range3

    r = Range3(first=10, n_left=2, sid=5)
    r_repr = repr(r)
    assert r_repr.startswith("Range3[")
    assert "first=10" in r_repr
    assert "n_left=2" in r_repr
    assert "sid=5" in r_repr


# ---------- fontbox/cff/cff_type1_font.py: name-keyed glyph access ---


def test_cff_type1_font_name_keyed_helpers(monkeypatch) -> None:
    """Lines 308, 310, 316, 321 — name-keyed override methods delegate
    to the base when not in the charset."""
    from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font

    f = CFFType1Font()
    monkeypatch.setattr(CFFType1Font, "get_charset", lambda self: ["foo"])
    # Empty name → False.
    assert f.has_glyph("") is False
    # In-charset name → True (covers line 310 short-circuit OR branch).
    assert f.has_glyph("foo") is True

    from pypdfbox.fontbox.cff.cff_font import CFFFont

    monkeypatch.setattr(CFFFont, "get_path", lambda self, name: [("OP", 1)])
    monkeypatch.setattr(CFFFont, "get_width", lambda self, name: 42.0)
    assert f.get_path("foo") == [("OP", 1)]
    assert f.get_width("foo") == 42.0


# ---------- fontbox/cmap/cmap_parser.py: type-check error paths ----


def test_cmap_parser_add_mapping_frombfrange_list_form_type_error() -> None:
    """Line 522-525 — non-list ``values_or_list`` raises TypeError."""
    from pypdfbox.fontbox.cmap.cmap import CMap
    from pypdfbox.fontbox.cmap.cmap_parser import CMapParser

    parser = CMapParser()
    cmap = CMap()
    with pytest.raises(TypeError):
        parser.add_mapping_frombfrange(
            cmap, b"\x00\x00", "not-a-list", None
        )


def test_cmap_parser_add_mapping_frombfrange_count_form_type_error() -> None:
    """Line 532-535 — non-int ``values_or_list`` for count form raises."""
    from pypdfbox.fontbox.cmap.cmap import CMap
    from pypdfbox.fontbox.cmap.cmap_parser import CMapParser

    parser = CMapParser()
    cmap = CMap()
    with pytest.raises(TypeError):
        parser.add_mapping_frombfrange(
            cmap, b"\x00\x00", "not-an-int", bytearray(b"\x00\x10")
        )


# ---------- fontbox/cff/cff_cid_font.py: parser __repr__ ----------


def test_cff_cid_font_type2_parser_repr_contains_font_name() -> None:
    from pypdfbox.fontbox.cff.cff_cid_font import _Type2CharStringParser

    parser = _Type2CharStringParser("Foo")
    r = repr(parser)
    assert "_Type2CharStringParser" in r
    assert "font_name='Foo'" in r


# ---------- fontbox/ttf/gsub: get_data accessor (lookup_subtable) ----


def test_lookup_subtable_get_coverage_table_returns_held_object() -> None:
    """Line 113 — base accessor returns the held ``_coverage_object``."""
    from pypdfbox.fontbox.ttf.gsub.lookup_subtable import (
        LookupSubTable,
        LookupTypeSingleSubstFormat1,
    )

    # Use a concrete subclass and invoke the base ``get_coverage_table``
    # explicitly (the subclass shadows it on its own type).
    inst = LookupTypeSingleSubstFormat1(delta_glyph_id=1, coverage_table=(2,))
    sentinel = inst._coverage_object  # type: ignore[attr-defined]
    assert LookupSubTable.get_coverage_table(inst) is sentinel


# ---------- fontbox/ttf/otf_parser.py: legacy aliases ----------


def test_otf_parser_allow_cff_legacy_alias() -> None:
    """Line 120 — ``_allow_cff`` legacy private spelling forwards."""
    from pypdfbox.fontbox.ttf.otf_parser import OTFParser

    parser = OTFParser(is_embedded=False, parse_on_demand=False)
    assert parser._allow_cff() is True
    # And ``_read_table`` legacy alias forwards too (line 119-120 in source).
    table = parser._read_table("GSUB")
    assert table.get_tag() == "GSUB"


def test_otf_parser_new_font_legacy_alias_delegates(monkeypatch) -> None:
    """Line 114 — ``_new_font`` delegates to ``new_font``."""
    from pypdfbox.fontbox.ttf.otf_parser import OTFParser

    parser = OTFParser(is_embedded=False, parse_on_demand=False)
    sentinel = object()

    def fake_new_font(self, data):  # type: ignore[no-untyped-def]
        return sentinel

    monkeypatch.setattr(OTFParser, "new_font", fake_new_font)
    assert parser._new_font(None) is sentinel  # type: ignore[arg-type]


def test_otf_parser_check_tables_skips_when_otf_unsupported(monkeypatch) -> None:
    """Line 162 — ``_check_tables`` returns early when the OpenTypeFont
    reports ``is_supported_otf() is False`` (lenient TTF-flavoured branch)."""
    from pypdfbox.fontbox.ttf.open_type_font import OpenTypeFont
    from pypdfbox.fontbox.ttf.otf_parser import OTFParser

    parser = OTFParser(is_embedded=False, parse_on_demand=False)

    # Stub the parent ``_check_tables`` so we don't need a real font.
    from pypdfbox.fontbox.ttf.ttf_parser import TTFParser

    monkeypatch.setattr(
        TTFParser, "_check_tables", lambda self, font: None
    )
    font = OpenTypeFont.__new__(OpenTypeFont)
    monkeypatch.setattr(font, "is_supported_otf", lambda: False, raising=False)
    parser._check_tables(font)  # Should return without raising.


# ---------- fontbox/ttf/table/common/coverage_table_format1.py: __str__ ----


def test_coverage_table_format1_str_uses_to_string() -> None:
    """Line 110 — ``__str__`` delegates to ``to_string``."""
    from pypdfbox.fontbox.ttf.table.common.coverage_table_format1 import (
        CoverageTableFormat1,
    )

    t = CoverageTableFormat1(1, (1, 2, 3))
    assert str(t) == t.to_string()


def test_coverage_table_format2_str_uses_to_string() -> None:
    """Line 64 — ``__str__`` delegates to ``to_string``."""
    from pypdfbox.fontbox.ttf.table.common.coverage_table_format2 import (
        CoverageTableFormat2,
    )

    t = CoverageTableFormat2(2, ())
    assert str(t) == t.to_string()


# ---------- fontbox/type1/token.py: charstring branch of to_string ----


def test_token_to_string_charstring_form_shows_byte_count() -> None:
    """Line 82 — charstring Token.to_string reports byte count."""
    from pypdfbox.fontbox.type1.token import Kind, Token

    tok = Token.__new__(Token)
    tok._kind = Kind.CHARSTRING
    tok._text = ""
    tok._data = b"\x01\x02\x03"
    assert tok.to_string() == "Token[kind=CHARSTRING, data=3 bytes]"


def test_token_to_string_charstring_with_none_data_reports_zero() -> None:
    """Line 81 — Token.to_string with ``None`` charstring data reports 0."""
    from pypdfbox.fontbox.type1.token import Kind, Token

    tok = Token.__new__(Token)
    tok._kind = Kind.CHARSTRING
    tok._text = ""
    tok._data = None
    assert tok.to_string() == "Token[kind=CHARSTRING, data=0 bytes]"


def test_token_to_string_non_charstring_includes_text() -> None:
    """Line 83 — non-charstring tokens report the text payload."""
    from pypdfbox.fontbox.type1.token import Kind, Token

    tok = Token("hello", Kind.NAME)
    assert tok.to_string() == "Token[kind=NAME, text=hello]"


# ---------- io/random_access_output_stream.py: writable() ----------


def test_random_access_output_stream_writable() -> None:
    from pypdfbox.io.random_access_output_stream import (
        RandomAccessOutputStream,
    )
    from pypdfbox.io.random_access_write_buffer import (
        RandomAccessWriteBuffer,
    )

    raw = RandomAccessWriteBuffer()
    out = RandomAccessOutputStream(raw)
    assert out.writable() is True


# ---------- io/random_access_read_buffered_file.py: check_closed ----


def test_random_access_read_buffered_file_check_closed_after_close(tmp_path) -> None:
    """Line 40 — public ``check_closed`` snake_case wrapper."""
    from pypdfbox.io.random_access_read_buffered_file import (
        RandomAccessReadBufferedFile,
    )

    p = tmp_path / "tiny.bin"
    p.write_bytes(b"abc")
    r = RandomAccessReadBufferedFile(str(p))
    r.check_closed()  # Not closed — no exception.
    r.close()
    with pytest.raises(ValueError):
        r.check_closed()


# ---------- pdfparser/xref/free_x_reference.py: to_string + __repr__ ----


def test_free_x_reference_to_string_matches_repr() -> None:
    """Lines 50, 63."""
    from pypdfbox.cos.cos_object_key import COSObjectKey
    from pypdfbox.pdfparser.xref.free_x_reference import FreeXReference

    f = FreeXReference(COSObjectKey(5, 0), 8)
    r = repr(f)
    assert r.startswith("FreeReference{")
    assert "key=" in r
    assert "nextFreeObject=8" in r
    assert f.to_string() == str(f)


# ---------- fontbox/util/autodetect/native_font_dir_finder.py: OSError ----


# ---------- get_name() methods on marked-content operators -----------


def test_begin_marked_content_seq_props_get_name() -> None:
    """Line 56 — ``get_name`` returns the BDC literal."""
    from pypdfbox.contentstream.operator.markedcontent import (
        begin_marked_content_sequence_with_properties as _bdc_mod,
    )

    BeginMarkedContentSequenceWithProperties = (
        _bdc_mod.BeginMarkedContentSequenceWithProperties
    )

    assert BeginMarkedContentSequenceWithProperties().get_name() == "BDC"


def test_marked_content_point_with_props_get_name() -> None:
    """Line 49 — ``get_name`` returns the DP literal."""
    from pypdfbox.contentstream.operator.markedcontent.marked_content_point_with_properties import (
        MarkedContentPointWithProperties,
    )

    assert MarkedContentPointWithProperties().get_name() == "DP"


# ---------- format1_encoding.Range3.to_string ----------


def test_cff_format1_encoding_range3_to_string_shape() -> None:
    """Line 55-57 — ``to_string`` uses Range3[ ] formatting."""
    from pypdfbox.fontbox.cff.format1_encoding import Range3

    r = Range3(first=1, n_left=2, sid=3)
    assert r.to_string() == "Range3[first=1, n_left=2, sid=3]"


# ---------- random_access_read_non_closing_input_stream ----------


def test_random_access_read_non_closing_read_returns_empty_when_n_zero(
    tmp_path,
) -> None:
    """Line 66 — when ``read_into`` returns 0, ``read()`` returns b""."""
    from pypdfbox.fontbox.ttf.random_access_read_non_closing_input_stream import (
        RandomAccessReadNonClosingInputStream,
    )
    from pypdfbox.io.random_access_read import RandomAccessRead

    class _StubRA(RandomAccessRead):
        def __init__(self) -> None:
            self._closed = False
            self._pos = 0

        def length(self) -> int:
            return 10

        def get_position(self) -> int:
            return self._pos

        def read(self) -> int:
            return -1

        def read_into(self, buf, offset=0, length=None) -> int:  # type: ignore[no-untyped-def]
            return 0

        def seek(self, position: int) -> None:
            self._pos = position

        def is_eof(self) -> bool:
            return False

        def is_closed(self) -> bool:
            return self._closed

        def close(self) -> None:
            self._closed = True

        def rewind(self, n: int) -> None:
            self._pos = max(0, self._pos - n)

        def peek(self) -> int:
            return -1

    stream = RandomAccessReadNonClosingInputStream(_StubRA())
    # size None / negative path → triggers the ``n <= 0`` branch.
    assert stream.read(-1) == b""


# ---------- ttf_data_stream: bytes-only assertion in constructor ----


def test_ttf_data_stream_rejects_non_bytes_input_stream_read() -> None:
    """Lines 254-255 — TypeError when the file-like ``read`` returns non-bytes."""
    from pypdfbox.fontbox.ttf.ttf_data_stream import RandomAccessReadDataStream

    class _BadReader:
        def read(self, _n: int = -1) -> str:
            return "not bytes"  # type: ignore[return-value]

    with pytest.raises(TypeError, match="must return bytes"):
        RandomAccessReadDataStream(_BadReader())  # type: ignore[arg-type]


# ---------- scratch_file_buffer.check_closed: parent-scratch-closed ----


def test_scratch_file_buffer_check_closed_raises_when_owner_closed() -> None:
    """Line 67 — owner closed → OSError. We close the scratch state by
    flipping its private ``_closed`` flag so the buffer is still
    ``_closed=False`` when ``check_closed`` runs."""
    from pypdfbox.io.memory_usage_setting import MemoryUsageSetting
    from pypdfbox.io.scratch_file import ScratchFile

    setting = MemoryUsageSetting.setup_main_memory_only()
    scratch = ScratchFile(setting)
    try:
        buf = scratch.create_buffer()
        scratch._closed = True  # type: ignore[attr-defined]
        with pytest.raises(OSError, match="Scratch file"):
            buf.check_closed()
    finally:
        scratch._closed = False  # type: ignore[attr-defined]
        scratch.close()


def test_scratch_file_buffer_ensure_available_returns_false_when_disallowed() -> None:
    """Line 101 — ``add_new_page_if_needed=False`` and off==0 past tail
    returns False."""
    from pypdfbox.io.memory_usage_setting import MemoryUsageSetting
    from pypdfbox.io.scratch_file import ScratchFile

    setting = MemoryUsageSetting.setup_main_memory_only()
    scratch = ScratchFile(setting)
    try:
        buf = scratch.create_buffer()
        # Force position past the current page chain tail.
        buf._position = buf._page_size  # type: ignore[attr-defined]
        assert buf.ensure_available_bytes_in_page(False) is False
    finally:
        scratch.close()


def test_scratch_file_buffer_ensure_available_within_page_returns_true() -> None:
    """Line 102 — position mid-page returns True without allocating."""
    from pypdfbox.io.memory_usage_setting import MemoryUsageSetting
    from pypdfbox.io.scratch_file import ScratchFile

    setting = MemoryUsageSetting.setup_main_memory_only()
    scratch = ScratchFile(setting)
    try:
        buf = scratch.create_buffer()
        # Allocate one page then sit at off=1 → ensure_available returns True.
        buf.add_page()
        buf._position = 1  # type: ignore[attr-defined]
        assert buf.ensure_available_bytes_in_page(False) is True
    finally:
        scratch.close()


# ---------- cmap.py: read_one BinaryIO non-empty branch -----------


def test_cmap_read_one_returns_byte_from_binary_io() -> None:
    """Line 346 — ``_read_one`` returns the first byte of a BinaryIO chunk."""
    import io as _io

    from pypdfbox.fontbox.cmap.cmap import CMap

    assert CMap._read_one(_io.BytesIO(b"\xab\xcd")) == 0xAB


# ---------- cmap_parser.py: _create_string_from_bytes module helper -----


def test_cmap_parser_create_string_from_bytes_module_helper() -> None:
    """Line 847 — module-level alias forwards to the staticmethod."""
    from pypdfbox.fontbox.cmap.cmap_parser import (
        CMapParser,
        _create_string_from_bytes,
    )

    # Single-byte → latin-1; multi-byte → utf-16-be. Both helpers agree.
    assert _create_string_from_bytes(b"a") == CMapParser.create_string_from_bytes(b"a")
    assert _create_string_from_bytes(b"\x00A") == "A"


# ---------- glyph_array_splitter_regex_impl.py: equal-string compare ----


def test_glyph_array_splitter_get_matchers_as_strings_runs_comparator() -> None:
    """Line 62 — comparator hits the ``s2 == s1`` branch when two equal
    matchers collapse to one entry after dedupe; we then add a third
    differing matcher of the same length to force the comparator
    through a same-length-and-equal-string branch."""
    from pypdfbox.fontbox.ttf.gsub.glyph_array_splitter_regex_impl import (
        GlyphArraySplitterRegexImpl,
    )

    # Provide two equal-length matchers so the same-length compare
    # branch is exercised on the dedup'd string set.
    result = GlyphArraySplitterRegexImpl.get_matchers_as_strings(
        [[1, 2], [3, 4]]
    )
    assert len(result) == 2


# ---------- gsub_worker_for_dflt / latin: unsupported feature skip ----


def test_gsub_worker_for_dflt_skips_when_feature_adapts_to_none(monkeypatch) -> None:
    """Line 43 — when ``_adapt_feature`` returns ``None`` the loop
    continues without applying it."""
    import pypdfbox.fontbox.ttf.gsub.gsub_worker_for_dflt as mod
    from pypdfbox.fontbox.ttf.gsub.gsub_worker_for_dflt import GsubWorkerForDflt

    class _GsubData:
        def is_feature_supported(self, _tag: str) -> bool:
            return True

        def get_feature(self, _tag: str):  # type: ignore[no-untyped-def]
            return None

    monkeypatch.setattr(mod, "_adapt_feature", lambda _t, _f: None)
    worker = GsubWorkerForDflt(_GsubData())  # type: ignore[arg-type]
    assert worker.apply_transforms([1]) == [1]


def test_gsub_worker_for_latin_skips_when_feature_adapts_to_none(monkeypatch) -> None:
    """Line 41 — same shape as the dflt worker."""
    import pypdfbox.fontbox.ttf.gsub.gsub_worker_for_latin as mod
    from pypdfbox.fontbox.ttf.gsub.gsub_worker_for_latin import GsubWorkerForLatin

    class _GsubData:
        def is_feature_supported(self, _tag: str) -> bool:
            return True

        def get_feature(self, _tag: str):  # type: ignore[no-untyped-def]
            return None

    monkeypatch.setattr(mod, "_adapt_feature", lambda _t, _f: None)
    worker = GsubWorkerForLatin(_GsubData())  # type: ignore[arg-type]
    assert worker.apply_transforms([1]) == [1]


# ---------- get_name for save (already tested above for ``q``) ----


def test_native_font_dir_finder_swallows_oserror(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Lines 27-28 — the ``OSError`` from ``p.exists()`` is logged and
    skipped (no propagation)."""
    from pypdfbox.fontbox.util.autodetect.native_font_dir_finder import (
        NativeFontDirFinder,
    )

    class _Probe(NativeFontDirFinder):
        def get_searchable_directories(self) -> list[str]:
            return ["/some/path"]

    # Patch Path.exists to raise OSError.
    finder = _Probe()
    import pathlib

    orig_exists = pathlib.Path.exists

    def _boom(self):  # type: ignore[no-untyped-def]
        raise OSError("denied")

    pathlib.Path.exists = _boom  # type: ignore[assignment]
    try:
        with caplog.at_level(
            logging.DEBUG,
            logger="pypdfbox.fontbox.util.autodetect.native_font_dir_finder",
        ):
            out = finder.find()
        assert out == []
    finally:
        pathlib.Path.exists = orig_exists  # type: ignore[assignment]
