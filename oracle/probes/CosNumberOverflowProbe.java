import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.pdfparser.PDFStreamParser;

/**
 * Live oracle probe for Apache PDFBox 3.0.7's {@code BaseParser.parseCOSNumber}
 * tokenizer — the numeric-literal reader shared by the document-body parser
 * ({@code COSParser}) and the content-stream parser ({@code PDFStreamParser}).
 *
 * Unlike {@code CosNumberProbe} (which calls {@code COSNumber.get(String)}
 * directly), this probe feeds each literal through the actual byte tokenizer
 * so the test pins the END-TO-END parse contract a real PDF exercises:
 *
 *   - {@code parseCOSNumber} accumulates digit / sign / {@code .} / {@code e}/{@code E}
 *     bytes into a {@code StringBuilder}, then hands the string to
 *     {@code COSNumber.get(String)};
 *   - an integer literal beyond Java {@code Long} range therefore does NOT
 *     become a wide integer — {@code COSNumber.get} returns the
 *     {@code OUT_OF_RANGE_MAX} / {@code OUT_OF_RANGE_MIN} {@code COSInteger}
 *     sentinel (value clamped to {@code Long.MAX_VALUE}/{@code MIN_VALUE},
 *     {@code isValid()==false} — PDFBOX-5176);
 *   - leading {@code +}, multiple leading zeros, a trailing dot {@code 5.},
 *     {@code -.5}, etc. all dispatch through the same path.
 *
 * Each CLI arg is a numeric literal. The probe appends a trailing space so the
 * tokenizer terminates the number cleanly. Output: one line per arg.
 *
 * Per-arg signal:
 *   int|valid=<bool>|long=<longValue>|fbits=<floatToIntBits-hex>|str=<toString>
 *   float|long=<longValue>|fbits=<...>|str=<toString>
 *   none                      (no COSBase number token produced)
 *   error                     (parse threw)
 */
public final class CosNumberOverflowProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        for (String lit : args) {
            sb.append(record(lit));
            sb.append('\n');
        }
        out.print(sb);
    }

    private static String record(String lit) {
        // Trailing space terminates the numeric token for the tokenizer.
        byte[] data = (lit + " ").getBytes(StandardCharsets.ISO_8859_1);
        try {
            PDFStreamParser parser = new PDFStreamParser(data);
            Object token = parser.parseNextToken();
            if (token instanceof COSInteger ci) {
                return "int|valid=" + ci.isValid()
                        + "|long=" + ci.longValue()
                        + "|fbits=" + fbits(ci.floatValue())
                        + "|str=" + ci.toString();
            }
            if (token instanceof COSFloat cf) {
                return "float|long=" + cf.longValue()
                        + "|fbits=" + fbits(cf.floatValue())
                        + "|str=" + cf.toString();
            }
            if (!(token instanceof COSBase)) {
                return "none";
            }
            return "other:" + token.getClass().getSimpleName();
        } catch (Exception e) {
            return "error";
        }
    }

    private static String fbits(float f) {
        return Integer.toHexString(Float.floatToIntBits(f));
    }
}
