import java.io.PrintStream;
import java.util.Locale;
import org.apache.fontbox.afm.FontMetrics;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;

/**
 * Live oracle probe: differential-fuzz the STATIC {@link Standard14Fonts} name
 * surface plus the bundled-AFM per-glyph widths that back it. These facets are
 * NOT pinned by the existing Std14 probes:
 *
 *   - Std14MetricsProbe / Std14SyntheticDescriptorProbe drive a constructed
 *     {@code PDType1Font} and pin per-CODE widths + the synthesised descriptor;
 *     they never touch the static name-mapping API.
 *   - FontSubstituteProbe pins the FontMapperImpl substitute table, not
 *     {@code Standard14Fonts.getMappedFontName / containsName / getNames / getAFM}.
 *
 * This probe exercises ~40 cases across:
 *   MAP\t<query>\t<getMappedFontName-or-null>\t<containsName>
 *       canonical names, the Acrobat aliases (Arial / ArialMT / Arial-Bold /
 *       CourierNew / TimesNewRoman / -PS / -MT variants), case-insensitive
 *       inputs, and unknown names. getMappedFontName returns a FontName enum;
 *       we emit its String name (FontName.getName()) or the literal "null".
 *   NAMES\t<size>   — Standard14Fonts.getNames() (canonical + every alias).
 *   GW\t<font>\t<glyph>\t<getCharacterWidth>  — per-glyph AFM advance widths,
 *       including Symbol (alpha, summation) and ZapfDingbats (a1, a10) glyphs,
 *       a missing glyph (".notdef"-ish unknown name -> 0), across the families.
 *   AFM\t<query>\t<present>  — getAFM presence for canonical + alias + unknown
 *       (unknown raises; we capture "ERR").
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Standard14FontFuzzProbe
 */
public final class Standard14FontFuzzProbe {

    // Name-mapping queries: canonical, aliases (Arial / TimesNewRoman /
    // CourierNew / -PS / -MT branches), case-folded inputs, and unknowns.
    private static final String[] MAP_QUERIES = {
        // canonical
        "Helvetica", "Helvetica-Bold", "Times-Roman", "Times-BoldItalic",
        "Courier", "Courier-BoldOblique", "Symbol", "ZapfDingbats",
        // Arial branch
        "Arial", "ArialMT", "Arial-Bold", "Arial-BoldMT", "Arial-Italic",
        "Arial-BoldItalicMT",
        // TimesNewRoman branch
        "TimesNewRoman", "TimesNewRomanPSMT", "TimesNewRoman-Bold",
        "TimesNewRomanPS-BoldMT", "TimesNewRomanPS-ItalicMT",
        // CourierNew branch
        "CourierNew", "CourierNewPSMT", "CourierNew-Bold",
        "CourierNewPS-BoldItalicMT",
        // Symbol/Times alias edge cases
        "Symbol,Bold", "Times", "Times,Bold",
        // case-insensitive
        "helvetica", "ARIAL", "couriernew", "TIMESNEWROMAN",
        // unknowns
        "NoSuchFont-XYZ", "Wingdings", "", "Helvetica-Light",
    };

    // Per-glyph width queries: (font, glyphName). Latin glyphs across the
    // families + Symbol/ZapfDingbats own glyph repertoire + an unknown glyph.
    private static final String[][] GW_QUERIES = {
        {"Helvetica", "A"}, {"Helvetica", "space"}, {"Helvetica", "i"},
        {"Helvetica-Bold", "A"}, {"Times-Roman", "A"}, {"Times-Roman", "W"},
        {"Courier", "A"}, {"Courier", "i"}, {"Courier", "W"},
        {"Symbol", "alpha"}, {"Symbol", "summation"}, {"Symbol", "space"},
        {"ZapfDingbats", "a1"}, {"ZapfDingbats", "a10"}, {"ZapfDingbats", "space"},
        {"Helvetica", "thisGlyphDoesNotExist"},
        // alias resolves to canonical -> identical widths
        {"Arial", "A"}, {"CourierNew", "i"},
    };

    // getAFM presence queries.
    private static final String[] AFM_QUERIES = {
        "Helvetica", "Symbol", "ZapfDingbats", "Arial", "TimesNewRomanPSMT",
        "NoSuchFont-XYZ",
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        for (String q : MAP_QUERIES) {
            Standard14Fonts.FontName mapped = Standard14Fonts.getMappedFontName(q);
            String mappedStr = mapped == null ? "null" : mapped.getName();
            boolean contains = Standard14Fonts.containsName(q);
            out.printf("MAP\t%s\t%s\t%b%n", q, mappedStr, contains);
        }

        out.printf("NAMES\t%d%n", Standard14Fonts.getNames().size());

        for (String[] gw : GW_QUERIES) {
            String w;
            try {
                FontMetrics afm = Standard14Fonts.getAFM(gw[0]);
                w = afm == null ? "NOAFM" : fmt(afm.getCharacterWidth(gw[1]));
            } catch (Exception e) {
                w = "ERR";
            }
            out.printf("GW\t%s\t%s\t%s%n", gw[0], gw[1], w);
        }

        for (String q : AFM_QUERIES) {
            String present;
            try {
                FontMetrics afm = Standard14Fonts.getAFM(q);
                present = afm == null ? "null" : "present";
            } catch (Exception e) {
                present = "ERR";
            }
            out.printf("AFM\t%s\t%s%n", q, present);
        }
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f; // collapse -0.0 to 0.0
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
