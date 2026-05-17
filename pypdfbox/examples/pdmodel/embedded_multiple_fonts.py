"""Port of ``org.apache.pdfbox.examples.pdmodel.EmbeddedMultipleFonts`` (lines 44-164).

Renders multi-script text by falling back through a font list.

Wave 1286 deviation
-------------------
Upstream hard-codes Windows-specific font collections (``batang.ttc``,
``mingliu.ttc``, ``mangal.ttf``, ``ArialUni.ttf``). pypdfbox does not
redistribute those binaries (project policy bans bundling external
fonts), so :meth:`main` only succeeds when the user provides explicit
paths and otherwise raises ``NotImplementedError``. The class body is
fully implemented through :meth:`demo_with_fonts`, which accepts an
arbitrary mix of TTC files (with the requested font name) and plain
TTF/OTF files; that path is faithful to upstream behaviour. The
``show_text_multiple`` and ``is_win_ansi_encoding`` helpers mirror the
upstream private methods so callers can reuse the fallback algorithm
independently of the demo's I/O.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pypdfbox.examples.pdmodel._font_helpers import make_standard14_type1_font
from pypdfbox.fontbox.ttf.true_type_collection import TrueTypeCollection
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# Default output filename matches upstream ``document.save("example.pdf")``.
_DEFAULT_OUTPUT = "example.pdf"

# Body of text upstream uses on line 75 — mixed scripts to drive the
# fallback algorithm.
_TEXT_SAMPLE = "abc 한국 中国 भारत 日本 abc"


# Spec for a font slot: either ``"helvetica"`` (the Standard-14 fallback
# that always anchors slot 0), ``(ttc_path, font_name)`` for a named
# entry inside a TTC, or just ``ttf_path`` for a plain TTF/OTF.
FontSpec = "str | Path | tuple[str | Path, str]"


def _load_font(doc: PDDocument, spec: Any) -> PDFont:
    """Resolve ``spec`` to a :class:`PDFont` ready for the demo.

    Three accepted forms:

    * ``"helvetica"`` — the Standard-14 Helvetica Type-1 fallback (the
      WinAnsi-encoded anchor font upstream uses as slot 0).
    * ``(ttc_path, name)`` — pull the named font out of a TrueType
      Collection (mirrors upstream ``ttc.getFontByName(name)``).
    * ``path`` (str or Path) — load the TTF / OTF directly.
    """
    if isinstance(spec, str) and spec.lower() == "helvetica":
        return make_standard14_type1_font(FontName.HELVETICA)
    if isinstance(spec, tuple):
        ttc_path, font_name = spec
        collection = TrueTypeCollection(Path(ttc_path))
        try:
            ttf = collection.get_font_by_name(font_name)
            if ttf is None:
                raise OSError(
                    f"font '{font_name}' not found in TTC '{ttc_path}'",
                )
            return PDType0Font.load(doc, Path(ttc_path))
        finally:
            collection.close()
    return PDType0Font.load(doc, Path(spec))


class EmbeddedMultipleFonts:
    """Mirrors ``EmbeddedMultipleFonts`` (line 44)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 50).

        Optional positional arguments: output path then one or more font
        paths (TTF/OTF files; TTC paths are supported via the
        ``demo_with_fonts`` helper). When no font paths are supplied
        raise ``NotImplementedError`` — the demo cannot pick fallback
        fonts without explicit user input (project policy forbids
        bundling them).
        """
        argv = argv if argv is not None else []
        output = argv[0] if len(argv) >= 1 else _DEFAULT_OUTPUT
        font_specs = [Path(p) for p in argv[1:]]
        if not font_specs:
            raise NotImplementedError(
                "EmbeddedMultipleFonts depends on Windows TTC/TTF fonts "
                "(batang.ttc, mingliu.ttc, mangal.ttf, ArialUni.ttf) — "
                "fixtures not bundled. Pass one or more font paths as "
                "extra arguments or call demo_with_fonts(...) directly.",
            )
        EmbeddedMultipleFonts.demo_with_fonts(output, font_specs)

    @staticmethod
    def demo_with_fonts(
        output: str | Path,
        font_specs: list[Any],
    ) -> None:
        """Render the upstream demo using ``font_specs`` as the fallback
        chain.

        Slot 0 of the chain is always the Standard-14 Helvetica
        Type 1 font (upstream comment line 59: "always have a simple
        font as first one"). Subsequent slots are loaded from
        ``font_specs`` via :func:`_load_font`; supported forms are
        documented there.
        """
        with PDDocument() as doc:
            page = PDPage(PDRectangle.A4)
            doc.add_page(page)

            # Slot 0 — always a simple font (upstream line 59).
            fonts: list[PDFont] = [
                make_standard14_type1_font(FontName.HELVETICA),
            ]
            for spec in font_specs:
                fonts.append(_load_font(doc, spec))

            with PDPageContentStream(doc, page) as cs:
                cs.begin_text()
                cs.new_line_at_offset(20, 700)
                EmbeddedMultipleFonts.show_text_multiple(
                    cs, _TEXT_SAMPLE, fonts, 20,
                )
                cs.end_text()

            doc.save(str(output))

    @staticmethod
    def show_text_multiple(
        cs: Any,
        text: str,
        fonts: list[Any],
        size: float,
    ) -> None:
        """Mirrors ``showTextMultiple`` (line 83).

        Tries the entire text in slot 0 first; if that fails encoding,
        walks character-by-character through the fallback chain. Once a
        font can encode the current character, keeps emitting with it
        until either a character it can't encode, or a WinAnsi-encodable
        character (which should snap back to slot 0 — upstream's
        "second abc must use the same font as the first abc" comment on
        line 115).
        """
        # Fast path — slot 0 can encode the whole string.
        try:
            fonts[0].encode(text)
            cs.set_font(fonts[0], size)
            cs.show_text(text)
            return
        except (ValueError, KeyError, OSError, TypeError):
            pass  # fall through to per-char walk.

        i = 0
        n = len(text)
        while i < n:
            found = False
            for font in fonts:
                try:
                    font.encode(text[i])
                except (ValueError, KeyError, OSError, TypeError):
                    continue  # this font can't encode the char.
                # Greedy extend with this font.
                j = i + 1
                while j < n:
                    ch = text[j]
                    if (
                        EmbeddedMultipleFonts.is_win_ansi_encoding(ord(ch))
                        and font is not fonts[0]
                    ):
                        break
                    try:
                        font.encode(ch)
                    except (ValueError, KeyError, OSError, TypeError):
                        break
                    j += 1
                cs.set_font(font, size)
                cs.show_text(text[i:j])
                i = j
                found = True
                break
            if not found:
                raise ValueError(
                    f"Could not show '{text[i]}' with the fonts provided",
                )

    @staticmethod
    def is_win_ansi_encoding(unicode: int) -> bool:
        """Mirrors ``isWinAnsiEncoding(int unicode)`` (line 155)."""
        from pypdfbox.fontbox.encoding.glyph_list import GlyphList
        from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import (
            WinAnsiEncoding,
        )

        name = GlyphList.get_adobe_glyph_list().code_point_to_name(unicode)
        if name == ".notdef":
            return False
        return WinAnsiEncoding.INSTANCE.contains(name)


if __name__ == "__main__":  # pragma: no cover — CLI parity only.
    EmbeddedMultipleFonts.main(sys.argv[1:])
