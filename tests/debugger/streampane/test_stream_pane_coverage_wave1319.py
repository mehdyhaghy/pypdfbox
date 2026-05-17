"""Coverage-boost tests for :mod:`pypdfbox.debugger.streampane.stream_pane`
(wave 1319).

Wave 1309 covered the public dispatch helpers. This wave exercises:

* The ``resources_dic`` construction branch (lazy PDResources import).
* :meth:`StreamPane._build_header` back-compat alias.
* :meth:`StreamPane._on_filter_changed` — image / decoded / text+hex
  branches, plus the OSError-swallow.
* :meth:`StreamPane._rebuild_notebook` — removes-old, adds-new tabs.
* :meth:`StreamPane.request_stream_text` — XML-metadata nice-view +
  empty-stream guard.
* :class:`_ContentStreamEmitter` — operand branches (COSBoolean,
  COSArray, COSString with escapes, COSNumber-int/float, COSDictionary,
  COSNull, fallback repr); operator branches (BT/ET indent push+pop,
  q/Q, BMC/EMC, BI/ID/EI inline image).
* :class:`DocumentCreator` — empty-stream early-return; XML payload
  nice-view; ``done()`` with unrun result; ``get_string_of_stream`` happy
  + OSError paths; per-token writer thin wrappers (``write_token``,
  ``write_operand``, ``add_operators``, ``write_indent``).
* :func:`_xml_segments` fallback on parse failure.
"""

from __future__ import annotations

import io
from typing import Any

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.debugger.streampane.stream import Stream
from pypdfbox.debugger.streampane.stream_pane import (
    DocumentCreator,
    StreamPane,
    _ContentStreamEmitter,
    _xml_segments,
)


# --------------------------------------------------------------------------
# Fixtures + builders
# --------------------------------------------------------------------------
def _content_stream() -> COSStream:
    stream = COSStream()
    stream.set_data(b"BT /F1 12 Tf (hello) Tj ET\n")
    return stream


def _image_stream() -> COSStream:
    stream = COSStream()
    stream.set_item("Type", COSName.get_pdf_name("XObject"))
    stream.set_item("Subtype", COSName.get_pdf_name("Image"))
    stream.set_data(b"\x00" * 16)
    return stream


def _xml_metadata_stream(payload: bytes = b"<root><child/></root>") -> COSStream:
    stream = COSStream()
    stream.set_item("Type", COSName.get_pdf_name("Metadata"))
    stream.set_item("Subtype", COSName.get_pdf_name("XML"))
    stream.set_data(payload)
    return stream


# --------------------------------------------------------------------------
# Construction — resources_dic branch
# --------------------------------------------------------------------------
def test_constructor_with_resources_dic(tk_root) -> None:
    """Passing ``resources_dic`` triggers the lazy ``PDResources`` import."""
    resources = COSDictionary()
    pane = StreamPane(
        tk_root,
        _content_stream(),
        is_content_stream=True,
        is_thumb=False,
        resources_dic=resources,
    )
    # The internal _resources slot is non-None when resources_dic is supplied.
    assert pane._resources is not None  # noqa: SLF001


# --------------------------------------------------------------------------
# _build_header back-compat alias
# --------------------------------------------------------------------------
def test_build_header_back_compat_alias(tk_root) -> None:
    """The ``_build_header`` private alias still packs a header into the
    panel (used by older debugger entry points)."""
    pane = StreamPane(tk_root, _content_stream(), is_content_stream=True, is_thumb=False)
    pane._build_header(pane._stream.get_filter_list(), Stream.DECODED)  # noqa: SLF001
    # No exception; the header is packed inside pane._panel.


# --------------------------------------------------------------------------
# _on_filter_changed — image, decoded, text+hex, OSError branches
# --------------------------------------------------------------------------
def test_on_filter_changed_image_branch_triggers_image_dispatch(
    tk_root, monkeypatch
) -> None:
    """Selecting the IMAGE filter rebuilds the notebook with only the
    image tab and calls ``request_image_showing``."""
    pane = StreamPane(
        tk_root, _image_stream(), is_content_stream=False, is_thumb=False
    )
    pane.init()

    called: list[bool] = []
    monkeypatch.setattr(pane, "request_image_showing", lambda: called.append(True))
    # Force the combo to IMAGE and fire the handler.
    pane._filter_combo.set(Stream.IMAGE)  # noqa: SLF001
    pane._on_filter_changed()  # noqa: SLF001
    assert called == [True]
    # Only one tab remains after rebuild.
    assert len(pane._notebook.tabs()) == 1  # noqa: SLF001


