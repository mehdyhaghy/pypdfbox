import java.io.ByteArrayInputStream;
import java.io.PrintStream;
import org.apache.fontbox.cmap.CMap;
import org.apache.fontbox.cmap.CMapParser;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for EMBEDDED CMap stream parsing.
 *
 * Unlike PredefCMapType0Probe (which loads a predefined CMap by *name* via
 * CMapParser.parsePredefined), this probe feeds a raw embedded CMap byte
 * stream — exactly the bytes that would live in a PDF /Encoding CMap stream
 * or a CIDFont's embedded CMap — to CMapParser.parse(RandomAccessRead) and
 * exercises:
 *
 *   - begincodespacerange / endcodespacerange variable-byte detection
 *     (mixed 1-byte / 2-byte codespaces),
 *   - begincidrange / endcidrange + begincidchar / endcidchar code->CID,
 *   - usecmap inheritance (when the stream references a bundled CMap),
 *   - the codespace byte-length disambiguation in CMap.readCode: how many
 *     bytes the parser commits to for a given leading byte.
 *
 * Usage:
 *   java EmbeddedCMapProbe <cmap-stream-hex> <code-hex> [<code-hex> ...]
 *
 * <cmap-stream-hex> is the full CMap program, hex-encoded (so arbitrary
 * bytes survive the command line). Each <code-hex> is a big-endian code.
 *
 * Output (one canonical line each):
 *   NAME <cmapName>
 *   WMODE <wmode>
 *   SWEEP <leadingByteHex> len=<n>      (only for leading bytes whose
 *                                        readCode length differs from the
 *                                        previous emitted leading byte —
 *                                        compresses the 0x00..0xFF sweep
 *                                        into its run boundaries)
 *   CID <codeHex> -> <cid> len=<n>
 */
public final class EmbeddedCMapProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] streamBytes = hexToBytes(args[0]);
        CMap cmap = new CMapParser()
                .parse(new RandomAccessReadBuffer(streamBytes));

        out.println("NAME " + cmap.getName());
        out.println("WMODE " + cmap.getWMode());

        // Codespace byte-length disambiguation: sweep every possible leading
        // byte and record how many bytes readCode consumes. Emit a line only
        // at each run boundary so the output stays compact.
        int prevLen = -1;
        for (int lead = 0; lead <= 0xFF; lead++) {
            // Pad with a 0x40 trailing byte: it sits inside the low-byte band
            // of the typical CJK 2-byte codespaces (<..40> .. <..FC>), so a
            // 2-byte range whose leading byte covers `lead` matches and
            // readCode commits to 2 bytes — revealing the 1-vs-2-byte
            // boundary. A trailing 0x00 would fall below most low-byte
            // bands and force a min-length fallback everywhere, hiding the
            // boundary.
            byte[] probe = new byte[] { (byte) lead, 0x40 };
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
