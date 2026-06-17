import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureElement;
import org.apache.pdfbox.pdmodel.documentinterchange.taggedpdf.PDLayoutAttributeObject;
import org.apache.pdfbox.pdmodel.documentinterchange.taggedpdf.PDListAttributeObject;

/**
 * Live oracle probe: dump the COS shape of /A and /C after a fixed sequence of
 * PDStructureElement attribute / class-name mutations, plus the stateful
 * getAttributes() / getClassNames() projection over hand-built (possibly
 * malformed) arrays.
 *
 * Pure in-memory — no PDF round trip needed. Emits one canonical line per case
 * so pypdfbox can be compared line-for-line.
 *
 *   ASHAPE\t<case>\t<cosShape>
 *   CSHAPE\t<case>\t<cosShape>
 *   AGET\t<case>\t<owner@rev,owner@rev,...>
 *
 * cosShape renders /A as: "null" (absent), "dict:<O>" (bare dict),
 *   "[<elem>;<elem>;...]" array, where elem is "d:<O>" for a dictionary,
 *   "i<n>" for an integer, "?" otherwise.
 */
public final class StructAttrMutateProbe {
    private static final COSName A = COSName.A;
    private static final COSName C = COSName.C;
    private static final COSName O = COSName.getPDFName("O");

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // --- /A remove-to-empty: add one, remove it. ---
        PDStructureElement e1 = new PDStructureElement("P", null);
        PDLayoutAttributeObject a1 = new PDLayoutAttributeObject();
        e1.addAttribute(a1);
        e1.removeAttribute(a1);
        out.println("ASHAPE\tremove_only\t" + aShape(e1, A));

        // --- /A remove one of two. ---
        PDStructureElement e2 = new PDStructureElement("P", null);
        PDLayoutAttributeObject l = new PDLayoutAttributeObject();
        PDListAttributeObject li = new PDListAttributeObject();
        e2.addAttribute(l);
        e2.addAttribute(li);
        e2.removeAttribute(l);
        out.println("ASHAPE\tremove_first_of_two\t" + aShape(e2, A));

        // --- /C remove-to-empty. ---
        PDStructureElement e3 = new PDStructureElement("P", null);
        e3.addClassName("warm");
        e3.removeClassName("warm");
        out.println("CSHAPE\tremove_only\t" + aShape(e3, C));

        // --- /C remove one of two. ---
        PDStructureElement e4 = new PDStructureElement("P", null);
        e4.addClassName("warm");
        e4.addClassName("cold");
        e4.removeClassName("warm");
        out.println("CSHAPE\tremove_first_of_two\t" + aShape(e4, C));

        // --- bare-dict /A getAttributes revision (upstream: rev 0). ---
        PDStructureElement e5 = new PDStructureElement("P", null);
        e5.setRevisionNumber(4);
        COSDictionary bare = new COSDictionary();
        bare.setName(O, "Layout");
        e5.getCOSObject().setItem(A, bare);
        out.println("AGET\tbare_dict_rev4\t" + aGet(e5));

        // --- leading orphan integer in /A array. ---
        PDStructureElement e6 = new PDStructureElement("P", null);
        COSArray arr6 = new COSArray();
        arr6.add(COSInteger.get(5));
        arr6.add(layoutDict());
        e6.getCOSObject().setItem(A, arr6);
        out.println("AGET\tleading_int\t" + aGet(e6));

        // --- double integer after dict in /A array (last wins). ---
        PDStructureElement e7 = new PDStructureElement("P", null);
        COSArray arr7 = new COSArray();
        arr7.add(layoutDict());
        arr7.add(COSInteger.get(1));
        arr7.add(COSInteger.get(2));
        arr7.add(listDict());
        e7.getCOSObject().setItem(A, arr7);
        out.println("AGET\tdouble_int\t" + aGet(e7));

        // --- addAttribute onto bare dict (promotes to array). ---
        PDStructureElement e8 = new PDStructureElement("P", null);
        COSDictionary bare8 = new COSDictionary();
        bare8.setName(O, "Layout");
        e8.getCOSObject().setItem(A, bare8);
        e8.setRevisionNumber(3);
        PDListAttributeObject added = new PDListAttributeObject();
        e8.addAttribute(added);
        out.println("ASHAPE\tadd_onto_bare\t" + aShape(e8, A));

        // --- remove a MISSING attribute from [dict, 0]: the size==2 collapse
        //     still fires, collapsing /A to a bare dict. ---
        PDStructureElement e9 = new PDStructureElement("P", null);
        PDLayoutAttributeObject present = new PDLayoutAttributeObject();
        PDListAttributeObject missing = new PDListAttributeObject();
        e9.addAttribute(present);
        e9.removeAttribute(missing);
        out.println("ASHAPE\tremove_missing\t" + aShape(e9, A));
        e9.removeAttribute(present);
        out.println("ASHAPE\tremove_missing_then_present\t" + aShape(e9, A));
    }

    private static COSDictionary layoutDict() {
        COSDictionary d = new COSDictionary();
        d.setName(O, "Layout");
        return d;
    }

    private static COSDictionary listDict() {
        COSDictionary d = new COSDictionary();
        d.setName(O, "List");
        return d;
    }

    private static String aGet(PDStructureElement e) {
        StringBuilder sb = new StringBuilder();
        var revs = e.getAttributes();
        for (int i = 0; i < revs.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(revs.getObject(i).getOwner());
            sb.append('@');
            sb.append(revs.getRevisionNumber(i));
        }
        return sb.length() == 0 ? "-" : sb.toString();
    }

    private static String aShape(PDStructureElement e, COSName key) {
        COSBase v = e.getCOSObject().getDictionaryObject(key);
        if (v == null) {
            return "null";
        }
        if (v instanceof COSArray) {
            COSArray a = (COSArray) v;
            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < a.size(); i++) {
                if (i > 0) {
                    sb.append(';');
                }
                COSBase item = a.getObject(i);
                if (item instanceof COSDictionary) {
                    COSBase o = ((COSDictionary) item).getDictionaryObject(O);
                    sb.append("d:").append(o instanceof COSName ? ((COSName) o).getName() : "?");
                } else if (item instanceof COSInteger) {
                    sb.append('i').append(((COSInteger) item).intValue());
                } else if (item instanceof COSName) {
                    sb.append("n:").append(((COSName) item).getName());
                } else {
                    sb.append('?');
                }
            }
            sb.append(']');
            return sb.toString();
        }
        if (v instanceof COSDictionary) {
            COSBase o = ((COSDictionary) v).getDictionaryObject(O);
            return "dict:" + (o instanceof COSName ? ((COSName) o).getName() : "?");
        }
        if (v instanceof COSName) {
            return "name:" + ((COSName) v).getName();
        }
        return "?";
    }
}
