import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import org.apache.fontbox.ttf.GlyphSubstitutionTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.model.GsubData;
import org.apache.fontbox.ttf.model.ScriptFeature;

/**
 * Live oracle probe: emit the GSUB glyph-substitution map that Apache FontBox's
 * {@code GlyphSubstitutionDataExtractor} materialises for a given font + script.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> GsubSubstitutionProbe <font.ttf> <scriptTag>
 *
 * Drives {@code GlyphSubstitutionTable.getGsubData(scriptTag)} which walks the
 * ScriptList -> LangSys -> FeatureList -> LookupList graph and runs
 * {@code GlyphSubstitutionDataExtractor} over the type-1 (single) and type-4
 * (ligature) lookups, producing a {@code feature_tag -> {glyph_run ->
 * substitute_glyph_id}} map. We dump that map verbatim so pypdfbox's own
 * {@code GlyphSubstitutionDataExtractor} (fed the same script's data classes)
 * can be asserted line-for-line.
 *
 * Output (UTF-8, stdout):
 *   SCRIPT\t<activeScriptName>\t<language>
 *   FEATURE\t<featureTag>\t<substitutionCount>
 *   SUB\t<featureTag>\t<comma-joined-glyph-run>\t<substituteGlyphId>
 * FEATURE lines are sorted by tag; SUB lines are sorted by (featureTag, run).
 * Run order inside a key follows the List<Integer> the extractor stored
 * (which is the on-disk component order). A run is rendered as the GIDs joined
 * by ','.
 */
public final class GsubSubstitutionProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File file = new File(args[0]);
        String scriptTag = args[1];

        TrueTypeFont ttf = new org.apache.fontbox.ttf.TTFParser()
                .parse(new org.apache.pdfbox.io.RandomAccessReadBufferedFile(file));

        // Fetch the parsed GSUB table directly from the table map.
        GlyphSubstitutionTable table =
                (GlyphSubstitutionTable) ttf.getTableMap().get("GSUB");

        GsubData data = table.getGsubData(scriptTag);
        if (data == null || data == GsubData.NO_DATA_FOUND) {
            out.printf("SCRIPT\t%s\t%s%n", "NO_DATA", "-");
            ttf.close();
            return;
        }

        out.printf("SCRIPT\t%s\t%s%n",
                String.valueOf(data.getActiveScriptName()),
                String.valueOf(data.getLanguage()));

        Set<String> features = new TreeSet<>(data.getSupportedFeatures());
        for (String featureTag : features) {
            ScriptFeature feature = data.getFeature(featureTag);
            Set<List<Integer>> runs = feature.getAllGlyphIdsForSubstitution();
            out.printf("FEATURE\t%s\t%d%n", featureTag, runs.size());

            List<List<Integer>> sortedRuns = new ArrayList<>(runs);
            sortedRuns.sort(new Comparator<List<Integer>>() {
                @Override
                public int compare(List<Integer> a, List<Integer> b) {
                    int n = Math.min(a.size(), b.size());
                    for (int i = 0; i < n; i++) {
                        int c = Integer.compare(a.get(i), b.get(i));
                        if (c != 0) {
                            return c;
                        }
                    }
                    return Integer.compare(a.size(), b.size());
                }
            });

            for (List<Integer> run : sortedRuns) {
                Integer sub = feature.getReplacementForGlyphs(run);
                out.printf("SUB\t%s\t%s\t%d%n", featureTag, joinRun(run), sub);
            }
        }

        ttf.close();
    }

    private static String joinRun(List<Integer> run) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < run.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(run.get(i));
        }
        return sb.toString();
    }
}
