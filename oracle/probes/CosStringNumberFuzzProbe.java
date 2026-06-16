import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSString;

/**
 * Combined COSString / COSFloat / COSInteger edge-fuzz differential probe
 * (pypdfbox parity wave 1544).
 *
 * Distinct from the existing single-surface probes:
 *
 *   - {@code CosStringTextDecodeFuzzProbe} pins ONLY {@code getString()} code
 *     points; this probe additionally pins {@code toHexString()} on the SAME
 *     raw-byte payload (the stored-bytes round-trip the writer relies on), so a
 *     decode-vs-store divergence is caught in one record.
 *   - {@code CosNumberFuzzProbe} pins {@code COSNumber.get(String)} dispatch and
 *     {@code toString()}; this probe drives the {@code COSFloat(String)} and
 *     {@code COSInteger.get(long)} leaf constructors DIRECTLY and pins the
 *     IEEE-754 single-precision bit pattern of {@code floatValue()} together
 *     with the {@code writePDF} serialization (the bytes that actually reach a
 *     PDF), plus {@code intValue()} narrowing on huge ints.
 *
 * Usage:
 *   java ... CosStringNumberFuzzProbe str   &lt;hexbytes&gt;   # COSString(byte[])
 *   java ... CosStringNumberFuzzProbe float &lt;literalHex&gt; # COSFloat(String)
 *   java ... CosStringNumberFuzzProbe int   &lt;decimal&gt;    # COSInteger.get(long)
 *
 * Output (UTF-8, single line):
 *
 *   str   : {@code cp=<codepoints>|hex=<toHexString>}
 *           where codepoints is space-separated lowercase hex of each Unicode
 *           code point of getString() (surrogate pairs folded), and hex is the
 *           uppercase toHexString() of the stored bytes. Empty getString emits
 *           {@code cp=|hex=...}.
 *
 *   float : {@code ok|fbits=<hex>|fmt=<writePDF-bytes>} or {@code error}.
 *           fbits is {@code Integer.toHexString(Float.floatToIntBits(floatValue))}
 *           and fmt is the ISO-8859-1 decode of writePDF's bytes (the serialized
 *           real-number literal).
 *
 *   int   : {@code i=<intValue>|l=<longValue>|w=<writePDF-bytes>} or
 *           {@code error}.
 *
 * The float literal and string bytes are passed as hex so signs / control bytes
 * / whitespace survive the shell intact.
 */
public final class CosStringNumberFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("str".equals(mode)) {
            out.print(strRecord(hexToBytes(args[1])));
        } else if ("float".equals(mode)) {
            out.print(floatRecord(new String(hexToBytes(args[1]), "UTF-8")));
        } else if ("int".equals(mode)) {
            out.print(intRecord(args[1]));
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static String strRecord(byte[] raw) {
        COSString cs = new COSString(raw);
        return "cp=" + codePointHex(cs.getString()) + "|hex=" + cs.toHexString();
    }

    private static String floatRecord(String lit) {
        try {
            COSFloat f = new COSFloat(lit);
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            f.writePDF(baos);
            String fmt = new String(baos.toByteArray(), "ISO-8859-1");
            return "ok|fbits=" + fbits(f.floatValue()) + "|fmt=" + fmt;
        } catch (IOException | RuntimeException e) {
            return "error";
        }
    }

    private static String intRecord(String decimal) {
        try {
            COSInteger ci = COSInteger.get(Long.parseLong(decimal));
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            ci.writePDF(baos);
            String w = new String(baos.toByteArray(), "ISO-8859-1");
            return "i=" + ci.intValue() + "|l=" + ci.longValue() + "|w=" + w;
        } catch (IOException | RuntimeException e) {
            return "error";
        }
    }

    private static String fbits(float f) {
        return Integer.toHexString(Float.floatToIntBits(f));
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

    private static byte[] hexToBytes(String hex) {
        int n = hex.length() / 2;
        byte[] out = new byte[n];
        for (int i = 0; i < n; i++) {
            out[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }
}
