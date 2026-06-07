import java.io.PrintStream;
import org.apache.fontbox.cmap.CMap;
import org.apache.fontbox.cmap.CMapParser;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Differential parse-fuzz probe for the embedded CMap path
 * ({@code CMapParser.parse(RandomAccessRead)}). The pypdfbox sibling
 * ({@code tests/fontbox/cmap/oracle/test_cmap_parse_fuzz_oracle.py}) feeds the
 * identical (possibly malformed) bytes to {@code CMapParser().parse(...)} and
 * compares a stable projection so any divergence in tokenization, lenient
 * recovery, codespace partitioning, CID/Unicode mapping or end-token handling
 * surfaces as a differing line.
 *
 * Usage:
 *   java CMapParseFuzzProbe &lt;cmap-stream-hex&gt; &lt;code-hex&gt; [&lt;code-hex&gt; ...]
 *
 * Projection (sole line {@code ok=false} on any parse-time throw, else):
 *   ok=true
 *   name=&lt;cmapName&gt;
 *   wmode=&lt;wmode&gt;
 *   type=&lt;cmapType&gt;
 *   registry=&lt;registry&gt;
 *   ordering=&lt;ordering&gt;
 *   CID &lt;codeHex&gt; -&gt; &lt;cid&gt; len=&lt;readLen&gt;
 *   UNI &lt;codeHex&gt; -&gt; U+XXXX[ U+YYYY...]   (or "(none)")
 */
public final class CMapParseFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] streamBytes = hexToBytes(args[0]);
        CMap cmap;
        try {
            cmap = new CMapParser().parse(new RandomAccessReadBuffer(streamBytes));
        } catch (Throwable t) {
            out.print("ok=false\n");
            return;
        }
        StringBuilder sb = new StringBuilder();
        sb.append("ok=true\n");
        sb.append("name=").append(cmap.getName()).append('\n');
        sb.append("wmode=").append(cmap.getWMode()).append('\n');
        sb.append("type=").append(cmap.getType()).append('\n');
        sb.append("registry=").append(cmap.getRegistry()).append('\n');
        sb.append("ordering=").append(cmap.getOrdering()).append('\n');
        for (int i = 1; i < args.length; i++) {
            byte[] code = hexToBytes(args[i]);
            int codeInt = toInt(code);
            int cid;
            try {
                cid = cmap.toCID(codeInt);
            } catch (Throwable t) {
                cid = -2;
            }
            int len = readLen(cmap, code);
            sb.append("CID ").append(args[i].toUpperCase()).append(" -> ")
              .append(cid).append(" len=").append(len).append('\n');
            String uni;
            try {
                uni = cmap.toUnicode(codeInt, code.length);
            } catch (Throwable t) {
                uni = null;
            }
            sb.append("UNI ").append(args[i].toUpperCase()).append(" -> ");
            if (uni == null || uni.isEmpty()) {
                sb.append("(none)");
            } else {
                final StringBuilder u = new StringBuilder();
                uni.codePoints().forEach(cp -> u.append(" U+").append(String.format("%04X", cp)));
                sb.append(u.toString().trim());
            }
            sb.append('\n');
        }
        out.print(sb.toString());
    }

    /** Number of bytes CMap.readCode consumes from the buffer. */
    private static int readLen(CMap cmap, byte[] code) {
        try {
            java.io.ByteArrayInputStream in = new java.io.ByteArrayInputStream(code);
            int before = in.available();
            cmap.readCode(in);
            return before - in.available();
        } catch (Throwable t) {
            return -1;
        }
    }

    private static int toInt(byte[] data) {
        int code = 0;
        for (byte b : data) {
            code = (code << 8) | (b & 0xFF);
        }
        return code;
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
