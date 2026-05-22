# pypdfbox.fontbox — font file parsers and mappers

`pypdfbox.fontbox` is the port of Apache FontBox: it owns every font file
format the higher layers might need (TTF, OTF, CFF, Type1, AFM), the
encoding tables, and the font mapper that picks a system font when an
embedded one is missing. The PDF-aware wrappers in
[`pypdfbox.pdmodel.font`](pdmodel-font.md) sit on top of this layer.

## Public surface (top level)

| Class | Purpose |
| --- | --- |
| `FontBoxFont` | Protocol — `name`, `path` (optional), `has_glyph(name)`, `get_path(name) -> Path`, `get_width(name) -> float`, `get_font_bbox() -> tuple[float, float, float, float]`, `get_font_matrix() -> Matrix`. Every concrete font implements it. |
| `EncodedFont` | Mixin for fonts that carry an `Encoding` (Type1, TrueType). |
| `Encoding` | Abstract single-byte encoding. `get_name(code) -> str`, `contains(name) -> bool`, `code_to_name`. Subclasses below. |
| `StandardEncoding`, `MacRomanEncoding`, `MacExpertEncoding`, `SymbolEncoding`, `WinAnsiEncoding`, `ZapfDingbatsEncoding` | Predefined encodings from PDF 32000 Appendix D. |
| `GlyphList` | Adobe glyph-name → Unicode mapping. `additional()` returns the supplemental list (PDFBox `additional.txt`). |
| `FontProvider` | Protocol — `get_font_names()`, `get_font_info(name) -> FontInfo`. |
| `FontMapper` | Protocol — `get_font_box_font(name, descriptor)`, `get_true_type_font(name, descriptor)`, `get_cid_font(name, descriptor, cid_system_info)`. |
| `DefaultFontMapper` | The shipping `FontMapper`. Owns the system-font scanner and the Liberation fallback (wave 1376). |
| `Standard14FontWrapper` | Adapter that exposes a Standard 14 AFM as a `FontBoxFont`. |
| `FontMappers` | Singleton accessor: `FontMappers.instance()`. |
| `FontMapping[T]` | The result of a `FontMapper` lookup — the chosen font plus a `is_fallback` flag. |
| `FontInfo` | Lightweight metadata struct returned by font providers (name, format, os2 panose, weight). |
| `FontFormat` | `enum.Enum` — `TTF`, `OTF`, `TYPE1`, `CFF`. |
| `CIDFontMapping` | Mapping from `(registry, ordering)` → preferred fallback font name. |

## Sub-packages

| Sub-package | Notable classes / contents |
| --- | --- |
| `pypdfbox.fontbox.ttf` | `TTFParser`, `TTFFont`, `OpenTypeFont`, `OpenTypeParser`, `CmapTable`, `GlyfTable`, `HeadTable`, `HheaTable`, `HmtxTable`, `MaxpTable`, `NameTable`, `OS2WindowsMetricsTable`, `PostScriptTable`, `LocaTable`, `GSUBTable`, `GPOSTable`, `BaseTable`, `KernTable`, `TTFSubsetter`. |
| `pypdfbox.fontbox.cff` | `CFFParser`, `CFFFont`, `CFFType1Font`, `CFFCIDFont`, `CharStringConverter`, `Type1CharString`, `Type2CharString`, `IndexData`. |
| `pypdfbox.fontbox.type1` | `Type1Parser`, `Type1Font`, `PfbParser` (Type1 segment splitter), `EncodedFont` integration. |
| `pypdfbox.fontbox.afm` | `AFMParser`, `FontMetrics`, `CharMetric`, `KernPair`, `Composite`. |
| `pypdfbox.fontbox.cmap` | `CMapParser`, `CMap`, `CMapName`, `IdentityHCMap`, `IdentityVCMap`, predefined CJK CMap loader. |
| `pypdfbox.fontbox.encoding` | Encoding adapters layered over the top-level `Encoding` classes; also `DictionaryEncoding` for custom `/Encoding` dicts in PDFs. |
| `pypdfbox.fontbox.pfb` | Type1 PFB (Printer Font Binary) segment parser. |
| `pypdfbox.fontbox.util` | Bounding-box helpers, BoundingBox class, advance-width unit helpers. |

## GSUB workers

The OpenType GSUB (Glyph Substitution) table is decoded by `GSUBTable` plus
script-specific workers under `pypdfbox.fontbox.ttf.gsub`. Lookup types
1-8 are implemented (wave 1379/1380); supported scripts:

- `Latin` (latn, default + AALT alternates + SMCP small caps)
- `DFLT`
- `Bengali` (beng / bng2)
- `Devanagari` (deva / dev2)
- `Gujarati` (gujr / gjr2)
- `Tamil` (taml / tml2)

Each worker applies the script's mandatory and optional features and yields
substituted glyph IDs. Use `GSUBTable.get_substitutions(script, features)`
to query.

## CMap subsystem

`pypdfbox.fontbox.cmap.CMapParser` parses CMap files (the PostScript
character-mapping format). Predefined CMaps shipped with PDFBox
(GB-EUC-H, GBpc-EUC-H, GBK-EUC-H, UniGB-UCS2-H, UniGB-UCS2-V,
UniCNS-UCS2-H, UniJIS-UCS2-H, UniKS-UCS2-H, …) are loaded from
`pypdfbox/resources/cmaps/`. `IdentityHCMap` / `IdentityVCMap` are the
horizontal/vertical identity mappings used by `PDType0Font` when the PDF
specifies `/Identity-H` or `/Identity-V`.

## Typical usage

```python
from pypdfbox.fontbox.ttf import TTFParser

with open("/usr/share/fonts/truetype/DejaVuSans.ttf", "rb") as f:
    font = TTFParser().parse(f.read())
print(font.name, font.get_units_per_em())
print(font.get_width("A"))
```

## PDFBox divergence

- `FontBoxFont.hasGlyph(name)` → `has_glyph(name)`.
- `Encoding.getName(int code)` → `get_name(code)`.
- The Java `BoundingBox(x_min, y_min, x_max, y_max)` is a frozen
  `dataclasses.dataclass` rather than a mutable class.
- TTF table classes expose attribute access (`font.head.units_per_em`)
  rather than upstream `getUnitsPerEm()`. The method form is kept as an
  alias for source parity.

## See also

- [pdmodel-font.md](pdmodel-font.md) — PDF-aware wrappers over these
  parsers.
- [rendering.md](rendering.md) — `GlyphCache` uses `FontBoxFont.get_path`.
- [guides/embedding-fonts.md](../guides/embedding-fonts.md).
