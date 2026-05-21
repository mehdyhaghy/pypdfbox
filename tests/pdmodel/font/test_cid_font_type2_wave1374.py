"""Wave 1374 pinning tests — close 2 latent bugs in
``pypdfbox.pdmodel.font.pd_cid_font_type2`` /
``pypdfbox.pdmodel.font.pd_cid_font_type2_embedder``.

Item 1 — ``PDCIDFontType2Embedder._create_cid_font`` referenced
``self._cid_font`` (via ``_build_vertical_metrics_for_subset``) before
the constructor assigned it, raising :class:`AttributeError` whenever
the font has ``vhea``/``vmtx`` and ``vertical=True``.

Item 2 — ``PDCIDFontType2Embedder.get_cid_font`` constructed
``PDCIDFontType2(self._cid_font, self._parent, self._ttf)`` against a
2-arg constructor, raising :class:`TypeError`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fontTools.ttLib import TTFont

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_cid_font_type2_embedder import (
    PDCIDFontType2Embedder,
)
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument

_TTF_DIR = Path(__file__).parent.parent.parent.parent / "pypdfbox" / "resources" / "ttf"
_LIB_SANS = _TTF_DIR / "LiberationSans-Regular.ttf"


@pytest.fixture(scope="module", autouse=True)
def _install_missing_cos_name_constants() -> None:
    """Inject COSName constants the embedder needs."""
    for attr, raw in (
        ("BASE_FONT", "BaseFont"),
        ("FONT", "Font"),
        ("FONT_DESC", "FontDescriptor"),
        ("IDENTITY", "Identity"),
        ("ENCODING", "Encoding"),
    ):
        if not hasattr(COSName, attr):
            setattr(COSName, attr, COSName.get_pdf_name(raw))


def _load_ttf() -> TTFont:
    if not _LIB_SANS.exists():
        pytest.skip(f"Bundled font missing: {_LIB_SANS}")
    return TTFont(str(_LIB_SANS))


# ---------------------------------------------------------------------------
# Item 1 — vertical-metrics branch self-reference
# ---------------------------------------------------------------------------


class _StubVhea:
    ascent = 880
    advanceHeightMax = 1000  # noqa: N815 — fontTools naming


class _StubGlyph:
    yMax = 700  # noqa: N815 — fontTools naming


class _SyntheticVerticalTTF:
    """Tiny duck-typed TTF that exposes the minimum surface
    ``_build_vertical_metrics_for_subset`` consults: ``vhea``, ``vmtx``,
    ``head``, ``hmtx``, ``glyf``, ``maxp`` and ``getGlyphName``. Reduces
    the bug to a deterministic AttributeError without depending on a
    bundled CJK font with real vertical metrics."""

    def __init__(self) -> None:
        head = type("_Head", (), {"unitsPerEm": 1000})()
        maxp = type("_Maxp", (), {"numGlyphs": 2})()
        # vmtx/hmtx: name -> (advance, sidebearing)
        vmtx_table = {"glyph0": (1000, 0), "glyph1": (1000, 0)}
        hmtx_table = {"glyph0": (500, 0), "glyph1": (500, 0)}
        # glyf table behaves like a dict yielding objects with ``yMax``.
        glyf_table = {"glyph0": _StubGlyph(), "glyph1": _StubGlyph()}
        self._tables = {
            "vhea": _StubVhea(),
            "vmtx": vmtx_table,
            "head": head,
            "hmtx": hmtx_table,
            "glyf": glyf_table,
            "maxp": maxp,
            "cmap": type("_Cmap", (), {"getBestCmap": staticmethod(dict)})(),
        }

    def __getitem__(self, name: str) -> Any:
        return self._tables[name]

    def __contains__(self, name: str) -> bool:
        return name in self._tables

    def getGlyphName(self, gid: int) -> str:  # noqa: N802 — fontTools naming
        return f"glyph{gid}"

    def getGlyphID(self, name: str) -> int:  # noqa: N802 — fontTools naming
        return int(name.removeprefix("glyph"))


def test_create_cid_font_vertical_does_not_raise_attribute_error() -> None:
    """Repro for the latent bug: when ``vertical=True`` and the font
    actually exposes ``vhea``/``vmtx``, the vertical-metrics builder
    writes through ``self._cid_font``. Before the fix this raised
    :class:`AttributeError` because the constructor had not yet bound
    ``self._cid_font`` — the assignment in ``__init__`` only happens
    after ``_create_cid_font`` returns.

    The fix binds ``self._cid_font`` inside ``_create_cid_font`` before
    the vertical branch runs. The test passes when ``_create_cid_font``
    completes without raising and writes ``/W2`` into the dict.

    Driver pattern: instantiate the embedder against a real TTF
    (Liberation lacks vhea/vmtx so it skips the vertical builder),
    then swap ``_ttf`` for a synthetic vhea-bearing fixture and replay
    ``_create_cid_font`` directly. This isolates the reordering fix to
    the method-under-test without depending on a bundled CJK font.
    """
    doc = PDDocument()
    parent = PDType0Font()
    dict_ = COSDictionary()
    embedder = PDCIDFontType2Embedder(
        doc,
        dict_,
        _load_ttf(),
        embed_subset=False,
        parent=parent,
        vertical=True,
    )
    # Erase the binding the constructor created so we can prove the
    # reordering inside ``_create_cid_font`` re-establishes it BEFORE
    # the vertical builder fires.
    del embedder._cid_font  # noqa: SLF001
    embedder._ttf = _SyntheticVerticalTTF()  # noqa: SLF001
    rebuilt = embedder._create_cid_font()  # noqa: SLF001 — under-test
    # /W2 must have been written into the rebuilt CIDFont dict via
    # ``self._cid_font.set_item`` (line 463) — confirms the vertical
    # branch executed past the self-reference site without raising.
    assert rebuilt.get_item(COSName.get_pdf_name("W2")) is not None
    # And ``self._cid_font`` is now bound to the rebuilt dict.
    assert embedder._cid_font is rebuilt  # noqa: SLF001


# ---------------------------------------------------------------------------
# Item 2 — get_cid_font constructor arity mismatch
# ---------------------------------------------------------------------------


def test_pd_cid_font_type2_constructor_accepts_ttf_argument() -> None:
    """``PDCIDFontType2.__init__`` now accepts an optional third
    ``true_type_font`` argument so callers (the embedder's
    ``get_cid_font`` factory) can hand back the already-parsed program.
    Before the fix this raised ``TypeError`` because the constructor
    only took two positional arguments.
    """
    font_dict = COSDictionary()
    parent = PDType0Font()
    fake_ttf = object()
    cid_font = PDCIDFontType2(font_dict, parent, fake_ttf)
    # The supplied TTF object is cached so the lazy /FontFile2 parse
    # short-circuits — confirms the argument flows through.
    assert cid_font._ttf is fake_ttf  # noqa: SLF001


def test_embedder_get_cid_font_returns_pd_cid_font_type2() -> None:
    """End-to-end: the embedder's ``get_cid_font`` builds a
    :class:`PDCIDFontType2` without raising. Pinning regression for the
    1-arg-vs-3-arg constructor mismatch."""
    doc = PDDocument()
    parent = PDType0Font()
    dict_ = COSDictionary()
    embedder = PDCIDFontType2Embedder(
        doc, dict_, _load_ttf(), embed_subset=False, parent=parent, vertical=False
    )
    result = embedder.get_cid_font()
    assert isinstance(result, PDCIDFontType2)


def test_pd_cid_font_type2_constructor_zero_args_still_supported() -> None:
    """The new optional argument must remain backward-compatible: the
    no-arg constructor (and the original 2-arg form) keeps working."""
    cid_font = PDCIDFontType2()
    assert cid_font._ttf is None  # noqa: SLF001
    cid_font_two = PDCIDFontType2(COSDictionary(), PDType0Font())
    assert cid_font_two._ttf is None  # noqa: SLF001


def test_pd_cid_font_type2_constructor_accepts_real_ttf_instance(
    tmp_path: Path,
) -> None:
    """When a real :class:`TrueTypeFont` is supplied, the lazy parser
    short-circuits and ``get_true_type_font`` returns the seeded
    instance directly (no /FontFile2 fetch required)."""
    raw = _LIB_SANS.read_bytes()
    ttf = TrueTypeFont.from_bytes(raw)
    assert ttf is not None
    cid_font = PDCIDFontType2(COSDictionary(), PDType0Font(), ttf)
    # No /FontFile2 in the dict — but the seeded instance wins.
    assert cid_font.get_true_type_font() is ttf
