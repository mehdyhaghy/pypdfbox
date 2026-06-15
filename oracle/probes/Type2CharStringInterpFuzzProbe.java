import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.apache.fontbox.cff.CharStringCommand;
import org.apache.fontbox.cff.Type2CharStringParser;

/**
 * Live oracle probe for the FontBox {@code Type2CharStringParser}
 * INTERPRETER/EXECUTION layer — how each Type 2 operator manipulates the
 * operand stack, unrolls subroutines (bias-adjusted index, trailing RET
 * trimmed), counts stem hints, and skips hint-mask bytes — fed with
 * MALFORMED char-string bytecode crafted directly (NOT via a CFF file).
 *
 * <p>The companion {@code CffType2ParseProbe} pins the token stream of
 * well-formed glyphs reached through a parsed CFF. This probe instead feeds
 * the parser raw, hand-built byte sequences (stack underflow, out-of-range /
 * negative post-bias subr indexes, truncated mask bytes, truncated operands,
 * odd operand counts, non-integer subr operand, deep recursion, empty
 * charstring) so the stack-execution semantics — including the Java exceptions
 * thrown on malformed input — are pinned directly.
 *
 * <pre>
 *   java -cp ... Type2CharStringInterpFuzzProbe run &lt;cs_hex&gt; [gsubr_hex,...] [lsubr_hex,...]
 * </pre>
 *
 * Args:
 *   args[0] = "run"
 *   args[1] = char-string bytes as hex (e.g. "8b0e" = 0 endchar). "" = empty.
 *   args[2] = optional comma-separated list of global subr byte strings (hex);
 *             "-" or absent = empty global subr index.
 *   args[3] = optional comma-separated list of local subr byte strings (hex);
 *             "-" or absent = empty local subr index.
 *
 * Output (UTF-8, stdout), one line:
 *   OK \t tokenCount \t tok0|tok1|...      (parse succeeded)
 *   ERR \t &lt;simpleExceptionClassName&gt;     (parse threw)
 *
 * token = an operand (integer as-is; float formatted "%.4f") or a command
 *         mnemonic ("RRCURVETO", "HINTMASK", ...). Joined by '|'.
 */
public final class Type2CharStringInterpFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 2 || !"run".equals(args[0])) {
            out.println("usage: Type2CharStringInterpFuzzProbe run <cs_hex> [gsubr] [lsubr]");
            return;
        }
        byte[] cs = hex(args[1]);
        byte[][] gsubr = subrs(args.length > 2 ? args[2] : "-");
        byte[][] lsubr = subrs(args.length > 3 ? args[3] : "-");
        Type2CharStringParser parser = new Type2CharStringParser("FuzzFont");
        try {
            List<Object> seq = parser.parse(cs, gsubr, lsubr, "g");
            StringBuilder sb = new StringBuilder();
            for (int k = 0; k < seq.size(); k++) {
                if (k > 0) {
                    sb.append('|');
                }
                sb.append(token(seq.get(k)));
            }
            out.printf(Locale.ROOT, "OK\t%d\t%s%n", seq.size(), sb);
        } catch (Throwable t) {
            out.printf(Locale.ROOT, "ERR\t%s%n", t.getClass().getSimpleName());
        }
    }

    private static String token(Object o) {
        if (o instanceof CharStringCommand) {
            String s = o.toString();
            if (s.endsWith("|")) {
                s = s.substring(0, s.length() - 1);
            }
            return s;
        }
        if (o instanceof Integer) {
            return Integer.toString((Integer) o);
        }
        if (o instanceof Number) {
            return String.format(Locale.ROOT, "%.4f", ((Number) o).doubleValue());
        }
        return String.valueOf(o);
    }

    /** Parse a hex string into bytes; "" -> empty array. */
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

    /** Parse a comma-separated list of hex subr strings into byte[][]. */
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
