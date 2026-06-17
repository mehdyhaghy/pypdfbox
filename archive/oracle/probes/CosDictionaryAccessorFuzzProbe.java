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
 * Live oracle probe for COSDictionary typed-accessor coercion under MALFORMED /
 * EDGE input — the fuzz complement to CosDictAccessorProbe (which covers the
 * common-shape matrix). This probe deliberately drills the corners the basic
 * probe does not:
 *
 *   - wrong-type coercion MATRIX: getInt / getLong / getFloat / getBoolean /
 *     getCOSName / getNameAsString / getString each driven over EVERY value
 *     shape (string, name, bool, array, dict, null), confirming the sentinel /
 *     default is returned for every mismatch;
 *   - numeric OVERFLOW / wrap: getInt over COSInteger values at and beyond the
 *     signed-32-bit boundary (2^31, 2^31-1, -2^31, Long.MAX, Long.MIN) where
 *     intValue() does a (int) narrowing-cast wrap; getLong / getFloat on the
 *     same; getInt over a huge / tiny COSFloat where f2i saturates;
 *   - getNameAsString coercing a COSString to text but NOT an int;
 *   - getDictionaryObject indirect resolution AND the two-key fallback when the
 *     first key resolves to COSNull (must fall through to the second key);
 *   - getItem vs getDictionaryObject on an indirect-COSNull entry (raw keeps the
 *     COSObject; resolved collapses to null);
 *   - COSName-key vs String-key overload equivalence (every accessor takes both;
 *     they must agree).
 *
 * Output: a single JSON object, keys sorted (TreeMap), floats as IEEE-754
 * single-precision bits in lowercase hex so the comparison is repr-independent.
 */