def test_on_filter_changed_decoded_branch_rebuilds_three_tabs(
    tk_root, monkeypatch
) -> None:
    """Selecting DECODED on a content-stream pane → 3 tabs + request_stream_text."""
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=True, is_thumb=False
    )
    pane.init()

    seen: list[Any] = []
    monkeypatch.setattr(
        pane, "request_stream_text", lambda key: seen.append(key)
    )
    pane._filter_combo.set(Stream.DECODED)  # noqa: SLF001
    pane._on_filter_changed()  # noqa: SLF001
    assert seen == [Stream.DECODED]
    assert len(pane._notebook.tabs()) == 3  # noqa: SLF001


def test_on_filter_changed_text_hex_branch_for_non_content_stream(
    tk_root, monkeypatch
) -> None:
    """On a non-content / non-image stream the else-branch rebuilds 2 tabs."""
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=False, is_thumb=False
    )
    pane.init()
    seen: list[Any] = []
    monkeypatch.setattr(pane, "request_stream_text", lambda key: seen.append(key))
    # A non-DECODED, non-IMAGE filter falls into the else-branch.
    pane._filter_combo.set("some-other-filter")  # noqa: SLF001
    pane._on_filter_changed()  # noqa: SLF001
    assert seen == ["some-other-filter"]
    assert len(pane._notebook.tabs()) == 2  # noqa: SLF001


def test_on_filter_changed_with_no_combo_returns_early(tk_root) -> None:
    """Bare pane (no ``init()``) has no combo → handler returns silently."""
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=True, is_thumb=False
    )
    # ``_filter_combo`` is None until create_header_panel is called.
    pane._on_filter_changed()  # noqa: SLF001 — no exception expected


def test_on_filter_changed_oserror_is_logged(
    tk_root, monkeypatch, caplog
) -> None:
    """OSError from request_stream_text is caught + logged."""
    import logging

    caplog.set_level(logging.ERROR)
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=False, is_thumb=False
    )
    pane.init()

    def _raise(_: Any) -> None:
        raise OSError("synthetic")

    monkeypatch.setattr(pane, "request_stream_text", _raise)
    pane._filter_combo.set(Stream.DECODED)  # noqa: SLF001
    pane._on_filter_changed()  # noqa: SLF001 — must not propagate
    assert any("synthetic" in r.message for r in caplog.records)


# --------------------------------------------------------------------------
# _rebuild_notebook — forget + re-add tabs
# --------------------------------------------------------------------------
def test_rebuild_notebook_resets_tabs(tk_root) -> None:
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=True, is_thumb=False
    )
    pane.init()
    initial_count = len(pane._notebook.tabs())  # noqa: SLF001
    assert initial_count == 3
    # Rebuild with two tabs.
    pane._rebuild_notebook([  # noqa: SLF001
        (pane._raw_view.get_stream_panel(), "A"),  # noqa: SLF001
        (pane._hex_view.get_pane(), "B"),  # noqa: SLF001
    ])
    assert len(pane._notebook.tabs()) == 2  # noqa: SLF001


# --------------------------------------------------------------------------
# request_stream_text — XML metadata nice view
# --------------------------------------------------------------------------
def test_request_stream_text_xml_metadata_uses_xml_nice_view(
    tk_root, monkeypatch
) -> None:
    pane = StreamPane(
        tk_root, _xml_metadata_stream(b"<root><child/></root>"),
        is_content_stream=False, is_thumb=False,
    )
    # is_xml_metadata() is True, so init builds Nice/Raw/Hex tabs.
    pane.init()
    captured: list[tuple] = []
    monkeypatch.setattr(
        pane._nice_view,  # noqa: SLF001
        "show_stream_text",
        lambda segments, styles, tool_tip_controller=None: captured.append(
            ("nice", list(segments))
        ),
    )
    pane.request_stream_text(Stream.DECODED)
    assert captured
    # XML nice view contains the pretty-printed root tag.
    text = "".join(seg for seg, _ in captured[0][1])
    assert "<root" in text


def test_request_stream_text_unknown_key_skips_hex_branch(
    tk_root, monkeypatch
) -> None:
    """Unknown filter key → Stream.get_stream returns None → hex-view
    update branch is skipped + a warning is logged."""
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=False, is_thumb=False
    )
    hex_calls: list[bytes] = []
    monkeypatch.setattr(
        pane._hex_view,  # noqa: SLF001
        "change_data",
        lambda data: hex_calls.append(bytes(data)),
    )
    pane.request_stream_text("no-such-filter")
    # hex view was never updated because get_stream returned None.
    assert hex_calls == []


