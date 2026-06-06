import java.io.PrintStream;
import java.math.BigDecimal;

/**
 * Live oracle probe: reproduces Apache PDFBox 3.0.7
 * {@code org.apache.pdfbox.multipdf.Overlay#float2String(float)} verbatim
 * (the method is package-private, so the exact body is inlined here) and
 * emits the formatted string for each float value supplied on the command
 * line so pypdfbox's {@code Overlay._float_to_string} can be diffed against
 * the real BigDecimal pipeline.
 *
 * Usage:
 *   java -cp &lt;...&gt; Float2StringProbe &lt;double&gt; [&lt;double&gt; ...]
 *
 * Each argument is parsed as a double, cast to float (matching upstream's
 * {@code (float) v} cast on the affine-matrix entries), and the resulting
 * {@code float2String} output is printed, one line per argument:
 *
 *   &lt;rawIntBits&gt; &lt;formatted&gt;
 *
 * The raw int bits of the float32 are emitted first so the Python side can
 * reconstruct the identical float32 value regardless of double parsing.
 */
public final class Float2StringProbe {

    // Verbatim copy of Overlay.float2String (PDFBox 3.0.7).
    private static String float2String(float floatValue) {
        BigDecimal value = new BigDecimal(String.valueOf(floatValue));
        String stringValue = value.toPlainString();
        if (stringValue.indexOf('.') > -1 && !stringValue.endsWith(".0")) {
            while (stringValue.endsWith("0") && !stringValue.endsWith(".0")) {
                stringValue = stringValue.substring(0, stringValue.length() - 1);
            }
        }
        return stringValue;
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        for (String arg : args) {
            float v = (float) Double.parseDouble(arg);
            out.println(Float.floatToRawIntBits(v) + " " + float2String(v));
        }
    }

    private Float2StringProbe() {}
}
