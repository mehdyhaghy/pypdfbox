import java.io.PrintStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Array;
import org.apache.fontbox.cff.FDSelect;

/**
 * Live oracle probe for the CID-keyed CFF /FDSelect glyph&rarr;font-dict
 * mapping algorithm under malformed / edge inputs.
 *
 * <p>Unlike {@link CffCidFdProbe} (which parses a whole well-formed raw CFF
 * program and walks {@code getFDIndex} over its real GID range), this probe
 * constructs Apache PDFBox's two concrete {@code FDSelect} implementations
 * directly &mdash; {@code CFFParser$Format0FDSelect(int[])} and
 * {@code CFFParser$Format3FDSelect(Range3[], int sentinel)} &mdash; via
 * reflection (their constructors are package/private inner-class
 * constructors). This lets us feed deliberately malformed payloads that a
 * normal CFF parse would never produce or would reject before the FDSelect is
 * built:
 *
 * <ul>
 *   <li>Format 0 arrays shorter / longer than the glyph sweep range;</li>
 *   <li>Format 3 ranges out of order, overlapping, first != 0, count
 *       mismatch, sentinel smaller than the last range first;</li>
 *   <li>FD indices that point past any real /FDArray bound (FDSelect itself
 *       does not validate the index against the FDArray &mdash; it returns
 *       whatever byte/value the on-disk record carries);</li>
 *   <li>negative and far-past-sentinel glyph indices in the sweep.</li>
 * </ul>
 *
 * <p>The contract under test is purely the {@code getFDIndex(int gid)}
 * resolution algorithm: which FD index each GID maps to, including the
 * upstream sentinel quirk (Format 3 returns -1 for a GID that lands in the
 * last range but is at or past the sentinel, and 0 when no range matches).
 *
 * <pre>
 *   java -cp ... CffFdSelectFuzzProbe sweep
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order):
 *
 *   CASE \t name \t format
 *   FD   \t name \t gid \t fdIndex          (one per swept gid)
 *   ERR  \t name \t exceptionSimpleName     (construction / call threw)
 *
 * Never mutates anything; builds in-memory objects only.
 */
public final class CffFdSelectFuzzProbe {