# --------------------------------------------------------------------------
# _content_stream_segments OSError branch (via the StreamPane internal)
# --------------------------------------------------------------------------
def test_content_stream_segments_oserror_returns_none(
    tk_root, monkeypatch
) -> None:
    pane = StreamPane(
        tk_root, _content_stream(), is_content_stream=True, is_thumb=False
    )
    from pypdfbox.pdfparser import pdf_stream_parser

    def _raise(*_a: Any, **_kw: Any) -> Any:
        raise OSError("synthetic")

    monkeypatch.setattr(pdf_stream_parser.PDFStreamParser, "from_bytes", _raise)
    result = pane._content_stream_segments(b"foo")  # noqa: SLF001
    assert result is None


# --------------------------------------------------------------------------
# _xml_segments fallback on garbage
# --------------------------------------------------------------------------
def test_xml_segments_falls_back_to_plain_text_on_parse_failure() -> None:
    out = _xml_segments(b"\x00\x01 not xml")
    assert out
    # Fallback emits a single plain segment (no tag).
    assert all(tag is None for _, tag in out)


# --------------------------------------------------------------------------
# _ContentStreamEmitter — operand branches
# --------------------------------------------------------------------------
def test_emitter_handles_cos_boolean() -> None:
    emitter = _ContentStreamEmitter()
    emitter._write_operand(COSBoolean.TRUE)  # noqa: SLF001
    text = "".join(s for s, _ in emitter.segments)
    assert "true" in text


def test_emitter_handles_cos_array_with_mixed_operands() -> None:
    emitter = _ContentStreamEmitter()
    arr = COSArray()
    arr.add(COSInteger.get(1))
    arr.add(COSName.get_pdf_name("Foo"))
    emitter._write_operand(arr)  # noqa: SLF001
    text = "".join(s for s, _ in emitter.segments)
    assert "[" in text and "]" in text
    assert "/Foo" in text


def test_emitter_handles_cos_string_with_escapes_and_high_bytes() -> None:
    emitter = _ContentStreamEmitter()
    # ``(`` ``)`` ``\`` need backslash escapes; high-byte → octal escape.
    s = COSString(b"a(b)\\c\xff")
    emitter._write_operand(s)  # noqa: SLF001
    text = "".join(seg for seg, _ in emitter.segments)
    assert "\\(" in text and "\\)" in text and "\\\\" in text
    assert "\\377" in text  # 0xff → \377


def test_emitter_handles_cos_float_and_cos_integer() -> None:
    emitter = _ContentStreamEmitter()
    emitter._write_operand(COSInteger.get(42))  # noqa: SLF001
    emitter._write_operand(COSFloat(3.14))  # noqa: SLF001
    text = "".join(s for s, _ in emitter.segments)
    assert "42" in text
    assert "3.14" in text


def test_emitter_handles_cos_dictionary_and_cos_null() -> None:
    emitter = _ContentStreamEmitter()
    d = COSDictionary()
    d.set_item("Foo", COSInteger.get(1))
    emitter._write_operand(d)  # noqa: SLF001
    emitter._write_operand(COSNull.NULL)  # noqa: SLF001
    text = "".join(s for s, _ in emitter.segments)
    assert "<<" in text and ">>" in text
    assert "null" in text


def test_emitter_fallback_repr_branch() -> None:
    """Unknown objects fall back to ``repr(obj)`` with brace-trim."""
    emitter = _ContentStreamEmitter()
    emitter._write_operand("plain-str")  # noqa: SLF001 — not a COS object
    text = "".join(s for s, _ in emitter.segments)
    # The fallback writes the repr (with surrounding quotes for a str).
    assert "plain-str" in text


# --------------------------------------------------------------------------
# _ContentStreamEmitter — operator branches (indent push/pop + BI/ID/EI)
# --------------------------------------------------------------------------
def test_emitter_indent_pushed_on_bt_popped_on_et() -> None:
    emitter = _ContentStreamEmitter()
    bt = Operator.get_operator(OperatorName.BEGIN_TEXT)
    et = Operator.get_operator(OperatorName.END_TEXT)
    emitter._add_operator(bt)  # noqa: SLF001 — pushes indent
    assert emitter._indent == 1  # noqa: SLF001
    emitter._add_operator(et)  # noqa: SLF001 — pops back
    assert emitter._indent == 0  # noqa: SLF001


