import java.io.IOException;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSNumber;

/**
 * COSNumber parse-fuzz differential probe (pypdfbox parity wave 1522).
 *
 * Drives Apache PDFBox 3.0.7's {@code COSNumber.get(String)} factory plus the
 * {@code COSInteger} / {@code COSFloat} leaf accessors on a battery of
 * malformed / boundary numeric literals, emitting one pipe-delimited record per
 * literal so the pypdfbox sibling can assert byte/behaviour parity.
 *
 * Deeper angle than the existing {@code CosNumberProbe} (which pins dispatch +
 * isValid + the raw accessor values): this probe additionally pins
 *
 *   - {@code intValue()} as the JVM {@code (int)} narrowing cast actually
 *     truncates it — a {@code COSInteger} whose value exceeds signed-32-bit
 *     range (the {@code OUT_OF_RANGE_*} sentinels at {@code Long.MAX/MIN}, or
 *     any literal above 2**31-1) wraps modulo 2**32. pypdfbox has unbounded
 *     ints, so this is the contract that exposed the wave-1522 truncation bug
 *     in {@code COSInteger.int_value()};
 *   - the small-value caching identity of {@code COSInteger.get(long)}
 *     (-100..256 inclusive return the SAME instance);
 *   - the {@code equals} / {@code hashCode} contract.
 *
 * Usage: java CosNumberFuzzProbe &lt;literal-hex&gt;
 *
 * The literal is passed as hex of its UTF-8 bytes so embedded control bytes,
 * whitespace, signs, and non-ASCII digits survive the shell intact.
 *
 * Output (single UTF-8 line). For a parsed number:
 *   {@code kind|valid=<b>|int=<i>|long=<l>|fbits=<hex>|str=<text>|cache=<b>}
 * where {@code kind} is {@code int} or {@code float}; {@code valid} and
 * {@code cache} are only meaningful for ints (cache = the value, re-fetched
 * from {@code COSInteger.get(long)}, is the identical instance). For an error:
 *   {@code error}
 */
public final class CosNumberFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] raw = hexToBytes(args[0]);
        String lit = new String(raw, "UTF-8");
        out.print(record(lit));
    }

    private static String record(String lit) {
        try {
            COSNumber n = COSNumber.get(lit);
            StringBuilder b = new StringBuilder();
            if (n instanceof COSInteger ci) {
                b.append("int");
                b.append("|valid=").append(ci.isValid());
                b.append("|int=").append(n.intValue());
                b.append("|long=").append(n.longValue());
                b.append("|fbits=").append(fbits(n.floatValue()));
                b.append("|str=").append(n.toString());
                // Caching identity: re-fetch the same numeric value via the
                // long factory; for -100..256 it is the interned instance.
                COSInteger again = COSInteger.get(ci.longValue());
                COSInteger first = COSInteger.get(ci.longValue());
                b.append("|cache=").append(again == first);
                b.append("|hash=").append(ci.hashCode());
            } else if (n instanceof COSFloat) {
                b.append("float");
                b.append("|int=").append(n.intValue());
                b.append("|long=").append(n.longValue());
                b.append("|fbits=").append(fbits(n.floatValue()));
                b.append("|str=").append(n.toString());
                b.append("|hash=").append(n.hashCode());
            } else {
                b.append("other");
            }
            return b.toString();
        } catch (IOException | RuntimeException e) {
            return "error";
        }
    }

    private static String fbits(float f) {
        return Integer.toHexString(Float.floatToIntBits(f));
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