    /** Glyph indices swept for every case (covers in-range, boundary,
     * past-sentinel and negative). */
    private static final int[] SWEEP = {
        -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 50, 255, 256, 1000,
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1 || !"sweep".equals(args[0])) {
            out.println("usage: CffFdSelectFuzzProbe sweep");
            return;
        }
        sweep(out);
    }

    private static void sweep(PrintStream out) throws Exception {
        // ---- Format 0 cases: flat per-GID byte array. ----
        format0(out, "f0_empty", new int[] {});
        format0(out, "f0_single", new int[] {0});
        format0(out, "f0_simple4", new int[] {0, 0, 1, 1});
        format0(out, "f0_three", new int[] {0, 0, 0, 1, 1, 2, 2, 2});
        // Array shorter than the sweep range -> in-bounds resolves, out
        // returns 0 (PDFBox guards with gid < fds.length implicitly? -> it
        // indexes fds[gid] directly; we record exactly what it does).
        format0(out, "f0_short", new int[] {2, 1});
        // fd index past any FDArray bound -> FDSelect does not validate.
        format0(out, "f0_fd_oob", new int[] {0, 5, 99, 200});
        // Long, non-monotonic.
        format0(out, "f0_zigzag", new int[] {3, 0, 2, 1, 4, 0, 1, 3});
        // All same high fd.
        format0(out, "f0_alln", new int[] {7, 7, 7, 7});

        // ---- Format 3 cases: [first, fd] ranges + sentinel. ----
        // Well-formed: [0,0)[2,1) sentinel 4 -> gid 0,1->0 ; 2,3->1.
        format3(out, "f3_simple", new int[][] {{0, 0}, {2, 1}}, 4);
        // Three ranges.
        format3(out, "f3_three",
                new int[][] {{0, 0}, {3, 1}, {5, 2}}, 8);
        // first != 0 (range starts above gid 0) -> gids below first => 0.
        format3(out, "f3_first_not_zero",
                new int[][] {{2, 1}, {5, 2}}, 8);
        // sentinel == last.first (zero-width final range).
        format3(out, "f3_sentinel_eq_last",
                new int[][] {{0, 0}, {4, 1}}, 4);
        // sentinel < last.first (sentinel smaller than the final range start).
        format3(out, "f3_sentinel_lt_last",
                new int[][] {{0, 0}, {6, 1}}, 4);
        // sentinel == 0 with a real range.
        format3(out, "f3_sentinel_zero",
                new int[][] {{0, 0}, {2, 1}}, 0);
        // Out-of-order ranges (descending firsts) -> exercises the linear
        // walk with non-monotonic data.
        format3(out, "f3_out_of_order",
                new int[][] {{5, 2}, {2, 1}, {0, 0}}, 8);
        // Overlapping ranges (next.first <= this.first).
        format3(out, "f3_overlap",
                new int[][] {{0, 0}, {0, 1}, {3, 2}}, 6);
        // Overlap where the second range starts inside the first.
        format3(out, "f3_overlap2",
                new int[][] {{0, 0}, {2, 1}, {1, 2}}, 6);
        // Empty range array, positive sentinel.
        format3(out, "f3_empty_ranges", new int[][] {}, 4);
        // Empty range array, zero sentinel.
        format3(out, "f3_empty_zero", new int[][] {}, 0);
        // Single range covering everything.
        format3(out, "f3_single_all", new int[][] {{0, 0}}, 256);
        // Single range, first != 0.
        format3(out, "f3_single_offset", new int[][] {{3, 1}}, 8);
        // fd index past any FDArray bound.
        format3(out, "f3_fd_oob",
                new int[][] {{0, 9}, {2, 200}}, 4);
        // Duplicate firsts (degenerate range).
        format3(out, "f3_dup_first",
                new int[][] {{0, 0}, {2, 1}, {2, 2}}, 5);
        // Large sentinel, gaps after last range.
        format3(out, "f3_big_sentinel",
                new int[][] {{0, 0}, {2, 1}}, 1000);
        // Range first beyond sentinel for the FIRST range.
        format3(out, "f3_first_beyond_sentinel",
                new int[][] {{10, 0}, {20, 1}}, 5);
        // sentinel exactly at a swept boundary (256).
        format3(out, "f3_sentinel_256",
                new int[][] {{0, 0}, {128, 1}}, 256);
        // Negative fd value (CFF cannot encode this, but FDSelect stores int).
        format3(out, "f3_negative_fd",
                new int[][] {{0, -1}, {2, 0}}, 4);
        // Two ranges, second.first == first.first + 1 (tight).
        format3(out, "f3_tight",
                new int[][] {{0, 0}, {1, 1}, {2, 0}, {3, 1}}, 4);
    }

    private static void format0(PrintStream out, String name, int[] fds)
            throws Exception {
        out.printf("CASE\t%s\t%d%n", name, 0);
        FDSelect sel;
        try {
            sel = newFormat0(fds);
        } catch (Throwable t) {
            out.printf("ERR\t%s\t%s%n", name, simple(t));
            return;
        }
        emit(out, name, sel);
    }

    private static void format3(PrintStream out, String name, int[][] ranges,
            int sentinel) throws Exception {
        out.printf("CASE\t%s\t%d%n", name, 3);
        FDSelect sel;
        try {
            sel = newFormat3(ranges, sentinel);
        } catch (Throwable t) {
            out.printf("ERR\t%s\t%s%n", name, simple(t));
            return;
        }
        emit(out, name, sel);
    }

    private static void emit(PrintStream out, String name, FDSelect sel) {
        for (int gid : SWEEP) {
            try {
                int fd = sel.getFDIndex(gid);
                out.printf("FD\t%s\t%d\t%d%n", name, gid, fd);
            } catch (Throwable t) {
                out.printf("FD\t%s\t%d\tERR:%s%n", name, gid, simple(t));
            }
        }
    }

    private static String simple(Throwable t) {
        Throwable c = (t.getCause() != null) ? t.getCause() : t;
        return c.getClass().getSimpleName();
    }

    // ---- reflective construction of the package-private inner classes ----

    private static final String PKG = "org.apache.fontbox.cff.CFFParser";

    private static FDSelect newFormat0(int[] fds) throws Exception {
        Class<?> cls = Class.forName(PKG + "$Format0FDSelect");
        Constructor<?> ctor = cls.getDeclaredConstructor(int[].class);
        ctor.setAccessible(true);
        return (FDSelect) ctor.newInstance((Object) fds);
    }

    private static FDSelect newFormat3(int[][] ranges, int sentinel)
            throws Exception {
        Class<?> rangeCls = Class.forName(PKG + "$Range3");
        Constructor<?> rangeCtor =
                rangeCls.getDeclaredConstructor(int.class, int.class);
        rangeCtor.setAccessible(true);
        Object arr = Array.newInstance(rangeCls, ranges.length);
        for (int i = 0; i < ranges.length; i++) {
            Object r = rangeCtor.newInstance(ranges[i][0], ranges[i][1]);
            Array.set(arr, i, r);
        }
        Class<?> cls = Class.forName(PKG + "$Format3FDSelect");
        Constructor<?> ctor = cls.getDeclaredConstructor(
                Array.newInstance(rangeCls, 0).getClass(), int.class);
        ctor.setAccessible(true);
        return (FDSelect) ctor.newInstance(arr, sentinel);
    }

    private CffFdSelectFuzzProbe() {
    }
}
