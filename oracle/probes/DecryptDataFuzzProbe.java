import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.io.PrintStream;
import org.apache.pdfbox.pdmodel.encryption.StandardSecurityHandler;

/**
 * Differential fuzz probe for the {@code SecurityHandler} DECRYPT DATA PATH,
 * Apache PDFBox 3.0.7 (wave 1532, agent E).
 *
 * The sibling {@code StandardSecurityHandlerFuzzProbe} (wave 1524) covers KEY
 * DERIVATION + password authentication. {@code CryptFilterFuzzProbe} drives the
 * whole document open path. NEITHER pokes the actual cipher DISPATCH +
 * AES/RC4 byte transform on malformed ciphertext. This probe targets exactly
 * the {@code SecurityHandler.encryptData(long objNum, long genNum, InputStream,
 * OutputStream, boolean decrypt)} private dispatch (reached by reflection),
 * which is the single funnel for both encrypt and decrypt:
 *
 *   - useAES && key.length==32  -> encryptDataAES256  (file key, 16-byte IV)
 *   - useAES                    -> encryptDataAESother (per-object key, IV)
 *   - else                      -> encryptDataRC4      (per-object key)
 *
 * Fuzz vectors: AES ciphertext shorter than 16 bytes (partial IV), exactly 16
 * bytes (IV only, empty payload), non-block-multiple length, empty input, RC4
 * of empty/short, AES-256 (32-byte key) vs AES-128 (per-object key) routing,
 * corrupt padding, and a zero-length key. Deterministic fixed keys/inputs.
 *
 * Driven by reflection so we exercise the production dispatch exactly as the
 * document open path does. The handler's encryptionKey / useAES are set via the
 * public setters; the version-equivalent (AES-256 vs AES-other) is decided by
 * key length, matching upstream's own branch.
 *
 * Line grammar (one per case, manifest order from argv):
 *   CASE &lt;name&gt; &lt;result&gt;
 * where result is one of:
 *   out=&lt;hex-or-empty&gt;
 *   ERR:&lt;ExcSimpleName&gt;
 */
public final class DecryptDataFuzzProbe {

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

    private static Method encryptData() throws Exception {
        // encryptData is declared on the SecurityHandler SUPERCLASS, so walk up
        // the hierarchy rather than using StandardSecurityHandler directly.
        Class<?> c = StandardSecurityHandler.class;
        while (c != null) {
            try {
                Method m = c.getDeclaredMethod(
                        "encryptData", long.class, long.class,
                        java.io.InputStream.class, java.io.OutputStream.class,
                        boolean.class);
                m.setAccessible(true);
                return m;
            } catch (NoSuchMethodException nsme) {
                c = c.getSuperclass();
            }
        }
        throw new NoSuchMethodException("encryptData");
    }

    // spec fields: key aes objnum gennum decrypt data
    private static String doData(String[] f) {
        try {
            StandardSecurityHandler h = new StandardSecurityHandler();
            h.setEncryptionKey(hex(f[0]));
            h.setAES(Boolean.parseBoolean(f[1]));
            long objNum = Long.parseLong(f[2]);
            long genNum = Long.parseLong(f[3]);
            boolean decrypt = Boolean.parseBoolean(f[4]);
            byte[] data = hex(f[5]);
            ByteArrayInputStream in = new ByteArrayInputStream(data);
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            try {
                encryptData().invoke(h, objNum, genNum, in, bos, decrypt);
            } catch (InvocationTargetException ite) {
                Throwable cause = ite.getCause();
                return "ERR:" + (cause == null
                        ? ite.getClass().getSimpleName()
                        : cause.getClass().getSimpleName());
            }
            return "out=" + toHex(bos.toByteArray());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        for (String spec : args) {
            String[] parts = spec.split("\\|", -1);
            String name = parts[0];
            String[] f = new String[parts.length - 1];
            System.arraycopy(parts, 1, f, 0, f.length);
            out.println("CASE " + name + " " + doData(f));
        }
    }
}
