import java.awt.geom.GeneralPath;
import java.awt.geom.PathIterator;
import java.awt.geom.Rectangle2D;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.apache.fontbox.cff.CharStringCommand;
import org.apache.fontbox.cff.Type1CharString;
import org.apache.fontbox.cff.Type2CharString;
import org.apache.fontbox.cff.Type2CharStringParser;
import org.apache.fontbox.type1.Type1CharStringReader;

/**
 * Live oracle probe for the FontBox Type 2 char-string INTERPRETER -> glyph
 * PATH layer: it drives {@code Type2CharStringParser.parse} on raw, hand-built
 * (mostly malformed / edge) Type 2 bytecode, wraps the resulting token sequence
 * in a {@code Type2CharString}, and projects the rendered outline
 * ({@code getPath()} / {@code getBounds()}) — a COORDINATE-TOLERANT,
 * STRUCTURE-STRICT fingerprint.
 *
 * <p>This is upstream-distinct from the two companions:
 * <ul>
 *   <li>{@code Type2CharStringInterpFuzzProbe} pins the parser's intermediate
 *       TOKEN STREAM (operands + command mnemonics) and the Java exceptions the
 *       decoder throws — it never builds a path.</li>
 *   <li>{@code GlyphPathProbe} pins {@code getPath()} but only for glyphs
 *       reached through a real, well-formed embedded CFF inside a PDF.</li>
 * </ul>
 * This probe closes the gap: malformed/edge bytecode fed all the way to the
 * width-prologue + Type2 -> Type1 conversion + {@code GeneralPath} build, so the
 * INTERPRETER (not just the decoder) is pinned: width-on-first-operator
 * detection (hstem/rmoveto/endchar/hmoveto prologue), unbalanced stem counts,
 * hintmask byte skipping, callsubr/callgsubr bias + inlining, the flex family,
 * seac-via-4-arg-endchar, 255 fixed-point operands, and odd operand remainders.
 *
 * <pre>
 *   java -cp ... Type2CharStringFuzzProbe run &lt;cs_hex&gt; [gsubr_hex,...] [lsubr_hex,...] [defW] [nomW]
 * </pre>
 *
 * Args:
 *   args[0] = "run"
 *   args[1] = char-string bytes as hex ("" / "-" = empty)
 *   args[2] = comma-separated global subr hex programs ("-" / absent = none)
 *   args[3] = comma-separated local subr hex programs  ("-" / absent = none)
 *   args[4] = defaultWidthX (int, default 0)
 *   args[5] = nominalWidthX (int, default 0)
 *
 * Output (UTF-8, stdout), one line:
 *   OK \t nseg \t typeSeq \t minX \t minY \t maxX \t maxY     (path built)
 *   ERR \t &lt;simpleExceptionClassName&gt;                        (parse/build threw)
 *
 * typeSeq uses M/L/Q/C/Z per PathIterator segment kind (CFF Type 2 only ever
 * emits M/L/C/Z). Bounds come from getBounds() rounded via Math.round; an empty
 * path yields nseg 0, empty typeSeq, bounds "0 0 0 0".
 */
public final class Type2CharStringFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 2 || !"run".equals(args[0])) {
            out.println("usage: Type2CharStringFuzzProbe run <cs_hex> [gsubr] [lsubr] [defW] [nomW]");
            return;
        }
        byte[] cs = hex(args[1]);
        byte[][] gsubr = subrs(args.length > 2 ? args[2] : "-");
        byte[][] lsubr = subrs(args.length > 3 ? args[3] : "-");
        int defW = args.length > 4 ? Integer.parseInt(args[4]) : 0;
        int nomW = args.length > 5 ? Integer.parseInt(args[5]) : 0;
        try {
            Type2CharStringParser parser = new Type2CharStringParser("FuzzFont");
            List<Object> seq = parser.parse(cs, gsubr, lsubr, "g");
            Type2CharString t2 = new Type2CharString(
                    new EmptyReader(), "FuzzFont", "g", 0, seq, defW, nomW);
            GeneralPath path = t2.getPath();
            emitPath(out, path);
        } catch (Throwable t) {
            out.printf(Locale.ROOT, "ERR\t%s%n", t.getClass().getSimpleName());
        }
    }

    private static void emitPath(PrintStream out, GeneralPath path) {
        StringBuilder types = new StringBuilder();
        int nseg = 0;
        double[] coords = new double[6];
        PathIterator it = path.getPathIterator(null);
        while (!it.isDone()) {
            switch (it.currentSegment(coords)) {
                case PathIterator.SEG_MOVETO:
                    types.append('M');
                    break;
                case PathIterator.SEG_LINETO:
                    types.append('L');
                    break;
                case PathIterator.SEG_QUADTO:
                    types.append('Q');
                    break;
                case PathIterator.SEG_CUBICTO:
                    types.append('C');
                    break;
                case PathIterator.SEG_CLOSE:
                    types.append('Z');
                    break;
                default:
                    types.append('?');
                    break;
            }
            nseg++;
            it.next();
        }
        int minX;
        int minY;
        int maxX;
        int maxY;
        if (nseg == 0) {
            minX = 0;
            minY = 0;
            maxX = 0;
            maxY = 0;
        } else {
            Rectangle2D b = path.getBounds2D();
            minX = (int) Math.round(b.getMinX());
            minY = (int) Math.round(b.getMinY());
            maxX = (int) Math.round(b.getMaxX());
            maxY = (int) Math.round(b.getMaxY());
        }
        out.printf(Locale.ROOT, "OK\t%d\t%s\t%d\t%d\t%d\t%d%n",
                nseg, types.toString(), minX, minY, maxX, maxY);
    }

    /** Stub reader: this probe never exercises seac component resolution that
     *  would call back into the font, so getType1CharString just throws. */
    private static final class EmptyReader implements Type1CharStringReader {
        @Override
        public Type1CharString getType1CharString(String name) {
            throw new UnsupportedOperationException("no component glyph: " + name);
        }
    }

    private static byte[] hex(String s) {
        if (s == null || s.isEmpty() || "-".equals(s)) {
            return new byte[0];
        }
        int n = s.length() / 2;
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) {
            b[i] = (byte) Integer.parseInt(s.substring(i * 2, i * 2 + 2), 16);
        }
        return b;
    }

    private static byte[][] subrs(String s) {
        if (s == null || s.isEmpty() || "-".equals(s)) {
            return new byte[0][];
        }
        String[] parts = s.split(",", -1);
        List<byte[]> list = new ArrayList<byte[]>();
        for (String p : parts) {
            list.add(hex(p));
        }
        return list.toArray(new byte[0][]);
    }
}
