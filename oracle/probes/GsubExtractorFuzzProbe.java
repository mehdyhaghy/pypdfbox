import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import org.apache.fontbox.ttf.gsub.GlyphSubstitutionDataExtractor;
import org.apache.fontbox.ttf.model.GsubData;
import org.apache.fontbox.ttf.model.ScriptFeature;
import org.apache.fontbox.ttf.table.common.CoverageTable;
import org.apache.fontbox.ttf.table.common.CoverageTableFormat1;
import org.apache.fontbox.ttf.table.common.FeatureListTable;
import org.apache.fontbox.ttf.table.common.FeatureRecord;
import org.apache.fontbox.ttf.table.common.FeatureTable;
import org.apache.fontbox.ttf.table.common.LangSysTable;
import org.apache.fontbox.ttf.table.common.LookupListTable;
import org.apache.fontbox.ttf.table.common.LookupSubTable;
import org.apache.fontbox.ttf.table.common.LookupTable;
import org.apache.fontbox.ttf.table.common.ScriptTable;
import org.apache.fontbox.ttf.table.gsub.LookupTypeSingleSubstFormat1;
import org.apache.fontbox.ttf.table.gsub.LookupTypeSingleSubstFormat2;

/**
 * Live oracle probe for the substitution-data level of FontBox's
 * {@code GlyphSubstitutionDataExtractor}.
 *
 * Where {@code GsubSubstitutionProbe} drives the whole
 * {@code GlyphSubstitutionTable.getGsubData(scriptTag)} pipeline over a real
 * font, this probe constructs <em>malformed</em> ScriptTable / FeatureListTable
 * / LookupListTable graphs directly and feeds them to the extractor's two
 * public {@code getGsubData} overloads. The aim is to pin how the extractor
 * itself behaves on:
 *
 *   - an empty script-list map
 *   - a script with no default LangSys
 *   - a feature referencing an out-of-range lookup index
 *   - a LangSys referencing an out-of-range feature index
 *   - an unsupported / unknown script tag
 *   - a lookup of an unhandled type (e.g. Type 2 multiple)
 *   - duplicate feature tags (later record overrides earlier in the map)
 *   - a script with no enabled features
 *   - a FeatureRecord whose FeatureTable is null
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> GsubExtractorFuzzProbe <case>
 *
 * Output (UTF-8, stdout), one of:
 *   RESULT\tNO_DATA                              (getGsubData returned null/NO_DATA_FOUND)
 *   RESULT\t<scriptName>\t<language>             then per supported feature/sub:
 *     FEATURE\t<tag>\t<count>
 *     SUB\t<tag>\t<run>\t<sub>
 *   ERROR\t<SimpleExceptionClassName>            (extractor threw)
 */
