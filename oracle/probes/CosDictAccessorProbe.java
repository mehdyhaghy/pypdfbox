import java.io.PrintStream;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;

/**
 * Live oracle probe for COSDictionary typed-accessor coercion / default
 * semantics.
 *
 * Builds one fixed COSDictionary carrying a spread of value shapes — integer,
 * float, whole-valued float, string, name, both booleans, array, sub-dict,
 * explicit COSNull, an indirect COSObject wrapping an integer, an indirect
 * COSObject wrapping COSNull, and a negative float — then drives Apache PDFBox
 * 3.0.7's accessor surface across them and emits one canonical JSON object so
 * the Python side can assert byte/behaviour parity of:
 *
 *   - getInt / getLong / getFloat numeric coercion (any COSNumber, intValue /
 *     longValue / floatValue truncation toward zero) and the -1 default on
 *     absent / wrong-type / COSNull;
 *   - getString returning the decoded text only for COSString (NOT for COSName)
 *     and null otherwise;
 *   - getCOSName returning the name only for COSName;
 *   - getBoolean returning the primitive only for COSBoolean, default otherwise;
 *   - getDictionaryObject dereferencing indirect COSObject and collapsing
 *     COSNull (direct and indirect) to null;
 *   - getItem returning the raw, un-dereferenced entry (so an indirect COSObject
 *     stays a reference);
 *   - the two-key overloads (getDictionaryObject / getItem / getInt / getBoolean
 *     firstKey,secondKey) falling back to the second key only when the first is
 *     absent.
 *
 * Usage: java -cp ... CosDictAccessorProbe
 *
 * Output: a single JSON object, keys sorted (TreeMap), values rendered in a
 * repr-independent canonical form (floats as IEEE-754 single-precision bits in
 * lowercase hex, booleans/ints raw, strings quoted, absent/null as the literal
 * JSON null).
 */
public final class CosDictAccessorProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        COSDictionary d = new COSDictionary();
        d.setItem(COSName.getPDFName("Int"), COSInteger.get(42));
        d.setItem(COSName.getPDFName("Float"), new COSFloat(3.5f));
        d.setItem(COSName.getPDFName("WholeFloat"), new COSFloat(7.0f));
        d.setItem(COSName.getPDFName("NegFloat"), new COSFloat(-2.9f));
        d.setItem(COSName.getPDFName("Str"), new COSString("hello"));
        d.setItem(COSName.getPDFName("Name"), COSName.getPDFName("Foo"));
        d.setItem(COSName.getPDFName("BoolT"), COSBoolean.TRUE);
        d.setItem(COSName.getPDFName("BoolF"), COSBoolean.FALSE);
        d.setItem(COSName.getPDFName("Arr"), new COSArray());
        d.setItem(COSName.getPDFName("Sub"), new COSDictionary());
        d.setItem(COSName.getPDFName("Null"), COSNull.NULL);
        d.setItem(COSName.getPDFName("IndInt"), new COSObject(COSInteger.get(99)));
        d.setItem(COSName.getPDFName("IndNull"), new COSObject(COSNull.NULL));

        TreeMap<String, Object> root = new TreeMap<>();

        // keys to exercise: a present-of-each-shape plus an absent one.
        String[] keys = {
            "Int", "Float", "WholeFloat", "NegFloat", "Str", "Name",
            "BoolT", "BoolF", "Arr", "Sub", "Null", "IndInt", "IndNull",
            "Absent"
        };
        for (String k : keys) {
            COSName key = COSName.getPDFName(k);
            TreeMap<String, Object> rec = new TreeMap<>();
            // getInt default -1
            rec.put("getInt", (long) d.getInt(key));
            // getInt with explicit default 5
            rec.put("getIntDef5", (long) d.getInt(key, 5));
            // getLong default -1
            rec.put("getLong", d.getLong(key));
            // getFloat default -1
            rec.put("getFloat", fbits(d.getFloat(key)));
            // getFloat with explicit default 2.5
            rec.put("getFloatDef", fbits(d.getFloat(key, 2.5f)));
            // getString default null
            rec.put("getString", d.getString(key));
            // getString with default
            rec.put("getStringDef", d.getString(key, "DEF"));
            // getCOSName as text (null if not a name)
            COSName cn = d.getCOSName(key);
            rec.put("getCOSName", cn == null ? null : cn.getName());
            // getBoolean default false
            rec.put("getBoolFalse", d.getBoolean(key, false));
            // getBoolean default true
            rec.put("getBoolTrue", d.getBoolean(key, true));
            // getDictionaryObject -> type tag (deref + collapse null)
            rec.put("getDictObj", typeTag(d.getDictionaryObject(key)));
            // getItem -> type tag (raw, no deref)
            rec.put("getItem", typeTag(d.getItem(key)));
            root.put(k, rec);
        }

        // two-key overloads: present-first, absent-first-present-second,
        // both-absent.
        TreeMap<String, Object> two = new TreeMap<>();
        two.put("firstPresent",
                typeTag(d.getDictionaryObject(COSName.getPDFName("Int"),
                        COSName.getPDFName("Float"))));
        two.put("firstAbsent",
                typeTag(d.getDictionaryObject(COSName.getPDFName("Nope"),
                        COSName.getPDFName("Float"))));
        two.put("bothAbsent",
                typeTag(d.getDictionaryObject(COSName.getPDFName("Nope"),
                        COSName.getPDFName("Nope2"))));
        // getItem two-key (raw) on an indirect first vs absent-first
        two.put("itemFirstPresent",
                typeTag(d.getItem(COSName.getPDFName("IndInt"),
                        COSName.getPDFName("Int"))));
        two.put("itemFirstAbsent",
                typeTag(d.getItem(COSName.getPDFName("Nope"),
                        COSName.getPDFName("IndInt"))));
        // getInt two-key
        two.put("intFirstAbsent",
                (long) d.getInt(COSName.getPDFName("Nope"),
                        COSName.getPDFName("Int"), 7));
        two.put("intBothAbsent",
                (long) d.getInt(COSName.getPDFName("Nope"),
                        COSName.getPDFName("Nope2"), 7));
        // getBoolean two-key
        two.put("boolFirstAbsent",
                d.getBoolean(COSName.getPDFName("Nope"),
                        COSName.getPDFName("BoolT"), false));
        root.put("_twoKey", two);

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
        if (b instanceof COSBoolean) {
            return "bool:" + (b == COSBoolean.TRUE);
        }
        // Array must precede Dictionary? COSArray is not a COSDictionary.
        if (b instanceof COSArray) {
            return "array";
        }
        if (b instanceof COSDictionary) {
            return "dict";
        }
        return "other:" + b.getClass().getSimpleName();
    }

    private static String fbits(float f) {
        return Integer.toHexString(Float.floatToIntBits(f));
    }

    // --- minimal JSON emitter ---

    private static String jsonify(Object value) {
        StringBuilder sb = new StringBuilder();
        emit(sb, value);
        return sb.toString();
    }

    private static void emit(StringBuilder sb, Object value) {
        if (value == null) {
            sb.append("null");
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
