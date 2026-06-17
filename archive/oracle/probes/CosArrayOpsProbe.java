import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSString;

/**
 * Live oracle probe for Apache PDFBox 3.0.7 {@link COSArray} mutation +
 * conversion helpers: {@code setFloatArray}/{@code toFloatArray}/{@code setInt},
 * {@code growToSize(int)} (pads with Java {@code null}, NOT {@code COSNull}),
 * {@code add}/{@code set}/{@code remove(int)}/{@code remove(COSBase)},
 * {@code setName}/{@code getName}, and {@code toList}.
 *
 * Each CLI arg names a scenario. Output: one line per arg of the form
 * {@code <scenario>=<signal>}; an exception is rendered as
 * {@code <scenario>=throws:<SimpleName>} so the index-out-of-range contract
 * (Java {@code ArrayList.set} on an index past the end throws — the typed
 * setters do NOT auto-grow) is pinned exactly.
 */
public final class CosArrayOpsProbe {

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

    /** Render an array's raw contents as a comparable token list. */
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
        if (b instanceof COSInteger ci) return "int:" + ci.longValue();
        if (b instanceof COSFloat cf) return "float:" + cf.floatValue();
        if (b instanceof COSName cn) return "name:" + cn.getName();
        if (b instanceof COSString cs) return "str:" + cs.getString();
        return b.getClass().getSimpleName();
    }

    private static String floats(float[] f) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < f.length; i++) {
            if (i > 0) sb.append(',');
            sb.append(f[i]);
        }
        return sb.append(']').toString();
    }

    private static String signal(String scenario) {
        switch (scenario) {
            case "setFloatArray": {
                COSArray a = new COSArray();
                a.add(COSName.getPDFName("preexisting"));
                a.setFloatArray(new float[] {1.5f, -2.25f, 0f, 100f});
                return dump(a) + "|size=" + a.size();
            }
            case "toFloatArray": {
                COSArray a = new COSArray();
                a.add(COSInteger.get(7));
                a.add(new COSFloat(3.5f));
                a.add(COSName.getPDFName("notnum"));
                a.add(COSNull.NULL);
                return floats(a.toFloatArray());
            }
            case "toFloatArrayEmpty": {
                return floats(new COSArray().toFloatArray());
            }
            case "setInt_inrange": {
                COSArray a = new COSArray();
                a.add(COSInteger.get(0));
                a.add(COSInteger.get(0));
                a.setInt(1, 42);
                return dump(a);
            }
            case "setInt_oob": {
                COSArray a = new COSArray();
                a.add(COSInteger.get(0));
                a.setInt(3, 42);
                return dump(a);
            }
            case "growToSize_grow": {
                COSArray a = new COSArray();
                a.add(COSName.getPDFName("x"));
                a.growToSize(4);
                return dump(a) + "|size=" + a.size();
            }
            case "growToSize_fill": {
                COSArray a = new COSArray();
                a.growToSize(3, COSInteger.get(9));
                return dump(a) + "|size=" + a.size();
            }
            case "growToSize_noshrink": {
                COSArray a = new COSArray();
                a.add(COSInteger.get(1));
                a.add(COSInteger.get(2));
                a.add(COSInteger.get(3));
                a.growToSize(1);
                return dump(a) + "|size=" + a.size();
            }
            case "add": {
                COSArray a = new COSArray();
                a.add(COSInteger.get(5));
                return dump(a);
            }
            case "set_inrange": {
                COSArray a = new COSArray();
                a.add(COSInteger.get(0));
                a.set(0, COSName.getPDFName("y"));
                return dump(a);
            }
            case "set_oob": {
                COSArray a = new COSArray();
                a.set(2, COSName.getPDFName("y"));
                return dump(a);
            }
            case "remove_int": {
                COSArray a = new COSArray();
                a.add(COSInteger.get(1));
                a.add(COSInteger.get(2));
                a.add(COSInteger.get(3));
                COSBase removed = a.remove(1);
                return "removed=" + tok(removed) + "|" + dump(a);
            }
            case "remove_int_oob": {
                COSArray a = new COSArray();
                a.add(COSInteger.get(1));
                a.remove(5);
                return dump(a);
            }
            case "remove_obj_present": {
                COSArray a = new COSArray();
                COSInteger one = COSInteger.get(1);
                a.add(one);
                a.add(COSInteger.get(2));
                a.add(COSInteger.get(1));
                boolean r = a.remove(COSInteger.get(1));
                return "r=" + r + "|" + dump(a);
            }
            case "remove_obj_absent": {
                COSArray a = new COSArray();
                a.add(COSInteger.get(1));
                boolean r = a.remove(COSInteger.get(99));
                return "r=" + r + "|" + dump(a);
            }
            case "setInt_inrange2": {
                COSArray a = new COSArray();
                a.add(COSInteger.get(1));
                a.add(COSInteger.get(2));
                a.setInt(0, 99);
                return dump(a);
            }
            case "setString_inrange": {
                COSArray a = new COSArray();
                a.add(COSName.getPDFName("a"));
                a.add(COSName.getPDFName("b"));
                a.setString(1, "hello");
                return dump(a);
            }
            case "setString_oob": {
                COSArray a = new COSArray();
                a.add(COSName.getPDFName("a"));
                a.setString(2, "hello");
                return dump(a);
            }
            case "setString_null_inrange": {
                COSArray a = new COSArray();
                a.add(COSName.getPDFName("a"));
                a.add(COSName.getPDFName("b"));
                a.setString(1, null);
                return dump(a);
            }
            case "setName_inrange": {
                COSArray a = new COSArray();
                a.add(COSName.getPDFName("a"));
                a.add(COSName.getPDFName("b"));
                a.setName(1, "z");
                return dump(a);
            }
            case "setName_oob": {
                COSArray a = new COSArray();
                a.add(COSName.getPDFName("a"));
                a.setName(4, "z");
                return dump(a);
            }
            case "getName_present": {
                COSArray a = new COSArray();
                a.add(COSName.getPDFName("hello"));
                return String.valueOf(a.getName(0));
            }
            case "getName_default": {
                COSArray a = new COSArray();
                a.add(COSInteger.get(7));
                return a.getName(0, "DEF");
            }
            case "getName_oob": {
                COSArray a = new COSArray();
                return String.valueOf(a.getName(5));
            }
            case "toList": {
                COSArray a = new COSArray();
                a.add(COSInteger.get(1));
                a.add(COSName.getPDFName("n"));
                List<? extends COSBase> l = a.toList();
                StringBuilder sb = new StringBuilder("[");
                for (int i = 0; i < l.size(); i++) {
                    if (i > 0) sb.append(',');
                    sb.append(tok(l.get(i)));
                }
                return sb.append(']').toString() + "|size=" + l.size();
            }
            default:
                return "UNKNOWN_SCENARIO";
        }
    }
}
