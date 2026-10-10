# Known limitations

See the
[issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues) for the
full list. The most common stable-state divergences and gaps are:

1. **Symbol / ZapfDingbats glyph coverage is partial.** Non-embedded
   Standard 14 `/Symbol` and `/ZapfDingbats` references substitute
   through the bundled `DejaVuSans.ttf` (Bitstream Vera + DejaVu
   public-domain — permissive). Coverage is roughly 100% of the
   Zapf Dingbats Unicode block and ~84% of the Adobe Symbol glyph
   set (Greek + math operators). The remaining 16% of Symbol glyphs
   render as `.notdef`. Bundling a true Symbol replacement would
   require pulling in a non-permissively-licensed font; we do not.

2. **ICU bidi reordering is not ported.** Text extraction uses
   Python's stdlib `unicodedata.bidirectional` for RTL detection and
   paragraph reversal. Pure-RTL and pure-LTR runs reorder correctly;
   mixed-LTR+RTL Unicode bidi paragraph reordering can differ from
   what Acrobat (or upstream PDFBox, which uses ICU) produces. This
   is a deliberate divergence — adding ICU as a runtime dependency
   would conflict with the permissive-license-only policy.

3. **Renderer pixel-exact parity is not portable.** Upstream's JUnit
   tests compare rendered output to bundled TIFF / PNG reference
   images produced by Java AWT. pypdfbox renders through Pillow plus a
   Skia-backed `_aggdraw_compat` rasteriser, so byte-equivalent
   output is unachievable. Parity is enforced *structurally* (page
   count, MediaBox, Rotation, Contents shape, Resources keys,
   save-reload round-trip) rather than pixel-by-pixel. See
   [`CHANGES.md`](../CHANGES.md) → "Active divergences".

4. **Standard 14 fallback fonts are bundled.** When a PDF uses a
   Standard 14 font (`Helvetica`, `Times-Roman`, `Courier`, and so on)
   without embedding it, pypdfbox substitutes the bundled Arimo, Tinos
   and Cousine TTFs (Apache-2.0) from `pypdfbox/resources/ttf/`. They
   are metric-compatible with Helvetica, Times and Courier, so layout
   and text widths are unchanged. Upstream PDFBox also uses a fallback
   font when the host lacks the original.

5. **Non-embedded CJK fonts need a CJK font on the host.** pypdfbox
   first uses a matching CJK font installed on the system. Unified fonts
   such as Noto Sans CJK and Source Han Sans can stand in for any
   Chinese, Japanese or Korean collection. If none is installed, the
   opt-in `pypdfbox[cjk]` extra with `PYPDFBOX_CJK_AUTODOWNLOAD=1`
   downloads Noto Sans CJK (release `Sans2.004`, SIL OFL 1.1), checks
   its SHA-256 and stores it in a per-user cache. Otherwise the glyphs
   render as `.notdef`, as in upstream PDFBox.

6. **No PDF/A or PDF/UA conformance validation.** Apache PDFBox 4.0
   removes the Preflight module; pypdfbox follows that decision.
   Validation is out of scope and not bundled. Downstream users who
   need it wire in whichever external validator they choose
   (pypdfbox stays validator-agnostic, in keeping with the
   permissive-license-only rule).

The full active-divergences list lives in
[`CHANGES.md` → Active divergences](../CHANGES.md#active-divergences-vs-upstream).
Open in-flight gaps that are *fixable but not yet done* are tracked on
the [issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues).
