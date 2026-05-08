"""
``pypdfbox texttopdf -i in.txt -o out.pdf [-pageSize SIZE] [-fontSize N]
[-standardFont NAME] [-landscape] [-margins L R T B] [-lineSpacing F]
[-charset ENC]`` — build a PDF document from a plain-text file.

Mirrors upstream ``org.apache.pdfbox.tools.TextToPDF``. Upstream reads a
text file via ``BufferedReader``, lays it out top-to-bottom in a single
column with one of the 14 Standard fonts (or a TTF supplied via
``-ttf``), wraps long lines at the right margin, and starts a new page
when a line would cross the bottom margin or when the input contains a
form-feed (``\\f``) character.

The pypdfbox port keeps the same defaults — Helvetica at 10pt, 40pt
margins on each side, 1.05x line spacing, Letter media box — and
follows the same wrap-by-words / page-break-on-form-feed semantics.

``-i -`` reads the text from stdin (no upstream equivalent — upstream
takes a ``File`` only — but pipe-from-stdin is the standard Python CLI
idiom and matches the rest of the pypdfbox tools).

Skipped flags (require subsystems pypdfbox does not yet expose at the
tool level):

* ``-ttf``  — needs ``PDType0Font.load(doc, ttf_path)``. The Type 0 /
  embedded-TTF cluster is not yet wired into the tools module; only
  Standard 14 fonts are accepted via ``-standardFont`` (alias ``-font``).

Exit codes follow upstream:
  0  success
  4  I/O error (raised as ``OSError`` and caught by ``cli.run_cli``)
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import IO, Protocol, TypeGuard, cast

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDFontFactory
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

# ---------------------------------------------------------------------------
# constants — mirror upstream TextToPDF
# ---------------------------------------------------------------------------

# The scaling factor for font units to PDF units (PDF font widths are in
# 1/1000 em; multiply a unit value by font_size / FONTSCALE to get user-space
# points).
_FONTSCALE = 1000

# The default font size (mirrors upstream DEFAULT_FONT_SIZE).
_DEFAULT_FONT_SIZE = 10.0

# The line height as a factor of the font size (mirrors upstream
# DEFAULT_LINE_HEIGHT_FACTOR — 1.05 picks up a tiny bit of leading between
# lines so descenders don't kiss ascenders on the next row).
_DEFAULT_LINE_HEIGHT_FACTOR = 1.05

# The default margin in points (mirrors upstream DEFAULT_MARGIN).
_DEFAULT_MARGIN = 40.0

# Page-size table — mirrors upstream TextToPDF.PageSizes enum. Values match
# the constants on Apache PDFBox's PDRectangle (which match PDF 32000-1 /
# ISO 216).
_LETTER = PDRectangle.from_width_height(PDRectangle.LETTER_WIDTH, PDRectangle.LETTER_HEIGHT)
_LEGAL = PDRectangle.from_width_height(PDRectangle.LEGAL_WIDTH, PDRectangle.LEGAL_HEIGHT)
_A4 = PDRectangle.from_width_height(PDRectangle.A4_WIDTH, PDRectangle.A4_HEIGHT)

_PAGE_SIZES: dict[str, PDRectangle] = {
    "letter": _LETTER,
    "legal": _LEGAL,
    "a0": PDRectangle(0.0, 0.0, 2384.0, 3370.0),
    "a1": PDRectangle(0.0, 0.0, 1684.0, 2384.0),
    "a2": PDRectangle(0.0, 0.0, 1191.0, 1684.0),
    "a3": PDRectangle(0.0, 0.0, 842.0, 1191.0),
    "a4": _A4,
    "a5": PDRectangle(0.0, 0.0, 420.0, 595.0),
    "a6": PDRectangle(0.0, 0.0, 298.0, 420.0),
}

_DEFAULT_PAGE_SIZE = "Letter"
_DEFAULT_STANDARD_FONT = Standard14Fonts.HELVETICA


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "texttopdf",
        help="create a PDF document from a text file",
        description="Create a PDF document from a plain-text file. Lines are "
        "laid out top-to-bottom in a single column with a Standard 14 font; "
        "long lines wrap at the right margin and form-feed characters force "
        "a new page.",
    )
    p.add_argument(
        "-i", "--input", dest="input", required=True, metavar="INFILE",
        help="the text file to convert (use '-' for stdin)",
    )
    p.add_argument(
        "-o", "--output", dest="output", required=True, metavar="OUTFILE",
        help="the generated PDF file",
    )
    p.add_argument(
        "-pageSize", "--pageSize", dest="page_size",
        default=_DEFAULT_PAGE_SIZE, metavar="SIZE",
        help="the page size to use: Letter, Legal, A0, A1, A2, A3, A4, A5, "
        "A6 (default: Letter).",
    )
    p.add_argument(
        "-fontSize", "--fontSize", dest="font_size", type=float,
        default=_DEFAULT_FONT_SIZE, metavar="N",
        help=f"the size of the font to use (default: {_DEFAULT_FONT_SIZE!s})",
    )
    p.add_argument(
        "-standardFont", "-font", "--standardFont", "--font",
        dest="standard_font", default=_DEFAULT_STANDARD_FONT, metavar="NAME",
        help="the Standard 14 font to use (canonical PostScript name or "
        f"registered alias; default: {_DEFAULT_STANDARD_FONT})",
    )
    p.add_argument(
        "-landscape", "--landscape", dest="landscape", action="store_true",
        help="set orientation to landscape",
    )
    p.add_argument(
        "-lineSpacing", "--lineSpacing", dest="line_spacing", type=float,
        default=_DEFAULT_LINE_HEIGHT_FACTOR, metavar="F",
        help="the factor of the font size for the line height (default: "
        f"{_DEFAULT_LINE_HEIGHT_FACTOR!s})",
    )
    p.add_argument(
        "-margins", "--margins", dest="margins", type=float, nargs=4,
        default=None, metavar=("LEFT", "RIGHT", "TOP", "BOTTOM"),
        help="left, right, top, bottom margins in points (default: "
        f"{_DEFAULT_MARGIN!s} on every side)",
    )
    p.add_argument(
        "-mediaBox", "--mediaBox", dest="media_box", type=float, nargs=4,
        default=None, metavar=("LLX", "LLY", "URX", "URY"),
        help="custom media-box rectangle in points (overrides -pageSize)",
    )
    p.add_argument(
        "-charset", "--charset", dest="charset", default="utf-8",
        metavar="ENCODING",
        help="the input file's text encoding (default: utf-8)",
    )
    p.set_defaults(func=run)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _resolve_page_size(name: str) -> PDRectangle:
    """Resolve a page-size keyword to a :class:`PDRectangle`.

    Unknown names fall back to Letter, matching upstream's default-enum
    behaviour for ``-pageSize`` (PicoCLI rejects out-of-range enum values
    at parse time, so the fall-back is what upstream uses for a *valid*
    keyword that's not in our table).
    """
    return _PAGE_SIZES.get((name or "").strip().lower(), _LETTER)


class _WidthCapableFont(Protocol):
    def encode(self, text: str) -> bytes: ...

    def get_glyph_width(self, code: int) -> float: ...


def _is_readable_text(value: object) -> TypeGuard[IO[str]]:
    read = getattr(value, "read", None)
    return callable(read)


def _font_bbox_height(font: PDFont) -> float:
    """Return the font's bounding-box height in font units (1/1000 em).

    Upstream calls ``font.getBoundingBox().getHeight()`` and divides by
    FONTSCALE; the bounding box on a Standard 14 ``PDType1Font`` comes
    from the bundled AFM. We pull the same number out of
    :class:`Standard14Fonts.get_font_descriptor` (which itself reads the
    AFM) and fall back to a sensible default for the rare case where the
    font name doesn't resolve.
    """
    name = font.get_name()
    if name is not None and Standard14Fonts.contains_name(name):
        bbox = Standard14Fonts.get_font_descriptor(name)["FontBBox"]
        return float(bbox[3]) - float(bbox[1])
    descriptor = font.get_font_descriptor()
    if descriptor is not None:
        rect = descriptor.get_font_bounding_box()
        if rect is not None:
            return rect.get_height()
    # Fall-back used for fonts without metrics: 1000 (1 em). This makes
    # the line-height approximately ``font_size * line_spacing``.
    return 1000.0


def _string_width_units(font: PDFont, text: str) -> float:
    """Return the advance width of ``text`` in font units (1/1000 em).

    Mirrors upstream ``font.getStringWidth(text)``. We encode the string
    through the font's encoding and sum per-byte glyph widths (the
    Standard 14 PDType1Font path resolves the codes through
    ``StandardEncoding`` / ``WinAnsiEncoding`` and looks the per-glyph
    advance up in the bundled AFM).
    """
    width_total = 0.0
    if not text:
        return 0.0
    if hasattr(font, "encode") and hasattr(font, "get_glyph_width"):
        width_font = cast(_WidthCapableFont, font)
        encoded = width_font.encode(text)
        for code in encoded:
            width_total += float(width_font.get_glyph_width(code))
        return width_total
    # Last-ditch fallback for fonts that don't yet expose encode/get_glyph_width:
    # treat every character as a half-em (500 units in 1/1000 em). Better than
    # zero (which would make every line wrap at the first character).
    return 500.0 * len(text)


def _readlines(raw: str) -> list[str]:
    """Split ``raw`` into lines on ``\\r``, ``\\n``, or ``\\r\\n`` only.

    Equivalent to Java's ``BufferedReader.readLine`` semantics — Python's
    built-in ``str.splitlines`` also splits on ``\\f`` (form-feed), which
    would silently consume the form-feed page-break trigger that
    upstream's wrap loop expects to see *inside* a line.
    """
    lines: list[str] = []
    cur: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "\r":
            lines.append("".join(cur))
            cur = []
            if i + 1 < n and raw[i + 1] == "\n":
                i += 2
            else:
                i += 1
        elif ch == "\n":
            lines.append("".join(cur))
            cur = []
            i += 1
        else:
            cur.append(ch)
            i += 1
    if cur:
        lines.append("".join(cur))
    return lines


def _split_words(line: str) -> list[str]:
    """Split a line on single spaces, preserving runs of empties.

    Mirrors upstream ``line.split(" ", -1)`` — Java's ``String.split`` with
    a negative limit keeps trailing empties, which the wrap loop relies on
    to track word boundaries inside multi-space runs.
    """
    return line.split(" ")


# ---------------------------------------------------------------------------
# core
# ---------------------------------------------------------------------------


def create_pdf_from_text(
    document: PDDocument,
    text: Iterable[str] | IO[str],
    *,
    font: PDFont,
    font_size: float = _DEFAULT_FONT_SIZE,
    media_box: PDRectangle | None = None,
    landscape: bool = False,
    line_spacing: float = _DEFAULT_LINE_HEIGHT_FACTOR,
    left_margin: float = _DEFAULT_MARGIN,
    right_margin: float = _DEFAULT_MARGIN,
    top_margin: float = _DEFAULT_MARGIN,
    bottom_margin: float = _DEFAULT_MARGIN,
) -> None:
    """Lay ``text`` out across one or more pages of ``document``.

    Mirrors upstream ``TextToPDF.createPDFFromText(PDDocument, Reader)``:
    reads the input one line at a time, splits each line on spaces,
    accumulates words into ``next_line_to_draw`` until adding the next
    word would push the line past the right margin, then emits the
    accumulated string with ``Tj`` and advances by ``line_height``.
    A new page is started whenever:

    * the next line would cross ``bottom_margin``, or
    * the input line contains a form-feed (``\\f``) character.

    An empty input text still produces a single (blank) page so the
    resulting PDF is valid for Adobe Reader and friends — matches the
    ``textIsEmpty`` branch in upstream.
    """
    if line_spacing <= 0:
        raise ValueError(f"line spacing must be positive: {line_spacing}")

    if media_box is None:
        media_box = _LETTER

    actual_media_box = (
        PDRectangle(0.0, 0.0, media_box.get_height(), media_box.get_width())
        if landscape
        else media_box
    )

    font_height_units = _font_bbox_height(font) / _FONTSCALE
    line_height = font_height_units * font_size * line_spacing
    max_string_length = (
        actual_media_box.get_width() - left_margin - right_margin
    )

    # Normalise the iterable / file-like into a "yield-line" iterator. We
    # accept a plain iterable of str (one item per line, no trailing newline)
    # so unit tests can pass ``["foo", "bar"]`` directly; we also accept a
    # readable text file — the TextIO splitlines path strips the newline.
    if _is_readable_text(text):
        raw = text.read()
        # Mirror Java BufferedReader.readLine: split on \r, \n, \r\n only —
        # *not* on \f (form-feed). Python's str.splitlines splits on \f as
        # well, which would silently swallow upstream's page-break trigger.
        lines = _readlines(raw)
    else:
        lines = list(text)

    text_is_empty = True
    page = PDPage(actual_media_box)
    content_stream: PDPageContentStream | None = None
    y = -1.0

    def _start_new_page() -> tuple[PDPage, PDPageContentStream, float]:
        new_page = PDPage(actual_media_box)
        document.add_page(new_page)
        new_stream = PDPageContentStream(document, new_page)
        new_stream.set_font(font, font_size)
        new_stream.begin_text()
        new_y = new_page.get_media_box().get_height() - top_margin
        # Upstream nudges y back up by the leading delta so the first line
        # sits at the top margin even when line_spacing != 1.
        new_y += line_height - font_height_units * font_size
        new_stream.new_line_at_offset(left_margin, new_y)
        return new_page, new_stream, new_y

    for next_line in lines:
        text_is_empty = False
        line_words = _split_words(next_line)
        line_index = 0
        while line_index < len(line_words):
            next_line_to_draw: list[str] = []
            add_space = False
            length_if_using_next_word = 0.0
            ff = False
            # Greedy word accumulation — pull one more word as long as the
            # resulting string still fits inside max_string_length.
            while True:
                word = line_words[line_index]
                ff_index = word.find("\f")
                if ff_index == -1:
                    word1 = word
                    word2 = ""
                else:
                    ff = True
                    word1 = word[:ff_index]
                    word2 = word[ff_index + 1:]

                # word1 is the slice before the form-feed (possibly empty);
                # word2 is everything after it. Append word1 separated by a
                # space iff we've already emitted a previous word. Empty
                # word1 with no form-feed (multi-space run) still triggers
                # the space rendezvous so the spacing is preserved.
                if len(word1) > 0 or not ff:
                    if add_space:
                        next_line_to_draw.append(" ")
                    else:
                        add_space = True
                    next_line_to_draw.append(word1)

                if not ff or len(word2) == 0:
                    line_index += 1
                else:
                    # Stash the post-form-feed remainder back into the
                    # word slot — it's the first word of the new page.
                    line_words[line_index] = word2

                if ff:
                    break
                if line_index < len(line_words):
                    next_word = line_words[line_index]
                    ff_index = next_word.find("\f")
                    if ff_index != -1:
                        next_word = next_word[:ff_index]
                    line_with_next_word = (
                        "".join(next_line_to_draw) + " " + next_word
                    )
                    length_if_using_next_word = (
                        _string_width_units(font, line_with_next_word)
                        / _FONTSCALE
                    ) * font_size
                if not (
                    line_index < len(line_words)
                    and length_if_using_next_word < max_string_length
                ):
                    break

            # Page break — open a new page if the current y would drop the
            # next line below the bottom margin.
            if y - line_height < bottom_margin:
                if content_stream is not None:
                    content_stream.end_text()
                    content_stream.close()
                page, content_stream, y = _start_new_page()

            # If we made it here without ever having opened a content stream
            # (first line of the document, y was sentinel -1) the
            # _start_new_page branch above will have run.
            assert content_stream is not None
            content_stream.new_line_at_offset(0, -line_height)
            y -= line_height
            content_stream.show_text("".join(next_line_to_draw))

            if ff:
                # Form-feed: close the current page and start a fresh one
                # for whatever comes next (the post-form-feed remainder is
                # already queued back into line_words[line_index]).
                content_stream.end_text()
                content_stream.close()
                page, content_stream, y = _start_new_page()

    # Empty input: upstream still adds a single page so the resulting PDF
    # is non-empty (Reader rejects zero-page documents).
    if text_is_empty:
        document.add_page(page)

    if content_stream is not None:
        content_stream.end_text()
        content_stream.close()


def create_pdf_from_text_file(
    infile: Path | str | None,
    outfile: Path | str,
    *,
    page_size: str = _DEFAULT_PAGE_SIZE,
    font_size: float = _DEFAULT_FONT_SIZE,
    standard_font: str = _DEFAULT_STANDARD_FONT,
    landscape: bool = False,
    line_spacing: float = _DEFAULT_LINE_HEIGHT_FACTOR,
    left_margin: float = _DEFAULT_MARGIN,
    right_margin: float = _DEFAULT_MARGIN,
    top_margin: float = _DEFAULT_MARGIN,
    bottom_margin: float = _DEFAULT_MARGIN,
    media_box: PDRectangle | None = None,
    charset: str = "utf-8",
) -> None:
    """Read text from ``infile`` (``None`` or ``-`` for stdin) and emit the
    rendered PDF at ``outfile``.

    High-level helper used by the CLI; equivalent in spirit to upstream
    ``TextToPDF.call``. ``media_box`` overrides the named ``page_size``
    when supplied.
    """
    if media_box is None:
        media_box = _resolve_page_size(page_size)

    font = PDFontFactory.create_default_font(standard_font)

    doc = PDDocument()
    try:
        def _write_from(text_source: IO[str]) -> None:
            create_pdf_from_text(
                doc,
                text_source,
                font=font,
                font_size=font_size,
                media_box=media_box,
                landscape=landscape,
                line_spacing=line_spacing,
                left_margin=left_margin,
                right_margin=right_margin,
                top_margin=top_margin,
                bottom_margin=bottom_margin,
            )

        if infile is None or str(infile) == "-":
            _write_from(sys.stdin)
        else:
            path = Path(infile)
            # Strip a UTF-8 BOM if present, mirroring upstream's explicit BOM
            # handling. Python's "utf-8-sig" codec does this transparently.
            opened_charset = "utf-8-sig" if charset.lower() in ("utf-8", "utf8") else charset
            with open(path, encoding=opened_charset) as text_source:
                _write_from(text_source)
        doc.save(outfile)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    if args.input != "-" and not Path(args.input).is_file():
        print(f"texttopdf: {args.input}: not a file", flush=True)
        return 4

    if args.margins is not None:
        left_margin, right_margin, top_margin, bottom_margin = (
            float(x) for x in args.margins
        )
    else:
        left_margin = right_margin = top_margin = bottom_margin = _DEFAULT_MARGIN

    media_box: PDRectangle | None = None
    if args.media_box is not None:
        llx, lly, urx, ury = (float(x) for x in args.media_box)
        media_box = PDRectangle(llx, lly, urx, ury)

    create_pdf_from_text_file(
        args.input,
        Path(args.output),
        page_size=args.page_size,
        font_size=float(args.font_size),
        standard_font=args.standard_font,
        landscape=bool(args.landscape),
        line_spacing=float(args.line_spacing),
        left_margin=left_margin,
        right_margin=right_margin,
        top_margin=top_margin,
        bottom_margin=bottom_margin,
        media_box=media_box,
        charset=args.charset,
    )
    return 0
