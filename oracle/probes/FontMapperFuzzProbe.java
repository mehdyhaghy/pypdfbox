import java.io.PrintStream;
import java.lang.reflect.Method;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import org.apache.pdfbox.pdmodel.font.FontMapper;
import org.apache.pdfbox.pdmodel.font.FontMappers;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;

/**
 * Differential fuzz probe for Apache PDFBox 3.0.7 FontMapperImpl
 * name-normalization + flag-heuristic surface (wave 1560, agent C).
 *
 * Complements the existing FontSubstituteProbe (which pins the
 * getFallbackFontName flag matrix and a fixed getSubstitutes query list).
 * This probe attacks three host-INDEPENDENT facets the older probe does not
 * exercise, all read via reflection on the package-private FontMapperImpl
 * returned by FontMappers.instance():
 *
 *  1. getPostScriptNames(String) — the verbatim + hyphen-stripped alt-spelling
 *     set used to build the name index. Emitted as:
 *       PSN\t<query>\t<sorted-csv-of-names>
 *     Fully deterministic (pure string transform; no host fonts).
 *
 *  2. getSubstitutes(String) fuzz — aggressive normalization edge cases NOT in
 *     FontSubstituteProbe's list: comma aliases for every canonical family
 *     (CourierNew,Bold / Times,Bold / Symbol,Bold / ...), leading/trailing/
 *     internal whitespace, mixed/upper case, empty string, names that
 *     normalize to the same internal key. Emitted as:
 *       SUBST\t<query>\t<csv-of-substitute-names>
 *     The list is the static constructor table — host-independent.
 *
 *  3. getFallbackFontName(PDFontDescriptor) bold-heuristic fuzz — the
 *     toLowerCase().contains("bold"|"black"|"heavy") branch across case
 *     variants, substring positions, and the false-positive guard ("notbold"
 *     etc. STILL match because "bold" is a substring — pinned to document the
 *     exact upstream contract). Emitted as:
 *       FALLBACK\t<label>\t<chosenStandard14Name>
 *
 * Deterministic and seed-free: the corpus is a fixed inline list. The pypdfbox
 * sibling (tests/pdmodel/font/oracle/test_font_mapper_fuzz_wave1560.py)
 * reconstructs each line and asserts an exact textual match.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FontMapperFuzzProbe
 */
public final class FontMapperFuzzProbe {

    // FLAG bit values mirror PDFontDescriptor's private constants.
    static final int FIXED_PITCH = 1;
    static final int SERIF = 2;
    static final int ITALIC = 64;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        FontMapper mapper = FontMappers.instance();

        Method postScriptNames = mapper.getClass()
                .getDeclaredMethod("getPostScriptNames", String.class);
        postScriptNames.setAccessible(true);
        Method substitutes = mapper.getClass()
                .getDeclaredMethod("getSubstitutes", String.class);
        substitutes.setAccessible(true);
        Method fallback = mapper.getClass()
                .getDeclaredMethod("getFallbackFontName", PDFontDescriptor.class);
        fallback.setAccessible(true);

        // ---- surface 1: getPostScriptNames ----
        String[] psnQueries = {
            "Arial",
            "Arial-Black",
            "Arial-BoldMT",
            "ArialMT",
            "Times-Roman",
            "Courier-BoldOblique",
            "A-B-C",
            "NoHyphenHere",
            "",
            "-",
            "Foo-",
            "-Bar",
        };
        for (String q : psnQueries) {
            @SuppressWarnings("unchecked")
            Set<String> names = (Set<String>) postScriptNames.invoke(mapper, q);
            Set<String> sorted = new TreeSet<>(names);
            out.printf("PSN\t%s\t%s%n", q, String.join(",", sorted));
        }

        // ---- surface 2: getSubstitutes fuzz ----
        String[] substQueries = {
            // comma aliases for every canonical style (not in FontSubstituteProbe):
            "CourierNew,Bold", "CourierNew,Italic", "CourierNew,BoldItalic",
            "Times,Bold", "Times,Italic", "Times,BoldItalic",
            "Symbol,Bold", "Symbol,Italic", "Symbol,BoldItalic",
            // whitespace fuzz — internal/leading/trailing spaces collapse:
            " Arial", "Arial ", "  Arial  ", "Ar ial", "Times New Roman",
            "Courier New", "Times Roman",
            // case fuzz:
            "ARIAL", "arial", "ArIaL", "TIMESNEWROMAN", "timesnewroman",
            // empty / pure-space / nonexistent:
            "", "   ", "TotallyUnknownFont",
            // canonical that should resolve:
            "Times", "Symbol", "ZapfDingbats",
        };
        for (String q : substQueries) {
            @SuppressWarnings("unchecked")
            List<String> subs = (List<String>) substitutes.invoke(mapper, q);
            out.printf("SUBST\t%s\t%s%n", q, String.join(",", subs));
        }

        // ---- surface 3: getFallbackFontName bold-heuristic fuzz ----
        // Each name is crossed with (sans, serif, fixed) via the flag bits.
        String[] heuristicNames = {
            "ArialBOLD", "arialbold", "ArialBold", "UltraBlackText",
            "heavyweight", "FooBlackItalic", "SemiBold", "notbold",
            "BOLD", "Black", "Heavy", "Regular", "Light", "Thin",
            "Bold Condensed", "Extra-Heavy", "", "Plain",
        };
        // Cross each name with (sans, serif, fixed, sansItalic) via flag bits.
        String[] styleLabels = {"sans", "serif", "fixed", "sansItalic"};
        int[] styleFlags = {0, SERIF, FIXED_PITCH, ITALIC};
        for (String nm : heuristicNames) {
            for (int s = 0; s < styleLabels.length; s++) {
                PDFontDescriptor d =
                        new PDFontDescriptor(new org.apache.pdfbox.cos.COSDictionary());
                d.setFlags(styleFlags[s]);
                d.setFontName(nm);
                String label = styleLabels[s] + "_n"
                        + (nm.isEmpty() ? "empty" : nm.replace(" ", "_"));
                String name = (String) fallback.invoke(mapper, d);
                out.printf("FALLBACK\t%s\t%s%n", label, name);
            }
        }
    }
}
