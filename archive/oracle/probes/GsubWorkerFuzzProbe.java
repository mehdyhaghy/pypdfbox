import java.io.PrintStream;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.apache.fontbox.ttf.CmapLookup;
import org.apache.fontbox.ttf.gsub.GsubWorker;
import org.apache.fontbox.ttf.gsub.GsubWorkerFactory;
import org.apache.fontbox.ttf.model.Language;
import org.apache.fontbox.ttf.model.MapBackedGsubData;

/**
 * Live oracle probe for the <em>per-script {@link GsubWorker}</em> layer of
 * Apache FontBox — the half {@code GsubLayoutFuzzProbe} (wave 1547, the
 * substitution-application <em>engine</em>: splitter + MapBackedScriptFeature)
 * never touches.
 *
 * This probe drives the public {@link GsubWorkerFactory#getGsubWorker} dispatch
 * and the resulting worker's {@link GsubWorker#applyTransforms} over a built
 * {@link MapBackedGsubData}. Unlike the wave-1547 probe, which re-implemented
 * the {@code applyGsubFeature} body by hand because the worker constructors are
 * package-private, here we go through the <em>public</em> factory so each case
 * exercises a real concrete worker (GsubWorkerForLatin / -Dflt / -Bengali /
 * -Devanagari / -Gujarati / DefaultGsubWorker) end to end:
 *
 *   - factory dispatch by {@link Language} (which concrete worker is chosen);
 *   - the worker's per-script FEATURES_IN_ORDER application order;
 *   - feature-not-supported short-circuit (run passes through unchanged);
 *   - a run that triggers a single-feature ligature;
 *   - multi-feature ordering (ccmp feeds liga — order is observable);
 *   - an unknown language (UNSPECIFIED) → DefaultGsubWorker (no substitution);
 *   - empty run; run with no applicable feature; repeated glyphs.
 *
 * A trivial {@link CmapLookup} stub is supplied because the Indic worker
 * constructors precompute reph / before-half glyph ids from the cmap; the stub
 * maps every char code to a fixed sentinel glyph so those constructors run.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> GsubWorkerFuzzProbe <case>
 *
 * Output (UTF-8, stdout), exactly one of:
 *   WORKER\t<SimpleWorkerClassName>\tOUT\t<comma-joined-gids-or-empty>
 *   ERROR\t<SimpleExceptionClassName>
 */
public final class GsubWorkerFuzzProbe {

    /** cmap stub: every char code maps to glyph 0 (a sentinel never in a run). */
    private static final CmapLookup STUB_CMAP = new CmapLookup() {
        @Override
        public int getGlyphId(int characterCode) {
            return 0;
        }

        @Override
        public List<Integer> getCharCodes(int gid) {
            return new ArrayList<>();
        }
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String name = args[0];
        try {
            runCase(name, out);
        } catch (Throwable t) {
            out.printf("ERROR\t%s%n", t.getClass().getSimpleName());
        }
    }

    private static void runCase(String name, PrintStream out) {
        switch (name) {
            // --- Latin worker: ccmp/liga/clig in order ----------------------
            case "latin_empty_run":
                emit(out, Language.LATIN, "latn", ligaMap(), run());
                return;
            case "latin_no_match":
                emit(out, Language.LATIN, "latn", ligaMap(), run(1, 2, 3));
                return;
            case "latin_ligature":
                emit(out, Language.LATIN, "latn", ligaMap(), run(10, 11));
                return;
            case "latin_ligature_in_context":
                emit(out, Language.LATIN, "latn", ligaMap(), run(7, 10, 11, 8));
                return;
            case "latin_repeated_glyphs":
                emit(out, Language.LATIN, "latn", ligaMap(), run(30, 30, 30));
                return;
            case "latin_no_features":
                // feature map empty -> every feature unsupported -> identity.
                emit(out, Language.LATIN, "latn",
                        new LinkedHashMap<>(), run(10, 11, 30));
                return;
            case "latin_feature_order_ccmp_then_liga":
                // ccmp: [5]->10 ; liga: [10,11]->100.  input [5,11]:
                //   ccmp first  -> [10,11] -> liga -> [100]
                //   (wrong order -> [10,11] would survive).
                emit(out, Language.LATIN, "latn", ccmpThenLigaMap(), run(5, 11));
                return;
            case "latin_only_clig":
                // only clig present; liga/ccmp absent -> clig still applies.
                emit(out, Language.LATIN, "latn", cligOnlyMap(), run(40, 41));
                return;

            // --- DFLT worker: ccmp/liga/clig/calt in order ------------------
            case "dflt_ligature":
                emit(out, Language.DFLT, "DFLT", ligaMap(), run(10, 11));
                return;
            case "dflt_calt_applies":
                // calt is DFLT-only (Latin lacks it); [40,41]->600 via calt.
                emit(out, Language.DFLT, "DFLT", caltOnlyMap(), run(40, 41));
                return;
            case "dflt_empty_run":
                emit(out, Language.DFLT, "DFLT", ligaMap(), run());
                return;

            // --- Unknown language -> DefaultGsubWorker (no substitution) ----
            case "unspecified_no_substitution":
                emit(out, Language.UNSPECIFIED, "zzzz", ligaMap(), run(10, 11));
                return;
            case "unspecified_empty_run":
                emit(out, Language.UNSPECIFIED, "zzzz", ligaMap(), run());
                return;

            // --- Bengali worker (Indic; reph/before-half from cmap stub) ----
            // The stub cmap maps every char to gid 0, so the reposition passes
            // are effectively inert on a numeric run that never contains 0.
            case "bengali_ligature":
                emit(out, Language.BENGALI, "bng2", bengaliMap(), run(10, 11));
                return;
            case "bengali_no_match":
                emit(out, Language.BENGALI, "bng2", bengaliMap(), run(1, 2, 3));
                return;
            case "bengali_empty_run":
                emit(out, Language.BENGALI, "bng2", bengaliMap(), run());
                return;

            // --- Devanagari worker ------------------------------------------
            case "devanagari_ligature":
                emit(out, Language.DEVANAGARI, "dev2", devaMap(), run(10, 11));
                return;
            case "devanagari_no_features":
                emit(out, Language.DEVANAGARI, "dev2",
                        new LinkedHashMap<>(), run(10, 11));
                return;

            // --- Gujarati worker --------------------------------------------
            case "gujarati_ligature":
                emit(out, Language.GUJARATI, "gjr2", devaMap(), run(10, 11));
                return;

            default:
                throw new IllegalArgumentException("unknown case: " + name);
        }
    }