def test_emitter_indent_pushed_on_q_popped_on_qq() -> None:
    emitter = _ContentStreamEmitter()
    q = Operator.get_operator(OperatorName.SAVE)
    qq = Operator.get_operator(OperatorName.RESTORE)
    emitter._add_operator(q)  # noqa: SLF001
    assert emitter._indent == 1  # noqa: SLF001
    emitter._add_operator(qq)  # noqa: SLF001
    assert emitter._indent == 0  # noqa: SLF001


def test_emitter_indent_push_on_bmc_pop_on_emc() -> None:
    emitter = _ContentStreamEmitter()
    bmc = Operator.get_operator(OperatorName.BEGIN_MARKED_CONTENT)
    emc = Operator.get_operator(OperatorName.END_MARKED_CONTENT)
    emitter._add_operator(bmc)  # noqa: SLF001
    assert emitter._indent == 1  # noqa: SLF001
    emitter._add_operator(emc)  # noqa: SLF001
    assert emitter._indent == 0  # noqa: SLF001


def test_emitter_inline_image_emits_bi_id_ei_block() -> None:
    """BI op with image_parameters + image_data emits the three-line block."""
    emitter = _ContentStreamEmitter()
    bi = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    params = COSDictionary()
    params.set_item("W", COSInteger.get(4))
    params.set_item("H", COSInteger.get(4))
    bi.set_image_parameters(params)
    bi.set_image_data(b"abcd")
    emitter._add_operator(bi)  # noqa: SLF001
    text = "".join(s for s, _ in emitter.segments)
    assert "BI\n" in text
    assert "ID\n" in text
    assert "EI\n" in text
    assert "abcd" in text


def test_emitter_inline_image_with_no_params_still_emits_block() -> None:
    """BI with image_parameters=None skips the param-key loop but still emits."""
    emitter = _ContentStreamEmitter()
    bi = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    bi.set_image_data(b"")  # empty data → image_data branch coverage
    emitter._add_operator(bi)  # noqa: SLF001
    text = "".join(s for s, _ in emitter.segments)
    assert "BI\n" in text and "EI\n" in text


# --------------------------------------------------------------------------
# _ContentStreamEmitter._write_indent — non-zero indent branch
# --------------------------------------------------------------------------
def test_emitter_write_indent_emits_spaces_at_non_zero_indent() -> None:
    emitter = _ContentStreamEmitter()
    emitter._indent = 2  # noqa: SLF001
    emitter._need_indent = True  # noqa: SLF001
    emitter._write_indent()  # noqa: SLF001
    text = "".join(s for s, _ in emitter.segments)
    assert text == "    "  # 2 levels × 2 spaces


# --------------------------------------------------------------------------
# DocumentCreator — empty stream + XML payload + done-with-no-result
# --------------------------------------------------------------------------
class _CapturingView:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def show_stream_text(
        self, segments: Any, styles: Any, tool_tip_controller: Any = None
    ) -> None:
        self.calls.append((list(segments), list(styles), tool_tip_controller))


def test_document_creator_empty_stream_returns_empty_segments() -> None:
    """When get_stream returns None, do_in_background returns []."""

    class _NullStream:
        def is_xml_metadata(self) -> bool:
            return False

        def get_stream(self, _key: str) -> Any:
            return None

    creator = DocumentCreator(_CapturingView(), _NullStream(), Stream.DECODED, nice=False)
    assert creator.execute() == []


def test_document_creator_done_returns_when_no_result() -> None:
    """``done()`` called before ``execute()`` short-circuits."""

    class _Stream:
        def is_xml_metadata(self) -> bool:
            return False

        def get_stream(self, _key: str) -> Any:
            return None

    creator = DocumentCreator(_CapturingView(), _Stream(), Stream.DECODED, nice=False)
    creator.done()  # _result is None → no-op


def test_document_creator_done_returns_when_view_has_no_method() -> None:
    """``done()`` ignores target views that lack ``show_stream_text``."""

    class _Stream:
        def is_xml_metadata(self) -> bool:
            return False

        def get_stream(self, _key: str) -> Any:
            return None

    class _BareView:
        pass

    creator = DocumentCreator(_BareView(), _Stream(), Stream.DECODED, nice=False)
    # Force a _result so the second branch (no method) is reached.
    creator._result = [("hi", None)]  # noqa: SLF001
    creator.done()


def test_document_creator_nice_xml_metadata_path() -> None:
    """Nice mode + XML metadata stream → uses get_xml_document path."""
    stream = Stream(_xml_metadata_stream(b"<a><b/></a>"), is_thumb=False)
    creator = DocumentCreator(_CapturingView(), stream, Stream.DECODED, nice=True)
    segments = creator.execute()
    text = "".join(s for s, _ in segments)
    assert "<a" in text and "<b" in text


