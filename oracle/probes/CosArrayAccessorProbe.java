import java.io.PrintStream;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;

/**
 * Live oracle probe for COSArray index-accessor coercion / default / grow /
 * search semantics in Apache PDFBox 3.0.7.
 *
 * Builds one fixed COSArray carrying a spread of element shapes — integer,
 * whole-valued float, fractional float, negative float, string, name, explicit
 * COSNull, and an indirect COSObject wrapping an integer — then drives the
 * index-accessor surface across every index plus an out-of-range index and
 * emits one canonical JSON object so the Python side can assert byte/behaviour
 * parity of:
 *
 *   - getInt(i) / getInt(i, default) — accepts any COSNumber via the *raw*
 *     entry (objects.get(i), NOT getObject), so an indirect COSObject wrapping
 *     an integer falls through to the default; intValue() truncates toward 0;
 *   - getName(i) / getName(i, default) — raw entry, COSName only, default else;
 *   - getString(i) / getString(i, default) — raw entry, COSString only;
 *   - get(i) (raw, no deref) vs getObject(i) (deref + COSNull -> null) type tag;
 *   - indexOf (reference/equals) vs indexOfObject (also matches the dereferenced
 *     target of an indirect COSObject);
 *   - growToSize(n) padding with null and growToSize(n, fill) padding with the
 *     fill object; size after each;
 *   - toFloatArray() (getObject deref, COSNumber -> floatValue, else 0.0f).
 *
 * Output: a single JSON object, keys sorted (TreeMap). Floats are emitted as
 * the IEEE-754 single-precision bit pattern in lowercase hex so the comparison
 * is repr-independent.
 */
