import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import org.apache.fontbox.ttf.gsub.GlyphArraySplitter;
import org.apache.fontbox.ttf.gsub.GlyphArraySplitterRegexImpl;
import org.apache.fontbox.ttf.model.Language;
import org.apache.fontbox.ttf.model.MapBackedGsubData;
import org.apache.fontbox.ttf.model.MapBackedScriptFeature;
import org.apache.fontbox.ttf.model.ScriptFeature;

/**
 * Live oracle probe for the GSUB <em>substitution-application</em> layer of
 * Apache FontBox — the half of GSUB that {@code GsubSubstitutionProbe} (which
 * dumps the extractor's feature map) and {@code GsubExtractorFuzzProbe} (which
 * fuzzes the extractor's graph walk) never touch.
 *
 * It drives the public application engine the per-script workers run inside
 * their (package-private) {@code applyGsubFeature} loop:
 *
 *   - {@link GlyphArraySplitterRegexImpl#split} — the greedy longest-match
 *     tokenizer that breaks an input glyph run into substitution chunks;
 *   - {@link MapBackedScriptFeature#canReplaceGlyphs} /
 *     {@link MapBackedScriptFeature#getReplacementForGlyphs} — the per-chunk
 *     substitution decision; and
 *   - {@link MapBackedGsubData#isFeatureSupported} /
 *     {@link MapBackedGsubData#getFeature} — feature lookup, including the
 *     unsupported-feature throw.
 *
 * The probe re-implements the worker {@code applyGsubFeature} body verbatim
 * (split, then replace each replaceable chunk) so each fuzz case projects the
 * substituted glyph-id sequence a real Latin/DFLT worker would produce, while
 * staying entirely in public API (the worker constructors are package-private
 * so a default-package probe cannot instantiate them directly).
 *
 * Fuzz angles (feature map fixed; the glyph run / feature varies):
 *   - empty input run
 *   - run with no applicable substitution at all
 *   - exact single-glyph substitution
 *   - exact 2- and 3-glyph ligature
 *   - partial ligature match (prefix present, run too short)
 *   - overlapping ligatures (longest-match wins; 3-glyph beats 2-glyph)
 *   - back-to-back ligatures
 *   - ligature surrounded by unmatched glyphs
 *   - duplicated glyph ids in the run
 *   - large / negative / zero glyph ids
 *   - unknown feature tag lookup
 *   - getFeature on an unsupported tag (throws)
 *   - empty feature map (no substitution keys → split is identity)
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> GsubLayoutFuzzProbe <case>
 *
 * Output (UTF-8, stdout), exactly one of:
 *   OUT\t<comma-joined-substituted-gids-or-empty>
 *   META\t<key>=<value>...                            (feature-lookup cases)
 *   ERROR\t<SimpleExceptionClassName>
 */