def test_document_creator_get_string_of_stream_happy() -> None:
    """``get_string_of_stream`` decodes the stream end-to-end."""
    stream = Stream(_content_stream(), is_thumb=False)
    creator = DocumentCreator(_CapturingView(), stream, Stream.DECODED, nice=False)
    text = creator.get_string_of_stream(io.BytesIO(b"hello world"), "utf-8")
    assert text == "hello world"


def test_document_creator_get_string_of_stream_oserror_returns_none() -> None:
    stream = Stream(_content_stream(), is_thumb=False)
    creator = DocumentCreator(_CapturingView(), stream, Stream.DECODED, nice=False)

    class _Broken:
        def __enter__(self) -> Any:
            raise OSError("synthetic")

        def __exit__(self, *_: Any) -> None:
            pass

    assert creator.get_string_of_stream(_Broken(), "utf-8") is None


def test_document_creator_get_content_stream_document_oserror_returns_none(
    monkeypatch,
) -> None:
    """OSError from the parser maps to None per upstream contract."""
    stream = Stream(_content_stream(), is_thumb=False)
    creator = DocumentCreator(_CapturingView(), stream, Stream.DECODED, nice=True)
    from pypdfbox.pdfparser import pdf_stream_parser

    def _raise(*_a: Any, **_kw: Any) -> Any:
        raise OSError("synthetic")

    monkeypatch.setattr(pdf_stream_parser.PDFStreamParser, "from_bytes", _raise)
    assert creator.get_content_stream_document(b"foo") is None


# --------------------------------------------------------------------------
# DocumentCreator — per-token writer wrappers
# --------------------------------------------------------------------------
def test_write_token_with_default_emitter() -> None:
    """Default emitter path — wrapper creates one internally."""
    stream = Stream(_content_stream(), is_thumb=False)
    creator = DocumentCreator(_CapturingView(), stream, Stream.DECODED, nice=False)
    # No assertion required beyond "does not raise" — covers the
    # ``target = emitter or _ContentStreamEmitter()`` branch.
    creator.write_token(COSInteger.get(7))


def test_write_token_with_supplied_emitter_routes_into_it() -> None:
    stream = Stream(_content_stream(), is_thumb=False)
    creator = DocumentCreator(_CapturingView(), stream, Stream.DECODED, nice=False)
    emitter = _ContentStreamEmitter()
    creator.write_token(COSInteger.get(7), emitter=emitter)
    text = "".join(s for s, _ in emitter.segments)
    assert "7" in text


def test_write_operand_with_supplied_emitter() -> None:
    stream = Stream(_content_stream(), is_thumb=False)
    creator = DocumentCreator(_CapturingView(), stream, Stream.DECODED, nice=False)
    emitter = _ContentStreamEmitter()
    creator.write_operand(COSName.get_pdf_name("Bar"), emitter=emitter)
    text = "".join(s for s, _ in emitter.segments)
    assert "/Bar" in text


def test_write_operand_with_default_emitter() -> None:
    stream = Stream(_content_stream(), is_thumb=False)
    creator = DocumentCreator(_CapturingView(), stream, Stream.DECODED, nice=False)
    creator.write_operand(COSInteger.get(2))


def test_add_operators_with_default_emitter_and_supplied_emitter() -> None:
    stream = Stream(_content_stream(), is_thumb=False)
    creator = DocumentCreator(_CapturingView(), stream, Stream.DECODED, nice=False)
    bt = Operator.get_operator(OperatorName.BEGIN_TEXT)
    # Default-emitter branch.
    creator.add_operators(bt)
    # Supplied-emitter branch.
    emitter = _ContentStreamEmitter()
    creator.add_operators(bt, emitter=emitter)
    text = "".join(s for s, _ in emitter.segments)
    assert "BT" in text


def test_write_indent_with_default_emitter_and_supplied_emitter() -> None:
    stream = Stream(_content_stream(), is_thumb=False)
    creator = DocumentCreator(_CapturingView(), stream, Stream.DECODED, nice=False)
    creator.write_indent()  # default emitter
    emitter = _ContentStreamEmitter()
    emitter._need_indent = True  # noqa: SLF001
    emitter._indent = 1  # noqa: SLF001
    creator.write_indent(emitter=emitter)
    text = "".join(s for s, _ in emitter.segments)
    assert text == "  "