public final class CosDictionaryAccessorFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        TreeMap<String, Object> root = new TreeMap<>();

        // ---- wrong-type coercion matrix ----
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.getPDFName("Str"), new COSString("hello"));
        d.setItem(COSName.getPDFName("NumStr"), new COSString("123"));
        d.setItem(COSName.getPDFName("Name"), COSName.getPDFName("Foo"));
        d.setItem(COSName.getPDFName("BoolT"), COSBoolean.TRUE);
        d.setItem(COSName.getPDFName("BoolF"), COSBoolean.FALSE);
        d.setItem(COSName.getPDFName("Arr"), new COSArray());
        d.setItem(COSName.getPDFName("Sub"), new COSDictionary());
        d.setItem(COSName.getPDFName("Null"), COSNull.NULL);

        String[] wrongKeys = {
            "Str", "NumStr", "Name", "BoolT", "BoolF", "Arr", "Sub", "Null", "Absent"
        };
        TreeMap<String, Object> matrix = new TreeMap<>();
        for (String k : wrongKeys) {
            COSName key = COSName.getPDFName(k);
            TreeMap<String, Object> rec = new TreeMap<>();
            rec.put("getInt", (long) d.getInt(key));
            rec.put("getIntDef7", (long) d.getInt(key, 7));
            rec.put("getLong", d.getLong(key));
            rec.put("getFloat", fbits(d.getFloat(key)));
            rec.put("getBoolDefT", d.getBoolean(key, true));
            COSName cn = d.getCOSName(key);
            rec.put("getCOSName", cn == null ? null : cn.getName());
            rec.put("getNameAsString", d.getNameAsString(key));
            rec.put("getString", d.getString(key));
            matrix.put(k, rec);
        }
        root.put("_wrongType", matrix);

        // ---- numeric overflow / wrap matrix (getInt/getLong/getFloat) ----
        COSDictionary n = new COSDictionary();
        n.setItem(COSName.getPDFName("I_2p31"), COSInteger.get(2147483648L));      // 2^31
        n.setItem(COSName.getPDFName("I_2p31m1"), COSInteger.get(2147483647L));    // 2^31-1
        n.setItem(COSName.getPDFName("I_neg2p31"), COSInteger.get(-2147483648L));  // -2^31
        n.setItem(COSName.getPDFName("I_neg2p31m1"), COSInteger.get(-2147483649L));// -(2^31+1)
        n.setItem(COSName.getPDFName("I_longmax"), COSInteger.get(Long.MAX_VALUE));
        n.setItem(COSName.getPDFName("I_longmin"), COSInteger.get(Long.MIN_VALUE));
        n.setItem(COSName.getPDFName("F_huge"), new COSFloat(1.0e30f));
        n.setItem(COSName.getPDFName("F_neghuge"), new COSFloat(-1.0e30f));
        n.setItem(COSName.getPDFName("F_tiny"), new COSFloat(0.4f));
        n.setItem(COSName.getPDFName("F_negtiny"), new COSFloat(-0.4f));

        String[] numKeys = {
            "I_2p31", "I_2p31m1", "I_neg2p31", "I_neg2p31m1", "I_longmax",
            "I_longmin", "F_huge", "F_neghuge", "F_tiny", "F_negtiny"
        };
        TreeMap<String, Object> num = new TreeMap<>();
        for (String k : numKeys) {
            COSName key = COSName.getPDFName(k);
            TreeMap<String, Object> rec = new TreeMap<>();
            rec.put("getInt", (long) n.getInt(key));
            rec.put("getLong", n.getLong(key));
            rec.put("getFloat", fbits(n.getFloat(key)));
            num.put(k, rec);
        }
        root.put("_numeric", num);

        // ---- indirect resolution + two-key fallback through COSNull ----
        COSDictionary ind = new COSDictionary();
        ind.setItem(COSName.getPDFName("IndInt"), new COSObject(COSInteger.get(55)));
        ind.setItem(COSName.getPDFName("IndNull"), new COSObject(COSNull.NULL));
        ind.setItem(COSName.getPDFName("DirNull"), COSNull.NULL);
        ind.setItem(COSName.getPDFName("Real"), COSInteger.get(9));

        TreeMap<String, Object> ix = new TreeMap<>();
        // getInt dereferences the indirect int.
        ix.put("getInt_indInt", (long) ind.getInt(COSName.getPDFName("IndInt")));
        // getDictionaryObject collapses indirect-null and direct-null to null.
        ix.put("dictObj_indNull", typeTag(ind.getDictionaryObject(COSName.getPDFName("IndNull"))));
        ix.put("dictObj_dirNull", typeTag(ind.getDictionaryObject(COSName.getPDFName("DirNull"))));
        // getItem keeps the raw COSObject for indirect-null, raw COSNull for direct.
        ix.put("item_indNull", typeTag(ind.getItem(COSName.getPDFName("IndNull"))));
        ix.put("item_dirNull", typeTag(ind.getItem(COSName.getPDFName("DirNull"))));
        // two-key: first key resolves to COSNull -> falls through to second.
        ix.put("twoKey_dirNullThenReal",
                typeTag(ind.getDictionaryObject(COSName.getPDFName("DirNull"),
                        COSName.getPDFName("Real"))));
        ix.put("twoKey_indNullThenReal",
                typeTag(ind.getDictionaryObject(COSName.getPDFName("IndNull"),
                        COSName.getPDFName("Real"))));
        // getInt two-key with first resolving to null.
        ix.put("getInt_twoKey_dirNull",
                (long) ind.getInt(COSName.getPDFName("DirNull"),
                        COSName.getPDFName("Real"), 3));
        root.put("_indirect", ix);

        // ---- COSName-key vs String-key overload equivalence ----
        TreeMap<String, Object> ov = new TreeMap<>();
        COSDictionary o = new COSDictionary();
        o.setItem(COSName.getPDFName("K"), COSInteger.get(17));
        ov.put("byName", (long) o.getInt(COSName.getPDFName("K")));
        ov.put("byString", (long) o.getInt("K"));
        ov.put("nameMissing", (long) o.getInt(COSName.getPDFName("X")));
        ov.put("stringMissing", (long) o.getInt("X"));
        root.put("_overload", ov);

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
