import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.fontbox.ttf.VerticalHeaderTable;
import org.apache.fontbox.ttf.VerticalMetricsTable;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;

/**
 * Live oracle probe: emit Apache FontBox's parsed {@code vhea} (vertical header)
 * and {@code vmtx} (vertical metrics) tables in a canonical line-oriented format
 * that pypdfbox's {@code VerticalHeaderTable} / {@code VerticalMetricsTable}
 * mirror.
 *
 * Recent waves pinned {@code hmtx}, {@code glyf}, {@code kern}, {@code cmap},
 * {@code OS/2}, and {@code head}/{@code maxp}; this probe targets the vertical
 * writing-mode metrics tables.
 *
 * The interesting parity surface is the {@code vmtx} trailing-TSB compression:
 * the table stores {@code numberOfVMetrics} (advanceHeight, topSideBearing)
 * pairs followed by a TSB-only array for the remaining glyphs (which all share
 * the last advance height). So {@code getTopSideBearing(gid)} for
 * {@code gid >= numberOfVMetrics} must read the trailing TSB array while
 * {@code getAdvanceHeight} clamps to the last advance height. The probed GID set
 * straddles {@code numberOfVMetrics} to exercise both branches.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> VheaVmtxProbe font.ttf
 *
 * Output (UTF-8, stdout): one TAB-separated KEY\tVALUE line per accessor for
 * vhea, then per-GID {@code VM \t gid \t advanceHeight \t topSideBearing}.
 */
public final class VheaVmtxProbe {
    private static final int GID_CAP = 256;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (TrueTypeFont ttf = new TTFParser().parse(
                new RandomAccessReadBufferedFile(new File(args[0])))) {
            int numGlyphs = ttf.getNumberOfGlyphs();

            VerticalHeaderTable vhea = ttf.getVerticalHeader();
            if (vhea == null) {
                out.println("vhea\tabsent");
            } else {
                out.println("vhea\tpresent");
                out.println("vhea.version\t" + vhea.getVersion());
                out.println("vhea.ascender\t" + vhea.getAscender());
                out.println("vhea.descender\t" + vhea.getDescender());
                out.println("vhea.lineGap\t" + vhea.getLineGap());
                out.println("vhea.advanceHeightMax\t" + vhea.getAdvanceHeightMax());
                out.println("vhea.minTopSideBearing\t" + vhea.getMinTopSideBearing());
                out.println("vhea.minBottomSideBearing\t" + vhea.getMinBottomSideBearing());
                out.println("vhea.yMaxExtent\t" + vhea.getYMaxExtent());
                out.println("vhea.caretSlopeRise\t" + vhea.getCaretSlopeRise());
                out.println("vhea.caretSlopeRun\t" + vhea.getCaretSlopeRun());
                out.println("vhea.caretOffset\t" + vhea.getCaretOffset());
                out.println("vhea.reserved1\t" + vhea.getReserved1());
                out.println("vhea.reserved2\t" + vhea.getReserved2());
                out.println("vhea.reserved3\t" + vhea.getReserved3());
                out.println("vhea.reserved4\t" + vhea.getReserved4());
                out.println("vhea.metricDataFormat\t" + vhea.getMetricDataFormat());
                out.println("vhea.numberOfVMetrics\t" + vhea.getNumberOfVMetrics());
            }

            VerticalMetricsTable vmtx = ttf.getVerticalMetrics();
            if (vmtx == null) {
                out.println("vmtx\tabsent");
            } else {
                out.println("vmtx\tpresent");
                int numVMetrics = vhea == null ? 0 : vhea.getNumberOfVMetrics();
                int upper = Math.min(numGlyphs, GID_CAP);
                for (int gid : gids(numGlyphs, numVMetrics, upper)) {
                    String adv;
                    String tsb;
                    try {
                        adv = Integer.toString(vmtx.getAdvanceHeight(gid));
                        tsb = Integer.toString(vmtx.getTopSideBearing(gid));
                    } catch (Exception e) {
                        adv = "ERR";
                        tsb = "ERR";
                    }
                    out.println("VM\t" + gid + "\t" + adv + "\t" + tsb);
                }
            }
        }
    }

    /**
     * GIDs straddling {@code numVMetrics}: leading GIDs [0, upper), plus the
     * boundary GIDs (numVMetrics-1, numVMetrics, numVMetrics+1) so both the
     * in-range (advance,TSB) pair path and the trailing-TSB-only path are
     * exercised. De-duplicated, insertion order preserved.
     */
    private static int[] gids(int numGlyphs, int numVMetrics, int upper) {
        java.util.LinkedHashSet<Integer> set = new java.util.LinkedHashSet<>();
        for (int g = 0; g < upper; g++) {
            set.add(g);
        }
        for (int b : new int[] {numVMetrics - 1, numVMetrics, numVMetrics + 1}) {
            if (b >= 0 && b < numGlyphs) {
                set.add(b);
            }
        }
        int[] arr = new int[set.size()];
        int i = 0;
        for (int g : set) {
            arr[i++] = g;
        }
        return arr;
    }
}
