import java.io.PrintStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import org.apache.fontbox.cff.FDSelect;

/**
 * Live oracle probe for the CID-keyed CFF /FDSelect <em>byte reader</em> in
 * Apache PDFBox &mdash; {@code CFFParser.readFDSelect(DataInput, int nGlyphs)}
 * and the Format0 / Format3 sub-readers it dispatches to.
 *
 * <p>The sibling {@code CffFdSelectFuzzProbe} builds the concrete
 * {@code Format0FDSelect} / {@code Format3FDSelect} objects directly via
 * reflection and exercises only {@code getFDIndex}. This probe instead feeds
 * raw on-disk FDSelect <em>bytes</em> (the format byte + the Format-0 per-glyph
 * array, or the Format-3 nRanges + [first, fd] records + sentinel) through the
 * package-private {@code CFFParser.readFDSelect(DataInput, int)} reader, then
 * sweeps {@code getFDIndex} over the resulting object. This is the surface a
 * normal CFF parse walks &mdash; the wrapper class chosen, the sentinel /
 * nRanges parsing, and the dispatch on an unknown format byte.
 *
 * <pre>
 *   java -cp ... CffFdSelectBytesProbe sweep
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order):
 *
 *   CASE \t name \t cls               (concrete FDSelect class, or NULL)
 *   FD   \t name \t gid \t fdIndex    (one per swept gid)
 *   ERR  \t name \t exceptionSimpleName
 *
 * Never mutates anything; builds in-memory objects only.
 */
public final class CffFdSelectBytesProbe {

