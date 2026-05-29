import java.lang.reflect.Method;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.pdmodel.font.FontMappers;
import org.apache.pdfbox.pdmodel.font.FontMapper;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;

/**
 * Live oracle probe: emit Apache PDFBox FontMapperImpl substitution decisions
 * for non-embedded fonts, restricted to the host-independent (deterministic)
 * facets.
 *
 * Two surfaces, both driven via reflection on the package-private
 * FontMapperImpl returned by FontMappers.instance():
 *
 *  1. getFallbackFontName(PDFontDescriptor) — flag/name driven Standard-14
 *     family + style selection. Emitted as:
 *       FALLBACK\t<label>\t<chosenStandard14Name>
 *     across a matrix of descriptor flag combinations and bold-name
 *     heuristics. This is fully deterministic (depends only on descriptor
 *     bits + the font name string, never on host fonts).
 *
 *  2. getSubstitutes(String) — the constructor-built substitute table,
 *     including the Standard14Fonts alias expansion (Acrobat names such as
 *     "Arial", "TimesNewRoman", "CourierNew" map to the canonical font's
 *     substitute list). Emitted as:
 *       SUBST\t<queryName>\t<csv-of-substitute-names>
 *     The returned list is the static constructor table — independent of
 *     which fonts are installed on the host.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FontSubstituteProbe
 */
public final class FontSubstituteProbe {

    // FLAG bit values mirror PDFontDescriptor's private constants.
    static final int FIXED_PITCH = 1;
    static final int SERIF = 2;
    static final int ITALIC = 64;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        FontMapper mapper = FontMappers.instance();

        Method fallback = mapper.getClass()
                .getDeclaredMethod("getFallbackFontName", PDFontDescriptor.class);
        fallback.setAccessible(true);
        Method substitutes = mapper.getClass()
                .getDeclaredMethod("getSubstitutes", String.class);
        substitutes.setAccessible(true);

        // ---- surface 1: getFallbackFontName matrix ----
        // null descriptor -> Times-Roman.
        emitFallback(out, mapper, fallback, "NULL", null);
        // Walk every (fixedPitch, serif, italic) flag combo x bold-name
        // heuristic. Serif is only consulted when fixedPitch is false (the
        // upstream if/else if chain), but we exercise all 8 flag combos to
        // pin the precedence anyway.
        String[] names = {null, "FooRegular", "FooBold", "FooBlack", "FooHeavy"};
        for (int fp = 0; fp <= 1; fp++) {
            for (int sf = 0; sf <= 1; sf++) {
                for (int it = 0; it <= 1; it++) {
                    for (String nm : names) {
                        int flags = 0;
                        if (fp == 1) flags |= FIXED_PITCH;
                        if (sf == 1) flags |= SERIF;
                        if (it == 1) flags |= ITALIC;
                        PDFontDescriptor d = new PDFontDescriptor(new org.apache.pdfbox.cos.COSDictionary());
                        d.setFlags(flags);
                        if (nm != null) d.setFontName(nm);
                        String label = "fp" + fp + "_sf" + sf + "_it" + it
                                + "_n" + (nm == null ? "null" : nm);
                        emitFallback(out, mapper, fallback, label, d);
                    }
                }
            }
        }

        // ---- surface 2: getSubstitutes table ----
        // Canonical Standard-14 names + the Acrobat alias names that the
        // constructor's Standard14Fonts.getNames() loop expands.
        String[] queries = {
            "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
            "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
            "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
            "Symbol", "ZapfDingbats",
            // Acrobat aliases (expanded by the constructor loop):
            "Arial", "ArialMT", "Arial-Bold", "Arial-BoldMT", "Arial-Italic",
            "Arial-ItalicMT", "Arial-BoldItalic", "Arial-BoldItalicMT",
            "CourierNew", "CourierNewPSMT", "CourierNew-Bold", "CourierNewPS-BoldMT",
            "TimesNewRoman", "TimesNewRomanPSMT", "TimesNewRoman-Bold",
            "TimesNewRomanPS-BoldMT", "TimesNewRomanPS-Italic",
            // case / spacing normalisation:
            "arial", "Arial ", "TIMESNEWROMAN",
            // a name with no substitutes at all:
            "NoSuchFont-XYZ",
        };
        for (String q : queries) {
            @SuppressWarnings("unchecked")
            List<String> subs = (List<String>) substitutes.invoke(mapper, q);
            out.printf("SUBST\t%s\t%s%n", q, String.join(",", subs));
        }
    }

    private static void emitFallback(PrintStream out, FontMapper mapper,
            Method fallback, String label, PDFontDescriptor d) throws Exception {
        String name = (String) fallback.invoke(mapper, d);
        out.printf("FALLBACK\t%s\t%s%n", label, name);
    }
}