public final class CosArrayAccessorProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        COSArray a = new COSArray();
        a.add(COSInteger.get(42));                       // 0
        a.add(new COSFloat(7.0f));                       // 1 whole float
        a.add(new COSFloat(3.9f));                       // 2 fractional float
        a.add(new COSFloat(-2.9f));                      // 3 negative float
        a.add(new COSString("hello"));                   // 4
        a.add(COSName.getPDFName("Foo"));                // 5
        a.add(COSNull.NULL);                             // 6
        a.add(new COSObject(COSInteger.get(99)));        // 7 indirect -> int

        TreeMap<String, Object> root = new TreeMap<>();

        // Per-index accessor records (index 0..7 plus 8 = out of range).
        for (int i = 0; i <= 8; i++) {
            TreeMap<String, Object> rec = new TreeMap<>();
            rec.put("getInt", (long) a.getInt(i));
            rec.put("getIntDef5", (long) a.getInt(i, 5));
            rec.put("getName", a.getName(i));
            rec.put("getNameDef", a.getName(i, "DEF"));
            rec.put("getString", a.getString(i));
            rec.put("getStringDef", a.getString(i, "DEF"));
            if (i < a.size()) {
                rec.put("get", typeTag(a.get(i)));
                rec.put("getObject", typeTag(a.getObject(i)));
            } else {
                rec.put("get", "oob");
                rec.put("getObject", "oob");
            }
            root.put(String.valueOf(i), rec);
        }

        // indexOf vs indexOfObject.
        TreeMap<String, Object> idx = new TreeMap<>();
        COSBase intElem = a.get(0);
        idx.put("indexOf_intElem", (long) a.indexOf(intElem));
        COSInteger wrapped = COSInteger.get(99);
        // The indirect element at 7 wraps a distinct COSInteger(99). COSInteger
        // equality is value-based, so indexOfObject should find it via deref.
        idx.put("indexOf_wrapped99", (long) a.indexOf(wrapped));
        idx.put("indexOfObject_wrapped99", (long) a.indexOfObject(wrapped));
        idx.put("indexOfObject_intElem", (long) a.indexOfObject(intElem));
        idx.put("indexOf_absent", (long) a.indexOf(COSName.getPDFName("Nope")));
        idx.put("indexOfObject_absent",
                (long) a.indexOfObject(COSName.getPDFName("Nope")));
        root.put("_index", idx);

        // toFloatArray over the mixed array.
        float[] fa = a.toFloatArray();
        StringBuilder faBits = new StringBuilder("[");
        for (int i = 0; i < fa.length; i++) {
            if (i > 0) {
                faBits.append(",");
            }
            faBits.append('"').append(fbits(fa[i])).append('"');
        }
        faBits.append("]");
        root.put("_toFloatArray", new RawJson(faBits.toString()));

        // growToSize on a fresh small array, then with a fill object.
        COSArray g1 = new COSArray();
        g1.add(COSInteger.get(1));
        g1.growToSize(4);
        TreeMap<String, Object> grow = new TreeMap<>();
        grow.put("nullPad_size", (long) g1.size());
        grow.put("nullPad_tail", typeTag(g1.get(3)));
        // growToSize when already big enough is a no-op.
        g1.growToSize(2);
        grow.put("noop_size", (long) g1.size());

        COSArray g2 = new COSArray();
        g2.growToSize(3, COSInteger.get(8));
        grow.put("fill_size", (long) g2.size());
        grow.put("fill_tail", typeTag(g2.get(2)));
        root.put("_grow", grow);

        // setFloatArray replaces contents and stores COSFloat.
        COSArray sf = new COSArray();
        sf.add(COSName.getPDFName("X"));
        sf.setFloatArray(new float[] {1.5f, -2.0f, 0.0f});
        TreeMap<String, Object> setf = new TreeMap<>();
        setf.put("size", (long) sf.size());
        StringBuilder sfTags = new StringBuilder("[");
        for (int i = 0; i < sf.size(); i++) {
            if (i > 0) {
                sfTags.append(",");
            }
            sfTags.append('"').append(typeTag(sf.get(i))).append('"');
        }
        sfTags.append("]");
        setf.put("tags", new RawJson(sfTags.toString()));
        root.put("_setFloatArray", setf);

        out.print(jsonify(root));
    }

    /** Coarse type tag for a (possibly null) COSBase. */
    private static String typeTag(COSBase b) {
        if (b == null) {
            return "null";
        }
        if (b instanceof COSObject) {
            return "object";
        }
        if (b instanceof COSNull) {
            return "cosnull";
        }
        if (b instanceof COSInteger) {
            return "int:" + ((COSInteger) b).longValue();
        }
        if (b instanceof COSFloat) {
            return "float:" + fbits(((COSFloat) b).floatValue());
        }
        if (b instanceof COSString) {
            return "string:" + ((COSString) b).getString();
        }
        if (b instanceof COSName) {
            return "name:" + ((COSName) b).getName();
        }
        return "other:" + b.getClass().getSimpleName();
    }

    private static String fbits(float f) {
        return Integer.toHexString(Float.floatToIntBits(f));
    }

    // --- minimal JSON emitter ---

    /** Wrapper so a pre-rendered JSON fragment is emitted verbatim. */
    private static final class RawJson {
        final String text;

        RawJson(String text) {
            this.text = text;
        }
    }

    private static String jsonify(Object value) {
        StringBuilder sb = new StringBuilder();
        emit(sb, value);
        return sb.toString();
    }

    private static void emit(StringBuilder sb, Object value) {
        if (value == null) {
            sb.append("null");
        } else if (value instanceof RawJson) {
            sb.append(((RawJson) value).text);
        } else if (value instanceof Map<?, ?>) {
            sb.append("{");
            boolean first = true;
            for (Map.Entry<?, ?> e : ((Map<?, ?>) value).entrySet()) {
                if (!first) {
                    sb.append(",");
                }
                first = false;
                emitString(sb, String.valueOf(e.getKey()));
                sb.append(":");
                emit(sb, e.getValue());
            }
            sb.append("}");
        } else if (value instanceof List<?>) {
            sb.append("[");
            List<?> list = (List<?>) value;
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) {
                    sb.append(",");
                }
                emit(sb, list.get(i));
            }
            sb.append("]");
        } else if (value instanceof Number) {
            sb.append(value.toString());
        } else if (value instanceof Boolean) {
            sb.append(value.toString());
        } else {
            emitString(sb, value.toString());
        }
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