    private static final int[] SWEEP = {
        -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100, 255, 256, 1000,
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1 || !"sweep".equals(args[0])) {
            out.println("usage: CffFdSelectBytesProbe sweep");
            return;
        }
        sweep(out);
    }

    private static void sweep(PrintStream out) throws Exception {
        // ---- Format 0 byte payloads: format(0) + nGlyphs FD bytes. ----
        emit(out, "f0_single", fmt0(new int[] {0}), 1);
        emit(out, "f0_simple4", fmt0(new int[] {0, 0, 1, 1}), 4);
        emit(out, "f0_three", fmt0(new int[] {0, 0, 0, 1, 1, 2, 2, 2}), 8);
        emit(out, "f0_fd_oob", fmt0(new int[] {0, 5, 99, 200}), 4);
        emit(out, "f0_high_fd", fmt0(new int[] {255, 0, 255}), 3);
        // nGlyphs smaller than the on-disk array (reader only reads nGlyphs).
        emit(out, "f0_nglyphs_short", fmt0(new int[] {3, 2, 1, 0}), 2);

        // ---- Format 3 byte payloads: format(3) + nRanges + records + sentinel.
        emit(out, "f3_simple",
                fmt3(new int[][] {{0, 0}, {2, 1}}, 4), 0);
        emit(out, "f3_three",
                fmt3(new int[][] {{0, 0}, {3, 1}, {5, 2}}, 8), 0);
        emit(out, "f3_single_all",
                fmt3(new int[][] {{0, 0}}, 256), 0);
        emit(out, "f3_first_not_zero",
                fmt3(new int[][] {{2, 1}, {5, 2}}, 8), 0);
        emit(out, "f3_high_first",
                fmt3(new int[][] {{0, 0}, {255, 1}, {256, 2}}, 300), 0);
        emit(out, "f3_sentinel_eq_last",
                fmt3(new int[][] {{0, 0}, {4, 1}}, 4), 0);
        emit(out, "f3_zero_ranges",
                fmt3(new int[][] {}, 4), 0);
        emit(out, "f3_fd_byte_max",
                fmt3(new int[][] {{0, 255}, {2, 0}}, 4), 0);

        // ---- Unknown format byte: upstream readFDSelect returns null. ----
        emitRaw(out, "unknown_fmt1", new int[] {1}, 4);
        emitRaw(out, "unknown_fmt2", new int[] {2}, 4);
        emitRaw(out, "unknown_fmt255", new int[] {255}, 4);
    }

    /** Build the on-disk bytes for a Format 0 FDSelect. */
    private static int[] fmt0(int[] fds) {
        int[] b = new int[1 + fds.length];
        b[0] = 0;
        System.arraycopy(fds, 0, b, 1, fds.length);
        return b;
    }

    /** Build the on-disk bytes for a Format 3 FDSelect. */
    private static int[] fmt3(int[][] ranges, int sentinel) {
        int n = ranges.length;
        int[] b = new int[1 + 2 + n * 3 + 2];
        int p = 0;
        b[p++] = 3;
        b[p++] = (n >> 8) & 0xFF;
        b[p++] = n & 0xFF;
        for (int[] r : ranges) {
            b[p++] = (r[0] >> 8) & 0xFF;
            b[p++] = r[0] & 0xFF;
            b[p++] = r[1] & 0xFF;
        }
        b[p++] = (sentinel >> 8) & 0xFF;
        b[p] = sentinel & 0xFF;
        return b;
    }

    /** Parse the bytes via readFDSelect and sweep getFDIndex. */
    private static void emit(PrintStream out, String name, int[] payload,
            int nGlyphs) {
        FDSelect sel;
        try {
            sel = readFDSelect(payload, nGlyphs);
        } catch (Throwable t) {
            out.printf("ERR\t%s\t%s%n", name, simple(t));
            return;
        }
        if (sel == null) {
            out.printf("CASE\t%s\t%s%n", name, "NULL");
            return;
        }
        out.printf("CASE\t%s\t%s%n", name, sel.getClass().getSimpleName());
        for (int gid : SWEEP) {
            try {
                out.printf("FD\t%s\t%d\t%d%n", name, gid, sel.getFDIndex(gid));
            } catch (Throwable t) {
                out.printf("FD\t%s\t%d\tERR:%s%n", name, gid, simple(t));
            }
        }
    }

    /** Like emit but used for the unknown-format dispatch cases. */
    private static void emitRaw(PrintStream out, String name, int[] payload,
            int nGlyphs) {
        FDSelect sel;
        try {
            sel = readFDSelect(payload, nGlyphs);
        } catch (Throwable t) {
            out.printf("ERR\t%s\t%s%n", name, simple(t));
            return;
        }
        if (sel == null) {
            out.printf("CASE\t%s\t%s%n", name, "NULL");
        } else {
            out.printf("CASE\t%s\t%s%n", name, sel.getClass().getSimpleName());
        }
    }

    private static String simple(Throwable t) {
        Throwable c = (t.getCause() != null) ? t.getCause() : t;
        return c.getClass().getSimpleName();
    }

    // ---- reflective invocation of CFFParser.readFDSelect + DataInputByteArray.
    private static FDSelect readFDSelect(int[] payload, int nGlyphs)
            throws Exception {
        byte[] bytes = new byte[payload.length];
        for (int i = 0; i < payload.length; i++) {
            bytes[i] = (byte) (payload[i] & 0xFF);
        }
        Class<?> diaCls =
                Class.forName("org.apache.fontbox.cff.DataInputByteArray");
        Constructor<?> diaCtor = diaCls.getDeclaredConstructor(byte[].class);
        diaCtor.setAccessible(true);
        Object dataInput = diaCtor.newInstance((Object) bytes);

        Class<?> parserCls = Class.forName("org.apache.fontbox.cff.CFFParser");
        Constructor<?> pCtor = parserCls.getDeclaredConstructor();
        pCtor.setAccessible(true);
        Object parser = pCtor.newInstance();

        Class<?> diCls = Class.forName("org.apache.fontbox.cff.DataInput");
        Method m = parserCls.getDeclaredMethod(
                "readFDSelect", diCls, int.class);
        m.setAccessible(true);
        return (FDSelect) m.invoke(parser, dataInput, nGlyphs);
    }

    private CffFdSelectBytesProbe() {
    }
}
