import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.CFFParser;

/**
 * Live oracle probe for CFF <em>subset projection</em> facts against Apache
 * PDFBox 3.0.7's own CFF parser.
 *
 * <p><b>Why a projection and not a real subset builder.</b> Apache PDFBox
 * 3.0.7 ships <em>no</em> public CFF subset-embed builder. {@code
 * PDType0Font.subset()} only handles {@code /CIDFontType2} (TrueType {@code
 * glyf}); a CFF descendant ({@code /CIDFontType0}) is rejected (pypdfbox
 * mirrors this with a {@code ValueError}). So there is no PDFBox API that
 * emits subset CFF bytes to diff against. The honest differential target is
 * therefore the set of <em>facts a CFF subsetter must compute</em> &mdash; the
 * data both engines expose identically from a parsed CFF:
 *
 * <ul>
 *   <li>the kept-glyph set after applying the standard subset rule
 *       (.notdef/GID&nbsp;0 always retained, out-of-range GIDs dropped,
 *       duplicates collapsed);</li>
 *   <li>the resulting charstring count of the subset;</li>
 *   <li>the GID remapping old&rarr;new (kept GIDs sorted ascending, then
 *       renumbered 0..k-1 &mdash; the canonical glyph-order subset);</li>
 *   <li>the charset glyph name at each new GID;</li>
 *   <li>whether the source font is CID-keyed.</li>
 * </ul>
 *
 * These are computed from {@code CFFFont.getNumCharStrings()} and {@code
 * CFFFont.getCharset().getNameForGID(gid)} &mdash; the same primitives a
 * real subsetter walks &mdash; so pypdfbox's projection can be diffed
 * line-for-line on identical inputs.
 *
 * <pre>
 *   java -cp ... CffSubsetterFuzzProbe project &lt;font.cff&gt;
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order):
 *
 *   FONT  \t numGlyphs \t isCID
 *   CASE  \t name \t keptCount
 *       keptCount = charstring count of the projected subset.
 *   MAP   \t name \t oldGid \t newGid          (one per kept glyph, by newGid)
 *   GNAME \t name \t newGid \t glyphName       (charset name at that new GID)
 *   ERR   \t name \t exceptionSimpleName       (projection threw)
 *
 * Never mutates anything; parses one in-memory CFF program.
 */
public final class CffSubsetterFuzzProbe {

    /**
     * Glyph-selection cases. The int[] is the raw requested GID set (may
     * contain duplicates, out-of-range, and high values). The subset rule
     * forces GID 0 (.notdef) in and drops anything &ge; numGlyphs.
     */
    private static final Map<String, int[]> CASES = new LinkedHashMap<>();

    static {
        CASES.put("empty", new int[] {});
        CASES.put("notdef_only", new int[] {0});
        CASES.put("single_g1", new int[] {1});
        CASES.put("single_high", new int[] {2});
        CASES.put("pair", new int[] {1, 2});
        CASES.put("triple", new int[] {1, 2, 3});
        CASES.put("with_dups", new int[] {1, 1, 2, 2, 2});
        CASES.put("unsorted", new int[] {3, 1, 2});
        CASES.put("zero_and_more", new int[] {0, 1, 2});
        CASES.put("gid_past_count", new int[] {1, 999999});
        CASES.put("all_oob", new int[] {500000, 600000});
        CASES.put("negative_dropped", new int[] {-1, 1});
        CASES.put("near_count_minus1", new int[] {-1}); // resolved to last gid
        CASES.put("near_count", new int[] {-2});        // resolved to last-1
        CASES.put("spread", new int[] {1, 5, 10, 20});
        CASES.put("full_set", new int[] {-100});        // sentinel => every gid
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 2 || !"project".equals(args[0])) {
            out.println("usage: CffSubsetterFuzzProbe project <font.cff>");
            return;
        }
        byte[] payload = Files.readAllBytes(Paths.get(args[1]));
        CFFFont font = new CFFParser().parse(payload,
                new CFFParser.ByteSource() {
                    @Override
                    public byte[] getBytes() {
                        return payload;
                    }
                }).get(0);

        int numGlyphs = font.getNumCharStrings();
        boolean isCid = font.getCharset().isCIDFont();
        out.printf("FONT\t%d\t%b%n", numGlyphs, isCid);

        for (Map.Entry<String, int[]> e : CASES.entrySet()) {
            String name = e.getKey();
            try {
                List<Integer> kept = project(e.getValue(), numGlyphs);
                out.printf("CASE\t%s\t%d%n", name, kept.size());
                int newGid = 0;
                for (int oldGid : kept) {
                    out.printf("MAP\t%s\t%d\t%d%n", name, oldGid, newGid);
                    newGid++;
                }
                // Charset glyph names at the first few new GIDs.
                int sampleMax = Math.min(kept.size(), 6);
                for (int g = 0; g < sampleMax; g++) {
                    int oldGid = kept.get(g);
                    String gn = font.getCharset().getNameForGID(oldGid);
                    out.printf("GNAME\t%s\t%d\t%s%n", name, g, gn);
                }
            } catch (Exception ex) {
                out.printf("ERR\t%s\t%s%n", name, ex.getClass().getSimpleName());
            }
        }
    }

    /**
     * Apply the canonical subset rule to a raw requested GID set.
     *
     * <p>Rules (the minimal contract any CFF subsetter honours):
     * <ul>
     *   <li>GID 0 (.notdef) is always retained.</li>
     *   <li>A request of {@code -1} resolves to {@code numGlyphs-1} (the
     *       last glyph), {@code -2} to {@code numGlyphs-2}, etc. &mdash; a
     *       compact "from the end" addressing used by the fuzz cases. A
     *       large-magnitude negative ({@code <= -100}) is the "full set"
     *       sentinel and selects every GID.</li>
     *   <li>Out-of-range positive GIDs ({@code >= numGlyphs}) are dropped.</li>
     *   <li>Duplicates collapse; the result is sorted ascending then the
     *       new GIDs are 0..k-1 in that order.</li>
     * </ul>
     */
    private static List<Integer> project(int[] requested, int numGlyphs) {
        TreeSet<Integer> kept = new TreeSet<>();
        kept.add(0); // .notdef always present
        for (int g : requested) {
            if (g <= -100) {
                for (int i = 0; i < numGlyphs; i++) {
                    kept.add(i);
                }
            } else if (g < 0) {
                int resolved = numGlyphs + g;
                if (resolved >= 0 && resolved < numGlyphs) {
                    kept.add(resolved);
                }
            } else if (g < numGlyphs) {
                kept.add(g);
            }
            // g >= numGlyphs: dropped.
        }
        return new ArrayList<>(kept);
    }
}
