import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.KerningSubtable;
import org.apache.fontbox.ttf.KerningTable;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;

/**
 * Live oracle probe: emit Apache PDFBox FontBox's TrueType {@code kern} table
 * decode for a font file on disk.
 *
 * Targets the format-0 horizontal kerning subtable surface:
 *   - {@link KerningTable#getVersion} is not public, so we emit the subtable
 *     count and the selected horizontal subtable's coverage as observed
 *     through the only public coverage accessors upstream exposes
 *     ({@link KerningSubtable#isHorizontalKerning()} and the cross-stream
 *     overload).
 *   - {@link KerningSubtable#getKerning(int, int)} per ordered GID pair (the
 *     binary-search lookup over the sorted pair list).
 *   - {@link KerningSubtable#getKerning(int[])} for a glyph sequence (the
 *     "Nth adjustment is between glyph N and the next non-negative glyph"
 *     contract, including a -1 sentinel that must be skipped).
 *
 * The font is loaded with {@link TTFParser#parse} (NOT parseEmbedded) so the
 * full on-disk table set — including {@code kern} — is available.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> KernTableProbe font.ttf
 *
 * Output (UTF-8, stdout), deterministic line order:
 *   KERN \t numSubtables
 *   HSUB \t present|absent \t isHorizontalKerning \t isHorizontalKerningCross
 *   PAIR \t left \t right \t value          (one line per probed GID pair)
 *   SEQ  \t i \t adjustment                 (one line per glyph-sequence index)
 * If no kern table or no horizontal subtable, the dependent lines are omitted
 * and HSUB reports "absent".
 */
public final class KernTableProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        TrueTypeFont ttf = new TTFParser()
                .parse(new RandomAccessReadBufferedFile(new File(args[0])));
        try {
            KerningTable kern = ttf.getKerning();
            if (kern == null) {
                out.printf("KERN\t0%n");
                out.printf("HSUB\tabsent\tfalse\tfalse%n");
                return;
            }
            int numGlyphs = ttf.getNumberOfGlyphs();
            // numSubtables is not directly exposed; reflect via the horizontal
            // lookups available. We emit a single 1/0 presence count for the
            // horizontal-kerning subtable selection result.
            KerningSubtable hsub = kern.getHorizontalKerningSubtable();
            KerningSubtable hsubCross = kern.getHorizontalKerningSubtable(true);
            out.printf("KERN\t%d%n", hsub != null ? 1 : 0);
            out.printf("HSUB\t%s\t%b\t%b%n",
                    hsub != null ? "present" : "absent",
                    hsub != null && hsub.isHorizontalKerning(),
                    hsub != null && hsub.isHorizontalKerning(true));
            if (hsub == null) {
                return;
            }
            for (int[] pair : pairs(numGlyphs)) {
                int v = hsub.getKerning(pair[0], pair[1]);
                out.printf("PAIR\t%d\t%d\t%d%n", pair[0], pair[1], v);
            }
            int[] seq = sequence(numGlyphs);
            int[] adj = hsub.getKerning(seq);
            for (int i = 0; i < adj.length; i++) {
                out.printf("SEQ\t%d\t%d%n", i, adj[i]);
            }
        } finally {
            ttf.close();
        }
    }

    /**
     * Deterministic ordered GID pairs covering both kerning hits and misses.
     * A dense grid over low GIDs (where Latin kerning pairs live) plus a few
     * out-of-range / negative-sentinel probes that must clamp to 0.
     */
    private static int[][] pairs(int numGlyphs) {
        java.util.List<int[]> list = new java.util.ArrayList<>();
        int cap = Math.min(numGlyphs, 90);
        for (int l = 0; l < cap; l++) {
            for (int r = 0; r < cap; r++) {
                list.add(new int[] {l, r});
            }
        }
        // Boundary / out-of-range / negative-sentinel pairs (lookup -> 0).
        list.add(new int[] {numGlyphs - 1, 0});
        list.add(new int[] {0, numGlyphs - 1});
        list.add(new int[] {numGlyphs, 0});
        list.add(new int[] {-1, 5});
        list.add(new int[] {5, -1});
        return list.toArray(new int[0][]);
    }

    /**
     * A glyph sequence exercising {@code getKerning(int[])}: the -1 entry is a
     * sentinel that must be skipped when locating the succeeding non-negative
     * glyph (so index i pairs with the next real glyph, not the sentinel).
     */
    private static int[] sequence(int numGlyphs) {
        int a = Math.min(36, numGlyphs - 1); // 'A' region
        int b = Math.min(55, numGlyphs - 1); // 'T' region
        int c = Math.min(3, numGlyphs - 1);  // 'space' region
        return new int[] {c, a, -1, b, a, c};
    }
}