public final class GsubExtractorFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String name = args[0];
        try {
            GsubData data = runCase(name);
            emit(out, data);
        } catch (Throwable t) {
            out.printf("ERROR\t%s%n", t.getClass().getSimpleName());
        }
    }

    private static GsubData runCase(String name) {
        GlyphSubstitutionDataExtractor extractor = new GlyphSubstitutionDataExtractor();
        switch (name) {
            case "empty_script_list":
                return extractor.getGsubData(
                        new LinkedHashMap<String, ScriptTable>(),
                        featureList(record("liga", featureTable(0))),
                        lookupList(singleF1Lookup()));
            case "unknown_script_tag": {
                Map<String, ScriptTable> sl = new LinkedHashMap<>();
                sl.put("zzzz", script(langSys(0), null));
                return extractor.getGsubData(sl,
                        featureList(record("liga", featureTable(0))),
                        lookupList(singleF1Lookup()));
            }
            case "no_default_langsys": {
                // explicit-script overload; script has no default LangSys and
                // no per-language LangSys -> empty substitution map.
                return extractor.getGsubData("latn",
                        script(null, null),
                        featureList(record("liga", featureTable(0))),
                        lookupList(singleF1Lookup()));
            }
            case "no_features": {
                // default LangSys with zero feature indices.
                return extractor.getGsubData("latn",
                        script(langSys(), null),
                        featureList(record("liga", featureTable(0))),
                        lookupList(singleF1Lookup()));
            }
            case "feature_index_out_of_range": {
                // LangSys references feature index 5 but only 1 feature exists.
                return extractor.getGsubData("latn",
                        script(langSys(5), null),
                        featureList(record("liga", featureTable(0))),
                        lookupList(singleF1Lookup()));
            }
            case "lookup_index_out_of_range": {
                // feature references lookup index 9 but only 1 lookup exists.
                return extractor.getGsubData("latn",
                        script(langSys(0), null),
                        featureList(record("liga", featureTable(9))),
                        lookupList(singleF1Lookup()));
            }
            case "unhandled_lookup_type": {
                // lookupType 2 with a Single subtable shell -> extractor's
                // dispatch ignores anything not matching its instanceof chain
                // by *subtable class*, not lookupType; here the subtable IS a
                // Single one wrapped under type 2, so it is still extracted.
                // To exercise the "unhandled" branch we use a real type-2
                // shell with a subtable class the extractor does not handle.
                LookupTable lt = new LookupTable(2, 0, 0,
                        new LookupSubTable[] { new UnhandledSubTable() });
                return extractor.getGsubData("latn",
                        script(langSys(0), null),
                        featureList(record("liga", featureTable(0))),
                        lookupList(lt));
            }
            case "duplicate_feature_tags": {
                // two records with the same tag "liga": the later wins in the
                // LinkedHashMap keyed by feature tag.
                return extractor.getGsubData("latn",
                        script(langSys(0, 1), null),
                        featureList(
                                record("liga", featureTable(0)),
                                record("liga", featureTable(1))),
                        lookupList(singleF1Lookup(), singleF2Lookup()));
            }
            case "null_feature_table": {
                // a FeatureRecord whose FeatureTable is null.
                return extractor.getGsubData("latn",
                        script(langSys(0), null),
                        featureList(new FeatureRecord("liga", null)),
                        lookupList(singleF1Lookup()));
            }
            case "single_f2_size_mismatch": {
                // SingleSubstFormat2 where substituteGlyphIDs count differs
                // from coverage size -> extractor logs and skips.
                CoverageTable cov = new CoverageTableFormat1(2, new int[] { 10, 11 });
                LookupSubTable st = new LookupTypeSingleSubstFormat2(2, cov,
                        new int[] { 100 });
                LookupTable lt = new LookupTable(1, 0, 0, new LookupSubTable[] { st });
                return extractor.getGsubData("latn",
                        script(langSys(0), null),
                        featureList(record("liga", featureTable(0))),
                        lookupList(lt));
            }
            default:
                throw new IllegalArgumentException("unknown case: " + name);
        }
    }

    // A LookupSubTable subclass the extractor's instanceof chain never matches.
    private static final class UnhandledSubTable extends LookupSubTable {
        UnhandledSubTable() {
            super(0, null);
        }

        @Override
        public int doSubstitution(int gid, int n) {
            return gid;
        }
    }

    private static void emit(PrintStream out, GsubData data) {
        if (data == null || data == GsubData.NO_DATA_FOUND) {
            out.printf("RESULT\tNO_DATA%n");
            return;
        }
        out.printf("RESULT\t%s\t%s%n",
                String.valueOf(data.getActiveScriptName()),
                String.valueOf(data.getLanguage()));
        Set<String> features = new TreeSet<>(data.getSupportedFeatures());
        for (String tag : features) {
            ScriptFeature feature = data.getFeature(tag);
            Set<List<Integer>> runs = feature.getAllGlyphIdsForSubstitution();
            out.printf("FEATURE\t%s\t%d%n", tag, runs.size());
            List<List<Integer>> sorted = new ArrayList<>(runs);
            sorted.sort(new Comparator<List<Integer>>() {
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
            for (List<Integer> run : sorted) {
                Integer sub = feature.getReplacementForGlyphs(run);
                out.printf("SUB\t%s\t%s\t%d%n", tag, joinRun(run), sub);
            }
        }
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

    // --- builders -------------------------------------------------------

    private static LangSysTable langSys(int... featureIndices) {
        return new LangSysTable(0, 0xFFFF, featureIndices.length, featureIndices);
    }

    private static ScriptTable script(LangSysTable def,
            Map<String, LangSysTable> langSysTables) {
        Map<String, LangSysTable> m = langSysTables == null
                ? new LinkedHashMap<String, LangSysTable>()
                : langSysTables;
        return new ScriptTable(def, m);
    }

    private static FeatureTable featureTable(int... lookupIndices) {
        return new FeatureTable(0, lookupIndices.length, lookupIndices);
    }

    private static FeatureRecord record(String tag, FeatureTable ft) {
        return new FeatureRecord(tag, ft);
    }

    private static FeatureListTable featureList(FeatureRecord... records) {
        return new FeatureListTable(records.length, records);
    }

    private static LookupListTable lookupList(LookupTable... lookups) {
        return new LookupListTable(lookups.length, lookups);
    }

    private static LookupTable singleF1Lookup() {
        // coverage {10,11,12}, delta +5 -> 10->15, 11->16, 12->17
        CoverageTable cov = new CoverageTableFormat1(3, new int[] { 10, 11, 12 });
        LookupSubTable st = new LookupTypeSingleSubstFormat1(1, cov, (short) 5);
        return new LookupTable(1, 0, 0, new LookupSubTable[] { st });
    }

    private static LookupTable singleF2Lookup() {
        // coverage {20,21}, subs {200,201} -> 20->200, 21->201
        CoverageTable cov = new CoverageTableFormat1(2, new int[] { 20, 21 });
        LookupSubTable st = new LookupTypeSingleSubstFormat2(2, cov,
                new int[] { 200, 201 });
        return new LookupTable(1, 0, 0, new LookupSubTable[] { st });
    }
}
