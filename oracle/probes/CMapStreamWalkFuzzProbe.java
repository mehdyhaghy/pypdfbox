import java.io.ByteArrayInputStream;
import java.io.PrintStream;
import org.apache.fontbox.cmap.CMap;
import org.apache.fontbox.cmap.CMapParser;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Differential STREAM-WALK fuzz probe for the embedded CMap path. Where the
 * existing {@code CMapParseFuzzProbe} (wave 1508) feeds each probe code to an
 * isolated buffer and looks it up once, this probe drives
 * {@code CMap.readCode(InputStream)} repeatedly over a SINGLE multi-code byte
 * stream until EOF, projecting the sequence of {@code (code, bytesConsumed,
 * cid)} tuples. That exercises the corners no prior cmap probe touches:
 *
 *   - codespace PARTITIONING across boundaries (a 1-byte code immediately
 *     followed by a 2-byte code in the same stream);
 *   - the mark/reset rewind upstream performs when NO codespace range matches
 *     (it reads up to maxCodeLength, then {@code in.reset()}s back to
 *     minCodeLength so the next code starts at the right offset — pypdfbox had
 *     to be hardened to match this, see CHANGES.md wave 1547);
 *   - variable-byte length detection driven by malformed codespace
 *     declarations (mismatched lo/hi lengths, overlapping bands, lo>hi).
 *
 * The pypdfbox sibling
 * ({@code tests/fontbox/cmap/oracle/test_cmap_stream_walk_fuzz_wave1547.py})
 * reconstructs the identical projection so any divergence in tokenisation,
 * codespace partitioning, readCode rewind, CID lookup or WMode surfaces as a
 * differing line.
 *
 * Usage:
 *   java CMapStreamWalkFuzzProbe &lt;cmap-stream-hex&gt; &lt;walk-hex&gt;
 *
 * Projection (sole line {@code ok=false} on any parse-time throw, else):
 *   ok=true
 *   name=&lt;cmapName&gt;
 *   wmode=&lt;wmode&gt;
 *   cscount=&lt;number of codespace ranges&gt;
 *   minlen=&lt;minCodeLength&gt; maxlen=&lt;maxCodeLength&gt;
 *   STEP &lt;codeHexBigEndian&gt; consumed=&lt;n&gt; cid=&lt;cid&gt;     (one per readCode)
 *   END consumed=&lt;total bytes consumed&gt;
 */
public final class CMapStreamWalkFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] streamBytes = hexToBytes(args[0]);
        byte[] walk = args.length > 1 ? hexToBytes(args[1]) : new byte[0];
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
        sb.append("cscount=").append(codespaceCount(cmap)).append('\n');
        sb.append("minlen=").append(minLen(cmap))
          .append(" maxlen=").append(maxLen(cmap)).append('\n');

        ByteArrayInputStream in = new ByteArrayInputStream(walk);
        int total = 0;
        int guard = 0;
        while (in.available() > 0 && guard++ < 4096) {
            int before = in.available();
            int code;
            int cid;
            try {
                code = cmap.readCode(in);
                cid = cmap.toCID(code);
            } catch (Throwable t) {
                sb.append("STEP throw\n");
                break;
            }
            int consumed = before - in.available();
            total += consumed;
            sb.append("STEP ").append(Integer.toHexString(code).toUpperCase())
              .append(" consumed=").append(consumed)
              .append(" cid=").append(cid).append('\n');
            if (consumed <= 0) {
                break;  // defensive: avoid infinite loop on a zero-progress read
            }
        }
        sb.append("END consumed=").append(total).append('\n');
        out.print(sb.toString());
    }

    private static int codespaceCount(CMap cmap) throws Exception {
        java.lang.reflect.Field f = CMap.class.getDeclaredField("codespaceRanges");
        f.setAccessible(true);
        return ((java.util.List<?>) f.get(cmap)).size();
    }

    private static int minLen(CMap cmap) throws Exception {
        java.lang.reflect.Field f = CMap.class.getDeclaredField("minCodeLength");
        f.setAccessible(true);
        return f.getInt(cmap);
    }

    private static int maxLen(CMap cmap) throws Exception {
        java.lang.reflect.Field f = CMap.class.getDeclaredField("maxCodeLength");
        f.setAccessible(true);
        return f.getInt(cmap);
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
