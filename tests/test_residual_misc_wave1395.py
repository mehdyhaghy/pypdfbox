"""Wave 1395 — miscellaneous residual coverage stragglers.

Bundles single-line / two-line uncovered branches across modules that
have only 1-2 missing lines each. Each test is a small behavioural
assertion targeting a specific missing line per the wave-1395 audit:

* ``fontbox/liberation_loader.py`` lines 209, 212 — ``_resolve_key``
  None-on-unknown-key and None-on-missing-file branches.
* ``fontbox/ttf/ttf_subsetter.py`` line 700 — ``_build_subset_font``
  honours the ``no_subset_tables`` policy (path through
  ``Options.no_subset_tables`` assignment).
* ``fontbox/ttf/glyph_substitution_table.py`` lines 622, 639 —
  ``get_gsub_data(None)`` when ``_gsub_table is not None`` but no
  preferred script is found; and the ``_pick_default_script_tag``
  fall-back when no Language preference matches.
* ``fontbox/ttf/gsub/gsub_worker_for_smcp.py`` line 57 — the
  ``script_feature is None`` continue branch (feature supported but
  ``get_feature`` returns ``None``).
* ``fontbox/ttf/gsub/gsub_worker_for_aalt.py`` line 52 — same branch in
  the aalt worker.
* ``xmpbox/type/layer_type.py`` lines 95-96 —
  ``set_layer_text_property`` non-None branch (assign property and
  rename to LayerText).
* ``rendering/soft_mask.py`` lines 32, 34 — ``_clamp_unit`` clamp-low
  and clamp-high branches.
* ``debugger/ui/debug_log_appender.py`` lines 176, 179 — ``_NullLock``
  context manager (used when ``Handler.lock`` is ``None``).
* ``pdfwriter/cos_writer.py`` line 1290 — placeholder-byterange detection
  short-circuits when ``to_cos_number_integer_list`` contains a ``None``.
"""

from __future__ import annotations

import pytest

# ---------- liberation_loader._resolve_key ----------


def test_liberation_loader_returns_none_for_unknown_key() -> None:
    from pypdfbox.fontbox.liberation_loader import _resolve_key

    # Clear cache so a fresh lookup hits the branch.
    _resolve_key.cache_clear()
    assert _resolve_key("Nonexistent-Bold") is None


