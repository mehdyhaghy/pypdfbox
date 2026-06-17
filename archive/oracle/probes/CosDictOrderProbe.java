import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;

/**
 * Live oracle probe for Apache PDFBox 3.0.7 {@link COSDictionary}
 * key-insertion-order preservation (the backing map is a
 * {@code LinkedHashMap}, so {@code keySet} iterates in insertion order) plus
 * the typed/raw getters: {@code getCOSName}, {@code getCOSArray},
 * {@code getDictionaryObject(firstKey, secondKey)} two-key lookup,
 * {@code getItem} (raw) vs {@code getDictionaryObject} (dereferenced), and
 * {@code setItem(key, null)} removing the key.
 *
 * Each CLI arg names a scenario. Output: one line per arg of the form
 * {@code <scenario>=<signal>}.
 */
public final class CosDictOrderProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        for (String scenario : args) {
            sb.append(scenario).append('=').append(run(scenario)).append('\n');
        }
        out.print(sb);
    }

    private static String run(String scenario) {
        try {
            return signal(scenario);
        } catch (Exception e) {
            return "throws:" + e.getClass().getSimpleName();
        }
    }

    /** Render keySet iteration order as a comparable token list. */
    private static String keys(COSDictionary d) {
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        for (COSName k : d.keySet()) {
            if (!first) sb.append(',');
            sb.append(k.getName());
            first = false;
        }
        return sb.append(']').toString();
    }

    private static String tok(COSBase b) {
        if (b == null) return "null";
        if (b instanceof COSInteger ci) return "int:" + ci.longValue();
        if (b instanceof COSName cn) return "name:" + cn.getName();
        if (b instanceof COSArray ca) return "array:size=" + ca.size();
        if (b instanceof COSObject co) return "object";
        if (b instanceof COSDictionary cd) return "dict:size=" + cd.size();
        return b.getClass().getSimpleName();
    }

    private static String signal(String scenario) {
        switch (scenario) {
            case "order_insert": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("A"), COSInteger.get(1));
                d.setItem(COSName.getPDFName("C"), COSInteger.get(2));
                d.setItem(COSName.getPDFName("B"), COSInteger.get(3));
                return keys(d);
            }
            case "order_overwrite_keeps_position": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("A"), COSInteger.get(1));
                d.setItem(COSName.getPDFName("B"), COSInteger.get(2));
                d.setItem(COSName.getPDFName("C"), COSInteger.get(3));
                d.setItem(COSName.getPDFName("A"), COSInteger.get(99));
                return keys(d) + "|A=" + tok(d.getDictionaryObject(COSName.getPDFName("A")));
            }
            case "order_remove_via_null": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("A"), COSInteger.get(1));
                d.setItem(COSName.getPDFName("B"), COSInteger.get(2));
                d.setItem(COSName.getPDFName("C"), COSInteger.get(3));
                d.setItem(COSName.getPDFName("B"), (COSBase) null);
                return keys(d) + "|size=" + d.size();
            }
            case "order_remove_then_reinsert": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("A"), COSInteger.get(1));
                d.setItem(COSName.getPDFName("B"), COSInteger.get(2));
                d.setItem(COSName.getPDFName("C"), COSInteger.get(3));
                d.setItem(COSName.getPDFName("B"), (COSBase) null);
                d.setItem(COSName.getPDFName("B"), COSInteger.get(22));
                return keys(d);
            }
            case "getCOSName_present": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("Type"), COSName.getPDFName("Page"));
                return tok(d.getCOSName(COSName.TYPE));
            }
            case "getCOSName_wrongtype": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("Type"), COSInteger.get(5));
                return tok(d.getCOSName(COSName.TYPE));
            }
            case "getCOSName_default": {
                COSDictionary d = new COSDictionary();
                return tok(d.getCOSName(COSName.TYPE, COSName.getPDFName("Fallback")));
            }
            case "getCOSArray_present": {
                COSDictionary d = new COSDictionary();
                COSArray a = new COSArray();
                a.add(COSInteger.get(1));
                a.add(COSInteger.get(2));
                d.setItem(COSName.getPDFName("Kids"), a);
                return tok(d.getCOSArray(COSName.getPDFName("Kids")));
            }
            case "getCOSArray_wrongtype": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("Kids"), COSInteger.get(5));
                return tok(d.getCOSArray(COSName.getPDFName("Kids")));
            }
            case "getCOSArray_absent": {
                COSDictionary d = new COSDictionary();
                return tok(d.getCOSArray(COSName.getPDFName("Kids")));
            }
            case "twokey_firstpresent": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("W"), COSInteger.get(1));
                d.setItem(COSName.getPDFName("Width"), COSInteger.get(2));
                return tok(d.getDictionaryObject(COSName.getPDFName("Width"),
                        COSName.getPDFName("W")));
            }
            case "twokey_firstabsent": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("W"), COSInteger.get(7));
                return tok(d.getDictionaryObject(COSName.getPDFName("Width"),
                        COSName.getPDFName("W")));
            }
            case "twokey_bothabsent": {
                COSDictionary d = new COSDictionary();
                return tok(d.getDictionaryObject(COSName.getPDFName("Width"),
                        COSName.getPDFName("W")));
            }
            case "getItem_vs_getDictionaryObject_direct": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("X"), COSInteger.get(42));
                COSBase raw = d.getItem(COSName.getPDFName("X"));
                COSBase deref = d.getDictionaryObject(COSName.getPDFName("X"));
                return "raw=" + tok(raw) + "|deref=" + tok(deref);
            }
            case "setItem_null_removes": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("X"), COSInteger.get(1));
                boolean before = d.containsKey(COSName.getPDFName("X"));
                d.setItem(COSName.getPDFName("X"), (COSBase) null);
                boolean after = d.containsKey(COSName.getPDFName("X"));
                return "before=" + before + "|after=" + after + "|size=" + d.size();
            }
            case "setItem_null_absent_noop": {
                COSDictionary d = new COSDictionary();
                d.setItem(COSName.getPDFName("A"), COSInteger.get(1));
                d.setItem(COSName.getPDFName("Z"), (COSBase) null);
                return keys(d) + "|size=" + d.size();
            }
            default:
                return "UNKNOWN_SCENARIO";
        }
    }
}
