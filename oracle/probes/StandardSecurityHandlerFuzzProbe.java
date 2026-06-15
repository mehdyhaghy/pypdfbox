import java.io.PrintStream;
import org.apache.pdfbox.pdmodel.encryption.StandardSecurityHandler;

/**
 * Differential fuzz probe for {@code StandardSecurityHandler} KEY DERIVATION +
 * PASSWORD AUTHENTICATION, Apache PDFBox 3.0.7 (wave 1524, agent E).
 *
 * The existing encryption oracle suite drives the full document open path
 * (Loader.loadPDF) and the on-the-wire /Encrypt dictionary. None of it pokes
 * the raw algorithm-level instance methods with deliberately MALFORMED /O /U
 * /OE /UE byte strings, out-of-range /R, odd /Length, etc. This probe targets
 * exactly those:
 *
 *   - {@code computeEncryptedKey(pw, o, u, oe, ue, perms, id, encRevision,
 *       keyLengthInBytes, encryptMetadata, isOwnerPassword)} — Algorithm 2 / 2.A
 *   - {@code isUserPassword(pw, u, o, perms, id, encRevision, keyLenBytes,
 *       encryptMetadata)} — Algorithm 6 / 11
 *   - {@code isOwnerPassword(pw, u, o, perms, id, encRevision, keyLenBytes,
 *       encryptMetadata)} — Algorithm 7 / 12
 *   - {@code getUserPassword(owner, o, encRevision, length)} — Algorithm 7 inverse
 *
 * Driven entirely by deterministic in-process inputs (no random, no files), so
 * the Python sibling can construct byte-for-byte identical inputs and compare
 * the projected hex / boolean / error-class.
 *
 * Line grammar (one per case, manifest order from argv):
 *   CASE &lt;name&gt; &lt;result&gt;
 * where result is one of:
 *   key=&lt;hex-or-empty&gt;
 *   user=&lt;0|1&gt;
 *   owner=&lt;0|1&gt;
 *   getuser=&lt;hex-or-empty&gt;
 *   ERR:&lt;ExcSimpleName&gt;
 */
public final class StandardSecurityHandlerFuzzProbe {

    static PrintStream out;

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

    private static String toHex(byte[] b) {
        if (b == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xff));
        }
        return sb.toString();
    }

    private static StandardSecurityHandler handler() {
        return new StandardSecurityHandler();
    }

    // computeEncryptedKey: pw o u oe ue perms id rev keylen encmeta isowner
    private static String doKey(String[] f) {
        try {
            byte[] key = handler().computeEncryptedKey(
                    hex(f[0]), hex(f[1]), hex(f[2]), hex(f[3]), hex(f[4]),
                    Integer.parseInt(f[5]), hex(f[6]),
                    Integer.parseInt(f[7]), Integer.parseInt(f[8]),
                    Boolean.parseBoolean(f[9]), Boolean.parseBoolean(f[10]));
            return "key=" + toHex(key);
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    // isUserPassword: pw u o perms id rev keylen encmeta
    private static String doUser(String[] f) {
        try {
            boolean r = handler().isUserPassword(
                    hex(f[0]), hex(f[1]), hex(f[2]),
                    Integer.parseInt(f[3]), hex(f[4]),
                    Integer.parseInt(f[5]), Integer.parseInt(f[6]),
                    Boolean.parseBoolean(f[7]));
            return "user=" + (r ? "1" : "0");
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    // isOwnerPassword: pw u o perms id rev keylen encmeta
    private static String doOwner(String[] f) {
        try {
            boolean r = handler().isOwnerPassword(
                    hex(f[0]), hex(f[1]), hex(f[2]),
                    Integer.parseInt(f[3]), hex(f[4]),
                    Integer.parseInt(f[5]), Integer.parseInt(f[6]),
                    Boolean.parseBoolean(f[7]));
            return "owner=" + (r ? "1" : "0");
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    // getUserPassword: owner o rev length
    private static String doGetUser(String[] f) {
        try {
            byte[] r = handler().getUserPassword(
                    hex(f[0]), hex(f[1]),
                    Integer.parseInt(f[2]), Integer.parseInt(f[3]));
            return "getuser=" + toHex(r);
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    /**
     * Each argv entry is a single case encoded as
     * {@code name|op|field0|field1|...}. Pipe-separated so a single string per
     * case survives the shell cleanly; the Python side builds the same strings.
     */
    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        for (String spec : args) {
            String[] parts = spec.split("\\|", -1);
            String name = parts[0];
            String op = parts[1];
            String[] f = new String[parts.length - 2];
            System.arraycopy(parts, 2, f, 0, f.length);
            String result;
            switch (op) {
                case "key":
                    result = doKey(f);
                    break;
                case "user":
                    result = doUser(f);
                    break;
                case "owner":
                    result = doOwner(f);
                    break;
                case "getuser":
                    result = doGetUser(f);
                    break;
                default:
                    result = "ERR:UnknownOp";
            }
            out.println("CASE " + name + " " + result);
        }
    }
}
