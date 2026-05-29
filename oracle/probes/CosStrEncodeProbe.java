import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import org.apache.pdfbox.cos.COSString;

/**
 * Live oracle probe for the {@code COSString(String)} text→bytes ENCODING
 * surface (PDF 32000-1 §7.9.2.2): how a text string passed to the
 * {@code new COSString(String)} constructor is encoded to the underlying
 * byte payload.
 *
 * <p>Upstream rule: if every {@code char} of the input is representable in
 * PDFDocEncoding, the bytes are the PDFDocEncoding of the string; otherwise
 * the bytes are UTF-16BE with a leading {@code FE FF} byte-order mark.
 *
 * <p>The input string is supplied on the command line as the UTF-16BE hex of
 * its UTF-16 code units (lower-hex, no spaces) so the exact {@code char[]}
 * Java sees is unambiguous regardless of the shell / argv encoding. An empty
 * argument denotes the empty string.
 *
 * <p>Two modes:
 * <ul>
 *   <li>{@code enc <utf16behex>} — emit the hex of
 *       {@code new COSString(text).getBytes()} (the constructed byte payload).</li>
 *   <li>{@code rt <utf16behex>} — round-trip: emit the space-separated hex of
 *       each Unicode code point of
 *       {@code new COSString(text).getString()} so the Python side can confirm
 *       {@code getString(new COSString(s)) == s} even across surrogate-pair vs
 *       single-code-point representation differences.</li>
 * </ul>
 *
 * Usage: {@code java -cp ... CosStrEncodeProbe <mode> <utf16behex>}
 */
public final class CosStrEncodeProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        String text = decodeUtf16beHex(args.length > 1 ? args[1] : "");
        if ("enc".equals(mode)) {
            out.print(hex(new COSString(text).getBytes()));
        } else if ("rt".equals(mode)) {
            String s = new COSString(text).getString();
            StringBuilder sb = new StringBuilder();
            int[] cps = s.codePoints().toArray();
            for (int i = 0; i < cps.length; i++) {
                if (i > 0) {
                    sb.append(' ');
                }
                sb.append(Integer.toHexString(cps[i]));
            }
            out.print(sb);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    /** Decode a lower-hex UTF-16BE byte string back to a Java String. */
    static String decodeUtf16beHex(String hex) {
        if (hex.isEmpty()) {
            return "";
        }
        int n = hex.length() / 2;
        byte[] bytes = new byte[n];
        for (int i = 0; i < n; i++) {
            bytes[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        return new String(bytes, StandardCharsets.UTF_16BE);
    }

    private static String hex(byte[] data) {
        StringBuilder s = new StringBuilder(data.length * 2);
        for (byte v : data) {
            s.append(Character.forDigit((v >> 4) & 0xF, 16));
            s.append(Character.forDigit(v & 0xF, 16));
        }
        return s.toString();
    }
}
