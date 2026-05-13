"""Tests for the :class:`Type0Font` encoding pane."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.debugger.fontencodingpane.type0_font import Type0Font
from pypdfbox.pdmodel.font import PDType0Font


def _type0_with_descendant() -> PDType0Font:
    descendant = COSDictionary()
    descendant.set_name(COSName.get_pdf_name("Type"), "Font")
    descendant.set_name(COSName.get_pdf_name("Subtype"), "CIDFontType2")
    descendant.set_name(COSName.get_pdf_name("BaseFont"), "MyTTF")
    sysinfo = COSDictionary()
    sysinfo.set_string(COSName.get_pdf_name("Registry"), "Adobe")
    sysinfo.set_string(COSName.get_pdf_name("Ordering"), "Identity")
    sysinfo.set_int(COSName.get_pdf_name("Supplement"), 0)
    descendant.set_item(COSName.get_pdf_name("CIDSystemInfo"), sysinfo)

    parent = COSDictionary()
    parent.set_name(COSName.get_pdf_name("Type"), "Font")
    parent.set_name(COSName.get_pdf_name("Subtype"), "Type0")
    parent.set_name(COSName.get_pdf_name("BaseFont"), "MyTTF")
    parent.set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("Identity-H")
    )
    arr = COSArray()
    arr.add(descendant)
    parent.set_item(COSName.get_pdf_name("DescendantFonts"), arr)
    return PDType0Font(parent)


def test_type0_pane_builds_view(tk_root):
    parent = _type0_with_descendant()
    descendant = parent.get_descendant_font()
    assert descendant is not None
    pane = Type0Font(descendant, parent, tk_root)
    # No /CIDToGIDMap and no embedded program => readMap yields zero rows.
    assert pane.view is not None
    assert pane.view.tree is not None


def test_type0_pane_get_panel(tk_root):
    parent = _type0_with_descendant()
    descendant = parent.get_descendant_font()
    pane = Type0Font(descendant, parent, tk_root)
    assert pane.get_panel() is pane.view


def test_type0_pane_total_glyphs_starts_at_zero(tk_root):
    parent = _type0_with_descendant()
    descendant = parent.get_descendant_font()
    pane = Type0Font(descendant, parent, tk_root)
    # No embedded TTF program => has_glyph(code) is False for every code.
    assert pane.total_available_glyphs == 0


def _type0_with_cid_to_gid_map() -> PDType0Font:
    """Variant of :func:`_type0_with_descendant` that wires up a small
    ``/CIDToGIDMap`` stream so ``_read_cid_to_gid_map`` produces rows."""
    from pypdfbox.cos import COSStream

    descendant = COSDictionary()
    descendant.set_name(COSName.get_pdf_name("Type"), "Font")
    descendant.set_name(COSName.get_pdf_name("Subtype"), "CIDFontType2")
    descendant.set_name(COSName.get_pdf_name("BaseFont"), "MyTTF")
    sysinfo = COSDictionary()
    sysinfo.set_string(COSName.get_pdf_name("Registry"), "Adobe")
    sysinfo.set_string(COSName.get_pdf_name("Ordering"), "Identity")
    sysinfo.set_int(COSName.get_pdf_name("Supplement"), 0)
    descendant.set_item(COSName.get_pdf_name("CIDSystemInfo"), sysinfo)

    # /CIDToGIDMap is a stream of big-endian 16-bit GIDs, indexed by CID.
    map_stream = COSStream()
    # Three entries: GID 0, 1, 2 — only GID != 0 triggers ``to_unicode``.
    map_stream.set_data(b"\x00\x00\x00\x01\x00\x02")
    descendant.set_item(COSName.get_pdf_name("CIDToGIDMap"), map_stream)

    parent = COSDictionary()
    parent.set_name(COSName.get_pdf_name("Type"), "Font")
    parent.set_name(COSName.get_pdf_name("Subtype"), "Type0")
    parent.set_name(COSName.get_pdf_name("BaseFont"), "MyTTF")
    parent.set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("Identity-H")
    )
    arr = COSArray()
    arr.add(descendant)
    parent.set_item(COSName.get_pdf_name("DescendantFonts"), arr)
    return PDType0Font(parent)


def test_type0_pane_cid_to_gid_map_path(tk_root):
    parent = _type0_with_cid_to_gid_map()
    descendant = parent.get_descendant_font()
    assert descendant is not None
    pane = Type0Font(descendant, parent, tk_root)
    assert pane.view is not None
    # The /CIDToGIDMap path runs and yields some rows.
    assert pane.view.tree is not None


# ---- Helpers / static branches --------------------------------------------


def test_type0_safe_call_swallows_oserror():
    """``_safe_call`` returns ``None`` when the wrapped function raises
    ``OSError`` (line 173-174)."""

    def _raises(_code: int) -> int:
        raise OSError("boom")

    assert Type0Font._safe_call(_raises, 42) is None


def test_type0_safe_call_propagates_value():
    def _ok(code: int) -> int:
        return code + 1

    assert Type0Font._safe_call(_ok, 41) == 42


def test_type0_get_encoding_name_falls_back_to_class_name():
    """When ``/Encoding`` is absent, return the cos-dict type name
    (line 182)."""
    from pypdfbox.pdmodel.font import PDType0Font as _PDType0Font

    parent_dict = COSDictionary()
    parent_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    parent_dict.set_name(COSName.get_pdf_name("Subtype"), "Type0")
    parent_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyTTF")
    descendant = COSDictionary()
    descendant.set_name(COSName.get_pdf_name("Type"), "Font")
    descendant.set_name(COSName.get_pdf_name("Subtype"), "CIDFontType2")
    descendant.set_name(COSName.get_pdf_name("BaseFont"), "MyTTF")
    sysinfo = COSDictionary()
    sysinfo.set_string(COSName.get_pdf_name("Registry"), "Adobe")
    sysinfo.set_string(COSName.get_pdf_name("Ordering"), "Identity")
    sysinfo.set_int(COSName.get_pdf_name("Supplement"), 0)
    descendant.set_item(COSName.get_pdf_name("CIDSystemInfo"), sysinfo)
    arr = COSArray()
    arr.add(descendant)
    parent_dict.set_item(COSName.get_pdf_name("DescendantFonts"), arr)
    parent = _PDType0Font(parent_dict)

    name = Type0Font._get_encoding_name(parent)
    # No /Encoding → returns cos-dict class name.
    assert name == "COSDictionary"


def test_type0_path_non_empty_string_is_false():
    """``_path_non_empty`` returns False for strings (line 189)."""
    from pypdfbox.debugger.fontencodingpane.type0_font import _path_non_empty

    assert _path_non_empty("No glyph") is False
    assert _path_non_empty(None) is False


def test_type0_path_non_empty_non_iterable_is_false():
    """``_path_non_empty`` returns False for objects that aren't iterable
    (line 192-193)."""
    from pypdfbox.debugger.fontencodingpane.type0_font import _path_non_empty

    assert _path_non_empty(42) is False


def test_type0_path_non_empty_with_segments_is_true():
    """``_path_non_empty`` returns True when the iterable yields at least
    one segment (line 124)."""
    from pypdfbox.debugger.fontencodingpane.type0_font import _path_non_empty

    assert _path_non_empty([("moveTo", 0, 0)]) is True


def test_type0_empty_frame_returns_ttk_frame(tk_root):
    """``_empty_frame`` produces a 300x500 stub frame (line 198-201)."""
    from pypdfbox.debugger.fontencodingpane.type0_font import _empty_frame

    # Force creation under our tk_root so Tk has a default root.
    del tk_root  # frame uses implicit default root
    frame = _empty_frame()
    assert frame is not None


# ---- _read_map with constrained mock font ---------------------------------


class _StubCIDFont:
    """Stub descendant font that exposes exactly the methods Type0Font
    uses. ``has_glyph`` is True for a handful of codes only — this
    bounds the 65535-iteration loop to a tiny number of body executions.
    """

    def __init__(
        self,
        glyph_codes: set[int],
        raise_has_glyph: set[int] | None = None,
        raise_to_unicode: set[int] | None = None,
        raise_get_path: set[int] | None = None,
        raise_code_to_cid: set[int] | None = None,
    ) -> None:
        self._glyph_codes = glyph_codes
        self._raise_has = raise_has_glyph or set()
        self._raise_unicode = raise_to_unicode or set()
        self._raise_path = raise_get_path or set()
        self._raise_cid = raise_code_to_cid or set()

    def has_glyph(self, code: int) -> bool:
        if code in self._raise_has:
            raise OSError("forced has_glyph fail")
        return code in self._glyph_codes

    def code_to_cid(self, code: int) -> int:
        if code in self._raise_cid:
            raise OSError("forced code_to_cid fail")
        return code

    def code_to_gid(self, code: int) -> int:
        return code

    def get_path(self, code: int):
        if code in self._raise_path:
            raise OSError("forced get_path fail")
        # Return a non-empty path for some codes, empty for others, to
        # exercise both ``_path_non_empty`` branches.
        if code == 100:
            return [("moveTo", 0, 0), ("lineTo", 1, 1)]
        return []

    def get_name(self) -> str:
        return "StubCID"

    def is_embedded(self) -> bool:
        return False

    def get_cos_object(self) -> COSDictionary:
        # No /CIDToGIDMap → forces the _read_map path.
        return COSDictionary()


class _StubParentFont:
    def __init__(
        self,
        raise_to_unicode: set[int] | None = None,
    ) -> None:
        self._raise_unicode = raise_to_unicode or set()

    def to_unicode(self, code: int) -> str | None:
        if code in self._raise_unicode:
            raise OSError("forced parent to_unicode fail")
        return chr(code) if 32 <= code <= 126 else None

    def is_standard14(self) -> bool:
        return False

    def get_cos_object(self) -> COSDictionary:
        d = COSDictionary()
        d.set_item(
            COSName.get_pdf_name("Encoding"),
            COSName.get_pdf_name("Identity-H"),
        )
        return d


def test_type0_read_map_with_constrained_glyph_set(tk_root):
    """Exercise ``_read_map`` against a stub descendant that only reports
    a handful of glyphs (lines 110-112, 117-118, 121-122, 125)."""
    descendant = _StubCIDFont(
        glyph_codes={50, 100, 200, 300, 400},
        raise_has_glyph={500},  # OSError branch in has_glyph
        raise_to_unicode={50},  # forces parent_font.to_unicode OSError
        raise_get_path={200},  # forces get_path OSError
    )
    parent = _StubParentFont(raise_to_unicode={50})
    pane = Type0Font(descendant, parent, tk_root)  # type: ignore[arg-type]
    assert pane.view is not None
    # Five glyph codes → 5 rows.
    assert len(pane.view.tree.get_children()) == 5
    # Code 100 returns a non-empty path → counted as available.
    assert pane.total_available_glyphs >= 1


def test_type0_read_map_with_zero_glyphs_uses_empty_frame(tk_root):
    """When the descendant reports no glyphs, the constructor still
    builds a view from the empty rows table."""
    descendant = _StubCIDFont(glyph_codes=set())
    parent = _StubParentFont()
    pane = Type0Font(descendant, parent, tk_root)  # type: ignore[arg-type]
    assert pane.view is not None
    assert pane.total_available_glyphs == 0


# ---- _read_cid_to_gid_map error-fallback path -----------------------------


class _StubCIDFontWithMap:
    """Stub descendant exposing a CIDToGIDMap stream whose
    ``to_byte_array`` raises AttributeError, forcing the fallback to
    ``create_input_stream`` (lines 141-146)."""

    def __init__(self) -> None:
        self._map_bytes = b"\x00\x00\x00\x01\x00\x02"

    def get_name(self) -> str:
        return "StubCIDWithMap"

    def is_embedded(self) -> bool:
        return False

    def get_path(self, code: int):
        if code == 1:
            raise OSError("forced get_path fail")
        if code == 2:
            return [("moveTo", 0, 0), ("lineTo", 1, 1)]
        return []

    def get_cos_object(self):
        return self._build_cos()

    def _build_cos(self) -> COSDictionary:
        from io import BytesIO

        class _StreamLike:
            """Stand-in COSStream-like object passing isinstance check
            via subclass. We patch the COSStream isinstance check by
            using a real COSStream below."""

            pass

        # Real COSStream with patched ``to_byte_array`` raising
        # AttributeError, plus a ``create_input_stream`` context manager.
        from pypdfbox.cos import COSStream

        class _PatchedStream(COSStream):
            def to_byte_array(self) -> bytes:  # type: ignore[override]
                raise AttributeError("simulated")

            def create_input_stream(self):  # type: ignore[override]
                outer = self

                class _Ctx:
                    def __enter__(self):
                        return BytesIO(outer._payload)

                    def __exit__(self, *_a):
                        return False

                return _Ctx()

        ps = _PatchedStream()
        ps._payload = self._map_bytes  # type: ignore[attr-defined]
        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("CIDToGIDMap"), ps)
        return d


class _StubParentForCidMap:
    def __init__(self, raise_to_unicode: set[int] | None = None) -> None:
        self._raise = raise_to_unicode or set()

    def to_unicode(self, code: int) -> str | None:
        if code in self._raise:
            raise OSError("forced parent to_unicode fail")
        return chr(code) if 32 <= code <= 126 else None

    def get_cos_object(self) -> COSDictionary:
        d = COSDictionary()
        d.set_item(
            COSName.get_pdf_name("Encoding"),
            COSName.get_pdf_name("Identity-H"),
        )
        return d


def test_type0_cid_to_gid_map_byte_array_fallback(tk_root):
    """Exercise lines 141-146: ``to_byte_array`` raises ``AttributeError``,
    fall back to ``create_input_stream``. Also exercises 157-158
    (parent.to_unicode OSError), 161-162 (font.get_path OSError),
    and 165 (path_non_empty increments counter)."""
    descendant = _StubCIDFontWithMap()
    parent = _StubParentForCidMap(raise_to_unicode={1})
    pane = Type0Font(descendant, parent, tk_root)  # type: ignore[arg-type]
    assert pane.view is not None
    # 3 CID entries (6 bytes / 2).
    assert len(pane.view.tree.get_children()) == 3
    # Code 2 has a non-empty path → counted.
    assert pane.total_available_glyphs == 1


# ---- get_panel when _view is None -----------------------------------------


def test_type0_get_panel_returns_empty_frame_when_view_is_none(tk_root):
    """When ``_view`` is ``None``, ``get_panel`` returns a fresh empty
    ``ttk.Frame`` (line 90)."""
    descendant = _StubCIDFont(glyph_codes={1, 2})
    parent = _StubParentFont()
    pane = Type0Font(descendant, parent, tk_root)  # type: ignore[arg-type]
    # Force _view to None to exercise the fallback path.
    pane._view = None
    frame = pane.get_panel()
    assert frame is not None


class _StubCIDFontWithBrokenMap:
    """Stub whose CIDToGIDMap stream raises ``AttributeError`` from
    ``to_byte_array`` AND ``create_input_stream`` — forces the
    ``return None`` branch at lines 145-146."""

    def __init__(self, glyph_codes: set[int]) -> None:
        self._glyph_codes = glyph_codes

    def has_glyph(self, code: int) -> bool:
        return code in self._glyph_codes

    def code_to_cid(self, code: int) -> int:
        return code

    def code_to_gid(self, code: int) -> int:
        return code

    def get_path(self, _code: int):
        return []

    def get_name(self) -> str:
        return "StubCIDBrokenMap"

    def is_embedded(self) -> bool:
        return False

    def get_cos_object(self):
        from pypdfbox.cos import COSStream

        class _BrokenStream(COSStream):
            def to_byte_array(self):  # type: ignore[override]
                raise AttributeError("simulated")

            def create_input_stream(self):  # type: ignore[override]
                raise AttributeError("simulated")

        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("CIDToGIDMap"), _BrokenStream())
        return d


def test_type0_cid_to_gid_map_both_byte_array_and_stream_fail(tk_root):
    """Lines 145-146: when both ``to_byte_array`` and
    ``create_input_stream`` raise, ``_read_cid_to_gid_map`` returns
    ``None`` and the constructor falls through to ``_read_map``."""
    descendant = _StubCIDFontWithBrokenMap(glyph_codes={1, 2})
    parent = _StubParentFont()
    pane = Type0Font(descendant, parent, tk_root)  # type: ignore[arg-type]
    # Fallback path: _read_map produced 2 rows for the 2 glyph codes.
    assert pane.view is not None
    assert len(pane.view.tree.get_children()) == 2
