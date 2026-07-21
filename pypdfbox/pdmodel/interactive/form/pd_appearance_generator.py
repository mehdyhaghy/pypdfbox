from __future__ import annotations

import logging
import re
from contextlib import suppress
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable
from xml.etree import ElementTree as ET

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget

    from .pd_button import PDButton
    from .pd_choice import PDChoice
    from .pd_field import PDField
    from .pd_push_button import PDPushButton
    from .pd_signature_field import PDSignatureField
    from .pd_text_field import PDTextField


@runtime_checkable
class _ValueField(Protocol):
    def set_value(self, value: str | None) -> None: ...


_LOG = logging.getLogger(__name__)

_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_RECT: COSName = COSName.get_pdf_name("Rect")
_DA: COSName = COSName.get_pdf_name("DA")
_V: COSName = COSName.get_pdf_name("V")
_TYPE: COSName = COSName.get_pdf_name("Type")
_XOBJECT: COSName = COSName.get_pdf_name("XObject")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_FORM: COSName = COSName.get_pdf_name("Form")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_RESOURCES: COSName = COSName.get_pdf_name("Resources")
_FORM_TYPE: COSName = COSName.get_pdf_name("FormType")
_OFF: COSName = COSName.get_pdf_name("Off")
_YES: COSName = COSName.get_pdf_name("Yes")
_MK: COSName = COSName.get_pdf_name("MK")


def _parse_default_appearance(
    da: str | None,
) -> tuple[str | None, float, tuple[float, ...] | None]:
    """Parse a ``/DA`` default-appearance string into ``(font_name, size, color)``.

    The ``/DA`` string is a sequence of content-stream operators. We look
    only for the two operators that appearance generation cares about:

    - ``/<font-name> <size> Tf`` — selects font + size.
    - ``g`` / ``rg`` / ``k`` — selects non-stroking color (1, 3, or 4
      components respectively).

    Returns ``(font_name, size, color_components)`` with ``font_name = None``
    when the string omits a ``Tf`` operator (caller falls back to Helvetica),
    ``size = 0.0`` when omitted (caller picks an auto-size), and
    ``color = None`` when no color operator was present (caller defaults
    to black).

    The lite parser is intentionally simple — it splits on whitespace and
    walks tokens. Upstream uses a proper content-stream parser
    (``COSStreamParser``), which is overkill for the operator subset that
    affects flat-text appearance.
    """
    if not da:
        return (None, 0.0, None)
    tokens = da.split()
    font_name: str | None = None
    size: float = 0.0
    color: tuple[float, ...] | None = None

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "Tf" and i >= 2:
            name_tok = tokens[i - 2]
            size_tok = tokens[i - 1]
            if name_tok.startswith("/"):
                font_name = name_tok[1:]
            try:
                size = float(size_tok)
            except ValueError:
                size = 0.0
        elif tok == "g" and i >= 1:
            with suppress(ValueError):
                color = (float(tokens[i - 1]),)
        elif tok == "rg" and i >= 3:
            with suppress(ValueError):
                color = (
                    float(tokens[i - 3]),
                    float(tokens[i - 2]),
                    float(tokens[i - 1]),
                )
        elif tok == "k" and i >= 4:
            with suppress(ValueError):
                color = (
                    float(tokens[i - 4]),
                    float(tokens[i - 3]),
                    float(tokens[i - 2]),
                    float(tokens[i - 1]),
                )
        i += 1

    return (font_name, size, color)


def _rect_from_cos(value: COSBase | None) -> tuple[float, float, float, float] | None:
    """Pull a ``/Rect`` array off a widget annotation as four floats."""
    if not isinstance(value, COSArray) or value.size() < 4:
        return None
    nums: list[float] = []
    for i in range(4):
        entry = value.get_object(i)
        if isinstance(entry, (COSFloat, COSInteger)):
            nums.append(float(entry.value))
        else:
            return None
    llx, lly, urx, ury = nums
    # Normalize so width / height are non-negative — matches PDRectangle.from_cos_array.
    if urx < llx:
        llx, urx = urx, llx
    if ury < lly:
        lly, ury = ury, lly
    return (llx, lly, urx, ury)


class _RichTextRun:
    """A styled run of text emitted by :func:`_parse_rv_runs`.

    Mirrors the minimal subset of the XHTML ``/RV`` payload that
    appearance generation actually consumes — a flat list of runs each
    carrying a glyph string plus optional style overrides. The walker
    in :func:`_parse_rv_runs` flattens ``<b>`` / ``<i>`` nesting into
    the booleans below and serialises paragraph / line breaks via the
    sentinel ``line_break`` field (``True`` ⇒ render this run as a
    hard newline, ignoring ``text``).

    Lite scope: PDF 32000-1 §12.7.3.4 nominally cites XHTML 1.0 + a CSS
    subset; the lite port handles ``font-size``, ``color`` (``#rgb`` /
    ``#rrggbb`` / ``rgb(r,g,b)``), and ``font-family`` style overrides
    plus ``<b>`` / ``<i>`` / ``<p>`` / ``<br>`` / ``<span>``. All other
    tags are walked through transparently so nested text inside
    unknown elements still renders.
    """

    __slots__ = (
        "text",
        "bold",
        "italic",
        "color",
        "font_size",
        "font_family",
        "line_break",
        "text_rise",
        "background_color",
        "underline",
    )

    def __init__(
        self,
        text: str = "",
        bold: bool = False,
        italic: bool = False,
        color: tuple[float, ...] | None = None,
        font_size: float | None = None,
        font_family: str | None = None,
        line_break: bool = False,
        text_rise: float = 0.0,
        background_color: tuple[float, ...] | None = None,
        underline: bool = False,
    ) -> None:
        self.text = text
        self.bold = bold
        self.italic = italic
        self.color = color
        self.font_size = font_size
        self.font_family = font_family
        self.line_break = line_break
        # Wave 1377: long-tail XHTML features.
        # ``text_rise`` carries the PDF ``Ts`` operator argument used to
        # offset the baseline for ``<sup>`` / ``<sub>`` runs (positive =
        # superscript, negative = subscript). ``background_color`` paints
        # a filled rect behind the run before the glyphs (``<span
        # style="background-color:...">``). ``underline`` draws a 1pt
        # underline below the run (``<a href="...">`` or ``<u>``).
        self.text_rise = text_rise
        self.background_color = background_color
        self.underline = underline


# Tags whose closing emits an implicit hard line break (paragraph
# boundary). ``<br/>`` is handled separately so the break lands at the
# tag's position, not after its (typically empty) text content.
_RV_BLOCK_TAGS: frozenset[str] = frozenset({"p", "div"})


def _strip_xhtml_ns(tag: str) -> str:
    """Drop the ``{namespace}`` prefix ElementTree wraps tags in.

    ``/RV`` payloads typically declare the XHTML namespace on the root
    (``xmlns="http://www.w3.org/1999/xhtml"``) which ElementTree then
    expands into ``{http://www.w3.org/1999/xhtml}p`` etc. We compare
    tags by their local name only so the lite walker doesn't care
    which namespace prefix the producer chose.
    """
    if tag.startswith("{"):
        return tag.split("}", 1)[1].lower()
    return tag.lower()


_RV_HEX_RE = re.compile(r"#([0-9a-fA-F]{3,8})")
_RV_RGB_RE = re.compile(
    r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", re.IGNORECASE
)
# Wave 1377: ``hsl(h, s%, l%)`` -- standard CSS HSL. ``h`` is degrees
# (0-360, wraps), ``s`` / ``l`` are percentages with the literal ``%``
# suffix optional in the regex so producers that elide the ``%`` still
# parse. ``hsla`` / ``hsl(h, s, l, a)`` alpha is silently ignored
# (form appearance streams are flattened over the page background).
_RV_HSL_RE = re.compile(
    r"hsla?\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)%?\s*,"
    r"\s*(\d+(?:\.\d+)?)%?(?:\s*,\s*[^)]+)?\s*\)",
    re.IGNORECASE,
)

# Wave 1377: W3C named colours -- the union of the original 16 HTML
# basic + the 147 extended (Level 3 / 4) names. Stored verbatim as
# 8-bit RGB; the caller normalises to 0..1 floats. Coverage matches
# https://www.w3.org/TR/css-color-4/#named-colors as of 2026.
_RV_NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "aliceblue": (240, 248, 255),
    "antiquewhite": (250, 235, 215),
    "aqua": (0, 255, 255),
    "aquamarine": (127, 255, 212),
    "azure": (240, 255, 255),
    "beige": (245, 245, 220),
    "bisque": (255, 228, 196),
    "black": (0, 0, 0),
    "blanchedalmond": (255, 235, 205),
    "blue": (0, 0, 255),
    "blueviolet": (138, 43, 226),
    "brown": (165, 42, 42),
    "burlywood": (222, 184, 135),
    "cadetblue": (95, 158, 160),
    "chartreuse": (127, 255, 0),
    "chocolate": (210, 105, 30),
    "coral": (255, 127, 80),
    "cornflowerblue": (100, 149, 237),
    "cornsilk": (255, 248, 220),
    "crimson": (220, 20, 60),
    "cyan": (0, 255, 255),
    "darkblue": (0, 0, 139),
    "darkcyan": (0, 139, 139),
    "darkgoldenrod": (184, 134, 11),
    "darkgray": (169, 169, 169),
    "darkgreen": (0, 100, 0),
    "darkgrey": (169, 169, 169),
    "darkkhaki": (189, 183, 107),
    "darkmagenta": (139, 0, 139),
    "darkolivegreen": (85, 107, 47),
    "darkorange": (255, 140, 0),
    "darkorchid": (153, 50, 204),
    "darkred": (139, 0, 0),
    "darksalmon": (233, 150, 122),
    "darkseagreen": (143, 188, 143),
    "darkslateblue": (72, 61, 139),
    "darkslategray": (47, 79, 79),
    "darkslategrey": (47, 79, 79),
    "darkturquoise": (0, 206, 209),
    "darkviolet": (148, 0, 211),
    "deeppink": (255, 20, 147),
    "deepskyblue": (0, 191, 255),
    "dimgray": (105, 105, 105),
    "dimgrey": (105, 105, 105),
    "dodgerblue": (30, 144, 255),
    "firebrick": (178, 34, 34),
    "floralwhite": (255, 250, 240),
    "forestgreen": (34, 139, 34),
    "fuchsia": (255, 0, 255),
    "gainsboro": (220, 220, 220),
    "ghostwhite": (248, 248, 255),
    "gold": (255, 215, 0),
    "goldenrod": (218, 165, 32),
    "gray": (128, 128, 128),
    "green": (0, 128, 0),
    "greenyellow": (173, 255, 47),
    "grey": (128, 128, 128),
    "honeydew": (240, 255, 240),
    "hotpink": (255, 105, 180),
    "indianred": (205, 92, 92),
    "indigo": (75, 0, 130),
    "ivory": (255, 255, 240),
    "khaki": (240, 230, 140),
    "lavender": (230, 230, 250),
    "lavenderblush": (255, 240, 245),
    "lawngreen": (124, 252, 0),
    "lemonchiffon": (255, 250, 205),
    "lightblue": (173, 216, 230),
    "lightcoral": (240, 128, 128),
    "lightcyan": (224, 255, 255),
    "lightgoldenrodyellow": (250, 250, 210),
    "lightgray": (211, 211, 211),
    "lightgreen": (144, 238, 144),
    "lightgrey": (211, 211, 211),
    "lightpink": (255, 182, 193),
    "lightsalmon": (255, 160, 122),
    "lightseagreen": (32, 178, 170),
    "lightskyblue": (135, 206, 250),
    "lightslategray": (119, 136, 153),
    "lightslategrey": (119, 136, 153),
    "lightsteelblue": (176, 196, 222),
    "lightyellow": (255, 255, 224),
    "lime": (0, 255, 0),
    "limegreen": (50, 205, 50),
    "linen": (250, 240, 230),
    "magenta": (255, 0, 255),
    "maroon": (128, 0, 0),
    "mediumaquamarine": (102, 205, 170),
    "mediumblue": (0, 0, 205),
    "mediumorchid": (186, 85, 211),
    "mediumpurple": (147, 112, 219),
    "mediumseagreen": (60, 179, 113),
    "mediumslateblue": (123, 104, 238),
    "mediumspringgreen": (0, 250, 154),
    "mediumturquoise": (72, 209, 204),
    "mediumvioletred": (199, 21, 133),
    "midnightblue": (25, 25, 112),
    "mintcream": (245, 255, 250),
    "mistyrose": (255, 228, 225),
    "moccasin": (255, 228, 181),
    "navajowhite": (255, 222, 173),
    "navy": (0, 0, 128),
    "oldlace": (253, 245, 230),
    "olive": (128, 128, 0),
    "olivedrab": (107, 142, 35),
    "orange": (255, 165, 0),
    "orangered": (255, 69, 0),
    "orchid": (218, 112, 214),
    "palegoldenrod": (238, 232, 170),
    "palegreen": (152, 251, 152),
    "paleturquoise": (175, 238, 238),
    "palevioletred": (219, 112, 147),
    "papayawhip": (255, 239, 213),
    "peachpuff": (255, 218, 185),
    "peru": (205, 133, 63),
    "pink": (255, 192, 203),
    "plum": (221, 160, 221),
    "powderblue": (176, 224, 230),
    "purple": (128, 0, 128),
    "rebeccapurple": (102, 51, 153),
    "red": (255, 0, 0),
    "rosybrown": (188, 143, 143),
    "royalblue": (65, 105, 225),
    "saddlebrown": (139, 69, 19),
    "salmon": (250, 128, 114),
    "sandybrown": (244, 164, 96),
    "seagreen": (46, 139, 87),
    "seashell": (255, 245, 238),
    "sienna": (160, 82, 45),
    "silver": (192, 192, 192),
    "skyblue": (135, 206, 235),
    "slateblue": (106, 90, 205),
    "slategray": (112, 128, 144),
    "slategrey": (112, 128, 144),
    "snow": (255, 250, 250),
    "springgreen": (0, 255, 127),
    "steelblue": (70, 130, 180),
    "tan": (210, 180, 140),
    "teal": (0, 128, 128),
    "thistle": (216, 191, 216),
    "tomato": (255, 99, 71),
    "turquoise": (64, 224, 208),
    "violet": (238, 130, 238),
    "wheat": (245, 222, 179),
    "white": (255, 255, 255),
    "whitesmoke": (245, 245, 245),
    "yellow": (255, 255, 0),
    "yellowgreen": (154, 205, 50),
    # CSS Color-4 "transparent" keyword: treat as no-paint by mapping to
    # ``None`` at the caller — we leave it OUT of this table so the
    # ``transparent`` lookup falls through and the caller returns ``None``.
}


