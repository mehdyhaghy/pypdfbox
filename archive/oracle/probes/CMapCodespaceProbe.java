import java.io.ByteArrayInputStream;
import java.io.PrintStream;
import org.apache.fontbox.cmap.CMap;
import org.apache.fontbox.cmap.CMapParser;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for variable-length code decoding driven by codespace
 * ranges of DIFFERENT byte widths in a single embedded (stream) CMap.
 *
 * Complements EmbeddedCMapProbe: where that probe uses *disjoint* 1- and
 * 2-byte bands (the textbook CJK partition), this probe stresses the harder
 * corners of ISO 32000-1 §9.7.6.2 byte-length disambiguation:
 *
 *   - OVERLAPPING widths: a 1-byte band and a 2-byte band whose leading byte
 *     ranges intersect, so a leading byte is covered by BOTH a 1-byte and a
 *     2-byte codespace. readCode must commit to the SHORTEST match (1 byte),
 *     because it tests byteCount = minCodeLength first and returns on the
 *     first anyMatch.
 *   - a leading byte covered ONLY by the 2-byte band (so readCode extends to
 *     2 bytes), interleaved with the 1-byte-covered bytes.
 *   - cidrange/cidchar entries at BOTH widths, including a numeric code value
 *     that collides across widths (e.g. 0x41 as a 1-byte char and 0x0041 as a
 *     2-byte char map to different CIDs) so toCID's min..max length sweep is
 *     observably order-sensitive.
 *
 * Usage:
 *   java CMapCodespaceProbe <cmap-stream-hex> <code-hex> [<code-hex> ...]
 *
 * Output (one canonical line each):
 *   NAME <cmapName>
 *   MINLEN <minCodeLength>
 *   MAXLEN <maxCodeLength>
 *   SWEEP <leadingByteHex> len=<n>     (only at readCode-length run boundaries)
 *   CID <codeHex> -> <cid> len=<n>
 */
public final class CMapCodespaceProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] streamBytes = hexToBytes(args[0]);
        CMap cmap = new CMapParser()
                .parse(new RandomAccessReadBuffer(streamBytes));

        out.println("NAME " + cmap.getName());
        out.println("MINLEN " + minLen(cmap));
        out.println("MAXLEN " + maxLen(cmap));

        // Sweep every leading byte, padded with a low byte (0x41) that sits
        // inside the low-byte band of the 2-byte ranges, recording how many
        // bytes readCode commits to. Emit only at run boundaries.
        int prevLen = -1;
        for (int lead = 0; lead <= 0xFF; lead++) {
            byte[] probe = new byte[] { (byte) lead, 0x41 };
            int len = readLen(cmap, probe);
            if (len != prevLen) {
                out.println("SWEEP " + String.format("%02X", lead)
                        + " len=" + len);
                prevLen = len;
            }
        }

        for (int i = 1; i < args.length; i++) {
            byte[] code = hexToBytes(args[i]);
            int cid = cmap.toCID(toInt(code));
            int len = readLen(cmap, code);
            out.println("CID " + args[i].toUpperCase() + " -> " + cid
                    + " len=" + len);
        }
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

    /** Number of bytes CMap.readCode consumes from the buffer. */
    private static int readLen(CMap cmap, byte[] code) throws Exception {
        ByteArrayInputStream in = new ByteArrayInputStream(code);
        int before = in.available();
        cmap.readCode(in);
        return before - in.available();
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
