import java.io.PrintStream;
import org.apache.pdfbox.cos.COSInteger;

/**
 * Live oracle probe for {@code COSInteger.get(long)} interning + accessors.
 *
 * Drives Apache PDFBox 3.0.7's {@link COSInteger#get(long)} static factory over
 * a battery of long values (one per CLI arg, parsed as a Java {@code long}) and
 * emits one JSON object per value so the Python side can assert byte/behaviour
 * parity of:
 *
 *   - the static singleton cache: upstream caches a small contiguous range and
 *     returns the *same* instance for two {@code get(n)} calls inside it, and
 *     distinct instances outside — captured as the {@code interned} flag
 *     ({@code get(n) == get(n)} reference identity, evaluated twice);
 *   - {@code intValue()} / {@code longValue()} (decimal), including the
 *     {@code (int)} narrowing wrap for values beyond 32-bit range;
 *   - {@code floatValue()} as an IEEE-754 bit pattern (repr-independent);
 *   - {@code equals} (two independently-built {@code COSInteger} of equal value
 *     are equal) and {@code hashCode};
 *   - {@code COSBase.toString()} text ("COSInt{..}").
 *
 * Usage: java -cp ... CosIntegerInternProbe "<long1>" "<long2>" ...
 *
 * Output: one JSON object per arg, newline-framed. Fields:
 *   {@code interned} : boolean — get(n) returns the same reference twice
 *   {@code int}      : intValue()  (decimal, may wrap)
 *   {@code long}     : longValue() (decimal)
 *   {@code fbits}    : floatValue()  as float32 bit pattern (lowercase hex)
 *   {@code eq}       : new COSInteger-style equals via get(n).equals(get(n))
 *   {@code hash}     : hashCode()
 *   {@code str}      : toString()
 */
public final class CosIntegerInternProbe {

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
        long value = Long.parseLong(lit);
        COSInteger a = COSInteger.get(value);
        COSInteger b = COSInteger.get(value);
        StringBuilder bld = new StringBuilder();
        bld.append('{');
        rawkv(bld, "interned", Boolean.toString(a == b));
        bld.append(',');
        rawkv(bld, "int", Integer.toString(a.intValue()));
        bld.append(',');
        rawkv(bld, "long", Long.toString(a.longValue()));
        bld.append(',');
        kv(bld, "fbits", fbits(a.floatValue()));
        bld.append(',');
        rawkv(bld, "eq", Boolean.toString(a.equals(b)));
        bld.append(',');
        rawkv(bld, "hash", Integer.toString(a.hashCode()));
        bld.append(',');
        kv(bld, "str", a.toString());
        bld.append('}');
        return bld.toString();
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