def _hsl_to_rgb(h: float, s: float, lightness: float) -> tuple[float, float, float]:
    """Convert CSS HSL (h in degrees, s/l in 0..1) to 0..1 RGB.

    Mirrors the CSS Color-3 formula (W3C). HSL hue wraps modulo 360;
    saturation and lightness are clamped to [0, 1].
    """
    s = max(0.0, min(1.0, s))
    lightness = max(0.0, min(1.0, lightness))
    # Hue in [0, 1).
    h = (h % 360.0) / 360.0
    if s == 0.0:
        return (lightness, lightness, lightness)
    q = (
        lightness * (1.0 + s)
        if lightness < 0.5
        else lightness + s - lightness * s
    )
    p = 2.0 * lightness - q

    def _hue_to_rgb(t: float) -> float:
        if t < 0.0:
            t += 1.0
        elif t > 1.0:
            t -= 1.0
        if t < 1.0 / 6.0:
            return p + (q - p) * 6.0 * t
        if t < 1.0 / 2.0:
            return q
        if t < 2.0 / 3.0:
            return p + (q - p) * (2.0 / 3.0 - t) * 6.0
        return p

    r = _hue_to_rgb(h + 1.0 / 3.0)
    g = _hue_to_rgb(h)
    b = _hue_to_rgb(h - 1.0 / 3.0)
    return (r, g, b)


def _parse_rv_color(raw: str) -> tuple[float, ...] | None:
    """Parse a CSS color expression into a 3-tuple of 0-1 RGB floats.

    Scope (wave 1377-extended):
        - ``#rgb`` / ``#rrggbb`` hex literals
        - ``rgb(r, g, b)`` functional notation
        - ``hsl(h, s%, l%)`` functional notation (CSS Color-3)
        - W3C named colours -- 147 names from CSS Color-4
          (basic 16 + extended), case-insensitive

    Anything else (``oklab(...)``, ``color-mix(...)``, the
    ``transparent`` keyword) returns ``None`` so the caller falls back
    to the inherited / ``/DA`` colour. ``oklab`` / ``oklch`` are rare
    in form rich text; deferred.
    """
    raw = raw.strip()
    hex_match = _RV_HEX_RE.fullmatch(raw)
    if hex_match is not None:
        digits = hex_match.group(1)
        if len(digits) == 3:
            # ValueError unreachable: regex restricts to [0-9a-fA-F].
            try:
                r = int(digits[0] * 2, 16)
                g = int(digits[1] * 2, 16)
                b = int(digits[2] * 2, 16)
            except ValueError:  # pragma: no cover - regex restricts to hex
                return None
            return (r / 255.0, g / 255.0, b / 255.0)
        if len(digits) == 6:
            try:
                r = int(digits[0:2], 16)
                g = int(digits[2:4], 16)
                b = int(digits[4:6], 16)
            except ValueError:  # pragma: no cover - regex restricts to hex
                return None
            return (r / 255.0, g / 255.0, b / 255.0)
        return None
    rgb_match = _RV_RGB_RE.fullmatch(raw)
    if rgb_match is not None:
        # ValueError unreachable: regex groups are ``\d+``.
        try:
            r = int(rgb_match.group(1))
            g = int(rgb_match.group(2))
            b = int(rgb_match.group(3))
        except ValueError:  # pragma: no cover - regex restricts to digits
            return None
        return (
            max(0.0, min(1.0, r / 255.0)),
            max(0.0, min(1.0, g / 255.0)),
            max(0.0, min(1.0, b / 255.0)),
        )
    # Wave 1377: hsl(...) functional notation.
    hsl_match = _RV_HSL_RE.fullmatch(raw)
    if hsl_match is not None:
        # ValueError unreachable: regex groups are ``-?\d+(\.\d+)?``.
        try:
            h = float(hsl_match.group(1))
            s = float(hsl_match.group(2)) / 100.0
            lightness = float(hsl_match.group(3)) / 100.0
        except ValueError:  # pragma: no cover - regex restricts to numeric
            return None
        return _hsl_to_rgb(h, s, lightness)
    # Wave 1377: W3C named colours (case-insensitive). Returns ``None``
    # for unknown names so the caller can keep the inherited colour.
    named = _RV_NAMED_COLORS.get(raw.lower())
    if named is not None:
        return (named[0] / 255.0, named[1] / 255.0, named[2] / 255.0)
    return None


def _parse_rv_style(style: str | None) -> dict[str, str]:
    """Parse a CSS ``style="k:v; k:v"`` attribute into a dict.

    Lite parser — splits on ``;`` then ``:``; values are trimmed but
    not unquoted (so ``font-family: "Courier New", monospace`` keeps
    the quotes for the caller to deal with). Empty / malformed
    entries are silently dropped.
    """
    out: dict[str, str] = {}
    if not style:
        return out
    for chunk in style.split(";"):
        if ":" not in chunk:
            continue
        key, _, val = chunk.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key and val:
            out[key] = val
    return out


def _parse_rv_font_size(raw: str) -> float | None:
    """Parse ``font-size: 12pt`` (or ``12px`` / bare number) into a float.

    Lite scope: ``pt`` / ``px`` (treated as 1pt = 1px — Acrobat does the
    same for the embedded XHTML), bare numbers (treated as ``pt``).
    Returns ``None`` when the value is non-numeric or zero — caller
    keeps the inherited size.
    """
    raw = raw.strip().lower()
    for suffix in ("pt", "px"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)].strip()
            break
    try:
        size = float(raw)
    except ValueError:
        return None
    if size <= 0.0:
        return None
    return size


def _parse_rv_runs(xhtml: str) -> list[_RichTextRun] | None:
    """Parse ``/RV`` XHTML into a flat sequence of styled runs.

    Returns ``None`` when the payload is not well-formed XML — caller
    falls back to the ``/V`` rendering path. The parser is intentionally
    lenient: unknown tags (e.g. ``<font>``) walk transparently so their
    text content still appears; unsupported style declarations are
    silently dropped.

    Implementation notes:
        - Uses stdlib :mod:`xml.etree.ElementTree`; no external deps
          (the project enforces a permissive-only / no-new-deps gate).
        - Treats ``<b>`` / ``<strong>`` as bold and ``<i>`` / ``<em>``
          as italic. ``<br/>`` and the close of any block tag (``<p>``,
          ``<div>``) inserts a hard line break.
        - Tag namespace prefixes are stripped (Acrobat wraps the body in
          ``<body xmlns="http://www.w3.org/1999/xhtml">``).
        - Empty paragraphs (``<p/>``, ``<p></p>``) produce a single
          line-break run — matches the "vertical spacing" spec note.

    Wave 1377 extensions (long-tail XHTML):
        - ``<sup>`` / ``<sub>`` superscript / subscript — emit a
          ``Ts`` (text-rise) offset and shrink the font size to
          ``0.583 * parent`` (matches the de-facto CSS rendering).
        - ``background-color: ...`` style declaration — fills a coloured
          rect behind the run before the glyphs are painted.
        - ``<a href="...">`` — applies the conventional blue colour
          (``#0000ee``) plus an underline unless the producer overrode
          the colour via ``style="color: ..."``. Doesn't wire a Link
          annotation (rich-text rendering produces an appearance
          stream, not annotations).
        - ``<u>`` — underline the run.
        - ``<ul>`` / ``<ol>`` / ``<li>`` — list rendering: each ``<li>``
          gets a ``"•  "`` prefix (``<ul>``) or ``"<n>.  "``
          (``<ol>``), and a hard line break between items.
        - ``<table>`` (deferred) — walked transparently, so cell text
          still renders but without column alignment. Real table
          layout is genuinely complex; deferred to a future wave.
    """
    try:
        root = ET.fromstring(xhtml)
    except ET.ParseError:
        return None
    runs: list[_RichTextRun] = []
    # Sub-/super-script font-size multiplier. CSS lays subscripts /
    # superscripts at ~0.583em (the empirical browser default).
    sub_sup_scale = 0.583
    # Conventional link colour Acrobat uses when no override is present
    # (matches HTML's ``a:link`` default ``#0000ee``).
    link_default_color: tuple[float, float, float] = (0.0, 0.0, 238.0 / 255.0)

    # Per-list state: stack of ("ul", None) / ("ol", counter) entries so
    # nested lists pick the right marker prefix. Pushed on ``<ul>`` /
    # ``<ol>`` enter, popped on close; the ``<li>`` enter reads the
    # innermost entry and increments the ``<ol>`` counter.
    list_stack: list[tuple[str, int]] = []

    def walk(
        element: ET.Element,
        *,
        bold: bool,
        italic: bool,
        color: tuple[float, ...] | None,
        font_size: float | None,
        font_family: str | None,
        text_rise: float,
        background_color: tuple[float, ...] | None,
        underline: bool,
    ) -> None:
        tag = _strip_xhtml_ns(element.tag)
        # Apply per-element style overrides (style attr + tag semantics).
        style = _parse_rv_style(element.get("style"))
        local_bold = bold or tag in ("b", "strong")
        local_italic = italic or tag in ("i", "em")
        local_color = color
        if "color" in style:
            parsed = _parse_rv_color(style["color"])
            if parsed is not None:
                local_color = parsed
        local_font_size = font_size
        if "font-size" in style:
            parsed_size = _parse_rv_font_size(style["font-size"])
            if parsed_size is not None:
                local_font_size = parsed_size
        local_font_family = font_family
        if "font-family" in style:
            local_font_family = style["font-family"].strip().strip('"\'')
        local_text_rise = text_rise
        local_background = background_color
        if "background-color" in style:
            parsed_bg = _parse_rv_color(style["background-color"])
            if parsed_bg is not None:
                local_background = parsed_bg
        elif "background" in style:
            # CSS shorthand -- accept colour-only declarations like
            # ``background: yellow``. Anything else (URL, gradient)
            # fails ``_parse_rv_color`` and falls through.
            parsed_bg = _parse_rv_color(style["background"])
            if parsed_bg is not None:
                local_background = parsed_bg
        local_underline = underline or tag == "u"
        # Sub / sup: shrink size + offset the baseline. The CSS Color-3
        # recommendation puts sup at +0.4em / sub at -0.2em on top of
        # the 0.583 shrink. Parent ``text_rise`` is preserved so nested
        # ``<sup><sub>`` stack correctly.
        if tag == "sup":
            base = local_font_size if local_font_size is not None else 0.0
            # Caller's font size may be ``None`` (inherit /DA size). The
            # rise is expressed in user units which the appearance
            # renderer later treats relative to the resolved base.
            local_font_size = (base if base > 0.0 else 1.0) * sub_sup_scale
            # Positive rise -- raise the baseline ~0.4em of the parent.
            local_text_rise = local_text_rise + (
                base if base > 0.0 else 1.0
            ) * 0.4
        elif tag == "sub":
            base = local_font_size if local_font_size is not None else 0.0
            local_font_size = (base if base > 0.0 else 1.0) * sub_sup_scale
            local_text_rise = local_text_rise - (
                base if base > 0.0 else 1.0
            ) * 0.2
        # <a href="..."> -- conventional blue + underline unless the
        # producer's own colour declaration already won above.
        if tag == "a" and element.get("href"):
            local_underline = True
            if "color" not in style:
                local_color = link_default_color

        # Self-closing line break.
        if tag == "br":
            runs.append(_RichTextRun(line_break=True))
            # Tail text after <br/> still belongs to the parent run.
            if element.tail:
                runs.append(
                    _RichTextRun(
                        text=element.tail,
                        bold=bold,
                        italic=italic,
                        color=color,
                        font_size=font_size,
                        font_family=font_family,
                        text_rise=text_rise,
                        background_color=background_color,
                        underline=underline,
                    )
                )
            return
        # ----- list enter -----------------------------------------------------
        if tag in ("ul", "ol"):
            list_stack.append((tag, 0))
        # <li> enter: emit the marker prefix as its own run.
        if tag == "li" and list_stack:
            kind, counter = list_stack[-1]
            counter += 1
            list_stack[-1] = (kind, counter)
            marker = "•  " if kind == "ul" else f"{counter}.  "
            runs.append(
                _RichTextRun(
                    text=marker,
                    bold=local_bold,
                    italic=local_italic,
                    color=local_color,
                    font_size=local_font_size,
                    font_family=local_font_family,
                    text_rise=local_text_rise,
                    background_color=local_background,
                    underline=local_underline,
                )
            )
        # Element text (before any children).
        if element.text:
            runs.append(
                _RichTextRun(
                    text=element.text,
                    bold=local_bold,
                    italic=local_italic,
                    color=local_color,
                    font_size=local_font_size,
                    font_family=local_font_family,
                    text_rise=local_text_rise,
                    background_color=local_background,
                    underline=local_underline,
                )
            )
        empty_block = (
            tag in _RV_BLOCK_TAGS
            and not element.text
            and len(list(element)) == 0
        )
        for child in element:
            walk(
                child,
                bold=local_bold,
                italic=local_italic,
                color=local_color,
                font_size=local_font_size,
                font_family=local_font_family,
                text_rise=local_text_rise,
                background_color=local_background,
                underline=local_underline,
            )
        # Block-level close: emit line break + paragraph spacing.
        if tag in _RV_BLOCK_TAGS:
            runs.append(_RichTextRun(line_break=True))
            if empty_block:
                # Empty <p/> nominally inserts vertical spacing — represent
                # as two line breaks so the rendered baseline advances
                # one full line height of blank space.
                runs.append(_RichTextRun(line_break=True))
        # <li> close: hard line break between items.
        if tag == "li":
            runs.append(_RichTextRun(line_break=True))
        # <ul> / <ol> close: pop the list stack.
        if tag in ("ul", "ol") and list_stack:
            list_stack.pop()
        # Tail text after the element (in the parent's context).
        if element.tail:
            runs.append(
                _RichTextRun(
                    text=element.tail,
                    bold=bold,
                    italic=italic,
                    color=color,
                    font_size=font_size,
                    font_family=font_family,
                    text_rise=text_rise,
                    background_color=background_color,
                    underline=underline,
                )
            )

    walk(
        root,
        bold=False,
        italic=False,
        color=None,
        font_size=None,
        font_family=None,
        text_rise=0.0,
        background_color=None,
        underline=False,
    )
    # Trim a single trailing line break so the rendered output doesn't
    # have an extra blank line at the bottom of the rect.
    while runs and runs[-1].line_break:
        runs.pop()
    return runs


