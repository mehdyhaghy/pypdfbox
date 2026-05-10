"""Codepoint → OpenType script-tag detection.

Mirrors ``org.apache.fontbox.ttf.OpenTypeScript`` (upstream
``OpenTypeScript.java`` L44-358).

Upstream parses a bundled ``Scripts.txt`` Unicode data file at static
init time and builds a sorted array of (range-start, script-name)
pairs; that is then joined with a hand-written Unicode-script →
OpenType-tag map. We wrap fontTools.unicodedata.ot_tags_from_script(),
which provides exactly that mapping out of the box — including the
``bng2``/``beng``-style "v2 tag listed first" convention upstream uses
and the special ``DFLT``/``Inherited`` casing. The single divergence is
that fontTools returns ``DFLT`` for the ``Inherited`` script, whereas
upstream returns the literal string ``Inherited``; we apply that
special-case here.
"""

from __future__ import annotations

import sys

from fontTools.unicodedata import script as _ft_script
from fontTools.unicodedata import script_name as _ft_script_name

# String constants — preserved from upstream so callers comparing
# against ``OpenTypeScript.INHERITED`` etc. behave identically.
INHERITED: str = "Inherited"
UNKNOWN: str = "Unknown"
TAG_DEFAULT: str = "DFLT"

# Hand-mirrored upstream table from OpenTypeScript.java L65-209. fontTools
# already encodes this mapping, but we keep our own copy because the
# upstream tests pin specific keys (and our parity tests against them).
_UNICODE_SCRIPT_TO_OPENTYPE_TAG_MAP: dict[str, tuple[str, ...]] = {
    "Adlam": ("adlm",),
    "Ahom": ("ahom",),
    "Anatolian_Hieroglyphs": ("hluw",),
    "Arabic": ("arab",),
    "Armenian": ("armn",),
    "Avestan": ("avst",),
    "Balinese": ("bali",),
    "Bamum": ("bamu",),
    "Bassa_Vah": ("bass",),
    "Batak": ("batk",),
    "Bengali": ("bng2", "beng"),
    "Bhaiksuki": ("bhks",),
    "Bopomofo": ("bopo",),
    "Brahmi": ("brah",),
    "Braille": ("brai",),
    "Buginese": ("bugi",),
    "Buhid": ("buhd",),
    "Canadian_Aboriginal": ("cans",),
    "Carian": ("cari",),
    "Caucasian_Albanian": ("aghb",),
    "Chakma": ("cakm",),
    "Cham": ("cham",),
    "Cherokee": ("cher",),
    "Common": (TAG_DEFAULT,),
    "Coptic": ("copt",),
    "Cuneiform": ("xsux",),
    "Cypriot": ("cprt",),
    "Cyrillic": ("cyrl",),
    "Deseret": ("dsrt",),
    "Devanagari": ("dev2", "deva"),
    "Duployan": ("dupl",),
    "Egyptian_Hieroglyphs": ("egyp",),
    "Elbasan": ("elba",),
    "Ethiopic": ("ethi",),
    "Georgian": ("geor",),
    "Glagolitic": ("glag",),
    "Gothic": ("goth",),
    "Grantha": ("gran",),
    "Greek": ("grek",),
    "Gujarati": ("gjr2", "gujr"),
    "Gurmukhi": ("gur2", "guru"),
    "Han": ("hani",),
    "Hangul": ("hang",),
    "Hanunoo": ("hano",),
    "Hatran": ("hatr",),
    "Hebrew": ("hebr",),
    "Hiragana": ("kana",),
    "Imperial_Aramaic": ("armi",),
    INHERITED: (INHERITED,),
    "Inscriptional_Pahlavi": ("phli",),
    "Inscriptional_Parthian": ("prti",),
    "Javanese": ("java",),
    "Kaithi": ("kthi",),
    "Kannada": ("knd2", "knda"),
    "Katakana": ("kana",),
    "Kayah_Li": ("kali",),
    "Kharoshthi": ("khar",),
    "Khmer": ("khmr",),
    "Khojki": ("khoj",),
    "Khudawadi": ("sind",),
    "Lao": ("lao ",),
    "Latin": ("latn",),
    "Lepcha": ("lepc",),
    "Limbu": ("limb",),
    "Linear_A": ("lina",),
    "Linear_B": ("linb",),
    "Lisu": ("lisu",),
    "Lycian": ("lyci",),
    "Lydian": ("lydi",),
    "Mahajani": ("mahj",),
    "Malayalam": ("mlm2", "mlym"),
    "Mandaic": ("mand",),
    "Manichaean": ("mani",),
    "Marchen": ("marc",),
    "Meetei_Mayek": ("mtei",),
    "Mende_Kikakui": ("mend",),
    "Meroitic_Cursive": ("merc",),
    "Meroitic_Hieroglyphs": ("mero",),
    "Miao": ("plrd",),
    "Modi": ("modi",),
    "Mongolian": ("mong",),
    "Mro": ("mroo",),
    "Multani": ("mult",),
    "Myanmar": ("mym2", "mymr"),
    "Nabataean": ("nbat",),
    "Newa": ("newa",),
    "New_Tai_Lue": ("talu",),
    "Nko": ("nko ",),
    "Ogham": ("ogam",),
    "Ol_Chiki": ("olck",),
    "Old_Italic": ("ital",),
    "Old_Hungarian": ("hung",),
    "Old_North_Arabian": ("narb",),
    "Old_Permic": ("perm",),
    "Old_Persian": ("xpeo",),
    "Old_South_Arabian": ("sarb",),
    "Old_Turkic": ("orkh",),
    "Oriya": ("ory2", "orya"),
    "Osage": ("osge",),
    "Osmanya": ("osma",),
    "Pahawh_Hmong": ("hmng",),
    "Palmyrene": ("palm",),
    "Pau_Cin_Hau": ("pauc",),
    "Phags_Pa": ("phag",),
    "Phoenician": ("phnx",),
    "Psalter_Pahlavi": ("phlp",),
    "Rejang": ("rjng",),
    "Runic": ("runr",),
    "Samaritan": ("samr",),
    "Saurashtra": ("saur",),
    "Sharada": ("shrd",),
    "Shavian": ("shaw",),
    "Siddham": ("sidd",),
    "SignWriting": ("sgnw",),
    "Sinhala": ("sinh",),
    "Sora_Sompeng": ("sora",),
    "Sundanese": ("sund",),
    "Syloti_Nagri": ("sylo",),
    "Syriac": ("syrc",),
    "Tagalog": ("tglg",),
    "Tagbanwa": ("tagb",),
    "Tai_Le": ("tale",),
    "Tai_Tham": ("lana",),
    "Tai_Viet": ("tavt",),
    "Takri": ("takr",),
    "Tamil": ("tml2", "taml"),
    "Tangut": ("tang",),
    "Telugu": ("tel2", "telu"),
    "Thaana": ("thaa",),
    "Thai": ("thai",),
    "Tibetan": ("tibt",),
    "Tifinagh": ("tfng",),
    "Tirhuta": ("tirh",),
    "Ugaritic": ("ugar",),
    UNKNOWN: (TAG_DEFAULT,),
    "Vai": ("vai ",),
    "Warang_Citi": ("wara",),
    "Yi": ("yi  ",),
}

