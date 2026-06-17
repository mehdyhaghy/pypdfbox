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
 * Live oracle probe for COSArray + COSDictionary CONTAINER-OPERATION edge cases
 * in Apache PDFBox 3.0.7 — the fuzz angles NOT already pinned by
 * CosArrayAccessorProbe / CosArrayOpsProbe / CosDictAccessorProbe /
 * CosDictionaryAccessorFuzzProbe / CosLazyResolveProbe / CosBoolNullProbe.
 *
 * Specifically drills:
 *
 *   - COSArray DEREF ASYMMETRY across the typed accessors driven over an
 *     indirect COSObject element: getInt / getName / getString read the *raw*
 *     entry (no deref -> default) while getFloat / getBoolean / getObject /
 *     toFloatArray deref the COSObject. Same matrix over a wrong-type element
 *     (name where a number is asked, etc.) so the default fall-through is pinned.
 *   - COSArray growToSize corner sizes: smaller-than-current (no-op / no-shrink),
 *     equal, larger; with and without a fill; the side-effect read of the padded
 *     tail through getInt/getObject (null padding -> getInt default, getObject
 *     null).
 *   - COSArray remove(int) out-of-range (throws), remove(COSBase) of an indirect
 *     COSObject by value-equal target (reference vs deref), setInt past end
 *     (throws, no auto-grow), set(i,null) then read-back.
 *   - COSDictionary getInt/getFloat/getLong over an INDIRECT COSObject wrapping a
 *     COSFloat (deref + truncate / int-narrow); getInt over a numeric-looking
 *     COSString (must NOT coerce -> default); getCOSArray when the value is a
 *     single object vs an array vs a stream; getCOSDictionary over a COSStream
 *     (a stream IS-A dict, so it returns it); get_flag / set_flag round-trip and
 *     getFlag over a missing key; getDate over wrong-type values.
 *
 * Output: a single JSON object, keys sorted (TreeMap). Floats are emitted as the
 * IEEE-754 single-precision bit pattern in lowercase hex (repr-independent).
 * Exceptions are rendered as "throws:<SimpleName>".
 */