class PDAppearanceGenerator:
    """Lite port of upstream ``AppearanceGeneratorHelper`` — generates
    *flat* normal appearances for AcroForm widget annotations.

    Mirrors ``org.apache.pdfbox.pdmodel.interactive.form.AppearanceGenerator``
    (the static facade) and ``AppearanceGeneratorHelper`` (the worker
    that actually composes the content stream). The lite scope covers:

    1. **Text fields (``/FT /Tx``)**: a single line of flat text, font /
       color resolved from ``/DA``.
    2. **Check boxes (``/FT /Btn`` without push/radio bits)**: a two-state
       appearance subdictionary keyed by the field's on-value name and
       ``/Off``. The on-state draws a ZapfDingbats checkmark glyph (code
       ``4``); the off-state is empty.
    3. **Radio buttons (``/FT /Btn`` with ``FLAG_RADIO``)**: same shape as
       check boxes but the on-state draws a filled circle inscribed in
       the widget rect.
    4. **Choice fields (``/FT /Ch`` — combo + list)**: the selected
       option(s) rendered as flat text in the widget area, mirroring the
       text-field path with newline-joined values.

    For each widget the generator:

    - Pulls ``/Rect`` to size the appearance ``/BBox``.
    - Parses the field's (or AcroForm's) ``/DA`` (font name, font size,
      non-stroking color).
    - Emits the per-field-type content stream into a fresh form-XObject.
    - Installs the result as the widget's ``/AP /N`` (normal appearance);
      for buttons this is the on-state-keyed subdictionary, for text
      and choice fields it's a single appearance stream.

    **Text fields (Wave 33+):** support multi-line (``Ff`` bit 13),
    comb (``Ff`` bit 25 — distributes the value's characters into
    ``/MaxLen`` equal-width cells), and quadding (``/Q`` 0/1/2 = left /
    centered / right alignment). Auto-line-wrap walks the value
    breaking on whitespace, advancing the baseline by ``size * 1.15``
    per line.

    **Push buttons (Wave 33+, /R + /D closed in Wave 1377):** the
    widget's ``/MK /CA`` caption is rendered as flat text centred in
    the rect, with an optional border drawn from ``/MK /BC`` and a
    flat background fill from ``/MK /BG``. Rollover (``/MK /RC``) and
    alternate / down (``/MK /AC``) captions emit ``/AP /R`` and ``/AP
    /D`` appearance streams alongside ``/N`` — rollover uses a
    lightened ``/MK /BG``, down uses a darkened ``/MK /BG``. When
    ``/RC`` / ``/AC`` are absent **and** no ``/MK /BG`` is set the
    variant is skipped (viewers fall back to ``/N`` per PDF 32000
    §12.5.5).

    **Signature fields (Wave 33+):** when the field carries a
    ``/V`` ``PDSignature``, the visual appearance is a flat box with
    the signer's ``/Name`` and ``/M`` sign date in two Helvetica-10
    lines. Sigfields without a signature value get an empty stream.

    **Closed in Wave 1374:** ``/MK /R`` widget rotation now applies to
    the appearance bbox + /Matrix; iterative auto-size loop ports
    upstream's measure-then-shrink (halve until the value fits the
    rect width, floored at :attr:`MINIMUM_FONT_SIZE`); unsigned
    signature widgets honour ``/MK /BC`` + ``/MK /BG`` colours and
    render a "Click to sign" prompt (matches upstream
    ``PDVisibleSigBuilder``).

    **Closed in Wave 1375:** custom-embedded ``/DA`` fonts now resolve
    through the three-tier walk ``AcroForm /DR /Font`` -> ``widget /AP /N
    /Resources /Font`` -> ``page /Resources /Font`` (first hit wins),
    matching upstream ``PDDefaultAppearanceString`` + the per-widget
    hoist in ``validateAndEnsureAcroFormResources``. The resolved font's
    ``COSDictionary`` is registered under the source ``/DA`` alias in
    the generated appearance ``/Resources``, so embedded TrueType / Type0
    fonts keep their metrics (width, ascent / descent) and the emitted
    ``/<alias> <size> Tf`` token continues to reference the right font
    object after regeneration.
    """

    DEFAULT_FONT_SIZE: float = 12.0
    AUTO_FONT_SIZE_MIN: float = 4.0
    AUTO_FONT_SIZE_MAX: float = 12.0

    # Upstream parity constants (mirror AppearanceGeneratorHelper static fields).
    # FONTSCALE — font units are 1/1000 em; multiply a unit value by
    # ``size / FONTSCALE`` to get user-space pixels.
    FONTSCALE: int = 1000
    # MINIMUM_FONT_SIZE — used by upstream's iterative auto-size to avoid
    # picking a size below 4pt; the lite-port auto-size also clamps here.
    MINIMUM_FONT_SIZE: float = 4.0
    # DEFAULT_PADDING — Acrobat's default 0.5pt padding around the field
    # bbox. The lite port uses a 1pt margin (interior_w = width - 2.0)
    # for the clip rect, but the upstream constant is preserved here so
    # callers porting from upstream code can reference it.
    DEFAULT_PADDING: float = 0.5
    # HIGHLIGHT_COLOR — Acrobat's listbox-selection highlight (sRGB).
    # Upstream value is {153/255, 193/255, 215/255} — preserved exactly.
    HIGHLIGHT_COLOR: tuple[float, float, float] = (
        153.0 / 255.0,
        193.0 / 255.0,
        215.0 / 255.0,
    )

    # Newline characters upstream's PATTERN regex matches (PDFBOX-3911):
    # CRLF, LF, VT, FF, CR, NEL (U+0085), LS (U+2028), PS (U+2029).
    # Single-line text fields collapse any of these to a single space.
    _NEWLINE_PATTERN: re.Pattern[str] = re.compile(
        "\r\n|[\n\u000B\u000C\r\u0085\u2028\u2029]"
    )

    # ZapfDingbats character code for the heavy check mark glyph (a4).
    # PDF 32000-1:2008 Annex D uses code 0x34 ('4') for "a20" check.
    ZAPFDINGBATS_CHECK = b"4"

    # Acrobat-recognised ``/MK /CA`` glyph codes for check-box style
    # selection. Stored as Python str so callers reading ``/MK /CA`` (which
    # comes back as a decoded string) can index this map directly. The
    # corresponding bytes are emitted verbatim into the ZapfDingbats text
    # operator at render time. PDF 32000-1:2008 Annex D names per code:
    #
    #     "4"  → a20  heavy check mark (default / Acrobat checkbox check)
    #     "5"  → a18  X mark
    #     "6"  → a22  ballot X
    #     "7"  → a13  six-pointed star
    #     "8"  → a17  six-pointed asterisk (Acrobat "cross")
    #     "u"  → a4   diamond
    #     "n"  → a6   square
    #     "l"  → a3   bullet circle
    #     "H"  → a39  heavy circle
    #
    # The map is deliberately a superset of the two codes called out in
    # Wave 1305's task spec ("4" check / "8" cross) so callers picking
    # less-common glyph styles still get a valid appearance.
    MK_CA_GLYPHS: dict[str, bytes] = {
        "4": b"4",
        "5": b"5",
        "6": b"6",
        "7": b"7",
        "8": b"8",
        "u": b"u",
        "n": b"n",
        "l": b"l",
        "H": b"H",
    }

    # /DA font-name aliases mapped to their resolved Standard 14 names.
    # Upstream Acrobat / Reader populate the AcroForm /DR /Font dict with
    # these short keys (``Helv``, ``HeBo``, ``TiRo``, etc.); the lite port
    # resolves them directly to the matching Standard 14 face so callers
    # without a /DR walk still pick a sensible font. Exposed publicly so
    # callers can introspect the mapping (e.g. for /DR fix-ups).
    DA_FONT_ALIASES: dict[str, str] = {
        "Helv": Standard14Fonts.HELVETICA,
        "HeBo": Standard14Fonts.HELVETICA_BOLD,
        "HeIt": Standard14Fonts.HELVETICA_OBLIQUE,
        "HeBI": Standard14Fonts.HELVETICA_BOLD_OBLIQUE,
        "TiRo": "Times-Roman",
        "TiBo": "Times-Bold",
        "TiIt": "Times-Italic",
        "TiBI": "Times-BoldItalic",
        "CoRo": "Courier",
        "CoBo": "Courier-Bold",
        "CoIt": "Courier-Oblique",
        "CoBI": "Courier-BoldOblique",
        "Symb": "Symbol",
        "ZaDb": "ZapfDingbats",
    }

    def __init__(self, default_appearance: str | None = None) -> None:
        """``default_appearance`` is an optional override used when the
        field carries no ``/DA`` of its own and the inheritable walk also
        returns nothing. Falls back to ``"/Helv 0 Tf 0 g"``."""
        self._default_appearance_override = default_appearance

    # ------------------------------------------------------------------
    # public surface
    # ------------------------------------------------------------------

    def set_appearance_value(self, field: PDField, ap_value: str | None) -> None:
        """Set ``field``'s ``/V`` to ``ap_value`` and regenerate every widget's
        normal appearance.

        Mirrors upstream ``AppearanceGeneratorHelper.setAppearanceValue``
        (the only public method on the upstream helper). Upstream
        constructs the helper with the field, then accepts only the new
        value here; the lite port collapses both into one call.

        Per PDFBOX-3911, single-line ``PDTextField`` values collapse
        every newline-class character (``\\n``, ``\\r``, VT, FF, NEL,
        LS, PS, and the CRLF pair) to a single space before
        regeneration — matches Adobe Reader's interactive-entry
        behavior.
        """
        from .pd_text_field import PDTextField

        if isinstance(field, PDTextField) and not field.is_multiline():
            normalized = self._NEWLINE_PATTERN.sub(" ", ap_value or "")
            field.set_value(normalized)
        elif isinstance(field, _ValueField):
            field.set_value(ap_value)
        self.generate(field)

    @staticmethod
    def is_supported_field(field: PDField) -> bool:
        """Predicate — ``True`` when :meth:`generate` will produce a
        non-trivial appearance for ``field``.

        Returns ``False`` for non-terminal fields and for terminal fields
        whose ``/FT`` is unrecognised (e.g. a custom subtype). Callers
        building tooling around the generator can use this to short-circuit
        before walking widgets — matches the ``instanceof`` cascade in
        :meth:`generate` so the two never disagree.
        """
        from .pd_button import PDButton
        from .pd_choice import PDChoice
        from .pd_signature_field import PDSignatureField
        from .pd_text_field import PDTextField

        return isinstance(
            field, (PDTextField, PDButton, PDChoice, PDSignatureField)
        )

    def generate(self, field: PDField) -> None:
        """Regenerate the ``/AP /N`` normal appearance of every widget on
        ``field``. Dispatches on field type:

        - ``/Tx`` text → flat text appearance (single-line, multi-line,
          comb, or quadded based on ``Ff`` / ``/Q``).
        - ``/Btn`` check / radio → two-state on/off appearance subdict.
        - ``/Btn`` push button → centred ``/MK /CA`` caption with
          optional border / background.
        - ``/Ch`` combo / list → flat text rendering of selected value(s).
        - ``/Sig`` signature → flat name + date box (when ``/V`` set).
        - anything else → debug-logged and skipped.
        """
        from .pd_button import PDButton
        from .pd_check_box import PDCheckBox
        from .pd_choice import PDChoice
        from .pd_push_button import PDPushButton
        from .pd_radio_button import PDRadioButton
        from .pd_signature_field import PDSignatureField
        from .pd_text_field import PDTextField

        if isinstance(field, PDTextField):
            self._generate_text_field(field)
            return
        if isinstance(field, PDPushButton):
            self._generate_push_button(field)
            return
        if isinstance(field, (PDCheckBox, PDRadioButton)):
            self._generate_button(field)
            return
        if isinstance(field, PDButton):
            # Untyped /Btn (generic PDButton) — treat as check box.
            self._generate_button(field)
            return
        if isinstance(field, PDChoice):
            self._generate_choice(field)
            return
        if isinstance(field, PDSignatureField):
            self._generate_signature(field)
            return
        _LOG.debug(
            "PDAppearanceGenerator.generate: skipping %s — not a "
            "supported field type",
            type(field).__name__,
        )

    # ------------------------------------------------------------------
    # text field
    # ------------------------------------------------------------------

    def _generate_text_field(self, field: PDTextField) -> None:
        value = field.get_value() or ""
        da = self._resolve_default_appearance(field)
        font_name, font_size, color = _parse_default_appearance(da)

        is_multiline = field.is_multiline()
        is_comb = field.is_comb()
        is_password = field.is_password()
        max_len = field.get_max_len()
        # Field-level (inheritable) ``/Q`` — used as the fallback when a
        # widget carries no ``/Q`` of its own. Per-widget resolution
        # happens inside the loop via :meth:`_resolve_text_align`,
        # matching upstream ``AppearanceGeneratorHelper.getTextAlign``.
        field_quadding = field.get_q()

        # Wave 1375 — rich-text (``/RV``) rendering. When the field carries
        # ``/RV`` we parse the XHTML payload into styled runs and render
        # those instead of the plain ``/V`` value. Comb, password, and
        # multi-line single-cell layouts ignore ``/RV`` (the rich payload
        # is not meaningful in those modes — PDF 32000-1 §12.7.3.4 ties
        # ``/RV`` to ``Ff`` bit 26 / multi-line layout). Password fields
        # never opt into ``/RV`` rendering — the masked output is the
        # /V-driven asterisk run. On any parse failure we silently fall
        # back to the /V path.
        rich_runs: list[_RichTextRun] | None = None
        if not is_comb and not is_password:
            rv = self._resolve_rich_text_value(field)
            if rv:
                rich_runs = _parse_rv_runs(rv)

        # PDFBOX-3911: single-line text fields collapse newline-class
        # characters to a single space before rendering. Multi-line and
        # comb fields keep newlines so the wrap / cell logic can split on
        # them.
        if not is_multiline and not is_comb and value:
            value = self._NEWLINE_PATTERN.sub(" ", value)

        # Password fields render every char as an asterisk per PDF 32000-1
        # §12.7.4.3 — the underlying ``/V`` value is unchanged. We mask once
        # here so the multi-line / comb / quadding layout below all observe
        # the masked string consistently. ``len(value)`` measures Python
        # codepoints, which matches upstream's character-by-character mask.
        if is_password and value:
            value = "*" * len(value)

        for widget in field.get_widgets():
            # Wave 1375 — resolve the font per widget so the widget's own
            # /AP /N /Resources /Font + parent-page /Resources /Font are
            # consulted in addition to the AcroForm /DR /Font (closes the
            # "custom-embedded /DA fonts not honoured" deviation).
            font = self._resolve_font_for_field(field, font_name, widget)
            # Resolve quadding per widget: a widget's own ``/Q`` wins,
            # else fall back to the field's (inheritable) ``/Q``. Mirrors
            # upstream ``AppearanceGeneratorHelper.getTextAlign(widget)``.
            quadding = self._resolve_text_align(widget, field_quadding)
            if rich_runs is not None:
                self._regenerate_rich_text_widget(
                    widget, rich_runs, font, font_name, font_size, color,
                )
                continue
            self._regenerate_text_widget(
                widget,
                value,
                font,
                font_name,
                font_size,
                color,
                is_multiline=is_multiline,
                is_comb=is_comb,
                max_len=max_len,
                quadding=quadding,
            )

    @staticmethod
    def _resolve_rich_text_value(field: PDTextField) -> str | None:
        """Pull ``/RV`` off ``field`` as a Python string. Returns ``None``
        when absent or when the typed accessor errors (defensive — the
        rich-text path falls back to ``/V`` on any failure).
        """
        getter = getattr(field, "get_rich_text_value", None)
        if not callable(getter):
            return None
        try:
            return getter()
        except Exception:  # noqa: BLE001 — defensive: any failure → /V fallback
            return None

    @staticmethod
    def _resolve_text_align(widget: PDAnnotationWidget, field_quadding: int) -> int:
        """Return the quadding (``/Q``) to apply to ``widget``.

        Mirrors upstream ``AppearanceGeneratorHelper.getTextAlign(widget)``
        which reads ``widget.getCOSObject().getInt(COSName.Q, field.getQ())``
        — a widget's own ``/Q`` wins, otherwise the field's (inheritable)
        ``/Q`` is used as the fallback. ``/Q`` values: ``0`` = left,
        ``1`` = centered, ``2`` = right.
        """
        widget_cos = widget.get_cos_object()
        return widget_cos.get_int(COSName.Q, field_quadding)

    # ------------------------------------------------------------------
    # button (check / radio)
    # ------------------------------------------------------------------

    def _generate_button(self, field: PDButton) -> None:
        """Build a two-state appearance subdictionary on each widget.

        - ``/AP /N /<on-state>`` — drawn glyph (check or filled circle).
        - ``/AP /N /Off`` — empty stream.

        The on-state name comes from the existing widget appearance dict
        when present (so re-generation preserves the upstream-chosen state
        name); otherwise we default to ``/Yes``. The widget's ``/AS`` is
        synced to either the on-state name or ``/Off`` based on the
        field's ``/V`` value.
        """
        from .pd_radio_button import PDRadioButton

        is_radio = isinstance(field, PDRadioButton)
        current_value = field.get_value()

        for widget in field.get_widgets():
            widget_cos = widget.get_cos_object()
            rect = _rect_from_cos(widget_cos.get_dictionary_object(_RECT))
            if rect is None:
                _LOG.debug(
                    "PDAppearanceGenerator: button widget has no /Rect, "
                    "skipping appearance regeneration"
                )
                continue
            llx, lly, urx, ury = rect
            width = urx - llx
            height = ury - lly
            if width <= 0.0 or height <= 0.0:
                continue

            on_state = self._on_state_name_for_widget(widget_cos)

            # Pull the optional ``/MK /CA`` caption — for check boxes this
            # is a ZapfDingbats glyph code (Acrobat default is "4" =
            # heavy check, "8" = cross). Radio buttons ignore it (the
            # on-state always draws a filled circle).
            glyph_bytes = self._mk_ca_glyph_bytes(widget_cos)

            # Wave 1374 — apply /MK /R rotation to both on / off states.
            rotation = self._resolve_widget_rotation(widget_cos)

            on_stream = self._build_button_on_appearance(
                width, height, is_radio, glyph_bytes, rotation
            )
            off_stream = self._build_empty_appearance(width, height, rotation)

            n_subdict = COSDictionary()
            n_subdict.set_item(
                COSName.get_pdf_name(on_state),
                on_stream.get_cos_object(),
            )
            n_subdict.set_item(_OFF, off_stream.get_cos_object())

            ap_dict = PDAppearanceDictionary()
            ap_dict.get_cos_object().set_item(_N, n_subdict)
            widget_cos.set_item(_AP, ap_dict.get_cos_object())

            # Sync /AS so the viewer renders the matching subdictionary entry.
            if current_value and current_value == on_state:
                widget_cos.set_item(
                    COSName.get_pdf_name("AS"),
                    COSName.get_pdf_name(on_state),
                )
            else:
                widget_cos.set_item(COSName.get_pdf_name("AS"), _OFF)

    @classmethod
    def _mk_ca_glyph_bytes(cls, widget_cos: COSDictionary) -> bytes:
        """Return the ZapfDingbats glyph bytes implied by ``/MK /CA``.

        Falls back to the heavy check mark when ``/MK`` is missing,
        ``/CA`` is absent, or ``/CA`` carries a glyph code that isn't in
        :attr:`MK_CA_GLYPHS`. The returned bytes are encoded for
        emission into a ``( … ) Tj`` operator (single-byte ZapfDingbats
        codes only — multi-glyph captions land in the push-button path
        instead).
        """
        mk = widget_cos.get_dictionary_object(_MK)
        if isinstance(mk, COSDictionary):
            ca = mk.get_string(COSName.get_pdf_name("CA"))
            # /MK /CA is conventionally a single-glyph code for
            # checkboxes — only honour the lookup when the caption
            # matches one of the spec-recognised codes. Multi-char
            # captions get the default check glyph (they belong on
            # push buttons, where the caption is rendered as text).
            if isinstance(ca, str) and len(ca) == 1 and ca in cls.MK_CA_GLYPHS:
                return cls.MK_CA_GLYPHS[ca]
        return cls.ZAPFDINGBATS_CHECK

    def _on_state_name_for_widget(self, widget_cos: COSDictionary) -> str:
        """Return the on-state name to use for ``widget_cos``.

        Prefers the first non-Off key already present in the widget's
        ``/AP /N`` subdictionary so re-generation preserves the
        per-widget state name (matters for radio groups where each kid
        carries its own on-state). Falls back to ``"Yes"``.
        """
        ap = widget_cos.get_dictionary_object(_AP)
        if isinstance(ap, COSDictionary):
            n = ap.get_dictionary_object(_N)
            if isinstance(n, COSDictionary):
                for key in n.key_set():
                    if key != _OFF:
                        return key.name
        return "Yes"

    def _build_button_on_appearance(
        self,
        width: float,
        height: float,
        is_radio: bool,
        glyph_bytes: bytes = ZAPFDINGBATS_CHECK,
        rotation: int = 0,
    ) -> PDAppearanceStream:
        if rotation in (90, 270):
            bbox_w, bbox_h = height, width
        else:
            bbox_w, bbox_h = width, height
        appearance_cos = self._fresh_form_xobject(bbox_w, bbox_h)
        appearance_stream = PDAppearanceStream(appearance_cos)
        if rotation != 0:
            appearance_stream.set_matrix(
                self._calculate_matrix(bbox_w, bbox_h, rotation)
            )
        with PDAppearanceContentStream(appearance_stream) as raw_cs:
            cs = cast(PDAppearanceContentStream, raw_cs)
            cs.save_graphics_state()
            if is_radio:
                self._draw_radio_dot(cs, width, height)
            else:
                self._draw_check_glyph(cs, width, height, glyph_bytes)
            cs.restore_graphics_state()
        return appearance_stream

    def _build_empty_appearance(
        self, width: float, height: float, rotation: int = 0
    ) -> PDAppearanceStream:
        if rotation in (90, 270):
            bbox_w, bbox_h = height, width
        else:
            bbox_w, bbox_h = width, height
        appearance_cos = self._fresh_form_xobject(bbox_w, bbox_h)
        appearance_stream = PDAppearanceStream(appearance_cos)
        if rotation != 0:
            appearance_stream.set_matrix(
                self._calculate_matrix(bbox_w, bbox_h, rotation)
            )
        # Open + close the writer so the body is committed (an empty
        # byte string is valid — the appearance stream is just a no-op).
        with PDAppearanceContentStream(appearance_stream):
            pass
        return appearance_stream

    def _draw_check_glyph(
        self,
        cs: PDAppearanceContentStream,
        width: float,
        height: float,
        glyph_bytes: bytes = ZAPFDINGBATS_CHECK,
    ) -> None:
        """Draw a ZapfDingbats glyph centered in the widget rect.

        Uses the resource-registered ZapfDingbats font so the encoded
        ``glyph_bytes`` (typically ``b"4"`` for the heavy check / ``b"8"``
        for the cross) map to the matching glyph at runtime. Caller picks
        the byte sequence via :meth:`_mk_ca_glyph_bytes` from the widget's
        ``/MK /CA`` caption.
        """
        font = PDFontFactory.create_default_font(Standard14Fonts.ZAPF_DINGBATS)
        # Glyph height ~ 0.7 of cap-height; pick a size that fits the rect
        # with a small margin.
        size = max(1.0, min(width, height) * 0.8)
        # ZapfDingbats glyph metrics put the check around half the em
        # square — center horizontally with a 50% nominal width estimate.
        x = (width - size * 0.5) / 2.0
        y = (height - size * 0.7) / 2.0
        cs.begin_text()
        cs.set_non_stroking_color((0.0,))
        cs.set_font(font, size)
        cs.new_line_at_offset(x, y)
        # Pass raw bytes so ``show_text`` emits ``(4) Tj`` verbatim — the
        # ZapfDingbats encoding handles the codepoint -> glyph mapping
        # at render time.
        cs.show_text(glyph_bytes)
        cs.end_text()

    def _draw_radio_dot(
        self, cs: PDAppearanceContentStream, width: float, height: float
    ) -> None:
        """Draw a filled circle inscribed in the widget rect.

        Uses the standard 4-Bezier circle approximation (kappa = 0.5523)
        about the rect center with radius = 0.4 * min(width, height).
        """
        cx = width / 2.0
        cy = height / 2.0
        r = min(width, height) * 0.4
        if r <= 0.0:
            return
        k = r * 0.5522847498  # 4-cubic-Bezier circle approximation constant
        cs.set_non_stroking_color((0.0,))
        cs.move_to(cx + r, cy)
        cs.curve_to(cx + r, cy + k, cx + k, cy + r, cx, cy + r)
        cs.curve_to(cx - k, cy + r, cx - r, cy + k, cx - r, cy)
        cs.curve_to(cx - r, cy - k, cx - k, cy - r, cx, cy - r)
        cs.curve_to(cx + k, cy - r, cx + r, cy - k, cx + r, cy)
        cs.close_path()
        cs.fill()

    # ------------------------------------------------------------------
    # choice (combo / list)
    # ------------------------------------------------------------------

    def _generate_choice(self, field: PDChoice) -> None:
        """Render the field's selected value(s) as flat text.

        For combo boxes (single-select) the selected value is rendered
        as a single line of flat text. For list boxes the entire option
        list is laid out one-per-row starting from the field's ``/TI``
        scroll-offset (top index), and rows whose option matches the
        selected ``/V`` (or whose index appears in ``/I``) get a
        highlight rectangle drawn behind the row text — mirrors
        upstream's ``insertGeneratedListboxAppearance``.
        """
        from .pd_list_box import PDListBox

        values = field.get_value()
        if isinstance(values, str):
            selected_values = [values] if values else []
        elif isinstance(values, list):
            selected_values = [v for v in values if v]
        else:
            selected_values = []

        da = self._resolve_default_appearance(field)
        font_name, font_size, color = _parse_default_appearance(da)

        is_listbox = isinstance(field, PDListBox)
        options: list[str] = []
        top_index = 0
        selected_indices: list[int] = []
        try:
            options = field.get_options_display_values() or field.get_options()
        except Exception:  # noqa: BLE001 — defensive on lite-port surface
            options = []
        top_index = max(0, field.get_top_index())
        selected_indices = field.get_selected_options_indices()

        # PDFBOX-6150 (3.0.8) — upstream ``PDComboBox.constructAppearances``:
        # when the field carries separate export and display values, a combo
        # box renders the DISPLAY value found at the index of the selected
        # export value within the options export list. When the export value
        # is not found in the options (or the pair list is too short), the
        # raw ``/V`` export value is rendered unchanged.
        combo_lines = selected_values
        if (
            not is_listbox
            and selected_values
            and field.has_separate_export_and_display_values()
        ):
            display_values = field.get_options_display_values()
            try:
                index = field.get_options().index(selected_values[0])
            except ValueError:
                index = -1
            if index != -1 and index < len(display_values):
                combo_lines = [display_values[index]]

        for widget in field.get_widgets():
            # Wave 1375 — per-widget font resolution: walks /AP /N /Resources
            # + page /Resources after /DR /Font so custom-embedded /DA fonts
            # are honoured even when they live at the widget or page level.
            font = self._resolve_font_for_field(field, font_name, widget)
            if is_listbox:
                # When the field has no /Opt entries (uncommon but legal),
                # fall back to the selected values themselves so the widget
                # surface still shows something. Selection highlight then
                # covers the entire visible row range.
                rows = options if options else selected_values
                self._regenerate_listbox_widget(
                    widget,
                    rows,
                    selected_values,
                    selected_indices,
                    top_index,
                    font,
                    font_name,
                    font_size,
                    color,
                )
            else:
                self._regenerate_choice_widget(
                    widget, combo_lines, font, font_name, font_size, color
                )

    def _regenerate_choice_widget(
        self,
        widget: PDAnnotationWidget,
        lines: list[str],
        font: PDFont,
        font_name: str | None,
        font_size: float,
        color: tuple[float, ...] | None,
    ) -> None:
        widget_cos = widget.get_cos_object()
        rect = _rect_from_cos(widget_cos.get_dictionary_object(_RECT))
        if rect is None:
            return
        llx, lly, urx, ury = rect
        width = urx - llx
        height = ury - lly
        if width <= 0.0 or height <= 0.0:
            return

        # Wave 1374 — apply /MK /R rotation.
        rotation = self._resolve_widget_rotation(widget_cos)
        if rotation in (90, 270):
            bbox_w, bbox_h = height, width
        else:
            bbox_w, bbox_h = width, height

        appearance_cos = self._fresh_form_xobject(bbox_w, bbox_h)
        appearance_stream = PDAppearanceStream(appearance_cos)
        if rotation != 0:
            appearance_stream.set_matrix(
                self._calculate_matrix(bbox_w, bbox_h, rotation)
            )
        if font_size > 0.0:
            resolved_size = font_size
        else:
            sample = lines[0] if lines else ""
            if sample:
                resolved_size = self._iterative_auto_size(
                    font, sample, max(0.0, width - 4.0), height
                )
            else:
                resolved_size = self._auto_size(height)

        with PDAppearanceContentStream(appearance_stream) as raw_cs:
            cs = cast(PDAppearanceContentStream, raw_cs)
            # Wave 1372 — preserve the /DA font alias (see text-field path).
            self._register_font_alias(cs, font, font_name)
            cs._buffer.extend(b"/Tx BMC\n")
            cs.save_graphics_state()
            interior_w = max(0.0, width - 2.0)
            interior_h = max(0.0, height - 2.0)
            if interior_w > 0.0 and interior_h > 0.0:
                cs.add_rect(1.0, 1.0, interior_w, interior_h)
                cs._write_operator(b"W")
                cs._write_operator(b"n")
            cs.begin_text()
            if color is not None:
                cs.set_non_stroking_color(color)
            cs.set_font(font, resolved_size)
            x = 2.0
            # Top-of-text baseline: position the first line near the top
            # of the widget so subsequent lines flow downward.
            top_y = max(2.0, height - resolved_size * 1.15)
            cs.new_line_at_offset(x, top_y)
            line_height = resolved_size * 1.15
            first = True
            for line in lines:
                if not first:
                    cs.new_line_at_offset(0.0, -line_height)
                first = False
                cs.show_text(line)
            cs.end_text()
            cs.restore_graphics_state()
            cs._buffer.extend(b"EMC\n")

        ap_value = widget_cos.get_dictionary_object(_AP)
        if isinstance(ap_value, COSDictionary):
            ap_dict = PDAppearanceDictionary(ap_value)
        else:
            ap_dict = PDAppearanceDictionary()
            widget_cos.set_item(_AP, ap_dict.get_cos_object())
        ap_dict.set_normal_appearance(appearance_stream)

    def _regenerate_listbox_widget(
        self,
        widget: PDAnnotationWidget,
        options: list[str],
        selected_values: list[str],
        selected_indices: list[int],
        top_index: int,
        font: PDFont,
        font_name: str | None,
        font_size: float,
        color: tuple[float, ...] | None,
    ) -> None:
        """Render a list-box appearance with selection highlight + scroll offset.

        Mirrors upstream ``insertGeneratedListboxAppearance``:

        - All option rows are drawn (not just the selected ones), starting
          from row index ``top_index`` (``/TI``) so callers controlling the
          scroll position get the same visible window as Acrobat.
        - Rows whose index appears in ``/I`` (or whose value appears in
          ``/V``) get a flat blue highlight rectangle drawn behind the
          row text — RGB ``(0.6, 0.75, 0.85)`` matches Acrobat's default
          listbox selection color.
        - Rows scroll downward from the top of the rect at one
          ``line_height`` per option; rows whose baseline falls below the
          rect are clipped by the standard ``/Tx BMC`` clip path.
        """
        widget_cos = widget.get_cos_object()
        rect = _rect_from_cos(widget_cos.get_dictionary_object(_RECT))
        if rect is None:
            return
        llx, lly, urx, ury = rect
        width = urx - llx
        height = ury - lly
        if width <= 0.0 or height <= 0.0:
            return

        # Wave 1374 — apply /MK /R rotation.
        rotation = self._resolve_widget_rotation(widget_cos)
        if rotation in (90, 270):
            bbox_w, bbox_h = height, width
        else:
            bbox_w, bbox_h = width, height

        appearance_cos = self._fresh_form_xobject(bbox_w, bbox_h)
        appearance_stream = PDAppearanceStream(appearance_cos)
        if rotation != 0:
            appearance_stream.set_matrix(
                self._calculate_matrix(bbox_w, bbox_h, rotation)
            )
        resolved_size = font_size if font_size > 0.0 else self._auto_size(height)
        line_height = resolved_size * 1.15

        # Resolve the highlighted-row index set: union of /I and any
        # option index whose value appears in /V.
        highlighted: set[int] = set(i for i in selected_indices if i >= 0)
        for sel in selected_values:
            for idx, opt in enumerate(options):
                if opt == sel:
                    highlighted.add(idx)

        with PDAppearanceContentStream(appearance_stream) as raw_cs:
            cs = cast(PDAppearanceContentStream, raw_cs)
            # Wave 1372 — preserve the /DA font alias (see text-field path).
            self._register_font_alias(cs, font, font_name)
            cs._buffer.extend(b"/Tx BMC\n")
            cs.save_graphics_state()
            interior_w = max(0.0, width - 2.0)
            interior_h = max(0.0, height - 2.0)
            if interior_w > 0.0 and interior_h > 0.0:
                cs.add_rect(1.0, 1.0, interior_w, interior_h)
                cs._write_operator(b"W")
                cs._write_operator(b"n")

            # Selection highlight rectangles — drawn before the text so
            # the glyphs paint on top.
            top_y = max(2.0, height - resolved_size * 1.15)
            visible_options = options[top_index:] if top_index < len(options) else []
            # Mirror upstream insertGeneratedListboxSelectionHighlight: a
            # highlight rect is emitted for EVERY selected option, positioned
            # by its row index relative to /TI. Options scrolled above the
            # window (index < top_index) land off the top of the rect and are
            # clipped by the /Tx clip path — upstream still writes the fill,
            # so the operator count must not be gated on the visible window.
            for option_idx in sorted(highlighted):
                visible_idx = option_idx - top_index
                row_y = top_y - visible_idx * line_height
                # Highlight rect spans the full interior width and one line.
                cs.set_non_stroking_color(self.HIGHLIGHT_COLOR)
                cs.add_rect(
                    1.0,
                    row_y - resolved_size * 0.15,
                    interior_w,
                    line_height,
                )
                cs.fill()

            # Row text. Highlighted rows render in white (so the
            # selection rectangle stays legible); other rows use the
            # /DA color (or default black). Color is set per row so the
            # selected/unselected switch happens inside the single BT/ET
            # block.
            default_color: tuple[float, ...] = color if color is not None else (0.0,)
            selected_color: tuple[float, ...] = (1.0, 1.0, 1.0)
            cs.begin_text()
            cs.set_non_stroking_color(default_color)
            cs.set_font(font, resolved_size)
            x = 2.0
            cs.new_line_at_offset(x, top_y)
            first = True
            current_is_selected = False
            for visible_idx, option in enumerate(visible_options):
                if not first:
                    cs.new_line_at_offset(0.0, -line_height)
                first = False
                option_idx = top_index + visible_idx
                row_selected = option_idx in highlighted
                if row_selected and not current_is_selected:
                    cs.set_non_stroking_color(selected_color)
                    current_is_selected = True
                elif not row_selected and current_is_selected:
                    cs.set_non_stroking_color(default_color)
                    current_is_selected = False
                cs.show_text(option)
            cs.end_text()
            cs.restore_graphics_state()
            cs._buffer.extend(b"EMC\n")

        ap_value = widget_cos.get_dictionary_object(_AP)
        if isinstance(ap_value, COSDictionary):
            ap_dict = PDAppearanceDictionary(ap_value)
        else:
            ap_dict = PDAppearanceDictionary()
            widget_cos.set_item(_AP, ap_dict.get_cos_object())
        ap_dict.set_normal_appearance(appearance_stream)

    # ------------------------------------------------------------------
    # widget-level regeneration (text)
    # ------------------------------------------------------------------

    def _regenerate_text_widget(
        self,
        widget: PDAnnotationWidget,
        value: str,
        font: PDFont,
        font_name: str | None,
        font_size: float,
        color: tuple[float, ...] | None,
        is_multiline: bool = False,
        is_comb: bool = False,
        max_len: int = -1,
        quadding: int = 0,
    ) -> None:
        widget_cos = widget.get_cos_object()
        rect = _rect_from_cos(widget_cos.get_dictionary_object(_RECT))
        if rect is None:
            # Mirror upstream AppearanceGeneratorHelper.setAppearanceContent
            # line 227: widgets without /Rect lose their /AP entry to behave
            # like Adobe Acrobat — no appearance stream can be drawn so the
            # stale /AP is removed rather than left to point at a bogus form
            # XObject.
            widget_cos.remove_item(_AP)
            _LOG.debug(
                "PDAppearanceGenerator: widget has no /Rect, removing /AP"
            )
            return
        llx, lly, urx, ury = rect
        width = urx - llx
        height = ury - lly
        if width <= 0.0 or height <= 0.0:
            _LOG.debug(
                "PDAppearanceGenerator: widget /Rect is degenerate "
                "(%s x %s), skipping",
                width,
                height,
            )
            return

        # Wave 1374 — apply /MK /R rotation to the appearance bbox + matrix.
        # 90/270 swap width and height so the rotated content fits.
        rotation = self._resolve_widget_rotation(widget_cos)
        if rotation in (90, 270):
            bbox_w, bbox_h = height, width
        else:
            bbox_w, bbox_h = width, height

        appearance_cos = self._fresh_form_xobject(bbox_w, bbox_h)
        appearance_stream = PDAppearanceStream(appearance_cos)
        if rotation != 0:
            appearance_stream.set_matrix(
                self._calculate_matrix(bbox_w, bbox_h, rotation)
            )

        # ``font_size = 0`` is the "auto-size" tag in the /DA spec — pick
        # a sane value clamped to widget height. Wave 1374 ports
        # upstream's iterative shrink-to-fit so long values actually
        # narrow to the rect width instead of overflowing the clip.
        resolved_size = font_size
        if resolved_size <= 0.0:
            # Use the post-rotation interior width when sizing so the
            # iterative shrink measures against the visible space.
            interior_w_for_size = max(0.0, width - 2.0)
            sample = value if value else ""
            if is_multiline or not sample:
                resolved_size = self._auto_size(height)
            else:
                resolved_size = self._iterative_auto_size(
                    font, sample, interior_w_for_size, height
                )

        interior_w = max(0.0, width - 2.0)
        interior_h = max(0.0, height - 2.0)
        line_height = resolved_size * 1.15

        with PDAppearanceContentStream(appearance_stream) as raw_cs:
            cs = cast(PDAppearanceContentStream, raw_cs)
            # Pre-register the font under the original /DA alias so the
            # emitted ``/<alias> <size> Tf`` token matches the source /DA
            # (upstream parity — wave 1372). When the alias is missing or
            # already taken by a different font object, fall back to the
            # auto-allocated ``F<n>`` key.
            self._register_font_alias(cs, font, font_name)
            # /Tx BMC marked-content tag — Acrobat looks for this on form
            # field appearance streams.
            cs._buffer.extend(b"/Tx BMC\n")
            cs.save_graphics_state()
            # Light interior clip (1pt margin all around) so the value
            # never bleeds over the widget border.
            if interior_w > 0.0 and interior_h > 0.0:
                cs.add_rect(1.0, 1.0, interior_w, interior_h)
                cs._write_operator(b"W")
                cs._write_operator(b"n")

            if is_comb and max_len > 0:
                self._emit_comb_text(
                    cs, value, font, resolved_size, color,
                    bbox_w, bbox_h, max_len, quadding,
                )
            elif is_multiline:
                self._emit_multiline_text(
                    cs, value, font, resolved_size, color,
                    interior_w, height, line_height, quadding,
                )
            else:
                self._emit_single_line_text(
                    cs, value, font, resolved_size, color,
                    interior_w, height, quadding,
                )

            cs.restore_graphics_state()
            cs._buffer.extend(b"EMC\n")

        # Wire the new appearance into the widget annotation as /AP /N.
        ap_value = widget_cos.get_dictionary_object(_AP)
        if isinstance(ap_value, COSDictionary):
            ap_dict = PDAppearanceDictionary(ap_value)
        else:
            ap_dict = PDAppearanceDictionary()
            widget_cos.set_item(_AP, ap_dict.get_cos_object())
        ap_dict.set_normal_appearance(appearance_stream)

    # ------------------------------------------------------------------
    # rich text (/RV — wave 1375)
    # ------------------------------------------------------------------

    def _regenerate_rich_text_widget(
        self,
        widget: PDAnnotationWidget,
        runs: list[_RichTextRun],
        base_font: PDFont,
        base_font_name: str | None,
        base_size: float,
        base_color: tuple[float, ...] | None,
    ) -> None:
        """Regenerate a text widget's ``/AP /N`` using styled rich-text runs.

        Wave 1375 closes the deferred ``/RV`` rendering note (CHANGES.md
        line 707) with the lite subset called out in the wave brief:
        ``<p>``, ``<br/>``, ``<b>`` / ``<i>``, ``<span style=...>``, and
        inline ``font-size`` / ``color`` / ``font-family`` overrides.
        """
        widget_cos = widget.get_cos_object()
        rect = _rect_from_cos(widget_cos.get_dictionary_object(_RECT))
        if rect is None:
            widget_cos.remove_item(_AP)
            return
        llx, lly, urx, ury = rect
        width = urx - llx
        height = ury - lly
        if width <= 0.0 or height <= 0.0:
            return

        rotation = self._resolve_widget_rotation(widget_cos)
        if rotation in (90, 270):
            bbox_w, bbox_h = height, width
        else:
            bbox_w, bbox_h = width, height

        appearance_cos = self._fresh_form_xobject(bbox_w, bbox_h)
        appearance_stream = PDAppearanceStream(appearance_cos)
        if rotation != 0:
            appearance_stream.set_matrix(
                self._calculate_matrix(bbox_w, bbox_h, rotation)
            )

        resolved_size = base_size if base_size > 0.0 else self._auto_size(height)
        interior_w = max(0.0, width - 2.0)
        interior_h = max(0.0, height - 2.0)

        with PDAppearanceContentStream(appearance_stream) as raw_cs:
            cs = cast(PDAppearanceContentStream, raw_cs)
            self._register_font_alias(cs, base_font, base_font_name)
            cs._buffer.extend(b"/Tx BMC\n")
            cs.save_graphics_state()
            if interior_w > 0.0 and interior_h > 0.0:
                cs.add_rect(1.0, 1.0, interior_w, interior_h)
                cs._write_operator(b"W")
                cs._write_operator(b"n")
            self._emit_rich_text_runs(
                cs,
                runs,
                base_font,
                base_font_name,
                resolved_size,
                base_color,
                interior_w,
                height,
            )
            cs.restore_graphics_state()
            cs._buffer.extend(b"EMC\n")

        ap_value2 = widget_cos.get_dictionary_object(_AP)
        if isinstance(ap_value2, COSDictionary):
            ap_dict2 = PDAppearanceDictionary(ap_value2)
        else:
            ap_dict2 = PDAppearanceDictionary()
            widget_cos.set_item(_AP, ap_dict2.get_cos_object())
        ap_dict2.set_normal_appearance(appearance_stream)

    def _emit_rich_text_runs(
        self,
        cs: PDAppearanceContentStream,
        runs: list[_RichTextRun],
        base_font: PDFont,
        base_font_name: str | None,
        base_size: float,
        base_color: tuple[float, ...] | None,
        interior_w: float,
        height: float,
    ) -> None:
        """Emit ``runs`` into ``cs`` as a sequence of text + path operations.

        Each run's bold/italic/font-family triple maps to a PDFont via
        :meth:`_resolve_rich_text_font`; ``color`` (when set) flushes a
        new non-stroking-color operator; ``font_size`` (when set)
        overrides the base size for the duration of the run.
        ``line_break`` runs emit ``T*`` (the PDF operator the brief
        calls out).

        Wave 1377 extensions:
            - ``text_rise`` non-zero emits the ``Ts`` operator (baseline
              offset for ``<sup>`` / ``<sub>``).
            - ``background_color`` set: end text, paint a filled rect
              under the run, resume text. The rect spans the run's
              measured advance width by ``size * 1.15`` (line height).
            - ``underline`` set: end text, draw a 1pt line below the
              baseline (at ``y - size * 0.1``), resume text.

        Pen position is tracked manually so background / underline rects
        line up with the glyph run.
        """
        default_color = base_color if base_color is not None else (0.0,)
        line_height = base_size * 1.15
        top_y = max(2.0, height - line_height)
        # Manual pen tracking. ``pen_x`` / ``pen_y`` mirror the text
        # matrix translation; we update them on every show_text /
        # line-break. Because PDF text mode forbids path operators
        # (re / f / S), we end+re-begin the text object whenever we
        # need to paint a background or stroke an underline.
        pen_x = 2.0
        pen_y = top_y
        line_start_x = 2.0

        current_font: PDFont = base_font
        current_font_cos = base_font.get_cos_object()
        current_size = base_size
        current_color = default_color
        current_text_rise = 0.0
        text_mode_open = False

        def _open_text_mode() -> None:
            nonlocal text_mode_open
            # Defensive: callers in this function always pair _close with
            # a subsequent _open, so text_mode_open should be False here.
            if text_mode_open:  # pragma: no cover - defensive: paired close/open
                return
            cs.begin_text()
            cs.set_non_stroking_color(current_color)
            cs.set_font(current_font, current_size)
            # We just emitted Tf; reset rise via Ts.
            if current_text_rise != 0.0:
                cs.set_text_rise(current_text_rise)
            cs._write_operands(line_height)
            cs._write_operator(b"TL")
            # Re-establish the text matrix at the current pen.
            cs.new_line_at_offset(pen_x, pen_y)
            text_mode_open = True

        def _close_text_mode() -> None:
            nonlocal text_mode_open
            # Defensive: callers only invoke _close after a paired _open.
            if not text_mode_open:  # pragma: no cover - defensive: paired close/open
                return
            cs.end_text()
            text_mode_open = False

        # Initial open: set up the baseline and the leading.
        cs.begin_text()
        cs.set_non_stroking_color(default_color)
        cs.set_font(base_font, base_size)
        cs.new_line_at_offset(2.0, top_y)
        # T* advances by the leading parameter -- drop a TL operator
        # so subsequent T* operators advance by ``line_height``.
        cs._write_operands(line_height)
        cs._write_operator(b"TL")
        text_mode_open = True

        for run in runs:
            if run.line_break:
                pen_y = pen_y - line_height
                pen_x = 2.0
                line_start_x = 2.0
                if text_mode_open:
                    cs.new_line()
                else:  # pragma: no cover - defensive: bg/underline branches re-open
                    # Path mode left us outside BT/ET. _open_text_mode
                    # will re-establish the text matrix at (pen_x, pen_y)
                    # on the next text-emitting run.
                    pass
                continue
            if not run.text:  # pragma: no cover - _parse_rv_runs collapses empty runs
                continue
            run_font = self._resolve_rich_text_font(
                base_font, base_font_name, run,
            )
            run_size = run.font_size if run.font_size is not None else base_size
            run_color = run.color if run.color is not None else default_color
            run_rise = run.text_rise
            font_cos = run_font.get_cos_object()
            # Measure the run's advance ahead of state changes -- needed
            # for background rect + underline regardless of which mode
            # we're in.
            advance = self._estimate_text_width(run_font, run_size, run.text)

            # ---- background-color (paint before glyphs) ----
            if run.background_color is not None:
                _close_text_mode()
                cs.save_graphics_state()
                cs.set_non_stroking_color(run.background_color)
                # Use the active run size for the rect height -- not the
                # base size -- so backgrounds behind super/sub runs are
                # also scaled.
                rect_h = run_size * 1.15
                # y baseline is pen_y, the rect should cover from the
                # baseline descender (~-0.2em) upward by line height.
                cs.add_rect(
                    pen_x,
                    pen_y - run_size * 0.2,
                    advance,
                    rect_h,
                )
                cs.fill()
                cs.restore_graphics_state()
                # Re-open text mode at the saved pen.
                _open_text_mode()

            # ---- text state ----
            if not text_mode_open:  # pragma: no cover - bg/underline branches re-open
                _open_text_mode()
            if font_cos is not current_font_cos or run_size != current_size:
                cs.set_font(run_font, run_size)
                current_font = run_font
                current_font_cos = font_cos
                current_size = run_size
            if run_color != current_color:
                cs.set_non_stroking_color(run_color)
                current_color = run_color
            if run_rise != current_text_rise:
                cs.set_text_rise(run_rise)
                current_text_rise = run_rise
            cs.show_text(run.text)

            # ---- underline (stroke after glyphs) ----
            if run.underline:
                _close_text_mode()
                cs.save_graphics_state()
                # Underline colour = run colour.
                cs.set_stroking_color(run_color)
                # 1pt line for typical body text; clamp to avoid the
                # 0-width hairline for tiny sub/sup runs.
                cs.set_line_width(max(0.5, run_size * 0.05))
                under_y = pen_y - run_size * 0.1
                cs.move_to(pen_x, under_y)
                cs.line_to(pen_x + advance, under_y)
                cs.stroke()
                cs.restore_graphics_state()
                _open_text_mode()

            pen_x = pen_x + advance
            # Track line_start_x for the next break (kept as a sentinel
            # for future width-based break logic; unused right now).
            _ = line_start_x

        if text_mode_open:  # pragma: no branch - bg/underline paths always re-open before EOL
            cs.end_text()

    def _resolve_rich_text_font(
        self,
        base_font: PDFont,
        base_font_name: str | None,
        run: _RichTextRun,
    ) -> PDFont:
        """Pick a Standard 14 font for ``run``'s bold/italic/family combo."""
        family_key = (run.font_family or "").strip().lower()
        if "times" in family_key:
            family_name: str | None = "Times"
        elif "courier" in family_key or "monospace" in family_key:
            family_name = "Courier"
        elif "helvetica" in family_key or "sans" in family_key:
            family_name = "Helvetica"
        elif family_key:
            family_name = None
        else:
            family_name = None
        if family_name is None and not run.bold and not run.italic:
            return base_font
        if family_name is None:
            inferred = self._infer_font_family(base_font, base_font_name)
            family_name = inferred or "Helvetica"
        variant = self._font_variant_name(family_name, run.bold, run.italic)
        if variant is None:
            return base_font
        if Standard14Fonts.get_mapped_font_name(variant) is None:
            return base_font
        return PDFontFactory.create_default_font(variant)

    @staticmethod
    def _infer_font_family(
        base_font: PDFont, base_font_name: str | None,
    ) -> str | None:
        """Return ``Helvetica`` / ``Times`` / ``Courier`` for the base font.

        Used when a rich-text run carries ``<b>`` / ``<i>`` but no
        ``font-family`` override -- we keep the base /DA family and just
        swap the weight / style. Returns ``None`` when the base font is
        not a recognised Standard 14 family.
        """
        candidate = ""
        if base_font_name:
            mapped = PDAppearanceGenerator.DA_FONT_ALIASES.get(
                base_font_name, base_font_name
            )
            candidate = mapped
        if not candidate:
            getter = getattr(base_font, "get_name", None)
            if callable(getter):
                with suppress(Exception):
                    name_val = getter()
                    if isinstance(name_val, str):
                        candidate = name_val
        candidate = candidate.lower()
        if "times" in candidate:
            return "Times"
        if "courier" in candidate:
            return "Courier"
        if "helvetica" in candidate:
            return "Helvetica"
        return None

    @staticmethod
    def _font_variant_name(family: str, bold: bool, italic: bool) -> str | None:
        """Map a family + bold/italic combo to a Standard 14 font name."""
        family = family.lower()
        if family == "helvetica":
            if bold and italic:
                return Standard14Fonts.HELVETICA_BOLD_OBLIQUE
            if bold:
                return Standard14Fonts.HELVETICA_BOLD
            if italic:
                return Standard14Fonts.HELVETICA_OBLIQUE
            return Standard14Fonts.HELVETICA
        if family == "times":
            if bold and italic:
                return "Times-BoldItalic"
            if bold:
                return "Times-Bold"
            if italic:
                return "Times-Italic"
            return "Times-Roman"
        if family == "courier":
            if bold and italic:
                return "Courier-BoldOblique"
            if bold:
                return "Courier-Bold"
            if italic:
                return "Courier-Oblique"
            return "Courier"
        return None

    def _emit_single_line_text(
        self,
        cs: PDAppearanceContentStream,
        value: str,
        font: PDFont,
        size: float,
        color: tuple[float, ...] | None,
        interior_w: float,
        height: float,
        quadding: int,
    ) -> None:
        cs.begin_text()
        if color is not None:
            cs.set_non_stroking_color(color)
        cs.set_font(font, size)
        x = self._x_for_quadding(font, size, value, interior_w, quadding)
        y = max(2.0, (height - size) / 2.0)
        cs.new_line_at_offset(x, y)
        if value:
            cs.show_text(value)
        cs.end_text()

    def _emit_multiline_text(
        self,
        cs: PDAppearanceContentStream,
        value: str,
        font: PDFont,
        size: float,
        color: tuple[float, ...] | None,
        interior_w: float,
        height: float,
        line_height: float,
        quadding: int,
    ) -> None:
        lines = self._wrap_lines(value, font, size, max(interior_w, 1.0))
        cs.begin_text()
        if color is not None:
            cs.set_non_stroking_color(color)
        cs.set_font(font, size)
        # First baseline near the top of the rect; subsequent lines
        # advance downward by ``line_height``.
        top_y = max(2.0, height - size * 1.15)
        first_x = self._x_for_quadding(
            font, size, lines[0] if lines else "", interior_w, quadding
        )
        cs.new_line_at_offset(first_x, top_y)
        first = True
        prev_x = first_x
        for line in lines:
            line_x = self._x_for_quadding(
                font, size, line, interior_w, quadding
            )
            if not first:
                # Td is relative to start-of-line — undo the previous
                # quadding offset so the new x lands at ``line_x``.
                cs.new_line_at_offset(line_x - prev_x, -line_height)
            first = False
            prev_x = line_x
            if line:
                cs.show_text(line)
        cs.end_text()

    def _emit_comb_text(
        self,
        cs: PDAppearanceContentStream,
        value: str,
        font: PDFont,
        size: float,
        color: tuple[float, ...] | None,
        width: float,
        height: float,
        max_len: int,
        quadding: int = 0,
    ) -> None:
        # Comb mode: PDF 32000-1 §12.7.3.3 — the field's value is split
        # into one-character-per-cell entries, each centered horizontally
        # within a 1/MaxLen wide cell. This mirrors upstream
        # AppearanceGeneratorHelper.insertGeneratedCombAppearance exactly:
        # the per-cell offsets are emitted with an incremental
        # ``xOffset = xOffset + prevCharWidth/2 - currCharWidth/2`` scheme
        # (note the ``fontSize/2`` half-width on currCharWidth), the
        # baseline is ascent-centred, and ``/Q`` shifts the run for a value
        # shorter than ``/MaxLen``.
        if not value:
            return
        num_chars = min(len(value), max_len)
        comb_width = width / float(max_len)

        descriptor = font.get_font_descriptor()
        ascent = descriptor.get_ascent() if descriptor is not None else 0.0
        ascent_at_font_size = ascent / self.FONTSCALE * size
        # The appearance bbox lower-left y is 0 for the fresh form XObject.
        baseline_offset = (height - ascent_at_font_size) / 2.0

        # Initial offset centres the first char in its cell.
        first_char_width = (
            font.get_string_width(value[0:1]) / self.FONTSCALE * size
        )
        initial_offset = (comb_width - first_char_width) / 2.0
        # Right-aligned / centred shift when the value is shorter than MaxLen.
        if quadding == 2:
            initial_offset += (max_len - num_chars) * comb_width
        elif quadding == 1:
            initial_offset += ((max_len - num_chars) // 2) * comb_width

        x_offset = initial_offset
        prev_char_width = 0.0

        cs.begin_text()
        if color is not None:
            cs.set_non_stroking_color(color)
        cs.set_font(font, size)
        for i in range(num_chars):
            comb_string = value[i : i + 1]
            curr_char_width = (
                font.get_string_width(comb_string) / self.FONTSCALE * size / 2.0
            )
            x_offset = x_offset + prev_char_width / 2.0 - curr_char_width / 2.0
            if i == 0:
                cs.new_line_at_offset(initial_offset, baseline_offset)
            else:
                cs.new_line_at_offset(x_offset, baseline_offset)
            cs.show_text(comb_string)
            baseline_offset = 0.0
            prev_char_width = curr_char_width
            x_offset = comb_width
        cs.end_text()

    def _x_for_quadding(
        self,
        font: PDFont,
        size: float,
        line: str,
        interior_w: float,
        quadding: int,
    ) -> float:
        """Pick the leftmost x-offset for ``line`` per ``/Q`` quadding.

        Quadding values per PDF 32000-1 §12.7.3.3:
        ``0`` = left, ``1`` = centered, ``2`` = right. Anything else
        falls back to left.
        """
        if quadding == 1 or quadding == 2:
            text_w = self._estimate_text_width(font, size, line)
            available = max(0.0, interior_w - text_w)
            if quadding == 1:
                return 2.0 + available / 2.0
            return 2.0 + available
        return 2.0

    def _wrap_lines(
        self,
        value: str,
        font: PDFont,
        size: float,
        interior_w: float,
    ) -> list[str]:
        """Word-wrap ``value`` onto lines that fit ``interior_w``.

        Delegates to :class:`PlainText` + :class:`Paragraph.get_lines`,
        the same engine upstream's ``AppearanceGeneratorHelper`` uses
        (via ``PlainTextFormatter``). That gives us real per-glyph
        widths via ``PDFont.get_string_width`` and the PDFBOX-5049 /
        PDFBOX-6082 force-split fallback for unbroken words wider than
        the rect (e.g. a long unbroken digit run wrapping to the same
        line shape Acrobat produces — see ``testMultilineBreak``,
        PDFBOX-3835).
        """
        from .plain_text import PlainText

        if not value:
            return [""]
        block = PlainText(value)
        out: list[str] = []
        for paragraph in block.get_paragraphs():
            try:
                lines = paragraph.get_lines(font, size, max(interior_w, 1.0))
            except (OSError, ValueError, KeyError, TypeError):
                # Font lookup / glyph-width resolution can raise OSError
                # (stream IO) or a key error for missing glyphs; fall
                # back to a single-line render rather than crash.
                lines = []
            if not lines:
                # ``Paragraph.get_lines`` returns ``[]`` for ``width <= 0``;
                # preserve the paragraph as a single line in that case.
                out.append(paragraph.get_text())
                continue
            for line in lines:
                out.append("".join(word.get_text() for word in line.get_words()))
        return out

    @staticmethod
    def _estimate_text_width(font: PDFont, size: float, text: str) -> float:
        """Estimate ``text`` width in user units at the given ``size``.

        Lite-port estimate: average-font-width per glyph (in 1/1000 em
        units) times the character count, scaled by ``size / 1000``.
        Falls back to ``size * 0.5`` when the font carries no widths
        (Standard 14 fonts without an explicit ``/Widths``).
        """
        if not text:
            return 0.0
        avg = font.get_average_font_width()
        if avg <= 0.0:
            avg = 500.0  # 0.5 em — plausible for Helvetica-style fonts
        return len(text) * avg * size / 1000.0

    # ------------------------------------------------------------------
    # push button (caption from /MK /CA)
    # ------------------------------------------------------------------

    def _generate_push_button(self, field: PDPushButton) -> None:
        """Render the widget's ``/MK /CA`` caption flat-centered.

        For each widget:

        - If ``/MK /BG`` is set, fill the rect with the background color.
        - If ``/MK /BC`` is set, stroke a 1pt rectangular border.
        - Render ``/MK /CA`` (if present) as Helvetica text, font size
          auto-sized to the rect height, centered horizontally and
          vertically.

        **Wave 1377 closes the wave-1374 deferred note**: rollover
        (``/MK /RC``) and alternate / down (``/MK /AC``) captions now
        emit ``/AP /R`` and ``/AP /D`` appearance streams alongside the
        ``/N`` normal stream. The rollover stream uses a lightened
        ``/MK /BG`` (Acrobat-style hover affordance); the down stream
        uses a darkened ``/MK /BG`` (pressed-button affordance). Both
        reuse the ``/MK /BC`` border colour and the widget's ``/MK /R``
        rotation. When ``/RC`` / ``/AC`` are absent **and** no ``/MK
        /BG`` is set the variant carries no visual signal, so the
        generator skips emitting it (PDF readers fall back to ``/N``
        per PDF 32000 §12.5.5).
        """
        for widget in field.get_widgets():
            self._regenerate_push_button_widget(widget)
            self._regenerate_push_button_rollover(widget)
            self._regenerate_push_button_down(widget)

    # Brightness deltas applied to /MK /BG for the rollover (hover) and
    # down (clicked) push-button variants. Mirrors Acrobat / Reader's
    # visual convention of a slightly lighter hover surface and a
    # slightly darker pressed surface so a viewer that honours /R and
    # /D immediately reads "interactive". Tuned to 0.10 so a typical
    # light-grey button (0.85, 0.85, 0.85) lands at (0.95, 0.95, 0.95)
    # on rollover and (0.75, 0.75, 0.75) on down — enough contrast to
    # register but not enough to invert the colour.
    _PUSH_BUTTON_ROLLOVER_DELTA: float = 0.10
    _PUSH_BUTTON_DOWN_DELTA: float = -0.10

    @staticmethod
    def _adjust_color_brightness(
        color: tuple[float, ...] | None, delta: float
    ) -> tuple[float, ...] | None:
        """Lighten (``delta > 0``) or darken (``delta < 0``) a ``/MK``
        colour tuple by adding ``delta`` to each component and clamping
        to ``[0.0, 1.0]``. ``None`` round-trips to ``None`` so callers
        treat "no background" as "no variant tint"."""
        if color is None:
            return None
        return tuple(max(0.0, min(1.0, c + delta)) for c in color)

    def _extract_push_button_mk(
        self, widget_cos: COSDictionary
    ) -> tuple[str, str, str, tuple[float, ...] | None, tuple[float, ...] | None]:
        """Pull ``(/CA, /RC, /AC, /BG, /BC)`` off a widget's ``/MK``.

        Captions default to the empty string when absent (the empty
        string is a sentinel for "no caption to render"). Colours
        default to ``None`` when absent or non-numeric.
        """
        caption = ""
        rollover_caption = ""
        alternate_caption = ""
        bg: tuple[float, ...] | None = None
        bc: tuple[float, ...] | None = None
        mk = widget_cos.get_dictionary_object(_MK)
        if isinstance(mk, COSDictionary):
            ca = mk.get_string(COSName.get_pdf_name("CA"))
            if isinstance(ca, str):
                caption = ca
            rc = mk.get_string(COSName.get_pdf_name("RC"))
            if isinstance(rc, str):
                rollover_caption = rc
            ac = mk.get_string(COSName.get_pdf_name("AC"))
            if isinstance(ac, str):
                alternate_caption = ac
            bg = self._color_array_to_tuple(
                mk.get_dictionary_object(COSName.get_pdf_name("BG"))
            )
            bc = self._color_array_to_tuple(
                mk.get_dictionary_object(COSName.get_pdf_name("BC"))
            )
        return caption, rollover_caption, alternate_caption, bg, bc

    def _build_push_button_appearance(
        self,
        widget_cos: COSDictionary,
        caption: str,
        bg: tuple[float, ...] | None,
        bc: tuple[float, ...] | None,
    ) -> PDAppearanceStream | None:
        """Build a single push-button appearance stream for ``caption``.

        Returns ``None`` when the widget rect is missing or degenerate.
        Shared by the ``/N``, ``/R`` and ``/D`` variants — caller
        decides which caption + background to feed in. Honours ``/MK
        /R`` rotation (matrix + bbox swap) and iterative shrink-to-fit
        auto-sizing exactly like the wave-1374 ``/N`` path.
        """
        rect = _rect_from_cos(widget_cos.get_dictionary_object(_RECT))
        if rect is None:
            return None
        llx, lly, urx, ury = rect
        width = urx - llx
        height = ury - lly
        if width <= 0.0 or height <= 0.0:
            return None

        # Wave 1374 — honor /MK /R rotation.
        rotation = self._resolve_widget_rotation(widget_cos)
        if rotation in (90, 270):
            bbox_w, bbox_h = height, width
        else:
            bbox_w, bbox_h = width, height

        appearance_cos = self._fresh_form_xobject(bbox_w, bbox_h)
        appearance_stream = PDAppearanceStream(appearance_cos)
        if rotation != 0:
            appearance_stream.set_matrix(
                self._calculate_matrix(bbox_w, bbox_h, rotation)
            )
        font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
        # Wave 1374 — iterative shrink-to-fit replaces the height clamp.
        if caption:
            size = self._iterative_auto_size(
                font, caption, max(0.0, width - 4.0), height
            )
        else:
            size = self._auto_size(height)

        with PDAppearanceContentStream(appearance_stream) as raw_cs:
            cs = cast(PDAppearanceContentStream, raw_cs)
            cs.save_graphics_state()
            # Background fill.
            if bg is not None:
                cs.set_non_stroking_color(bg)
                cs.add_rect(0.0, 0.0, width, height)
                cs.fill()
            # Border stroke (1pt inset by 0.5 so the stroke sits inside).
            if bc is not None:
                cs.set_stroking_color(bc)
                cs.set_line_width(1.0)
                cs.add_rect(0.5, 0.5, max(0.0, width - 1.0), max(0.0, height - 1.0))
                cs.stroke()
            # Caption.
            if caption:
                cs.begin_text()
                cs.set_non_stroking_color((0.0,))
                cs.set_font(font, size)
                text_w = self._estimate_text_width(font, size, caption)
                x = max(2.0, (width - text_w) / 2.0)
                y = max(2.0, (height - size) / 2.0)
                cs.new_line_at_offset(x, y)
                cs.show_text(caption)
                cs.end_text()
            cs.restore_graphics_state()
        return appearance_stream

    @staticmethod
    def _ensure_ap_dict(widget_cos: COSDictionary) -> PDAppearanceDictionary:
        """Get or create the widget's ``/AP`` dictionary."""
        ap_value = widget_cos.get_dictionary_object(_AP)
        if isinstance(ap_value, COSDictionary):
            return PDAppearanceDictionary(ap_value)
        ap_dict = PDAppearanceDictionary()
        widget_cos.set_item(_AP, ap_dict.get_cos_object())
        return ap_dict

    def _regenerate_push_button_widget(self, widget: PDAnnotationWidget) -> None:
        widget_cos = widget.get_cos_object()
        caption, _rc, _ac, bg, bc = self._extract_push_button_mk(widget_cos)
        appearance_stream = self._build_push_button_appearance(
            widget_cos, caption, bg, bc
        )
        if appearance_stream is None:
            return
        ap_dict = self._ensure_ap_dict(widget_cos)
        ap_dict.set_normal_appearance(appearance_stream)

    def _regenerate_push_button_rollover(
        self, widget: PDAnnotationWidget
    ) -> None:
        """Emit the ``/AP /R`` rollover appearance stream (Wave 1377).

        Pulls the rollover caption from ``/MK /RC`` (falling back to
        ``/CA`` when ``/RC`` is the empty string) and tints ``/MK /BG``
        lighter by :attr:`_PUSH_BUTTON_ROLLOVER_DELTA`. When the widget
        has neither a distinguishing rollover caption nor a background
        colour to tint, the rollover state carries no visual signal,
        so the method returns without writing ``/AP /R`` (viewers fall
        back to ``/N`` per PDF 32000 §12.5.5).
        """
        widget_cos = widget.get_cos_object()
        caption, rollover_caption, _ac, bg, bc = self._extract_push_button_mk(
            widget_cos
        )
        # No distinguishing rollover signal -> skip the entry entirely.
        if not rollover_caption and bg is None:
            return
        effective_caption = rollover_caption if rollover_caption else caption
        effective_bg = self._adjust_color_brightness(
            bg, self._PUSH_BUTTON_ROLLOVER_DELTA
        )
        appearance_stream = self._build_push_button_appearance(
            widget_cos, effective_caption, effective_bg, bc
        )
        if appearance_stream is None:
            return
        ap_dict = self._ensure_ap_dict(widget_cos)
        ap_dict.set_rollover_appearance(appearance_stream)

    def _regenerate_push_button_down(self, widget: PDAnnotationWidget) -> None:
        """Emit the ``/AP /D`` down (clicked) appearance stream (Wave 1377).

        Pulls the down caption from ``/MK /AC`` (falling back to ``/CA``
        when ``/AC`` is the empty string) and tints ``/MK /BG`` darker
        by :attr:`_PUSH_BUTTON_DOWN_DELTA`. When the widget has neither
        a distinguishing down caption nor a background colour to tint,
        the down state carries no visual signal, so the method returns
        without writing ``/AP /D``.
        """
        widget_cos = widget.get_cos_object()
        caption, _rc, alternate_caption, bg, bc = self._extract_push_button_mk(
            widget_cos
        )
        if not alternate_caption and bg is None:
            return
        effective_caption = alternate_caption if alternate_caption else caption
        effective_bg = self._adjust_color_brightness(
            bg, self._PUSH_BUTTON_DOWN_DELTA
        )
        appearance_stream = self._build_push_button_appearance(
            widget_cos, effective_caption, effective_bg, bc
        )
        if appearance_stream is None:
            return
        ap_dict = self._ensure_ap_dict(widget_cos)
        ap_dict.set_down_appearance(appearance_stream)

    @staticmethod
    def _color_array_to_tuple(value: COSBase | None) -> tuple[float, ...] | None:
        """Pull a ``/MK`` color array (1, 3, or 4 numeric entries) into
        a non-stroking-color components tuple. Returns ``None`` for
        empty / non-numeric arrays."""
        if not isinstance(value, COSArray):
            return None
        comps: list[float] = []
        for i in range(value.size()):
            entry = value.get_object(i)
            if isinstance(entry, (COSFloat, COSInteger)):
                comps.append(float(entry.value))
            else:
                return None
        if len(comps) in (1, 3, 4):
            return tuple(comps)
        return None

    # ------------------------------------------------------------------
    # signature field
    # ------------------------------------------------------------------

    def _generate_signature(self, field: PDSignatureField) -> None:
        """Render a flat name + date appearance for a signature field.

        Pulls ``/Name`` and ``/M`` (sign date) off the field's
        ``PDSignature`` ``/V`` value and writes them on two
        Helvetica-10 lines inside the widget rect. A 1pt border is
        stroked around the rect so unsigned-but-rendered widgets are
        still visible. Sigfields without a signature value get an
        empty stream (matches PDFBox's behavior of leaving an empty
        appearance until the field is signed).
        """
        signature = field.get_signature()
        signer_name = signature.get_name() if signature is not None else None
        sign_date = signature.get_sign_date() if signature is not None else None

        for widget in field.get_widgets():
            self._regenerate_signature_widget(widget, signer_name, sign_date)

    # Default placeholder caption rendered for unsigned signature
    # widgets. Mirrors the prompt shown by Acrobat's visible-signature
    # builder (``PDVisibleSigBuilder``) for an empty sigfield — "Click to
    # sign" reads as an actionable prompt instead of the static
    # "Sign here" label the lite port shipped before wave 1374.
    UNSIGNED_PLACEHOLDER: str = "Click to sign"

    def _regenerate_signature_widget(
        self,
        widget: PDAnnotationWidget,
        signer_name: str | None,
        sign_date: str | None,
    ) -> None:
        widget_cos = widget.get_cos_object()
        rect = _rect_from_cos(widget_cos.get_dictionary_object(_RECT))
        if rect is None:
            return
        llx, lly, urx, ury = rect
        width = urx - llx
        height = ury - lly
        if width <= 0.0 or height <= 0.0:
            return

        # Wave 1374 — honor widget rotation when generating sig appearance,
        # mirroring the upstream ``prepareNormalAppearanceStream`` swap.
        rotation = self._resolve_widget_rotation(widget_cos)
        if rotation in (90, 270):
            bbox_width, bbox_height = height, width
        else:
            bbox_width, bbox_height = width, height

        # /MK /BC + /MK /BG colors — wave 1374 closes the upstream
        # ``PDVisibleSigBuilder`` background/border parity gap for unsigned
        # widgets.
        bg: tuple[float, ...] | None = None
        bc: tuple[float, ...] | None = None
        mk = widget_cos.get_dictionary_object(_MK)
        if isinstance(mk, COSDictionary):
            bg = self._color_array_to_tuple(
                mk.get_dictionary_object(COSName.get_pdf_name("BG"))
            )
            bc = self._color_array_to_tuple(
                mk.get_dictionary_object(COSName.get_pdf_name("BC"))
            )

        appearance_cos = self._fresh_form_xobject(bbox_width, bbox_height)
        appearance_stream = PDAppearanceStream(appearance_cos)
        if rotation != 0:
            appearance_stream.set_matrix(
                self._calculate_matrix(bbox_width, bbox_height, rotation)
            )
        font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
        size = 10.0
        is_signed = bool(signer_name or sign_date)

        with PDAppearanceContentStream(appearance_stream) as raw_cs:
            cs = cast(PDAppearanceContentStream, raw_cs)
            cs.save_graphics_state()
            # /MK /BG fill — drawn first so the border + caption paint on top.
            if bg is not None:
                cs.set_non_stroking_color(bg)
                cs.add_rect(0.0, 0.0, width, height)
                cs.fill()
            # Frame the signature box with a thin border. Unsigned widgets
            # use a dashed outline so reviewers visually distinguish them
            # from signed-and-rendered widgets. /MK /BC overrides the
            # default black stroke.
            border_color: tuple[float, ...] = bc if bc is not None else (0.0,)
            cs.set_stroking_color(border_color)
            cs._buffer.extend(b"1 w\n")
            if not is_signed:
                # 3-on / 3-off dashed line — Acrobat default for empty sigs.
                cs._buffer.extend(b"[3 3] 0 d\n")
            cs.add_rect(0.5, 0.5, max(0.0, width - 1.0), max(0.0, height - 1.0))
            cs.stroke()
            if not is_signed:
                # Reset the dash pattern so subsequent drawing inside the
                # appearance isn't unintentionally dashed.
                cs._buffer.extend(b"[] 0 d\n")

            if is_signed:
                cs.begin_text()
                cs.set_non_stroking_color((0.0,))
                cs.set_font(font, size)
                # Two-line layout: top line = signer name, bottom line = date.
                line_height = size * 1.4
                top_y = max(2.0, height - size * 1.4)
                cs.new_line_at_offset(4.0, top_y)
                cs.show_text(signer_name or "")
                cs.new_line_at_offset(0.0, -line_height)
                cs.show_text(sign_date or "")
                cs.end_text()
            else:
                # Unsigned placeholder — 50% gray "Click to sign" centered
                # in the box (wave 1374 — Acrobat visible-sig builder prompt).
                placeholder_size = self._iterative_auto_size(
                    font,
                    self.UNSIGNED_PLACEHOLDER,
                    max(0.0, width - 4.0),
                    height,
                )
                placeholder = self.UNSIGNED_PLACEHOLDER
                text_w = self._estimate_text_width(
                    font, placeholder_size, placeholder
                )
                x = max(2.0, (width - text_w) / 2.0)
                y = max(2.0, (height - placeholder_size) / 2.0)
                cs.begin_text()
                cs.set_non_stroking_color((0.5,))
                cs.set_font(font, placeholder_size)
                cs.new_line_at_offset(x, y)
                cs.show_text(placeholder)
                cs.end_text()

            cs.restore_graphics_state()

        ap_value = widget_cos.get_dictionary_object(_AP)
        if isinstance(ap_value, COSDictionary):
            ap_dict = PDAppearanceDictionary(ap_value)
        else:
            ap_dict = PDAppearanceDictionary()
            widget_cos.set_item(_AP, ap_dict.get_cos_object())
        ap_dict.set_normal_appearance(appearance_stream)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _resolve_default_appearance(self, field: PDField) -> str | None:
        """Pull the field's ``/DA`` (with inheritable walk) or fall back
        to the explicit override passed to the generator constructor."""
        da: str | None = None
        getter = getattr(field, "get_default_appearance", None)
        if callable(getter):
            try:
                da = getter()
            except Exception:  # noqa: BLE001 — defensive on lite-port surface
                da = None
        if not da:
            da = self._default_appearance_override
        return da

    @staticmethod
    def _fresh_form_xobject(width: float, height: float) -> COSStream:
        """Build a fresh form-XObject COSStream sized to ``width x height``."""
        appearance_cos = COSStream()
        appearance_cos.set_item(_TYPE, _XOBJECT)
        appearance_cos.set_item(_SUBTYPE, _FORM)
        appearance_cos.set_int(_FORM_TYPE, 1)
        bbox = COSArray(
            [
                COSFloat(0.0),
                COSFloat(0.0),
                COSFloat(width),
                COSFloat(height),
            ]
        )
        appearance_cos.set_item(_BBOX, bbox)
        return appearance_cos

    @classmethod
    def _resolve_font(cls, font_name: str | None) -> PDFont:
        """Return a :class:`PDFont` for ``font_name`` without walking the
        form's ``/DR`` resources.

        The /DA font key is a /Resources/Font dict alias (e.g. ``Helv``).
        Without access to the AcroForm, the alias is mapped through
        :attr:`DA_FONT_ALIASES` (``Helv`` -> Helvetica, ``HeBo`` ->
        Helvetica-Bold, ``TiRo`` -> Times-Roman, ``CoRo`` -> Courier,
        ``ZaDb`` -> ZapfDingbats, etc.) with Helvetica as a final
        fallback. Use :meth:`_resolve_font_for_field` when a field is
        available — that path also consults the form's ``/DR /Font``
        dictionary so embedded /DA fonts are preserved (wave 1372).
        """
        if font_name:
            mapped = cls.DA_FONT_ALIASES.get(font_name, font_name)
            if Standard14Fonts.get_mapped_font_name(mapped) is not None:
                return PDFontFactory.create_default_font(mapped)
        return PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)

    def _resolve_font_for_field(
        self,
        field: PDField,
        font_name: str | None,
        widget: PDAnnotationWidget | None = None,
    ) -> PDFont:
        """Resolve ``font_name`` to a :class:`PDFont`, walking the form's
        ``/DR /Font`` dictionary first so embedded /DA fonts survive
        appearance regeneration. Falls back to the alias-mapped Standard
        14 font when the lookups are empty or non-resolvable.

        When ``widget`` is supplied (the per-widget call site introduced
        in wave 1375 to close the "custom-embedded /DA fonts not honoured"
        deviation), the resolver walks three locations in order:

        1. The form's ``/DR /Font`` dictionary (Acrobat / Reader's default
           bucket for ``/DA`` aliases like ``Helv``).
        2. The widget's ``/AP /N /Resources /Font`` (per-widget resources
           — Acrobat sometimes hoists per-widget fonts here when a single
           field's widgets carry differing layouts).
        3. The widget's parent page ``/Resources /Font`` (rare but legal
           — some authoring tools register form fonts at the page level).

        First hit wins. Falls back to the Standard 14 alias-mapped font
        when none of the three buckets resolves the name. Mirrors the
        upstream ``PDDefaultAppearanceString`` chain (parse ``/DA`` ->
        resolve through ``/DR``) plus the widget-level hoist from
        ``AppearanceGeneratorHelper.validateAndEnsureAcroFormResources``
        in spirit.
        """
        if font_name:
            key = COSName.get_pdf_name(font_name)
            # 1) AcroForm /DR /Font — canonical location for /DA fonts.
            try:
                acro_form = field.get_acro_form()
            except Exception:  # noqa: BLE001 — defensive on lite-port surface
                acro_form = None
            if acro_form is not None:
                dr = acro_form.get_default_resources()
                if dr is not None:
                    font = self._coerce_to_pd_font(dr.get_font(key))
                    if font is not None:
                        return font
            # 2) Widget /AP /N /Resources /Font — per-widget override.
            if widget is not None:
                font = self._lookup_font_in_widget_appearance(widget, key)
                if font is not None:
                    return font
                # 3) Page /Resources /Font — last legal location to look.
                font = self._lookup_font_in_widget_page(widget, key)
                if font is not None:
                    return font
        return self._resolve_font(font_name)

    @staticmethod
    def _coerce_to_pd_font(entry: object | None) -> PDFont | None:
        """Coerce a :meth:`PDResources.get_font` return into a :class:`PDFont`.

        ``PDResources.get_font`` now always returns a typed :class:`PDFont`
        (or ``None``), matching upstream — direct and indirect entries alike
        are wrapped via ``PDFontFactory``. A raw :class:`COSDictionary` is
        still tolerated here defensively in case a caller hands one in
        directly.
        """
        if isinstance(entry, PDFont):
            return entry
        if isinstance(entry, COSDictionary):
            return PDFontFactory.create_font(entry)
        return None

    @staticmethod
    def _lookup_font_in_widget_appearance(
        widget: PDAnnotationWidget, key: COSName
    ) -> PDFont | None:
        """Walk ``widget``'s ``/AP /N /Resources /Font`` for ``key``.

        Returns the typed :class:`PDFont` instance when present, ``None``
        otherwise. ``/AP /N`` may be a single stream (single-state widgets
        like text fields) or a dictionary keyed by state name (buttons);
        for the dictionary form we walk every state's resources until a
        match is found — Acrobat hoists the font onto the first state it
        emits, but pypdfbox callers may legitimately register it elsewhere.
        """
        from pypdfbox.pdmodel.pd_resources import PDResources

        try:
            cos = widget.get_cos_object()
        except AttributeError:
            return None
        ap = cos.get_dictionary_object(_AP)
        if not isinstance(ap, COSDictionary):
            return None
        n_entry = ap.get_dictionary_object(_N)
        candidates: list[COSStream] = []
        if isinstance(n_entry, COSStream):
            candidates.append(n_entry)
        elif isinstance(n_entry, COSDictionary):
            for sub_key in n_entry.key_set():
                value = n_entry.get_dictionary_object(sub_key)
                if isinstance(value, COSStream):
                    candidates.append(value)
        for stream in candidates:
            res_cos = stream.get_dictionary_object(_RESOURCES)
            if not isinstance(res_cos, COSDictionary):
                continue
            resources = PDResources(res_cos)
            font = PDAppearanceGenerator._coerce_to_pd_font(
                resources.get_font(key)
            )
            if font is not None:
                return font
        return None

    @staticmethod
    def _lookup_font_in_widget_page(
        widget: PDAnnotationWidget, key: COSName
    ) -> PDFont | None:
        """Walk the widget's parent page ``/Resources /Font`` for ``key``.

        Returns the typed :class:`PDFont` instance when present, ``None``
        otherwise. The widget's ``/P`` (parent page back-pointer) is
        consulted; widgets without ``/P`` (legal — many authoring tools
        omit it) short-circuit to ``None``.
        """
        from pypdfbox.pdmodel.pd_resources import PDResources

        page = None
        getter = getattr(widget, "get_page", None)
        if callable(getter):
            try:
                page = getter()
            except Exception:  # noqa: BLE001 — defensive on lite-port surface
                page = None
        if not isinstance(page, COSDictionary):
            return None
        res_cos = page.get_dictionary_object(_RESOURCES)
        if not isinstance(res_cos, COSDictionary):
            return None
        resources = PDResources(res_cos)
        return PDAppearanceGenerator._coerce_to_pd_font(
            resources.get_font(key)
        )

    @staticmethod
    def _register_font_alias(
        cs: PDAppearanceContentStream,
        font: PDFont,
        alias: str | None,
    ) -> None:
        """Pre-register ``font`` under ``alias`` in ``cs``'s resources.

        :meth:`PDPageContentStream.set_font` later resolves the resource
        key by identity, so seeding the alias here makes the emitted
        ``/<alias> <size> Tf`` token preserve the source ``/DA`` alias.
        When ``alias`` is already taken by a different font COS object,
        the seeding is skipped — :meth:`set_font` will then auto-allocate
        a fresh ``F<n>`` slot, matching the historical lite-port shape
        for that edge case. ``alias=None`` (no source ``/DA`` font name)
        is also a no-op.
        """
        if not alias:
            return
        key = COSName.get_pdf_name(alias)
        resources = cs.get_resources()
        sub = resources.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Font")
        )
        font_cos = font.get_cos_object()
        if isinstance(sub, COSDictionary):
            existing = sub.get_dictionary_object(key)
            if existing is font_cos:
                return
            if existing is not None:
                # The alias is already claimed by a different font — let
                # set_font auto-allocate so we don't clobber the slot.
                return
        resources.put(COSName.get_pdf_name("Font"), key, font_cos)

    @classmethod
    def _auto_size(cls, height: float) -> float:
        """Pick an auto-size font size from a widget rect height alone.

        Used by paths where the text to render is unknown (or empty) at
        sizing time — keeps the height-only proportional heuristic and
        clamps to ``[AUTO_FONT_SIZE_MIN, AUTO_FONT_SIZE_MAX]``. Use
        :meth:`_iterative_auto_size` when both the text and width are
        known and the result needs to actually fit the rect.
        """
        candidate = height * 0.7
        return max(
            cls.AUTO_FONT_SIZE_MIN,
            min(cls.AUTO_FONT_SIZE_MAX, candidate),
        )

    @classmethod
    def _iterative_auto_size(
        cls,
        font: PDFont,
        text: str,
        interior_w: float,
        height: float,
    ) -> float:
        """Iteratively shrink the font size until ``text`` fits ``interior_w``.

        Wave 1374 closes the upstream ``calculateFontSize`` parity gap for
        the lite port: start at the height-based candidate (same as
        :meth:`_auto_size`), then halve repeatedly until the rendered
        width fits, never dipping below :attr:`MINIMUM_FONT_SIZE`. When
        ``text`` is empty or ``interior_w`` is non-positive the height
        clamp wins (no width constraint to satisfy).

        Mirrors upstream's "measure, then shrink" loop in spirit — we
        halve rather than decrement by 1 so the iterations stay bounded
        (~5 iterations to walk 12 → 0.375).
        """
        candidate = cls._auto_size(height)
        if not text or interior_w <= 0.0:
            return candidate
        size = candidate
        # Bound the loop: at minimum size 4 from a 12pt start, halving
        # gives 12 → 6 → 4 (clamped) — well under the 16-iteration cap.
        for _ in range(16):
            width = cls._estimate_text_width(font, size, text)
            if width <= interior_w:
                return size
            next_size = size * 0.5
            if next_size <= cls.MINIMUM_FONT_SIZE:
                return cls.MINIMUM_FONT_SIZE
            size = next_size
        # Defensive: starting at AUTO_FONT_SIZE_MAX (12pt), 16 halvings
        # reach 12 / 2**16 ≈ 0.0002pt — well below MINIMUM_FONT_SIZE — so
        # the loop always returns via the ``next_size <=`` check above.
        return max(size, cls.MINIMUM_FONT_SIZE)  # pragma: no cover - loop exits early

    @staticmethod
    def _resolve_widget_rotation(widget_cos: COSDictionary) -> int:
        """Pull the widget's ``/MK /R`` rotation, normalised to one of
        ``{0, 90, 180, 270}``.

        Mirrors upstream ``AppearanceGeneratorHelper.resolveRotation``
        (which delegates to ``PDAppearanceCharacteristicsDictionary.getRotation``).
        Non-multiple-of-90 values collapse to 0 — appearance generation
        only handles the four canonical orientations.
        """
        mk = widget_cos.get_dictionary_object(_MK)
        if not isinstance(mk, COSDictionary):
            return 0
        raw = mk.get_int(COSName.get_pdf_name("R"), 0)
        if raw % 90 != 0:
            return 0
        normalised = raw % 360
        # Defensive: Python's ``%`` returns a non-negative remainder so
        # ``normalised`` is always in [0, 360); guard kept for porters
        # on languages with a truncated-remainder operator.
        if normalised < 0:  # pragma: no cover - Python % is non-negative
            normalised += 360
        return normalised

    @staticmethod
    def _calculate_matrix(
        bbox_width: float,
        bbox_height: float,
        rotation: int,
    ) -> tuple[float, float, float, float, float, float]:
        """Return the ``/Matrix`` six-tuple to compose with the rotated bbox.

        Mirrors upstream ``AppearanceGeneratorHelper.calculateMatrix``:
        rotates by ``rotation`` degrees about the origin, then translates
        so the rotated content stays inside the bbox. For a widget rect
        of width ``W`` × height ``H``, after rotation the bbox dimensions
        swap to ``H × W`` for 90/270 (the caller passes pre-swapped
        ``bbox_width`` / ``bbox_height``).
        """
        import math

        if rotation == 0:
            return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        tx = 0.0
        ty = 0.0
        if rotation == 90:
            tx = bbox_height
        elif rotation == 180:
            tx = bbox_width
            ty = bbox_height
        elif rotation == 270:
            ty = bbox_width
        rad = math.radians(rotation)
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)
        return (cos_r, sin_r, -sin_r, cos_r, tx, ty)


__all__ = ["PDAppearanceGenerator"]