# fontTools returns short 4-letter script codes (``Latn``); upstream uses
# the long property names (``Latin``). ``_ft_script_name`` gives us the
# long form, but a few codes need name normalisation to match upstream's
# UAX-#24 spelling (``_`` instead of space, e.g. ``Old_Italic``).
_LONG_NAME_OVERRIDES: dict[str, str] = {
    # fontTools / unicodedata returns short tags ``Zinh`` and ``Zzzz``
    # whose long names are ``Inherited`` / ``Unknown`` — these already
    # match upstream verbatim, so no override needed. The general rule is
    # ``script_name(...).replace(' ', '_')``.
}


def _to_long_script_name(short: str) -> str:
    """Translate a 4-letter ISO script code (``Latn``) to upstream's long
    Unicode script name (``Latin``).

    Falls back to :data:`UNKNOWN` for codes fontTools doesn't recognise.
    """
    if short in _LONG_NAME_OVERRIDES:
        return _LONG_NAME_OVERRIDES[short]
    try:
        name = _ft_script_name(short)
    except Exception:  # pragma: no cover - fontTools throws on unknown
        return UNKNOWN
    if name is None:
        return UNKNOWN
    return name.replace(" ", "_")


def _max_code_point() -> int:
    """Return the Unicode max code point (``0x10FFFF``).

    Equivalent to Java's ``Character.MAX_CODE_POINT``. ``sys.maxunicode``
    in Python 3 is always ``0x10FFFF`` on the CPython distributions we
    target, but we expose it as a helper so the bounds check is easy to
    follow.
    """
    return sys.maxunicode


