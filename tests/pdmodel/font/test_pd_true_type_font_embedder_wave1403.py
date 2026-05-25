"""Wave 1403 branch-closure tests for
:meth:`PDTrueTypeFontEmbedder.set_widths`.

Closes the untested sides of the per-code width loop (source lines
114 / 116):

* ``114->116`` — a glyph name the Adobe glyph list cannot resolve to a
  unicode codepoint (``glyph_list.to_unicode(name)`` falsy), so the
  ``if uni:`` guard is false and ``gid`` stays 0.
* ``116->109`` — a code mapped to ``.notdef`` with ``gid == 0``: the
  ``gid > 0 or name != ".notdef"`` guard is false, so the loop skips the
  width lookup and continues to the next code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSDictionary, COSName

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
    from fontTools.ttLib import TTFont

    if not _LIBERATION_SANS.exists():
        pytest.skip(f"Bundled font missing: {_LIBERATION_SANS}")
    return TTFont(str(_LIBERATION_SANS))


class _NotdefAndBogusEncoding(Encoding):
    """Encoding mapping one code to a name with no unicode (``114->116``)
    and one code to ``.notdef`` with gid 0 (``116->109``)."""

    def get_encoding_name(self) -> str | None:
        return None

    def get_cos_object(self) -> None:
        return None

    def get_code_to_name_map(self) -> dict[int, str]:
        # 0x41: a glyph name the Adobe glyph list cannot map → uni falsy.
        # 0x42: .notdef → gid 0 and name == ".notdef" → skip.
        return {0x41: "zzbogusglyphname", 0x42: ".notdef"}


def test_set_widths_handles_unresolvable_name_and_notdef_code() -> None:
    doc = PDDocument()
    ttf = _load_ttf()
    emb = PDTrueTypeFontEmbedder(doc, COSDictionary(), ttf, WinAnsiEncoding())
    emb._font_encoding = _NotdefAndBogusEncoding()  # type: ignore[assignment]
    out = COSDictionary()
    emb.set_widths(out)
    # FirstChar/LastChar span 0x41..0x42 (2 entries).
    assert out.get_int(COSName.FIRST_CHAR) == 0x41
    assert out.get_int(COSName.LAST_CHAR) == 0x42
    widths = out.get_item(COSName.WIDTHS)
    assert widths is not None
    assert len(widths) == 2
    # Both codes resolved to gid 0:
    #  - 0x41 (bogus, name != .notdef) -> hmtx lookup for gid 0 glyph.
    #  - 0x42 (.notdef) -> width loop skipped entirely, stays 0.
    assert int(widths.get(1).int_value()) == 0