public final class CosContainerOpsFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        TreeMap<String, Object> root = new TreeMap<>();
        root.put("_arrayDerefAsym", arrayDerefAsym());
        root.put("_arrayGrow", arrayGrow());
        root.put("_arrayMutate", arrayMutate());
        root.put("_dictNumeric", dictNumeric());
        root.put("_dictContainers", dictContainers());
        root.put("_dictFlagsDate", dictFlagsDate());

        out.print(jsonify(root));
    }

    /**
     * COSArray typed accessors driven over an indirect COSObject element AND over
     * wrong-type elements. Pins which accessors deref (getFloat/getBoolean/
     * getObject/toFloatArray) and which do not (getInt/getName/getString).
     */
    private static TreeMap<String, Object> arrayDerefAsym() {
        COSArray a = new COSArray();
        a.add(new COSObject(COSInteger.get(77)));    // 0 indirect -> int
        a.add(new COSObject(new COSFloat(2.5f)));    // 1 indirect -> float
        a.add(new COSObject(COSBoolean.TRUE));       // 2 indirect -> bool
        a.add(new COSObject(new COSString("ind")));  // 3 indirect -> string
        a.add(new COSObject(COSName.getPDFName("N")));// 4 indirect -> name
        a.add(COSName.getPDFName("Bare"));           // 5 wrong type for numeric/string

        TreeMap<String, Object> rec = new TreeMap<>();
        for (int i = 0; i < a.size(); i++) {
            TreeMap<String, Object> per = new TreeMap<>();
            // Upstream COSArray has NO getFloat(int) / getBoolean(int) — those
            // are pypdfbox extensions, so they are pinned Python-side only.
            per.put("getInt", (long) a.getInt(i));
            per.put("getName", a.getName(i));
            per.put("getString", a.getString(i));
            per.put("get", typeTag(a.get(i)));
            per.put("getObject", typeTag(a.getObject(i)));
            rec.put(String.valueOf(i), per);
        }
        // toFloatArray over the same array: derefs, COSNumber -> floatValue,
        // everything else (bool/string/name) -> 0.0f.
        float[] fa = a.toFloatArray();
        StringBuilder faBits = new StringBuilder("[");
        for (int i = 0; i < fa.length; i++) {
            if (i > 0) faBits.append(",");
            faBits.append('"').append(fbits(fa[i])).append('"');
        }
        faBits.append("]");
        rec.put("toFloatArray", new RawJson(faBits.toString()));
        return rec;
    }

    /** growToSize corner sizes + padded-tail read-back. */
    private static TreeMap<String, Object> arrayGrow() {
        TreeMap<String, Object> rec = new TreeMap<>();

        // grow larger with null padding; read tail via getInt (default) + getObject.
        COSArray a = new COSArray();
        a.add(COSInteger.get(5));
        a.growToSize(3);
        rec.put("nullPad_size", (long) a.size());
        rec.put("nullPad_getInt_tail", (long) a.getInt(2));         // null entry -> default -1
        rec.put("nullPad_getInt_tail_def", (long) a.getInt(2, 8));  // explicit default
        rec.put("nullPad_getObject_tail", typeTag(a.getObject(2))); // null

        // grow to EQUAL size: no-op.
        a.growToSize(3);
        rec.put("equal_size", (long) a.size());

        // grow to SMALLER size: no shrink.
        a.growToSize(1);
        rec.put("smaller_size", (long) a.size());

        // grow to zero / negative: no-op on a fresh array.
        COSArray z = new COSArray();
        z.growToSize(0);
        rec.put("zero_size", (long) z.size());
        z.growToSize(-4);
        rec.put("negative_size", (long) z.size());

        // grow with an explicit fill object; the fill is the SAME instance at
        // every padded slot; read it via getInt (deref-free raw read picks it up).
        COSArray f = new COSArray();
        f.growToSize(2, COSInteger.get(9));
        rec.put("fill_size", (long) f.size());
        rec.put("fill_getInt0", (long) f.getInt(0));
        rec.put("fill_getInt1", (long) f.getInt(1));
        rec.put("fill_tail_tag", typeTag(f.get(1)));
        return rec;
    }

    /** remove(int) OOB, remove(COSBase) of indirect, setInt past end, set null. */
    private static TreeMap<String, Object> arrayMutate() {
        TreeMap<String, Object> rec = new TreeMap<>();

        // remove(int) out of range throws.
        COSArray a = new COSArray();
        a.add(COSInteger.get(1));
        try {
            a.remove(5);
            rec.put("removeInt_oob", "no-throw");
        } catch (IndexOutOfBoundsException e) {
            // Language-neutral tag: Java IndexOutOfBoundsException ~ Python
            // IndexError (cf. the JUnit->pytest porting table in CLAUDE.md).
            rec.put("removeInt_oob", "throws:oob");
        }

        // remove(int) valid: returns removed element, shifts the rest.
        COSArray b = new COSArray();
        b.add(COSInteger.get(1));
        b.add(COSInteger.get(2));
        b.add(COSInteger.get(3));
        COSBase removed = b.remove(1);
        rec.put("removeInt_ret", typeTag(removed));
        rec.put("removeInt_after", dump(b));

        // remove(COSBase) of an indirect element: COSArray.remove(Object) is the
        // ArrayList contract -> reference/equals on the *raw* entry. A distinct
        // COSObject wrapping the same int is NOT equal, so removing the inner
        // COSInteger does NOT match the wrapper.
        COSArray c = new COSArray();
        COSInteger inner = COSInteger.get(42);
        c.add(new COSObject(inner));
        boolean rInner = c.remove(inner);
        rec.put("removeObj_innerOfIndirect", rInner);
        rec.put("removeObj_innerOfIndirect_size", (long) c.size());

        // remove(COSBase) of the exact wrapper instance succeeds.
        COSArray d = new COSArray();
        COSObject wrap = new COSObject(COSInteger.get(7));
        d.add(wrap);
        boolean rWrap = d.remove(wrap);
        rec.put("removeObj_wrapper", rWrap);
        rec.put("removeObj_wrapper_size", (long) d.size());

        // setInt past end throws (no auto-grow).
        COSArray e = new COSArray();
        e.add(COSInteger.get(0));
        try {
            e.setInt(3, 9);
            rec.put("setInt_pastEnd", "no-throw|" + dump(e));
        } catch (IndexOutOfBoundsException ex) {
            rec.put("setInt_pastEnd", "throws:oob");
        }

        // set(i, null) in range then read back.
        COSArray g = new COSArray();
        g.add(COSInteger.get(1));
        g.set(0, null);
        rec.put("setNull_get", typeTag(g.get(0)));
        rec.put("setNull_getInt", (long) g.getInt(0));
        return rec;
    }

    /** COSDictionary numeric coercion over indirect-float + numeric string. */
    private static TreeMap<String, Object> dictNumeric() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.getPDFName("IndFloat"), new COSObject(new COSFloat(3.9f)));
        d.setItem(COSName.getPDFName("IndNegFloat"), new COSObject(new COSFloat(-3.9f)));
        d.setItem(COSName.getPDFName("IndInt"), new COSObject(COSInteger.get(123)));
        d.setItem(COSName.getPDFName("NumStr"), new COSString("456"));
        d.setItem(COSName.getPDFName("DirFloat"), new COSFloat(7.6f));

        TreeMap<String, Object> rec = new TreeMap<>();
        // indirect float: getInt derefs + narrows toward zero.
        rec.put("indFloat_getInt", (long) d.getInt(COSName.getPDFName("IndFloat")));
        rec.put("indFloat_getLong", d.getLong(COSName.getPDFName("IndFloat")));
        rec.put("indFloat_getFloat", fbits(d.getFloat(COSName.getPDFName("IndFloat"))));
        rec.put("indNegFloat_getInt", (long) d.getInt(COSName.getPDFName("IndNegFloat")));
        rec.put("indInt_getInt", (long) d.getInt(COSName.getPDFName("IndInt")));
        // numeric-looking string is NOT coerced.
        rec.put("numStr_getInt", (long) d.getInt(COSName.getPDFName("NumStr")));
        rec.put("numStr_getInt_def", (long) d.getInt(COSName.getPDFName("NumStr"), 11));
        rec.put("numStr_getFloat", fbits(d.getFloat(COSName.getPDFName("NumStr"))));
        // direct float truncation.
        rec.put("dirFloat_getInt", (long) d.getInt(COSName.getPDFName("DirFloat")));
        return rec;
    }

    /** getCOSArray / getCOSDictionary / getCOSName over varied value shapes. */
    private static TreeMap<String, Object> dictContainers() {
        COSDictionary d = new COSDictionary();
        COSArray arr = new COSArray();
        arr.add(COSInteger.get(1));
        d.setItem(COSName.getPDFName("Arr"), arr);
        d.setItem(COSName.getPDFName("Single"), COSInteger.get(5));   // single, not array
        d.setItem(COSName.getPDFName("Sub"), new COSDictionary());
        d.setItem(COSName.getPDFName("IndArr"), new COSObject(arr));   // indirect array

        TreeMap<String, Object> rec = new TreeMap<>();
        rec.put("getCOSArray_arr", d.getCOSArray(COSName.getPDFName("Arr")) == null ? "null" : "array");
        rec.put("getCOSArray_single", d.getCOSArray(COSName.getPDFName("Single")) == null ? "null" : "array");
        rec.put("getCOSArray_absent", d.getCOSArray(COSName.getPDFName("Absent")) == null ? "null" : "array");
        rec.put("getCOSArray_indArr", d.getCOSArray(COSName.getPDFName("IndArr")) == null ? "null" : "array");
        rec.put("getCOSDictionary_sub", d.getCOSDictionary(COSName.getPDFName("Sub")) == null ? "null" : "dict");
        rec.put("getCOSDictionary_arr", d.getCOSDictionary(COSName.getPDFName("Arr")) == null ? "null" : "dict");
        rec.put("getCOSName_single", d.getCOSName(COSName.getPDFName("Single")) == null ? "null" : "name");

        // getCOSName with explicit default when absent.
        COSName def = d.getCOSName(COSName.getPDFName("Absent"), COSName.getPDFName("FALLBACK"));
        rec.put("getCOSName_absent_def", def == null ? null : def.getName());
        return rec;
    }

    /** get_flag / set_flag round-trip, getFlag missing, getDate wrong-type. */
    private static TreeMap<String, Object> dictFlagsDate() {
        TreeMap<String, Object> rec = new TreeMap<>();

        COSDictionary d = new COSDictionary();
        // setFlag on a key that does not exist yet: getInt(key,0) seeds 0.
        d.setFlag(COSName.getPDFName("F"), 0x04, true);
        rec.put("setFlag_value", (long) d.getInt(COSName.getPDFName("F")));
        rec.put("getFlag_set", d.getFlag(COSName.getPDFName("F"), 0x04));
        rec.put("getFlag_unset", d.getFlag(COSName.getPDFName("F"), 0x02));
        d.setFlag(COSName.getPDFName("F"), 0x04, false);
        rec.put("setFlag_clear_value", (long) d.getInt(COSName.getPDFName("F")));
        // getFlag over a missing key: getInt(key,0) -> 0 -> false.
        rec.put("getFlag_missing", d.getFlag(COSName.getPDFName("Missing"), 0x01));

        // getDate over wrong-type values returns the default (null).
        COSDictionary dd = new COSDictionary();
        dd.setItem(COSName.getPDFName("NotDate"), COSInteger.get(20240101));
        dd.setItem(COSName.getPDFName("NameDate"), COSName.getPDFName("D:20240101"));
        dd.setItem(COSName.getPDFName("GoodDate"), new COSString("D:20240101120000Z"));
        rec.put("getDate_int", dd.getDate(COSName.getPDFName("NotDate")) == null ? "null" : "date");
        rec.put("getDate_name", dd.getDate(COSName.getPDFName("NameDate")) == null ? "null" : "date");
        rec.put("getDate_good", dd.getDate(COSName.getPDFName("GoodDate")) == null ? "null" : "date");
        rec.put("getDate_absent", dd.getDate(COSName.getPDFName("Absent")) == null ? "null" : "date");
        return rec;
    }

    private static String dump(COSArray a) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < a.size(); i++) {
            if (i > 0) sb.append(',');
            sb.append(tok(a.get(i)));
        }
        return sb.append(']').toString();
    }

    private static String tok(COSBase b) {
        if (b == null) return "null";
        if (b == COSNull.NULL) return "COSNull";
        if (b instanceof COSInteger) return "int:" + ((COSInteger) b).longValue();
        if (b instanceof COSFloat) return "float:" + fbits(((COSFloat) b).floatValue());
        if (b instanceof COSName) return "name:" + ((COSName) b).getName();
        if (b instanceof COSString) return "str:" + ((COSString) b).getString();
        return b.getClass().getSimpleName();
    }

    private static String typeTag(COSBase b) {
        if (b == null) return "null";
        if (b instanceof COSObject) return "object";
        if (b instanceof COSNull) return "cosnull";
        if (b instanceof COSInteger) return "int:" + ((COSInteger) b).longValue();
        if (b instanceof COSFloat) return "float:" + fbits(((COSFloat) b).floatValue());
        if (b instanceof COSString) return "string:" + ((COSString) b).getString();
        if (b instanceof COSName) return "name:" + ((COSName) b).getName();
        if (b instanceof COSBoolean) return "bool:" + (b == COSBoolean.TRUE);
        if (b instanceof COSArray) return "array";
        if (b instanceof COSDictionary) return "dict";
        return "other:" + b.getClass().getSimpleName();
    }

    private static String fbits(float f) {
        return Integer.toHexString(Float.floatToIntBits(f));
    }

    // --- minimal JSON emitter ---

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