def test_liberation_loader_returns_none_when_bundled_file_missing(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``not path.is_file()`` branch fires when the resource bundle
    is incomplete (e.g. a wheel built without all TTFs). Force the
    branch by pointing ``bundled_dir`` at an empty temp directory."""
    from pypdfbox.fontbox import liberation_loader

    real_bundled_dir = liberation_loader.bundled_dir
    try:
        # Clear caches so the monkeypatched dir is consulted.
        liberation_loader._resolve_key.cache_clear()
        real_bundled_dir.cache_clear()
        monkeypatch.setattr(liberation_loader, "bundled_dir", lambda: tmp_path)
        # Known key — _ASSET_MAP has it — but the file isn't on disk.
        assert liberation_loader._resolve_key("Sans-Regular") is None
    finally:
        # Reset cache for any later tests (restore via monkeypatch's undo).
        liberation_loader._resolve_key.cache_clear()


# ---------- TTFSubsetter._build_subset_font no_subset_tables policy ----------


def test_ttf_subsetter_build_with_no_subset_tables_policy_takes_branch() -> None:
    """Line 700 — when ``_no_subset_tables`` is non-empty, the
    ``_build_subset_font`` arm assigns ``Options.no_subset_tables``.
    Reach it by calling ``build_head_table`` after setting the policy."""
    import os
    from pathlib import Path

    from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
    from pypdfbox.fontbox.ttf.ttf_subsetter import TTFSubsetter

    fixture = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "fontbox"
        / "ttf"
        / "LiberationSans-Regular.ttf"
    )
    if not fixture.exists():
        pytest.skip("LiberationSans-Regular.ttf fixture unavailable")
    font = TTFParser().parse(os.fspath(fixture))
    try:
        subsetter = TTFSubsetter(font)
        subsetter.add(ord("A"))
        subsetter.set_no_subset_tables(("head", "name"))
        # build_head_table -> _get_compiled_table -> _build_subset_font.
        head_bytes = subsetter.build_head_table()
        assert head_bytes is not None
        assert len(head_bytes) > 0
    finally:
        font.close()


# ---------- GlyphSubstitutionTable picks no default script (line 622) ----------


def test_glyph_substitution_table_default_script_returns_no_data() -> None:
    """Line 622 — when ``script_tag is None`` and ``_pick_default_script_tag``
    returns ``None`` (empty script-tag list), return ``GsubData.NO_DATA_FOUND``."""
    from pypdfbox.fontbox.ttf.glyph_substitution_table import (
        GlyphSubstitutionTable,
    )
    from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData

    # Build an empty table — gsub_table populated (so it doesn't take the
    # outer None branch) but with no scripts.
    table = GlyphSubstitutionTable.__new__(GlyphSubstitutionTable)
    table._gsub_table = object()  # sentinel — anything truthy works  # noqa: SLF001
    table._script_tags = []  # noqa: SLF001
    # Call: script_tag=None -> _pick_default_script_tag walks Language
    # preference list, none match because _script_tags is empty; the
    # final ``return self._script_tags[0] if self._script_tags else None``
    # arm returns None; we then hit line 622 (NO_DATA_FOUND).
    assert table.get_gsub_data(None) is GsubData.NO_DATA_FOUND


def test_glyph_substitution_table_default_script_falls_back_to_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 639 — ``_pick_default_script_tag`` fall-back to the first
    script when no Language preference matches. Build a fake table whose
    script_tags list contains an exotic tag (no Language matches)."""
    from pypdfbox.fontbox.ttf.glyph_substitution_table import (
        GlyphSubstitutionTable,
    )

    table = GlyphSubstitutionTable.__new__(GlyphSubstitutionTable)
    table._gsub_table = object()  # noqa: SLF001
    table._script_tags = ["zzzz"]  # not in any Language.script_names  # noqa: SLF001
    picked = table._pick_default_script_tag()  # noqa: SLF001
    assert picked == "zzzz"


# ---------- gsub workers — feature supported but get_feature is None ----------


def test_gsub_worker_smcp_skips_feature_when_get_feature_is_none() -> None:
    """Line 57 — ``script_feature is None`` continue branch in
    :class:`GsubWorkerForSMCP`. Reach it by setting the feature in
    ``feature_list`` with a ``None`` value so ``is_feature_supported``
    returns True but ``get_feature`` returns ``None``."""
    from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData
    from pypdfbox.fontbox.ttf.gsub.gsub_worker_for_smcp import GsubWorkerForSMCP

    class _Cmap:
        def get_glyph_id(self, _cp: int) -> int:
            return 0

    # ``smcp`` is "supported" but the feature payload is None.
    gsub = GsubData(active_script_name="latn", feature_list={"smcp": None})
    worker = GsubWorkerForSMCP(_Cmap(), gsub)
    # Input passes through unchanged (no substitution applied).
    assert worker.apply_transforms([10, 20, 30]) == [10, 20, 30]


def test_gsub_worker_aalt_skips_feature_when_get_feature_is_none() -> None:
    """Line 52 — same continue arm in :class:`GsubWorkerForAALT`.

    AALT's constructor takes only ``gsub_data`` (matches upstream's
    parameter shape — no cmap)."""
    from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData
    from pypdfbox.fontbox.ttf.gsub.gsub_worker_for_aalt import GsubWorkerForAALT

    gsub = GsubData(active_script_name="latn", feature_list={"aalt": None})
    worker = GsubWorkerForAALT(gsub)
    assert worker.apply_transforms([10, 20, 30]) == [10, 20, 30]


# ---------- LayerType.set_layer_text_property non-None branch ----------


def test_layer_type_set_layer_text_property_round_trip() -> None:
    """Lines 95-96 — ``set_layer_text_property`` non-None branch
    assigns the LayerText property name and adds the property."""
    from pypdfbox.xmpbox import XMPMetadata
    from pypdfbox.xmpbox.type import LayerType, TextType

    metadata = XMPMetadata.create_xmp_metadata()
    layer = LayerType(metadata)
    text = TextType(
        metadata,
        LayerType.NAMESPACE,
        LayerType.PREFERRED_PREFIX,
        "AnythingElse",
        "Hello, layer.",
    )
    layer.set_layer_text_property(text)
    # The setter must rename to LayerType.LAYER_TEXT and install the prop.
    same = layer.get_layer_text_property()
    assert same is text
    assert layer.get_layer_text() == "Hello, layer."
    assert text.get_property_name() == LayerType.LAYER_TEXT


# ---------- soft_mask._clamp_unit ----------


def test_soft_mask_clamp_unit_low_high_and_inside() -> None:
    """Lines 32, 34 — ``_clamp_unit`` clamp-low / clamp-high arms."""
    from pypdfbox.rendering.soft_mask import _clamp_unit

    assert _clamp_unit(-0.1) == 0.0
    assert _clamp_unit(1.5) == 1.0
    # Sanity: in-range pass-through.
    assert _clamp_unit(0.5) == 0.5


# ---------- DebugLogAppender._NullLock context manager ----------


def test_debug_log_appender_null_lock_enters_and_exits() -> None:
    """Lines 176, 179 — ``_NullLock.__enter__`` returns self and
    ``__exit__`` returns ``None``. Reach via ``extend_buffer`` when the
    handler has no real lock."""
    from pypdfbox.debugger.ui.debug_log_appender import DebugLogAppender

    appender = DebugLogAppender(max_records=4)
    # Force the no-lock path so ``with`` opens _NullLock.
    appender.lock = None  # type: ignore[assignment]
    appender.extend_buffer(["first", "second"])
    # Buffer should now contain the two records (proves _NullLock
    # was entered + exited without raising).
    assert list(appender.get_records()) == ["first", "second"]


# ---------- pdf_text2_html.write_paragraph_end sink path ----------


def test_pdf_text2_html_write_paragraph_end_routes_through_sink() -> None:
    """Lines 323, 333 — ``write_paragraph_end(sink=callable)`` routes
    the font-state flush text through the provided sink and then forwards
    ``sink`` into the parent's ``write_paragraph_end``."""
    from pypdfbox.tools.pdf_text2_html import PDFText2HTML

    p = PDFText2HTML()
    # Prime the font state so ``clear()`` returns non-empty markup.
    p._font_state.open("b")  # noqa: SLF001

    captured: list[str] = []

    def _sink(text: str) -> None:
        captured.append(text)

    p.write_paragraph_end(sink=_sink)
    # The flush text was routed through the sink.
    assert any("</b>" in chunk for chunk in captured)


# ---------- cos_writer placeholder /ByteRange contains a None integer ----------


def test_cos_writer_placeholder_byterange_with_none_integer_is_skipped() -> None:
    """Line 1290 — placeholder /ByteRange where ``to_cos_number_integer_list``
    contains a ``None`` short-circuits with ``continue`` (does not treat
    the dictionary as a signed/timestamp dict).

    Wires the sig dict into the doc as an indirect object so
    ``doc.get_objects()`` returns it during iteration. Stubs
    ``COSArray.to_cos_number_integer_list`` so the returned list contains
    a ``None`` (the wave 1361 fix point where a malformed PDF could yield
    a non-integer entry in a ByteRange array)."""
    from unittest.mock import patch

    from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
    from pypdfbox.cos.cos_object_key import COSObjectKey
    from pypdfbox.pdfwriter.cos_writer import COSWriter
    from pypdfbox.pdmodel.pd_document import PDDocument

    doc = PDDocument()
    sig_dict = COSDictionary()
    sig_dict.set_name(COSName.TYPE, "Sig")
    br = COSArray()
    br.add(COSInteger.get(0))
    br.add(COSInteger.get(0))
    br.add(COSInteger.get(0))
    br.add(COSInteger.get(0))
    sig_dict.set_item(COSName.get_pdf_name("ByteRange"), br)
    # Register the sig dict as an indirect object so doc.get_objects() yields it.
    cos_doc = doc.get_document()
    indirect = cos_doc.get_object_from_pool(COSObjectKey(900, 0))
    indirect.set_object(sig_dict)

    writer = COSWriter.__new__(COSWriter)
    writer._incremental_input = None  # noqa: SLF001
    # Stub to_cos_number_integer_list so it returns a list with a None
    # — this fires the ``any(i is None for i in ints): continue`` arm.
    with patch.object(
        COSArray, "to_cos_number_integer_list", return_value=[0, None, 0, 0]
    ):
        # Must not raise — the ``None`` integer takes the ``continue``
        # branch before reaching the placeholder-detection raise.
        writer._reject_signed_with_byterange_placeholder(cos_doc)  # noqa: SLF001


# ---------- PDShadingType7 decode-None branch ----------


def test_pd_shading_type7_parse_patches_returns_empty_when_decode_missing() -> None:
    """Line 262 — ``parse_patches`` returns ``[]`` when ``/Decode`` is
    absent on the backing stream."""
    from pypdfbox.cos import COSName, COSStream
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type7 import PDShadingType7

    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("ShadingType"), 7)
    # Seed the stream with arbitrary bytes so create_input_stream succeeds;
    # the test then exercises the next-line ``decode is None`` early-return.
    with stream.create_output_stream() as out:
        out.write(b"\x00" * 8)
    # No /Decode entry — ``get_decode()`` returns None -> early-return.
    shading = PDShadingType7(stream)
    assert shading.parse_patches() == []


# ---------- non_seekable available — no available / no getbuffer ----------


def test_non_seekable_available_returns_zero_when_no_introspection() -> None:
    """Line 207 — final ``return 0`` when the underlying stream exposes
    neither ``available()`` nor ``getbuffer()`` / ``tell()``. Mirrors the
    upstream behaviour for ad-hoc Java InputStreams without an
    ``available`` override."""
    from pypdfbox.io.non_seekable_random_access_read_input_stream import (
        NonSeekableRandomAccessReadInputStream,
    )

    class _BareReadable:
        def __init__(self) -> None:
            self._buf = b"abc"
            self._pos = 0

        def read(self, n: int) -> bytes:
            chunk = self._buf[self._pos : self._pos + n]
            self._pos += len(chunk)
            return chunk

        def readinto(self, dest: bytearray) -> int:
            chunk = self.read(len(dest))
            dest[: len(chunk)] = chunk
            return len(chunk)

        def close(self) -> None:
            return None

    stream = NonSeekableRandomAccessReadInputStream(_BareReadable())
    # Neither ``available`` nor ``getbuffer`` is present -> final return 0.
    assert stream._available_on_underlying() == 0  # noqa: SLF001