def _ensure_valid_code_point(code_point: int) -> None:
    """Mirror ``ensureValidCodePoint`` (OpenTypeScript.java L351-357).

    Raises :class:`ValueError` (Python's idiomatic ``IllegalArgumentException``)
    for negative or out-of-range codepoints.
    """
    if code_point < 0 or code_point > _max_code_point():
        raise ValueError(f"Invalid codepoint: {code_point}")


def get_unicode_script(code_point: int) -> str:
    """Mirror ``getUnicodeScript(int)`` (OpenTypeScript.java L317-331).

    Returns the long Unicode script name for ``code_point``
    (e.g. ``Latin``, ``Bengali``, ``Inherited``). Unassigned codepoints
    map to :data:`UNKNOWN`. Upstream marks this method ``private``; we
    expose it because the helper is useful for tooling and the only
    plausible mis-use (returning a name that isn't a map key) is
    inherent to the data layer, not the access modifier.
    """
    _ensure_valid_code_point(code_point)
    short = _ft_script(code_point)
    if short == "Zzzz":
        return UNKNOWN
    return _to_long_script_name(short)


def get_script_tags(code_point: int) -> tuple[str, ...] | None:
    """Mirror ``getScriptTags(int)`` (OpenTypeScript.java L344-349).

    Returns the tuple of OpenType script tags associated with
    ``code_point``. Unknown codepoints return ``(TAG_DEFAULT,)``;
    inherited codepoints return ``(INHERITED,)`` — callers (typically
    :class:`SubstitutingCmapLookup`) need to fold that string into the
    surrounding context.

    Returns ``None`` only when the resolved Unicode script name doesn't
    appear in :data:`_UNICODE_SCRIPT_TO_OPENTYPE_TAG_MAP` — upstream
    surfaces the same ``null`` in that branch.
    """
    _ensure_valid_code_point(code_point)
    unicode_script = get_unicode_script(code_point)
    return _UNICODE_SCRIPT_TO_OPENTYPE_TAG_MAP.get(unicode_script)


class OpenTypeScript:
    """Static container class for parity with upstream's all-static API.

    Upstream is a ``final`` class with a private constructor and only
    static methods (``OpenTypeScript.java`` L44-358). We expose the same
    surface as classmethods so call sites that read like
    ``OpenTypeScript.getScriptTags(cp)`` translate cleanly.
    """

    INHERITED = INHERITED
    UNKNOWN = UNKNOWN
    TAG_DEFAULT = TAG_DEFAULT

    def __init__(self) -> None:  # pragma: no cover - mirrors private ctor
        # Upstream's constructor is private (OpenTypeScript.java L235-237).
        # We keep it accessible (Python has no enforceable private) but
        # raise so accidental instantiation surfaces immediately.
        raise TypeError("OpenTypeScript is a static utility class")

    @staticmethod
    def get_script_tags(code_point: int) -> tuple[str, ...] | None:
        """Module-level alias of :func:`get_script_tags`."""
        return get_script_tags(code_point)

    @staticmethod
    def get_unicode_script(code_point: int) -> str:
        """Module-level alias of :func:`get_unicode_script`."""
        return get_unicode_script(code_point)

    @staticmethod
    def ensure_valid_code_point(code_point: int) -> None:
        """Mirror upstream's ``ensureValidCodePoint`` (OpenTypeScript.java L351).

        Validates a codepoint is in the legal Unicode range; raises
        :class:`ValueError` otherwise.
        """
        _ensure_valid_code_point(code_point)

    @staticmethod
    def parse_scripts_file(input_stream) -> None:  # noqa: ARG004
        """Mirror upstream's ``parseScriptsFile`` (OpenTypeScript.java L246).

        Upstream walks a bundled ``Scripts.txt`` Unicode data file at
        static init time. The Python port delegates to fontTools'
        already-baked codepoint→script tables, so the runtime parse is
        a no-op preserved for API parity.
        """
        # No-op: the codepoint-to-script mapping is sourced from
        # fontTools / unicodedata in this port; there is no per-call
        # parsing required.
        return None


__all__ = [
    "INHERITED",
    "OpenTypeScript",
    "TAG_DEFAULT",
    "UNKNOWN",
    "get_script_tags",
    "get_unicode_script",
]
