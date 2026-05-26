import java.io.ByteArrayInputStream;
import java.io.PrintStream;
import org.apache.fontbox.cmap.CMap;
import org.apache.fontbox.cmap.CMapParser;

/**
 * Live oracle probe: emit Apache PDFBox's predefined-CMap behaviour.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PredefCMapProbe <name> [<hexcode> ...]
 *
 * For the named predefined CMap (loaded via CMapParser.parsePredefined) emits,
 * UTF-8, no extra framing:
 *   CMAP <name>            (CMap.getName())
 *   WMODE <wmode>          (CMap.getWMode())
 * then for each hex-encoded input byte sequence one line:
 *   CID <hexcode> -> <cid> len=<codeLength>
 * where <cid> is CMap.toCID(int) over the big-endian value of the bytes and
 * <codeLength> is how many bytes CMap.readCode(InputStream) consumes for that
 * sequence (i.e. the length the codespace assigns to the leading bytes).
 */
public final class PredefCMapProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String name = args[0];
        CMap cmap = new CMapParser().parsePredefined(name);
        out.println("CMAP " + cmap.getName());
        out.println("WMODE " + cmap.getWMode());
        for (int i = 1; i < args.length; i++) {
            byte[] code = hexToBytes(args[i]);
            int value = toInt(code);
            int cid = cmap.toCID(value);
            int len = codeLength(cmap, code);
            out.println("CID " + args[i].toUpperCase() + " -> " + cid + " len=" + len);
        }
    }

    /** Number of bytes readCode consumes from the given buffer. */
    private static int codeLength(CMap cmap, byte[] code) throws Exception {
        ByteArrayInputStream in = new ByteArrayInputStream(code);
        int before = in.available();
        cmap.readCode(in);
        int after = in.available();
        return before - after;
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
