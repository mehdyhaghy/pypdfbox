"""Coverage round-out for :class:`PDTrueTypeFontEmbedder`.

Targets the previously-uncovered Java-line ranges 47-56 (constructor wiring),
63 (``get_font_encoding``), 78-127 (``set_widths``), and 131-144
(``_get_unicode_cmap``). The module depends on three ``COSName``
attribute constants (``BASE_FONT``, ``ENCODING``, ``FONT_DESC``) that
upstream defines as static singletons but are not yet pre-registered in
``pypdfbox.cos.cos_name``; we register them defensively at module
import so this test can drive the embedder end-to-end.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSDictionary, COSName

# Defensive: the embedder references these as static-attribute constants.
# Register the canonical PDF names so __init__ doesn't AttributeError.
if not hasattr(COSName, "BASE_FONT"):
    COSName.BASE_FONT = COSName.get_pdf_name("BaseFont")  # type: ignore[attr-defined]
if not hasattr(COSName, "ENCODING"):
    COSName.ENCODING = COSName.get_pdf_name("Encoding")  # type: ignore[attr-defined]
if not hasattr(COSName, "FONT_DESC"):
    COSName.FONT_DESC = COSName.get_pdf_name("FontDescriptor")  # type: ignore[attr-defined]

from pypdfbox.pdmodel.font.encoding.encoding import Encoding  # noqa: E402
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import (  # noqa: E402
    WinAnsiEncoding,
)
from pypdfbox.pdmodel.font.pd_true_type_font_embedder import (  # noqa: E402
    PDTrueTypeFontEmbedder,
)
from pypdfbox.pdmodel.pd_document import PDDocument  # noqa: E402

_TTF_DIR = Path(__file__).resolve().parents[2].parent / "pypdfbox" / "resources" / "ttf"
_LIBERATION_SANS = _TTF_DIR / "LiberationSans-Regular.ttf"


def _load_ttf() -> Any:
    """Load Liberation Sans via fontTools — used by every test below."""
    from fontTools.ttLib import TTFont

    return TTFont(str(_LIBERATION_SANS))


# ---------- __init__ + happy path ----------


def test_constructor_writes_subtype_truetype() -> None:
    """Java line 47-48: ``/Subtype /TrueType`` set on the wrapped dict."""
    doc = PDDocument()
    ttf = _load_ttf()
    cos = COSDictionary()
    PDTrueTypeFontEmbedder(doc, cos, ttf, WinAnsiEncoding())
    assert cos.get_name(COSName.SUBTYPE) == "TrueType"


def test_constructor_writes_encoding_when_cos_object_present() -> None:
    """Java line 50-52: when ``Encoding.get_cos_object()`` returns
    something, it is written under ``/Encoding``."""
    doc = PDDocument()
    ttf = _load_ttf()
    cos = COSDictionary()
    PDTrueTypeFontEmbedder(doc, cos, ttf, WinAnsiEncoding())
    enc_value = cos.get_item(COSName.ENCODING)
    assert enc_value is not None
    # WinAnsiEncoding yields a COSName /WinAnsiEncoding.
    assert isinstance(enc_value, COSName)
    assert enc_value.get_name() == "WinAnsiEncoding"


def test_constructor_skips_encoding_when_cos_object_is_none() -> None:
    """Java line 50-52: the ``cos_encoding is not None`` guard means a
    bare encoding (no PDF representation) is silently skipped."""

    class _NoCosEncoding(Encoding):
        def __init__(self) -> None:
            super().__init__()
            # Add a couple entries so set_widths still runs.
            self.add(0x41, "A")
            self.add(0x42, "B")

        def get_encoding_name(self) -> str | None:
            return None

        def get_cos_object(self) -> None:
            return None

        def get_code_to_name_map(self) -> dict[int, str]:
            return {0x41: "A", 0x42: "B"}

    doc = PDDocument()
    ttf = _load_ttf()
    cos = COSDictionary()
    PDTrueTypeFontEmbedder(doc, cos, ttf, _NoCosEncoding())
    # /Encoding should be absent.
    assert cos.get_item(COSName.ENCODING) is None


def test_constructor_flips_symbolic_flags() -> None:
    """Java line 53-54: descriptor must be marked non-symbolic.

    The base ``TrueTypeEmbedder`` sets symbolic=True; the TrueType-typed
    subclass flips that so callers know the font is a Latin-1 / WinAnsi
    style font, not a Symbol-style program.
    """
    doc = PDDocument()
    ttf = _load_ttf()
    cos = COSDictionary()
    emb = PDTrueTypeFontEmbedder(doc, cos, ttf, WinAnsiEncoding())
    fd = emb.font_descriptor
    assert fd.is_symbolic() is False
    assert fd.is_non_symbolic() is True


def test_constructor_attaches_font_descriptor_object() -> None:
    """Java line 55: ``/FontDescriptor`` populated with the descriptor's
    COS object."""
    doc = PDDocument()
    ttf = _load_ttf()
    cos = COSDictionary()
    emb = PDTrueTypeFontEmbedder(doc, cos, ttf, WinAnsiEncoding())
    fd_dict = cos.get_item(COSName.FONT_DESC)
    assert fd_dict is emb.font_descriptor.get_cos_object()


def test_constructor_attaches_base_font_name() -> None:
    """Inherited via ``TrueTypeEmbedder``: ``/BaseFont`` is the
    PostScript name (name ID 6) read from the TTF."""
    doc = PDDocument()
    ttf = _load_ttf()
    cos = COSDictionary()
    PDTrueTypeFontEmbedder(doc, cos, ttf, WinAnsiEncoding())
    assert cos.get_name(COSName.BASE_FONT) == "LiberationSans"


# ---------- get_font_encoding ----------


def test_get_font_encoding_returns_constructor_argument() -> None:
    """Java line 63: identity-stable accessor."""
    doc = PDDocument()
    ttf = _load_ttf()
    enc = WinAnsiEncoding()
    emb = PDTrueTypeFontEmbedder(doc, COSDictionary(), ttf, enc)
    assert emb.get_font_encoding() is enc


# ---------- build_subset (raises) ----------


def test_build_subset_raises_not_implemented() -> None:
    """Java line 128-134: subsetting routes through PDType0Font and the
    direct TrueType embedder rejects subset requests."""
    doc = PDDocument()
    ttf = _load_ttf()
    emb = PDTrueTypeFontEmbedder(doc, COSDictionary(), ttf, WinAnsiEncoding())
    with pytest.raises(NotImplementedError, match="PDType0Font"):
        emb.build_subset(io.BytesIO(), "ABCDEF+", {1: 1})


# ---------- set_widths ----------


def test_set_widths_populates_first_last_widths() -> None:
    """Java line 86-127: with WinAnsi (32..255) and Liberation Sans,
    we expect FirstChar=32, LastChar=255, and 224 width entries."""
    doc = PDDocument()
    ttf = _load_ttf()
    cos = COSDictionary()
    PDTrueTypeFontEmbedder(doc, cos, ttf, WinAnsiEncoding())
    assert cos.get_int(COSName.FIRST_CHAR) == 32
    assert cos.get_int(COSName.LAST_CHAR) == 255
    widths = cos.get_item(COSName.WIDTHS)
    assert widths is not None
    assert len(widths) == 224
    # /space (code 0x20 -> index 0) should have positive width.
    # Liberation Sans 2048-upem -> ~500 advance for space.
    space_width = int(widths.get(0).int_value())
    assert 200 < space_width < 800


def test_set_widths_skips_when_head_table_missing() -> None:
    """Java line 88-92: KeyError on ``head`` returns early — no
    /FirstChar/LastChar/Widths emitted."""
    doc = PDDocument()
    ttf = _load_ttf()
    emb = PDTrueTypeFontEmbedder(doc, COSDictionary(), ttf, WinAnsiEncoding())

    class _NoHeadTTF:
        def __getitem__(self, key: str) -> Any:
            raise KeyError(key)

    emb._ttf = _NoHeadTTF()  # type: ignore[assignment]
    cos = COSDictionary()
    emb.set_widths(cos)
    assert cos.get_item(COSName.FIRST_CHAR) is None
    assert cos.get_item(COSName.LAST_CHAR) is None
    assert cos.get_item(COSName.WIDTHS) is None


def test_set_widths_skips_when_encoding_map_is_empty() -> None:
    """Java line 102-103: empty code_to_name map -> early return."""
    doc = PDDocument()
    ttf = _load_ttf()
    emb = PDTrueTypeFontEmbedder(doc, COSDictionary(), ttf, WinAnsiEncoding())

    class _EmptyEncoding(Encoding):
        def get_encoding_name(self) -> str | None:
            return None

        def get_cos_object(self) -> None:
            return None

        def get_code_to_name_map(self) -> dict[int, str]:
            return {}

    emb._font_encoding = _EmptyEncoding()  # type: ignore[assignment]
    cos = COSDictionary()
    emb.set_widths(cos)
    assert cos.get_item(COSName.FIRST_CHAR) is None


# ---------- _get_unicode_cmap ----------


def test_get_unicode_cmap_returns_codepoint_to_gid() -> None:
    """Java helper: cmap[0x41] should resolve to the GID for ``A``."""
    doc = PDDocument()
    ttf = _load_ttf()
    emb = PDTrueTypeFontEmbedder(doc, COSDictionary(), ttf, WinAnsiEncoding())
    cmap = emb._get_unicode_cmap()
    # ASCII 'A' (0x41) should be in any usable Latin font cmap.
    assert 0x41 in cmap
    assert cmap[0x41] == ttf.getGlyphID("A")


def test_get_unicode_cmap_returns_empty_when_cmap_table_missing() -> None:
    """Defensive: missing ``cmap`` table -> ``{}``."""
    doc = PDDocument()
    ttf = _load_ttf()
    emb = PDTrueTypeFontEmbedder(doc, COSDictionary(), ttf, WinAnsiEncoding())

    class _NoCmap:
        def __getitem__(self, key: str) -> Any:
            raise KeyError(key)

    emb._ttf = _NoCmap()  # type: ignore[assignment]
    assert emb._get_unicode_cmap() == {}


def test_get_unicode_cmap_returns_empty_when_best_cmap_is_none() -> None:
    """Defensive: ``getBestCmap`` may return ``None`` for fonts with no
    Unicode cmap subtable — we surface that as ``{}``."""
    doc = PDDocument()
    ttf = _load_ttf()
    emb = PDTrueTypeFontEmbedder(doc, COSDictionary(), ttf, WinAnsiEncoding())

    class _NullBest:
        def getBestCmap(self) -> None:  # noqa: N802 — fontTools name
            return None

    class _ShimTTF:
        def __getitem__(self, key: str) -> Any:
            if key == "cmap":
                return _NullBest()
            raise KeyError(key)

    emb._ttf = _ShimTTF()  # type: ignore[assignment]
    assert emb._get_unicode_cmap() == {}
