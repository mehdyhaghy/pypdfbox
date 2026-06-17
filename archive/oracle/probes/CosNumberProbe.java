import java.io.IOException;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSNumber;

/**
 * Live oracle probe for COSNumber boundary behaviour.
 *
 * Drives Apache PDFBox 3.0.7's numeric COS leaf classes directly on a set of
 * raw numeric literal strings (one per CLI arg) and emits one JSON object per
 * literal so the Python side can assert byte/behaviour parity of:
 *
 *   - {@code COSNumber.get(String)} int-vs-float dispatch and its error cases;
 *   - long-overflow handling (a literal beyond Java {@code Long} range falls
 *     back to the {@code OUT_OF_RANGE_*} {@code COSInteger} sentinel flagged
 *     invalid — PDFBOX-5176);
 *   - {@code COSFloat} construction from malformed reals (leading {@code +},
 *     {@code .5}, {@code 5.}, double-negative, internal {@code -} recovery);
 *   - canonical formatting: {@code COSFloat.toString} trailing-zero handling
 *     and the float32 round-trip serialisation;
 *   - {@code intValue()} / {@code longValue()} / {@code floatValue()}
 *     truncation toward zero.
 *
 * Usage: java -cp ... CosNumberProbe "<lit1>" "<lit2>" ...
 *
 * Output: one JSON object per arg, newline-framed (one line each). Fields:
 *   {@code kind}   : "int" | "float" | "error"
 *   {@code valid}  : (int only) the COSInteger.isValid() flag
 *   {@code int}    : intValue()  (decimal)
 *   {@code long}   : longValue() (decimal)
 *   {@code fbits}  : floatValue() as the IEEE-754 single-precision bit pattern
 *                    (lowercase hex) — repr-independent float comparison
 *   {@code str}    : the COSBase.toString() text ("COSInt{..}" / "COSFloat{..}")
 *
 * For an "error" record only {@code kind} and {@code msg} (exception class
 * simple name) are present.
 */
public final class CosNumberProbe {

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
        try {
            COSNumber n = COSNumber.get(lit);
            StringBuilder b = new StringBuilder();
            b.append('{');
            if (n instanceof COSInteger ci) {
                kv(b, "kind", "int");
                b.append(',');
                rawkv(b, "valid", Boolean.toString(ci.isValid()));
                b.append(',');
            } else if (n instanceof COSFloat) {
                kv(b, "kind", "float");
                b.append(',');
            } else {
                kv(b, "kind", "other");
                b.append(',');
            }
            rawkv(b, "int", Integer.toString(n.intValue()));
            b.append(',');
            rawkv(b, "long", Long.toString(n.longValue()));
            b.append(',');
            kv(b, "fbits", fbits(n.floatValue()));
            b.append(',');
            kv(b, "str", n.toString());
            b.append('}');
            return b.toString();
        } catch (IOException | RuntimeException e) {
            StringBuilder b = new StringBuilder();
            b.append('{');
            kv(b, "kind", "error");
            b.append(',');
            kv(b, "msg", e.getClass().getSimpleName());
            b.append('}');
            return b.toString();
        }
    }

    private static String fbits(float f) {
        return Integer.toHexString(Float.floatToIntBits(f));
    }

    private static void kv(StringBuilder b, String key, String value) {
        emitString(b, key);
        b.append(':');
        emitString(b, value);
    }

    private static void rawkv(StringBuilder b, String key, String value) {
        emitString(b, key);
        b.append(':');
        b.append(value);
    }

    private static void emitString(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\b': sb.append("\\b"); break;
                case '\f': sb.append("\\f"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
    }
}
