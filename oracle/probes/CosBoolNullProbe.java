import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.pdfparser.PDFStreamParser;

/**
 * Live oracle probe for Apache PDFBox 3.0.7 {@link COSBoolean} and
 * {@link COSNull} singleton + serialisation behaviour.
 *
 * <p>No CLI args. Emits a single JSON object on stdout (UTF-8) capturing the
 * full leaf-object surface so the Python side can assert byte/behaviour parity:
 *
 * <ul>
 *   <li>{@code COSBoolean.getBoolean(true/false)} returns the {@code TRUE} /
 *       {@code FALSE} singletons (reference identity — the {@code *_id} fields
 *       expose {@code System.identityHashCode} so Python can confirm the two
 *       calls return the same instance and that {@code TRUE != FALSE});</li>
 *   <li>{@code getValue()} / {@code getValueAsObject()};</li>
 *   <li>{@code writePDF(OutputStream)} byte output ({@code true} / {@code false}
 *       / {@code null});</li>
 *   <li>{@code hashCode()} (1231 / 1237 — the {@code java.lang.Boolean}
 *       recipe) and {@code toString()};</li>
 *   <li>{@code COSNull.NULL} identity, {@code writePDF}, {@code toString};</li>
 *   <li>the content-stream tokenizer reading the literal {@code true},
 *       {@code false} and {@code null} tokens back to the very same
 *       singletons (identity again verified via identityHashCode).</li>
 * </ul>
 *
 * Output JSON fields (booleans serialised as the JSON literals true/false):
 *   true_value, true_value_obj, false_value, false_value_obj   (booleans)
 *   getbool_true_is_true, getbool_false_is_false                (identity)
 *   true_ne_false                                               (identity)
 *   true_write, false_write, null_write                         (strings)
 *   true_hash, false_hash                                       (ints)
 *   true_str, false_str, null_str                               (strings)
 *   parsed_true_is_singleton, parsed_false_is_singleton,
 *   parsed_null_is_singleton                                    (booleans)
 */
public final class CosBoolNullProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        COSBoolean t = COSBoolean.getBoolean(true);
        COSBoolean t2 = COSBoolean.getBoolean(true);
        COSBoolean f = COSBoolean.getBoolean(false);
        COSBoolean f2 = COSBoolean.getBoolean(false);

        // Parse the three literal tokens back from a content stream and verify
        // they resolve to the very same singletons.
        boolean parsedTrue = parseScalar("true ") == COSBoolean.TRUE;
        boolean parsedFalse = parseScalar("false ") == COSBoolean.FALSE;
        boolean parsedNull = parseScalar("null ") == COSNull.NULL;

        StringBuilder b = new StringBuilder();
        b.append('{');
        rawkv(b, "true_value", Boolean.toString(t.getValue()));
        b.append(',');
        rawkv(b, "true_value_obj", Boolean.toString(t.getValueAsObject()));
        b.append(',');
        rawkv(b, "false_value", Boolean.toString(f.getValue()));
        b.append(',');
        rawkv(b, "false_value_obj", Boolean.toString(f.getValueAsObject()));
        b.append(',');
        // getBoolean returns the singleton every time (reference identity).
        rawkv(b, "getbool_true_is_singleton",
                Boolean.toString(t == COSBoolean.TRUE && t2 == COSBoolean.TRUE));
        b.append(',');
        rawkv(b, "getbool_false_is_singleton",
                Boolean.toString(f == COSBoolean.FALSE && f2 == COSBoolean.FALSE));
        b.append(',');
        rawkv(b, "true_ne_false", Boolean.toString(t != f));
        b.append(',');
        kv(b, "true_write", writePdf(t));
        b.append(',');
        kv(b, "false_write", writePdf(f));
        b.append(',');
        kv(b, "null_write", writePdf(COSNull.NULL));
        b.append(',');
        rawkv(b, "true_hash", Integer.toString(t.hashCode()));
        b.append(',');
        rawkv(b, "false_hash", Integer.toString(f.hashCode()));
        b.append(',');
        kv(b, "true_str", t.toString());
        b.append(',');
        kv(b, "false_str", f.toString());
        b.append(',');
        kv(b, "null_str", COSNull.NULL.toString());
        b.append(',');
        rawkv(b, "parsed_true_is_singleton", Boolean.toString(parsedTrue));
        b.append(',');
        rawkv(b, "parsed_false_is_singleton", Boolean.toString(parsedFalse));
        b.append(',');
        rawkv(b, "parsed_null_is_singleton", Boolean.toString(parsedNull));
        b.append('}');
        out.print(b);
    }

    /** writePDF the leaf to an ISO-8859-1 string. */
    private static String writePdf(COSBoolean v) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        v.writePDF(bos);
        return new String(bos.toByteArray(), "ISO-8859-1");
    }

    private static String writePdf(COSNull v) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        v.writePDF(bos);
        return new String(bos.toByteArray(), "ISO-8859-1");
    }

    /** Tokenize a tiny content-stream snippet and return its first token. */
    private static Object parseScalar(String snippet) throws Exception {
        PDFStreamParser parser =
                new PDFStreamParser(snippet.getBytes("ISO-8859-1"));
        return parser.parseNextToken();
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
