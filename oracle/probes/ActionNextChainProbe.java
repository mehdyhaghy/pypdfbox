import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionGoTo;

/**
 * Live oracle probe: pin {@code PDAction.getNext()} list-shape semantics and
 * {@code PDActionFactory.createAction} dispatch for the edge cases pypdfbox's
 * port might diverge on:
 *
 *  - single /Next dict whose /S is an UNKNOWN subtype  → factory returns null,
 *    COSArrayList wraps it as a 1-element list whose sole element is null.
 *  - single /Next dict with NO /S                       → same (null element).
 *  - /Next array mixing a known + an unknown subtype    → list keeps both,
 *    unknown slot is null.
 *  - single /Next dict with a KNOWN subtype             → 1-element list.
 *  - factory dispatch on an unknown subtype             → null.
 *
 * Output: one "case=...\t..." record per scenario; for getNext lists the
 * record reports size and per-element subtype (or "NULLELEM" for a null entry).
 */
public final class ActionNextChainProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();

        // --- factory dispatch on unknown subtype ---
        COSDictionary unknown = new COSDictionary();
        unknown.setName(COSName.S, "TotallyMadeUp");
        PDAction made = org.apache.pdfbox.pdmodel.interactive.action.PDActionFactory
                .createAction(unknown);
        sb.append("case=factory_unknown\tresult=")
          .append(made == null ? "null" : made.getClass().getSimpleName())
          .append('\n');

        // factory dispatch on missing /S
        COSDictionary noS = new COSDictionary();
        PDAction madeNoS = org.apache.pdfbox.pdmodel.interactive.action.PDActionFactory
                .createAction(noS);
        sb.append("case=factory_no_s\tresult=")
          .append(madeNoS == null ? "null" : madeNoS.getClass().getSimpleName())
          .append('\n');

        // factory dispatch on null dict
        PDAction madeNull = org.apache.pdfbox.pdmodel.interactive.action.PDActionFactory
                .createAction(null);
        sb.append("case=factory_null\tresult=")
          .append(madeNull == null ? "null" : madeNull.getClass().getSimpleName())
          .append('\n');

        // --- getNext: single dict, unknown subtype ---
        PDActionGoTo parent1 = new PDActionGoTo();
        COSDictionary nextUnknown = new COSDictionary();
        nextUnknown.setName(COSName.S, "TotallyMadeUp");
        parent1.getCOSObject().setItem(COSName.NEXT, nextUnknown);
        sb.append("case=next_single_unknown\t").append(describe(parent1.getNext())).append('\n');

        // --- getNext: single dict, no /S ---
        PDActionGoTo parent2 = new PDActionGoTo();
        COSDictionary nextNoS = new COSDictionary();
        parent2.getCOSObject().setItem(COSName.NEXT, nextNoS);
        sb.append("case=next_single_no_s\t").append(describe(parent2.getNext())).append('\n');

        // --- getNext: single dict, known subtype (URI) ---
        PDActionGoTo parent3 = new PDActionGoTo();
        COSDictionary nextUri = new COSDictionary();
        nextUri.setName(COSName.S, "URI");
        parent3.getCOSObject().setItem(COSName.NEXT, nextUri);
        sb.append("case=next_single_known\t").append(describe(parent3.getNext())).append('\n');

        // --- getNext: array mixing known + unknown ---
        PDActionGoTo parent4 = new PDActionGoTo();
        COSArray arr = new COSArray();
        COSDictionary a0 = new COSDictionary();
        a0.setName(COSName.S, "Named");
        COSDictionary a1 = new COSDictionary();
        a1.setName(COSName.S, "TotallyMadeUp");
        arr.add(a0);
        arr.add(a1);
        parent4.getCOSObject().setItem(COSName.NEXT, arr);
        sb.append("case=next_array_mixed\t").append(describe(parent4.getNext())).append('\n');

        // --- getNext: array with a null member ---
        PDActionGoTo parent6 = new PDActionGoTo();
        COSArray arr2 = new COSArray();
        COSDictionary b0 = new COSDictionary();
        b0.setName(COSName.S, "Named");
        arr2.add(b0);
        arr2.add(null);
        parent6.getCOSObject().setItem(COSName.NEXT, arr2);
        try {
            sb.append("case=next_array_null_member\t").append(describe(parent6.getNext()))
              .append('\n');
        } catch (Exception e) {
            sb.append("case=next_array_null_member\tEXC=").append(e.getClass().getSimpleName())
              .append('\n');
        }

        // --- getNext: absent ---
        PDActionGoTo parent5 = new PDActionGoTo();
        List<PDAction> n5 = parent5.getNext();
        sb.append("case=next_absent\tresult=").append(n5 == null ? "null" : "size=" + n5.size())
          .append('\n');

        out.print(sb);
    }

    private static String describe(List<PDAction> list) {
        if (list == null) {
            return "result=null";
        }
        StringBuilder s = new StringBuilder("size=").append(list.size());
        for (int i = 0; i < list.size(); i++) {
            PDAction a = list.get(i);
            s.append(';');
            if (a == null) {
                s.append("NULLELEM");
            } else {
                String st = a.getSubType();
                s.append(a.getClass().getSimpleName()).append(':').append(st == null ? "null" : st);
            }
        }
        return s.toString();
    }
}
