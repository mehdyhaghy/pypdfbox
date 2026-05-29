import java.io.PrintStream;
import org.apache.fontbox.cmap.CMap;
import org.apache.fontbox.cmap.CMapParser;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for /ToUnicode CMap bfchar / bfrange UTF-16BE destination
 * decoding — specifically the cases where a destination is NOT a single BMP
 * character:
 *
 *   (a) SURROGATE PAIR  — a 4-byte UTF-16BE destination whose two 16-bit code
 *       units form a high+low surrogate pair and must collapse to a single
 *       astral code point (e.g. <D83DDE00> -> U+1F600).
 *   (b) MULTI-CHAR      — a destination of several BMP characters (e.g. an
 *       ffi-ligature code -> "ffi", three U+006X code points).
 *   (c) bfrange ARRAY   — a beginbfrange entry whose destination is a
 *       [ <dst0> <dst1> ... ] array, one UTF-16BE string per source code,
 *       where some of those strings are themselves surrogate pairs.
 *   (d) ASTRAL+COMBINING — surrogate pair followed by a BMP combining mark.
 *
 * Unlike ToUnicodeCMapProbe (which drives PDFont.toUnicode over a real font),
 * this probe feeds a raw embedded /ToUnicode CMap byte stream straight to
 * CMapParser.parse and queries CMap.toUnicode directly, so the decode path is
 * isolated from font-level encoding fallbacks.
 *
 * Usage:
 *   java ToUnicodeSurrogateProbe <cmap-stream-hex> <code-hex> [<code-hex> ...]
 *
 * <cmap-stream-hex> is the full CMap program, hex-encoded so arbitrary bytes
 * survive the command line. Each <code-hex> is a big-endian character code
 * whose byte length is taken from the hex string length.
 *
 * Output (one canonical line per code):
 *   UNI <codeHexUpper> -> U+XXXX[ U+YYYY...]      (via toUnicode(byte[]))
 *   or
 *   UNI <codeHexUpper> -> (none)
 *
 * Code points are taken via String.codePoints() so a non-BMP destination
 * (surrogate pair) collapses to a single U+1XXXX entry — exactly how Python
 * iterates its decoded string.
 */
public final class ToUnicodeSurrogateProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] streamBytes = hexToBytes(args[0]);
        CMap cmap = new CMapParser()
                .parse(new RandomAccessReadBuffer(streamBytes));

        for (int i = 1; i < args.length; i++) {
            byte[] code = hexToBytes(args[i]);
            String uni = cmap.toUnicode(code);
            StringBuilder sb = new StringBuilder();
            sb.append("UNI ").append(args[i].toUpperCase()).append(" ->");
            if (uni == null || uni.isEmpty()) {
                sb.append(" (none)");
            } else {
                uni.codePoints().forEach(
                        cp -> sb.append(" U+").append(String.format("%04X", cp)));
            }
            out.println(sb.toString());
        }
    }

    private static byte[] hexToBytes(String hex) {
        int n = hex.length() / 2;
        byte[] out = new byte[n];
        for (int i = 0; i < n; i++) {
            out[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }
}