public final class GsubLayoutFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String name = args[0];
        try {
            runCase(name, out);
        } catch (Throwable t) {
            out.printf("ERROR\t%s%n", t.getClass().getSimpleName());
        }
    }

    // The canonical "liga" feature shared by every substitution case.
    //   [10, 11]        -> 100   (2-glyph ligature)
    //   [10, 11, 12]    -> 200   (3-glyph ligature, overlaps the 2-glyph one)
    //   [20, 21]        -> 300   (a second 2-glyph ligature)
    //   [30]            -> 400   (single-glyph substitution)
    //   [10, 99]        -> 500   (shares a prefix glyph with the 10,11* ligatures)
    private static MapBackedScriptFeature ligaFeature() {
        Map<List<Integer>, Integer> m = new LinkedHashMap<>();
        m.put(run(10, 11), 100);
        m.put(run(10, 11, 12), 200);
        m.put(run(20, 21), 300);
        m.put(run(30), 400);
        m.put(run(10, 99), 500);
        return new MapBackedScriptFeature("liga", m);
    }

    private static void runCase(String name, PrintStream out) {
        switch (name) {
            // --- substitution-application cases (apply the liga feature) ---
            case "empty_run":
                emitApply(out, ligaFeature(), run());
                return;
            case "no_match":
                emitApply(out, ligaFeature(), run(1, 2, 3));
                return;
            case "single_sub":
                emitApply(out, ligaFeature(), run(30));
                return;
            case "single_sub_in_context":
                emitApply(out, ligaFeature(), run(1, 30, 2));
                return;
            case "ligature_2":
                emitApply(out, ligaFeature(), run(10, 11));
                return;
            case "ligature_3":
                emitApply(out, ligaFeature(), run(10, 11, 12));
                return;
            case "partial_ligature_prefix":
                // [10] alone never matches; [10,11] does — here run ends at 10.
                emitApply(out, ligaFeature(), run(10));
                return;
            case "partial_ligature_short":
                // [10,11,12] is a key, but run is only [10,11] -> 2-glyph wins.
                emitApply(out, ligaFeature(), run(10, 11));
                return;
            case "overlap_longest_wins":
                // [10,11,12,13]: greedy longest match takes [10,11,12]->200,
                // then 13 is unmatched.
                emitApply(out, ligaFeature(), run(10, 11, 12, 13));
                return;
            case "overlap_short_then_tail":
                // [10,11,20,21]: [10,11]->100 then [20,21]->300.
                emitApply(out, ligaFeature(), run(10, 11, 20, 21));
                return;
            case "shared_prefix_alt":
                // [10,99] matches the 500 key even though 10 starts 100/200.
                emitApply(out, ligaFeature(), run(10, 99));
                return;
            case "ligature_in_context":
                emitApply(out, ligaFeature(), run(7, 10, 11, 8));
                return;
            case "back_to_back":
                emitApply(out, ligaFeature(), run(10, 11, 10, 11, 12));
                return;
            case "duplicate_glyphs":
                emitApply(out, ligaFeature(), run(30, 30, 30));
                return;
            case "repeated_prefix_no_complete":
                // 10,10,11: first 10 unmatched (10,10 is no key), then 10,11->100.
                emitApply(out, ligaFeature(), run(10, 10, 11));
                return;
            case "large_gids":
                emitApply(out, ligaFeature(), run(65535, 70000, 100000));
                return;
            case "negative_gid":
                emitApply(out, ligaFeature(), run(-1, 30, -5));
                return;
            case "zero_gid":
                emitApply(out, ligaFeature(), run(0, 10, 11));
                return;
            case "all_keys_back_to_back":
                emitApply(out, ligaFeature(), run(10, 11, 12, 20, 21, 30));
                return;

            // --- empty / degenerate feature ---
            case "empty_feature_identity": {
                MapBackedScriptFeature empty =
                        new MapBackedScriptFeature("liga", new LinkedHashMap<>());
                emitApply(out, empty, run(10, 11, 30));
                return;
            }
            case "empty_feature_empty_run": {
                MapBackedScriptFeature empty =
                        new MapBackedScriptFeature("liga", new LinkedHashMap<>());
                emitApply(out, empty, run());
                return;
            }

            // --- direct splitter projection (no substitution) ---
            case "split_only": {
                GlyphArraySplitter splitter = new GlyphArraySplitterRegexImpl(
                        ligaFeature().getAllGlyphIdsForSubstitution());
                List<List<Integer>> chunks = splitter.split(run(10, 11, 12, 20, 21, 5));
                StringBuilder sb = new StringBuilder("SPLIT");
                for (List<Integer> c : chunks) {
                    sb.append('\t').append(join(c));
                }
                out.println(sb);
                return;
            }

            // --- feature-lookup (MapBackedGsubData) cases ---
            case "gsub_supported_feature": {
                MapBackedGsubData data = gsubData();
                out.printf("META\tsupported=%b%n", data.isFeatureSupported("liga"));
                return;
            }
            case "gsub_unknown_feature": {
                MapBackedGsubData data = gsubData();
                out.printf("META\tsupported=%b%n", data.isFeatureSupported("zzzz"));
                return;
            }
            case "gsub_get_unknown_feature_throws": {
                MapBackedGsubData data = gsubData();
                // upstream throws UnsupportedOperationException
                ScriptFeature f = data.getFeature("zzzz");
                out.printf("META\tname=%s%n", f.getName());
                return;
            }
            case "gsub_get_replacement_unknown_throws": {
                ScriptFeature f = ligaFeature();
                // canReplaceGlyphs is false, so getReplacementForGlyphs throws.
                Integer r = f.getReplacementForGlyphs(run(1, 2));
                out.printf("META\trepl=%d%n", r);
                return;
            }
            case "gsub_metadata": {
                MapBackedGsubData data = gsubData();
                Set<String> feats = new TreeSet<>(data.getSupportedFeatures());
                out.printf("META\tlang=%s\tscript=%s\tfeatures=%s%n",
                        data.getLanguage().name(),
                        data.getActiveScriptName(),
                        String.join(",", feats));
                return;
            }
            case "can_replace_true":
                out.printf("META\tcan=%b%n",
                        ligaFeature().canReplaceGlyphs(run(10, 11)));
                return;
            case "can_replace_false_partial":
                out.printf("META\tcan=%b%n",
                        ligaFeature().canReplaceGlyphs(run(10)));
                return;
            case "can_replace_empty":
                out.printf("META\tcan=%b%n",
                        ligaFeature().canReplaceGlyphs(run()));
                return;

            default:
                throw new IllegalArgumentException("unknown case: " + name);
        }
    }

    /**
     * Replays the worker {@code applyGsubFeature} body: split the run into
     * chunks, replace each replaceable chunk, leave the rest as-is.
     */
    private static void emitApply(PrintStream out, ScriptFeature feature,
            List<Integer> glyphs) {
        Set<List<Integer>> keys = feature.getAllGlyphIdsForSubstitution();
        List<Integer> result;
        if (keys.isEmpty()) {
            result = glyphs;
        } else {
            GlyphArraySplitter splitter = new GlyphArraySplitterRegexImpl(keys);
            List<List<Integer>> tokens = splitter.split(glyphs);
            result = new ArrayList<>();
            for (List<Integer> chunk : tokens) {
                if (feature.canReplaceGlyphs(chunk)) {
                    result.add(feature.getReplacementForGlyphs(chunk));
                } else {
                    result.addAll(chunk);
                }
            }
        }
        out.printf("OUT\t%s%n", join(result));
    }

    private static MapBackedGsubData gsubData() {
        Map<String, Map<List<Integer>, Integer>> m = new LinkedHashMap<>();
        Map<List<Integer>, Integer> liga = new LinkedHashMap<>();
        liga.put(run(10, 11), 100);
        m.put("liga", liga);
        Map<List<Integer>, Integer> ccmp = new LinkedHashMap<>();
        ccmp.put(run(30), 400);
        m.put("ccmp", ccmp);
        return new MapBackedGsubData(Language.LATIN, "latn", m);
    }

    private static List<Integer> run(int... ids) {
        List<Integer> list = new ArrayList<>(ids.length);
        for (int id : ids) {
            list.add(id);
        }
        return list;
    }

    private static String join(List<Integer> run) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < run.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(run.get(i));
        }
        return sb.toString();
    }

    // Suppress unused-import style warnings on Arrays in some toolchains.
    static {
        Arrays.asList(0);
    }
}
