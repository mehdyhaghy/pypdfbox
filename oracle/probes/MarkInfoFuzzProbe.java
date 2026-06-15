import java.io.PrintStream;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDMarkInfo;

/**
 * Live oracle probe for PDMarkInfo (/MarkInfo catalog dictionary) under
 * MALFORMED input. Projects isMarked / isSuspect / usesUserProperties
 * (each /Marked, /Suspects, /UserProperties bool, default false) across:
 *
 *   - each boolean absent (default false);
 *   - present true / present false;
 *   - WRONG TYPE: int / name / string / array / dict / null where a bool is
 *     expected (PDFBox getBoolean returns the default for any non-COSBoolean);
 *   - indirect references that resolve to a boolean (getDictionaryObject deref);
 *   - empty dict;
 *   - setter round-trips (setMarked/setSuspects/setUserProperties true & false).
 *
 * Output: a single JSON object, keys sorted (TreeMap), so the comparison is
 * order-independent and repr-independent.
 */
public final class MarkInfoFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        TreeMap<String, Object> root = new TreeMap<>();

        // ---- read matrix: drive each of the three keys over every value shape ----
        // We set the SAME shaped value on all three keys for each case so the
        // three getters are exercised uniformly.
        String[] shapes = {
            "absent", "true", "false", "int1", "int0", "name_true", "string_true",
            "array", "dict", "null", "ind_true", "ind_false", "ind_null"
        };
        TreeMap<String, Object> reads = new TreeMap<>();
        for (String shape : shapes) {
            PDMarkInfo mi = new PDMarkInfo(buildDict(shape));
            TreeMap<String, Object> rec = new TreeMap<>();
            rec.put("isMarked", mi.isMarked());
            rec.put("isSuspect", mi.isSuspect());
            rec.put("usesUserProperties", mi.usesUserProperties());
            reads.put(shape, rec);
        }
        root.put("_reads", reads);

        // ---- empty / default constructor ----
        TreeMap<String, Object> def = new TreeMap<>();
        PDMarkInfo empty = new PDMarkInfo();
        def.put("isMarked", empty.isMarked());
        def.put("isSuspect", empty.isSuspect());
        def.put("usesUserProperties", empty.usesUserProperties());
        def.put("cosEmpty", empty.getCOSObject().size() == 0);
        root.put("_default", def);

        // ---- setter round-trips ----
        // NOTE: upstream setSuspect(boolean) ALWAYS writes false (a longstanding
        // PDFBox bug), so isSuspect after setSuspect(true) stays false. We project
        // that exact behavior here.
        TreeMap<String, Object> setters = new TreeMap<>();
        boolean[] vals = {true, false};
        for (boolean v : vals) {
            PDMarkInfo mi = new PDMarkInfo();
            mi.setMarked(v);
            mi.setSuspect(v);
            mi.setUserProperties(v);
            TreeMap<String, Object> rec = new TreeMap<>();
            rec.put("isMarked", mi.isMarked());
            rec.put("isSuspect", mi.isSuspect());
            rec.put("usesUserProperties", mi.usesUserProperties());
            // overwrite a previously-set key with the opposite value
            mi.setMarked(!v);
            rec.put("isMarkedFlip", mi.isMarked());
            setters.put(Boolean.toString(v), rec);
        }
        root.put("_setters", setters);

        out.print(jsonify(root));
    }

    private static COSDictionary buildDict(String shape) {
        COSDictionary d = new COSDictionary();
        COSName[] keys = {
            COSName.getPDFName("Marked"),
            COSName.getPDFName("Suspects"),
            COSName.getPDFName("UserProperties")
        };
        for (COSName k : keys) {
            switch (shape) {
                case "absent":
                    break;
                case "true":
                    d.setItem(k, COSBoolean.TRUE);
                    break;
                case "false":
                    d.setItem(k, COSBoolean.FALSE);
                    break;
                case "int1":
                    d.setItem(k, COSInteger.get(1));
                    break;
                case "int0":
                    d.setItem(k, COSInteger.get(0));
                    break;
                case "name_true":
                    d.setItem(k, COSName.getPDFName("true"));
                    break;
                case "string_true":
                    d.setItem(k, new COSString("true"));
                    break;
                case "array":
                    d.setItem(k, new COSArray());
                    break;
                case "dict":
                    d.setItem(k, new COSDictionary());
                    break;
                case "null":
                    d.setItem(k, COSNull.NULL);
                    break;
                case "ind_true":
                    d.setItem(k, new COSObject(COSBoolean.TRUE));
                    break;
                case "ind_false":
                    d.setItem(k, new COSObject(COSBoolean.FALSE));
                    break;
                case "ind_null":
                    d.setItem(k, new COSObject(COSNull.NULL));
                    break;
                default:
                    throw new IllegalStateException("unknown shape " + shape);
            }
        }
        return d;
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
