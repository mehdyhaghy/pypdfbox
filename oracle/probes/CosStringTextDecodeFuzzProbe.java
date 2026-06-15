import java.io.PrintStream;
import org.apache.pdfbox.cos.COSString;

/**
 * Live oracle probe for COSString *text-string decoding* of raw bytes — the
 * {@code new COSString(byte[]).getString()} path that turns a stored byte
 * payload into a Unicode text string. This is a DISTINCT surface from
 * {@code CosStringLiteralEscapeFuzzProbe} (literal {@code (...)} escape lexing)
 * and {@code CosStringWriteProbe} (writing): here we sweep how the SAME raw
 * bytes become text via PDFBox's {@code getString()} fallback chain —
 *   FE FF        -> UTF-16BE,
 *   FF FE        -> UTF-16LE,
 *   (PDF 2.0 / 4.0 also EF BB BF -> UTF-8; 3.0.7 has no such branch),
 *   else         -> PDFDocEncoding (ISO 32000-1 table D.2).
 *
 * Unlike {@code CosStrTextDateProbe} which builds the COSString via
 * {@code COSString.parseHex(...)}, this probe builds it straight from the raw
 * byte array (the constructor path), so the hex argument here is the literal
 * stored byte payload, not a hex-string-literal body.
 *
 * Usage:  java ... CosStringTextDecodeFuzzProbe &lt;hexbytes&gt;
 *
 * Output: space-separated lowercase hex of each Unicode *code point* of
 * getString() (surrogate pairs folded to one supplementary code point so a
 * Python str compares equal). Empty result emits the empty string.
 */
public final class CosStringTextDecodeFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        COSString cs = new COSString(hex(args[0]));
        out.print(codePointHex(cs.getString()));
    }

    /** Space-separated lowercase hex of each Unicode code point. */
    private static String codePointHex(String s) {
        StringBuilder sb = new StringBuilder();
        int i = 0;
        boolean first = true;
        while (i < s.length()) {
            int cp = s.codePointAt(i);
            if (!first) {
                sb.append(' ');
            }
            first = false;
            sb.append(Integer.toHexString(cp));
            i += Character.charCount(cp);
        }
        return sb.toString();
    }

    private static byte[] hex(String h) {
        int n = h.length() / 2;
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) {
            b[i] = (byte) Integer.parseInt(h.substring(2 * i, 2 * i + 2), 16);
        }
        return b;
    }
}
