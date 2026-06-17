# pypdfbox.pdmodel.font — font hierarchy

The font hierarchy under `pypdfbox.pdmodel.font` mirrors PDFBox class-for-class
and preserves the inheritance graph (`PDFont` → `PDSimpleFont` →
`PDType1Font` / `PDTrueTypeFont` / `PDType3Font`, `PDFont` → `PDType0Font`
with a child `PDCIDFont` chain). The PDF-level model in this package wraps
font dictionaries; the actual glyph data and TTF/OTF/CFF/Type1 parsing live
in [`pypdfbox.fontbox`](fontbox.md), which this package depends on.

## Public surface

| Class | Purpose |
| --- | --- |
| `PDFont` | Abstract root. `encode(text) -> bytes`, `get_string_width(text)`, `get_width(code)`, `get_height(code)`, `to_unicode(code)`, `get_font_descriptor`, `get_name`, `is_embedded`, `is_subset`, `is_symbolic`. |
| `PDFontLike` | Protocol implemented by every `PDFont` subtype. Used to type the resource cache and the glyph cache without forcing a concrete subtype. |
| `PDSimpleFont` | Common base for the 8-bit fonts (Type1, TrueType, Type3). Owns the encoding + first/last char + widths array. |
| `PDType1Font` | Type1 / PostScript font. Lazy-loads from the embedded `/FontFile` (`PFB` segments via `pypdfbox.fontbox.type1`). Standard 14 entries skip embedding. |
| `PDType1CFont` | Type1C (CFF-flavoured) font. Wraps a CFF table via `pypdfbox.fontbox.cff`. |
| `PDMMType1Font` | Multi-Master Type 1 (deprecated upstream; preserved for source parity). |
| `PDTrueTypeFont` | TrueType (`.ttf`) 8-bit font. |
| `PDType3Font` | Glyphs defined by content streams (a `PDType3CharProc` per glyph). Rendered via `pypdfbox.rendering` rather than fontbox. |
| `PDType3CharProc` | One Type-3 glyph procedure. Contains its own content stream + resources. |
| `PDType0Font` | Composite font: a CID-keyed font + a CMap. `encode(text)` runs through the CMap. |
| `PDCIDFont` | Abstract CIDFont root used as `/DescendantFonts[0]` of `PDType0Font`. |
| `PDCIDFontType0` | CIDFontType0 (CFF/Type1-derived descendant font). |
| `PDCIDFontType2` | CIDFontType2 (TrueType-derived descendant font). |
| `PDCIDFontType2Embedder` | Embeds + subsets a TrueType file as a CIDFontType2. |
| `PDVectorFont` | Protocol for fonts that can hand back an outline path for a glyph (used by rendering + appearance generation). |
| `PDFontDescriptor` | `/FontDescriptor` dictionary view (italic angle, ascent, descent, cap height, x-height, stem widths, font BBox, embedded font file). |
| `PDFontFactory` | Factory: dispatch on `/Subtype` to instantiate the right `PDFont` subtype from a `COSDictionary`. |
| `PDCIDSystemInfo` / `CIDSystemInfo` | Registry/ordering/supplement triple. |
| `PDType1FontEmbedder` / `PDTrueTypeFontEmbedder` / `TrueTypeEmbedder` | Embedding helpers — given a binary font, build the PDF dictionaries. |
| `Subsetter` | Glyph-subset planner used by the embedders to drop unreferenced glyphs. |
| `ToUnicodeWriter` | Builds the `/ToUnicode` CMap from a per-code Unicode map. |
| `FileSystemFontProvider` | Scans system font directories on demand (Windows, macOS, Linux). Cached. |
| `FontCache` / `FontMapperImpl` / `FontMatch` / `FSFontInfo` | Plumbing for the upstream font-matching algorithm. |
| `Standard14Fonts` | The 14 PDF base fonts: `HELVETICA`, `TIMES_ROMAN`, `COURIER`, plus bold/italic/oblique variants and `SYMBOL` / `ZAPF_DINGBATS`. Use `Standard14Fonts.get_afm(name)` to retrieve the metrics. |
| `UniUtil.get_uni_name_of_code_point(cp)` | Map a Unicode code point to its Adobe glyph name. |
| `VerticalDisplacementRange` | Vertical-writing displacement metadata for CID fonts. |

## Standard 14 (no file needed)

```python
from pypdfbox.pdmodel.font import PDType1Font, Standard14Fonts

font = PDType1Font(Standard14Fonts.FontName.HELVETICA)
width = font.get_string_width("Hello") / 1000.0  # em -> page units at 1pt
```

`Standard14Fonts.FontName` is a sealed enum — all 14 names are valid and
guaranteed to resolve without embedding.

## Liberation fallback

When a referenced font is neither standard-14 nor embedded, the renderer
falls back to the Liberation family bundled at
`pypdfbox/resources/fonts/liberation/`. This is the last-resort path —
embed your own font when fidelity matters.

## CJK opt-in

`pypdfbox.fontbox.cjk_loader` is a separate, opt-in entry point that loads
the bundled CJK fonts (Source Han Sans subset) on first use. Importing the
loader is mandatory: the fonts are not registered by default to keep cold
imports light.

```python
from pypdfbox.fontbox.cjk_loader import register_cjk_fonts
register_cjk_fonts()  # ~150ms, idempotent
```

## Typical usage

```python
from pypdfbox import PDDocument, PDPage
from pypdfbox.pdmodel.font import PDType0Font

with PDDocument() as doc:
    page = PDPage()
    doc.add_page(page)
    font = PDType0Font.load(doc, "/usr/share/fonts/truetype/DejaVuSans.ttf")
    with doc.open_content_stream(page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.new_line_at_offset(72, 720)
        cs.show_text("Hello, world")
        cs.end_text()
    doc.save("out.pdf")
```

## PDFBox divergence

- `PDFont.encode(String) -> byte[]` → `encode(str) -> bytes`. Encoding
  errors raise `IllegalArgumentException` upstream; pypdfbox raises
  `ValueError`.
- `PDType0Font.load(PDDocument, File, boolean embedSubset)` →
  `PDType0Font.load(doc, path_or_bytes, *, embed_subset=True)`. Always
  keyword-only for the boolean flag.
- `getStringWidth(String) -> float` (em units) preserved verbatim. Width
  is expressed in 1/1000 em as upstream.
- `Standard14Fonts.containsName(name)` → `Standard14Fonts.contains_name(name)`.

## See also

- [fontbox.md](fontbox.md) — TTF / OTF / CFF / Type1 / CMap parsers.
- [contentstream.md](contentstream.md) — `Tf`, `Tj`, `TJ` operator usage.
- [rendering.md](rendering.md) — glyph caching + Type-3 path.
- [guides/embedding-fonts.md](../guides/embedding-fonts.md) — when to
  subset vs embed full.
