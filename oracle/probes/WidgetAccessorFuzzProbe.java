import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.interactive.action.PDAnnotationAdditionalActions;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;

/**
 * Live oracle probe for the WIDGET dictionary accessors NOT covered by
 * WidgetApProbe (/AP) / WidgetIconProbe / WidgetMkProbe (/MK).
 *
 * Surface: the OTHER PDAnnotationWidget accessors against malformed widget
 * dicts:
 *
 *   getHighlightingMode()  -> /H : N/I/O/P/T (default I), unknown name,
 *                                 non-name (string/int), missing
 *   getAppearanceState()   -> /AS : name, non-name, missing
 *   getBorderStyle()       -> /BS : dict present? (none / dict / non-dict)
 *   getActions()           -> /AA : present? (none / dict / non-dict)
 *   getAnnotationFlags()   -> /F : int, missing(->0), non-int(->0),
 *                                 the bit accessors isHidden/isInvisible/...
 *   getParent()            -> /Parent : dict / non-dict / cyclic / missing
 *
 * The probe BUILDS each malformed case in-memory (no file round-trip) and
 * emits a canonical one-line block per case so pypdfbox's read path can be
 * diffed value-for-value:
 *
 *   CASE <id> H=<mode> AS=<state|none> BS=<dict|none> AA=<dict|none>
 *             F=<int> hidden=<0|1> inv=<0|1> print=<0|1> noview=<0|1>
 *             locked=<0|1> Parent=<dict|none>
 */
public final class WidgetAccessorFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        for (String id : IDS) {
            emit(sb, id, build(id));
        }
        out.print(sb);
    }

    private static final String[] IDS = {
        "empty",
        "h_n", "h_i", "h_o", "h_p", "h_t",
        "h_unknown", "h_lower", "h_string", "h_int", "h_array", "h_null",
        "as_on", "as_off", "as_string", "as_int", "as_null",
        "bs_dict", "bs_nondict", "bs_array", "bs_null",
        "aa_dict", "aa_nondict", "aa_array", "aa_null",
        "f_0", "f_2", "f_4", "f_hidden", "f_all",
        "f_string", "f_float", "f_neg", "f_null",
        "parent_dict", "parent_nondict", "parent_cyclic", "parent_null",
    };

    private static PDAnnotationWidget build(String id) {
        COSDictionary d = new COSDictionary();
        switch (id) {
            case "empty":
                break;
            case "h_n": d.setItem(COSName.H, COSName.getPDFName("N")); break;
            case "h_i": d.setItem(COSName.H, COSName.getPDFName("I")); break;
            case "h_o": d.setItem(COSName.H, COSName.getPDFName("O")); break;
            case "h_p": d.setItem(COSName.H, COSName.getPDFName("P")); break;
            case "h_t": d.setItem(COSName.H, COSName.getPDFName("T")); break;
            case "h_unknown": d.setItem(COSName.H, COSName.getPDFName("Z")); break;
            case "h_lower": d.setItem(COSName.H, COSName.getPDFName("i")); break;
            case "h_string": d.setItem(COSName.H, new COSString("O")); break;
            case "h_int": d.setItem(COSName.H, COSInteger.get(3)); break;
            case "h_array": d.setItem(COSName.H, new COSArray()); break;
            case "h_null": d.setItem(COSName.H, COSNull.NULL); break;
            case "as_on": d.setItem(COSName.AS, COSName.getPDFName("On")); break;
            case "as_off": d.setItem(COSName.AS, COSName.getPDFName("Off")); break;
            case "as_string": d.setItem(COSName.AS, new COSString("On")); break;
            case "as_int": d.setItem(COSName.AS, COSInteger.get(1)); break;
            case "as_null": d.setItem(COSName.AS, COSNull.NULL); break;
            case "bs_dict": d.setItem(COSName.BS, new COSDictionary()); break;
            case "bs_nondict": d.setItem(COSName.BS, new COSString("x")); break;
            case "bs_array": d.setItem(COSName.BS, new COSArray()); break;
            case "bs_null": d.setItem(COSName.BS, COSNull.NULL); break;
            case "aa_dict": d.setItem(COSName.AA, new COSDictionary()); break;
            case "aa_nondict": d.setItem(COSName.AA, new COSString("x")); break;
            case "aa_array": d.setItem(COSName.AA, new COSArray()); break;
            case "aa_null": d.setItem(COSName.AA, COSNull.NULL); break;
            case "f_0": d.setInt(COSName.F, 0); break;
            case "f_2": d.setInt(COSName.F, 2); break;
            case "f_4": d.setInt(COSName.F, 4); break;
            case "f_hidden": d.setInt(COSName.F, 2); break;
            case "f_all": d.setInt(COSName.F, 0xFFFF); break;
            case "f_string": d.setItem(COSName.F, new COSString("2")); break;
            case "f_float": d.setItem(COSName.F, new org.apache.pdfbox.cos.COSFloat(2.7f)); break;
            case "f_neg": d.setInt(COSName.F, -2); break;
            case "f_null": d.setItem(COSName.F, COSNull.NULL); break;
            case "parent_dict": d.setItem(COSName.PARENT, new COSDictionary()); break;
            case "parent_nondict": d.setItem(COSName.PARENT, new COSString("x")); break;
            case "parent_cyclic": d.setItem(COSName.PARENT, d); break;
            case "parent_null": d.setItem(COSName.PARENT, COSNull.NULL); break;
            default: throw new IllegalArgumentException(id);
        }
        return new PDAnnotationWidget(d);
    }

    private static void emit(StringBuilder sb, String id, PDAnnotationWidget w) {
        sb.append("CASE ").append(id);
        sb.append(" H=").append(safeH(w));
        sb.append(" AS=").append(w.getAppearanceState() == null ? "none" : w.getAppearanceState().getName());
        sb.append(" BS=").append(bs(w));
        sb.append(" AA=").append(aa(w));
        sb.append(" F=").append(w.getAnnotationFlags());
        sb.append(" hidden=").append(b(w.isHidden()));
        sb.append(" inv=").append(b(w.isInvisible()));
        sb.append(" print=").append(b(w.isPrinted()));
        sb.append(" noview=").append(b(w.isNoView()));
        sb.append(" locked=").append(b(w.isLocked()));
        sb.append(" Parent=").append(parent(w));
        sb.append('\n');
    }

    private static String safeH(PDAnnotationWidget w) {
        try {
            String h = w.getHighlightingMode();
            return h == null ? "null" : h;
        } catch (RuntimeException e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    private static String bs(PDAnnotationWidget w) {
        try {
            PDBorderStyleDictionary bs = w.getBorderStyle();
            return bs == null ? "none" : "dict";
        } catch (RuntimeException e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    private static String aa(PDAnnotationWidget w) {
        try {
            PDAnnotationAdditionalActions aa = w.getActions();
            return aa == null ? "none" : "dict";
        } catch (RuntimeException e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    private static String parent(PDAnnotationWidget w) {
        try {
            COSDictionary p = (COSDictionary) w.getCOSObject().getDictionaryObject(COSName.PARENT);
            return p == null ? "none" : "dict";
        } catch (RuntimeException e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    private static String b(boolean v) {
        return v ? "1" : "0";
    }
}