    /** liga feature only: [10,11]->100, [30]->400. */
    private static Map<String, Map<List<Integer>, Integer>> ligaMap() {
        Map<String, Map<List<Integer>, Integer>> m = new LinkedHashMap<>();
        Map<List<Integer>, Integer> liga = new LinkedHashMap<>();
        liga.put(run(10, 11), 100);
        liga.put(run(30), 400);
        m.put("liga", liga);
        return m;
    }

    /** ccmp ([5]->10) plus liga ([10,11]->100): pins ccmp-before-liga order. */
    private static Map<String, Map<List<Integer>, Integer>> ccmpThenLigaMap() {
        Map<String, Map<List<Integer>, Integer>> m = new LinkedHashMap<>();
        Map<List<Integer>, Integer> ccmp = new LinkedHashMap<>();
        ccmp.put(run(5), 10);
        m.put("ccmp", ccmp);
        Map<List<Integer>, Integer> liga = new LinkedHashMap<>();
        liga.put(run(10, 11), 100);
        m.put("liga", liga);
        return m;
    }

    /** clig only: [40,41]->500. */
    private static Map<String, Map<List<Integer>, Integer>> cligOnlyMap() {
        Map<String, Map<List<Integer>, Integer>> m = new LinkedHashMap<>();
        Map<List<Integer>, Integer> clig = new LinkedHashMap<>();
        clig.put(run(40, 41), 500);
        m.put("clig", clig);
        return m;
    }

    /** calt only: [40,41]->600 (DFLT applies calt; Latin does not). */
    private static Map<String, Map<List<Integer>, Integer>> caltOnlyMap() {
        Map<String, Map<List<Integer>, Integer>> m = new LinkedHashMap<>();
        Map<List<Integer>, Integer> calt = new LinkedHashMap<>();
        calt.put(run(40, 41), 600);
        m.put("calt", calt);
        return m;
    }

    /** Bengali feature in pipeline: pres ([10,11]->100). */
    private static Map<String, Map<List<Integer>, Integer>> bengaliMap() {
        Map<String, Map<List<Integer>, Integer>> m = new LinkedHashMap<>();
        Map<List<Integer>, Integer> pres = new LinkedHashMap<>();
        pres.put(run(10, 11), 100);
        m.put("pres", pres);
        return m;
    }

    /** Devanagari/Gujarati feature in pipeline: pres ([10,11]->100). */
    private static Map<String, Map<List<Integer>, Integer>> devaMap() {
        Map<String, Map<List<Integer>, Integer>> m = new LinkedHashMap<>();
        Map<List<Integer>, Integer> pres = new LinkedHashMap<>();
        pres.put(run(10, 11), 100);
        m.put("pres", pres);
        return m;
    }

    private static void emit(PrintStream out, Language language,
            String scriptName, Map<String, Map<List<Integer>, Integer>> features,
            List<Integer> glyphs) {
        MapBackedGsubData data = new MapBackedGsubData(language, scriptName, features);
        GsubWorker worker = new GsubWorkerFactory().getGsubWorker(STUB_CMAP, data);
        List<Integer> result = worker.applyTransforms(glyphs);
        out.printf("WORKER\t%s\tOUT\t%s%n",
                worker.getClass().getSimpleName(), join(result));
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
}
