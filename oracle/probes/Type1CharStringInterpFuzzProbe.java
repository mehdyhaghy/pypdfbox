import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import org.apache.fontbox.cff.CharStringCommand;
import org.apache.fontbox.cff.Type1CharStringParser;

/**
 * Live oracle probe for Apache FontBox's Type 1 charstring BYTE-LEVEL PARSER
 * ({@code org.apache.fontbox.cff.Type1CharStringParser}) under MALFORMED
 * charstring bytecode (wave 1525 differential fuzz; sibling of
 * {@code Type1GlyphPathProbe}, which exercises the assembled glyph PATH).
 *
 * This probe isolates the interpreter at the operator / stack-execution level:
 * the operand encoding (Adobe Type 1 spec §6.2: 32-246 single byte, 247-254
 * two-byte, 255 = int32), the {@code callsubr} unrolling (out-of-range /
 * negative index, deeply nested recursion), and the {@code callothersubr} /
 * {@code pop} OtherSubrs machinery (flex OtherSubr 0/1/2, hint-replacement
 * OtherSubr 3, default N-arg, the trailing {@code pop} loop, the {@code div}
 * expansion inside {@code removeInteger}). {@code parse()} returns a
 * {@code List<Object>} of Integer operands interleaved with
 * {@code CharStringCommand}s — exactly the flat sequence pypdfbox's
 * {@code Type1CharStringParser.parse()} produces, so the token stream is a
 * sharp regression pin for the byte-decode + subr/othersubr unroll path.
 *
 * Input: a fuzz-case file, one case per line, fields space-separated:
 *
 *   &lt;label&gt; &lt;charstringHex&gt; &lt;subrsHexCsv&gt;
 *
 *   label         - short case id (echoed back verbatim)
 *   charstringHex - hex of the charstring bytes ("." = empty)
 *   subrsHexCsv   - comma-separated hex blobs, one per subr ("." = no subrs)
 *
 * Output (UTF-8, stdout), one line per case, deterministic order (input order):
 *
 *   &lt;label&gt; &lt;tokenSeq&gt;
 *
 * where tokenSeq is a "|"-joined projection of the returned list:
 *   - an Integer operand        -&gt; "i&lt;value&gt;"
 *   - a CharStringCommand       -&gt; "c&lt;Type1KeyWordName&gt;" ("c?" when the
 *                                   command has no Type1KeyWord)
 *   - any other object type     -&gt; "o&lt;ClassName&gt;"
 * An empty list emits "-". A throw from {@code parse()} emits
 *   "ERR&lt;ExceptionSimpleName&gt;".
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; Type1CharStringInterpFuzzProbe cases.txt
 */
public final class Type1CharStringInterpFuzzProbe {
    public static void main(String[] args) throws Exception {
        List<String> lines = Files.readAllLines(
            new java.io.File(args[0]).toPath(), StandardCharsets.UTF_8);
        StringBuilder out = new StringBuilder();
        for (String line : lines) {
            String trimmed = line.trim();
            if (trimmed.isEmpty() || trimmed.startsWith("#")) {
                continue;
            }
            String[] parts = trimmed.split("\\s+");
            String label = parts[0];
            byte[] cs = parseHex(parts.length > 1 ? parts[1] : ".");
            List<byte[]> subrs = parseSubrs(parts.length > 2 ? parts[2] : ".");
            out.append(label).append(' ').append(run(cs, subrs)).append('\n');
        }
        System.out.print(out);
    }

    private static String run(byte[] cs, List<byte[]> subrs) {
        try {
            Type1CharStringParser parser = new Type1CharStringParser("FuzzFont");
            List<Object> seq = parser.parse(cs, subrs, "fuzzGlyph");
            return project(seq);
        } catch (Throwable t) {
            return "ERR" + t.getClass().getSimpleName();
        }
    }

    private static String project(List<Object> seq) {
        if (seq == null || seq.isEmpty()) {
            return "-";
        }
        StringBuilder sb = new StringBuilder();
        for (Object o : seq) {
            if (sb.length() > 0) {
                sb.append('|');
            }
            if (o instanceof Integer) {
                sb.append('i').append(((Integer) o).intValue());
            } else if (o instanceof Number) {
                // Type1 parser only ever pushes Integers, but be defensive.
                sb.append('i').append(((Number) o).longValue());
            } else if (o instanceof CharStringCommand) {
                CharStringCommand c = (CharStringCommand) o;
                Object kw = c.getType1KeyWord();
                sb.append('c').append(kw == null ? "?" : kw.toString());
            } else {
                sb.append('o').append(o.getClass().getSimpleName());
            }
        }
        return sb.toString();
    }

    private static byte[] parseHex(String hex) {
        if (hex.equals(".") || hex.isEmpty()) {
            return new byte[0];
        }
        int n = hex.length() / 2;
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) {
            b[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        return b;
    }

    private static List<byte[]> parseSubrs(String csv) {
        List<byte[]> subrs = new ArrayList<byte[]>();
        if (csv.equals(".") || csv.isEmpty()) {
            return subrs;
        }
        for (String part : csv.split(",")) {
            subrs.add(parseHex(part));
        }
        return subrs;
    }
}
