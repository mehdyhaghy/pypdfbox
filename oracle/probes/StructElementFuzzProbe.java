import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDMarkInfo;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureElement;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureNode;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.Revisions;

/**
 * Differential malformed structure-element accessor probe (wave 1540, agent D).
 *
 * Complements the wave-1531 StructureElementFuzzProbe by widening the fuzz to
 * accessor corners that probe did not exercise:
 *   - /C class names (getClassNames Revisions<String>) — single name vs array
 *     vs interleaved revision integers vs wrong type (string / dict / array).
 *   - /Pg page as array / integer / wrong-type (dangling) — not just string.
 *   - /R revision huge / very-large positive (32-bit identity).
 *   - /E expanded form / string slots as a /Name vs an integer (getString only
 *     decodes COSString — a name or int leaves the slot null).
 *   - getStandardStructureType across a two-hop /RoleMap chain (upstream does a
 *     SINGLE lookup, so a second hop is NOT followed).
 *   - kids count + kind for a single-dict /K, a deeply nested /K subtree, and a
 *     /K that is itself an MCID integer.
 * Plus a compact PDMarkInfo section over absent / true / false / non-bool.
 */
public final class StructElementFuzzProbe {

    private static COSArray array(COSBase... values) {
        COSArray out = new COSArray();
        for (COSBase value : values) out.add(value);
        return out;
    }

    private static COSDictionary typed(String type) {
        COSDictionary out = new COSDictionary();
        if (type != null) out.setName(COSName.TYPE, type);
        return out;
    }

    private static String nv(String value) {
        return value == null ? "-" : value;
    }

    private static String kidKind(Object kid) {
        if (kid == null) return "null";
        if (kid instanceof Integer) return "mcid" + kid;
        if (kid instanceof PDStructureElement) return "elem";
        return kid.getClass().getSimpleName();
    }

    private static String kids(PDStructureElement elem) {
        try {
            List<Object> kidList = elem.getKids();
            if (kidList == null || kidList.isEmpty()) return "-";
            StringBuilder sb = new StringBuilder();
            sb.append(kidList.size());
            for (int i = 0; i < kidList.size(); i++) {
                sb.append(i == 0 ? ':' : ',').append(kidKind(kidList.get(i)));
            }
            return sb.toString();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    private static String classNames(PDStructureElement elem) {
        try {
            Revisions<String> rev = elem.getClassNames();
            if (rev == null) return "null";
            StringBuilder sb = new StringBuilder();
            sb.append(rev.size());
            for (int i = 0; i < rev.size(); i++) {
                sb.append('|').append(nv(rev.getObject(i)));
                sb.append('@').append(rev.getRevisionNumber(i));
            }
            return sb.toString();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    private static String parent(PDStructureElement elem) {
        try {
            PDStructureNode p = elem.getParent();
            return p == null ? "null" : p.getClass().getSimpleName();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    private static String page(PDStructureElement elem) {
        try {
            return elem.getPage() == null ? "null" : "page";
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    private static String revision(PDStructureElement elem) {
        try {
            return String.valueOf(elem.getRevisionNumber());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    private static String accessor(String label, java.util.concurrent.Callable<String> call) {
        try {
            return label + "=" + nv(call.call());
        } catch (Exception e) {
            return label + "=ERR:" + e.getClass().getSimpleName();
        }
    }

    private static void run(String name, COSDictionary dictionary) {
        PDStructureElement elem = new PDStructureElement(dictionary);
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name);
        sb.append(' ').append(accessor("s", elem::getStructureType));
        sb.append(' ').append(accessor("std", elem::getStandardStructureType));
        sb.append(' ').append(accessor("t", elem::getTitle));
        sb.append(' ').append(accessor("lang", elem::getLanguage));
        sb.append(' ').append(accessor("alt", elem::getAlternateDescription));
        sb.append(' ').append(accessor("exp", elem::getExpandedForm));
        sb.append(' ').append(accessor("actual", elem::getActualText));
        sb.append(' ').append(accessor("id", elem::getElementIdentifier));
        sb.append(" r=").append(revision(elem));
        sb.append(" parent=").append(parent(elem));
        sb.append(" pg=").append(page(elem));
        sb.append(" kids=").append(kids(elem));
        sb.append(" cls=").append(classNames(elem));
        System.out.println(sb.toString());
    }

    private static void runMark(String name, COSDictionary dictionary) {
        PDMarkInfo mi = new PDMarkInfo(dictionary);
        System.out.println(
            "MARK " + name
            + " marked=" + mi.isMarked()
            + " up=" + mi.usesUserProperties()
            + " suspect=" + mi.isSuspect());
    }

    public static void main(String[] args) {
        // ---- /C class names ----
        COSDictionary cName = new COSDictionary();
        cName.setItem(COSName.C, COSName.getPDFName("ClsA"));
        run("c_name", cName);

        COSDictionary cArray = new COSDictionary();
        cArray.setItem(COSName.C, array(
            COSName.getPDFName("ClsA"),
            COSName.getPDFName("ClsB")));
        run("c_array", cArray);

        // Array with interleaved revision integers (stateful parse).
        COSDictionary cRev = new COSDictionary();
        cRev.setItem(COSName.C, array(
            COSName.getPDFName("ClsA"),
            COSInteger.get(2),
            COSName.getPDFName("ClsB")));
        run("c_array_rev", cRev);

        // Leading orphan integer (no preceding name) is dropped.
        COSDictionary cOrphan = new COSDictionary();
        cOrphan.setItem(COSName.C, array(
            COSInteger.get(9),
            COSName.getPDFName("ClsA")));
        run("c_orphan_int", cOrphan);

        // Wrong types for /C.
        COSDictionary cString = new COSDictionary();
        cString.setItem(COSName.C, new COSString("ClsA"));
        run("c_string", cString);

        COSDictionary cDict = new COSDictionary();
        cDict.setItem(COSName.C, new COSDictionary());
        run("c_dict", cDict);

        COSDictionary cArrMixed = new COSDictionary();
        cArrMixed.setItem(COSName.C, array(
            COSName.getPDFName("ClsA"),
            new COSString("skip"),
            COSName.getPDFName("ClsB")));
        run("c_array_mixed", cArrMixed);

        // ---- /Pg page non-dict shapes ----
        COSDictionary pgArray = new COSDictionary();
        pgArray.setItem(COSName.PG, array(COSInteger.get(1)));
        run("pg_array", pgArray);

        COSDictionary pgInt = new COSDictionary();
        pgInt.setItem(COSName.PG, COSInteger.get(1));
        run("pg_int", pgInt);

        COSDictionary pgName = new COSDictionary();
        pgName.setItem(COSName.PG, COSName.getPDFName("nope"));
        run("pg_name", pgName);

        // ---- /R revision corners ----
        COSDictionary rHuge = new COSDictionary();
        rHuge.setItem(COSName.R, COSInteger.get(2147483647L));
        run("r_max", rHuge);

        COSDictionary rZero = new COSDictionary();
        rZero.setItem(COSName.R, COSInteger.get(0));
        run("r_zero", rZero);

        COSDictionary rName = new COSDictionary();
        rName.setItem(COSName.R, COSName.getPDFName("5"));
        run("r_name", rName);

        // ---- /E expanded form + string slots as name/int (getString only
        //      decodes COSString; a name or int leaves the slot null). ----
        COSDictionary eName = new COSDictionary();
        eName.setItem(COSName.E, COSName.getPDFName("etc"));
        eName.setItem(COSName.T, COSName.getPDFName("Title"));
        eName.setItem(COSName.getPDFName("Alt"), COSInteger.get(7));
        run("e_t_name_alt_int", eName);

        COSDictionary eStr = new COSDictionary();
        eStr.setItem(COSName.E, new COSString("et cetera"));
        eStr.setItem(COSName.getPDFName("ActualText"), new COSString("act"));
        run("e_actual_string", eStr);

        // ---- /Pg valid dict ----
        COSDictionary pgDict = new COSDictionary();
        pgDict.setItem(COSName.PG, typed("Page"));
        run("pg_dict", pgDict);

        // ---- getStandardStructureType: two-hop /RoleMap chain ----
        // Custom -> Custom2 (a name), Custom2 -> P. Upstream does a SINGLE
        // lookup; /S resolves to Custom2 (NOT followed to P).
        COSDictionary chainRoot = typed("StructTreeRoot");
        COSDictionary chainRm = new COSDictionary();
        chainRm.setItem(COSName.getPDFName("Custom"), COSName.getPDFName("Custom2"));
        chainRm.setItem(COSName.getPDFName("Custom2"), COSName.P);
        chainRoot.setItem(COSName.ROLE_MAP, chainRm);
        COSDictionary chainElem = new COSDictionary();
        chainElem.setName(COSName.S, "Custom");
        chainElem.setItem(COSName.P, chainRoot);
        run("role_two_hop", chainElem);

        // /S already standard, with a role map that would remap it: upstream
        // does not short-circuit on standard types, so the remap WINS.
        COSDictionary stdRemapRoot = typed("StructTreeRoot");
        COSDictionary stdRm = new COSDictionary();
        stdRm.setItem(COSName.P, COSName.getPDFName("H1"));
        stdRemapRoot.setItem(COSName.ROLE_MAP, stdRm);
        COSDictionary stdRemapElem = new COSDictionary();
        stdRemapElem.setName(COSName.S, "P");
        stdRemapElem.setItem(COSName.P, stdRemapRoot);
        run("role_std_remapped", stdRemapElem);

        // ---- /K shapes: single dict, deep nesting, MCID int ----
        COSDictionary kSingle = new COSDictionary();
        kSingle.setItem(COSName.K, typed("StructElem"));
        run("k_single_dict", kSingle);

        // Deeply nested: K -> elem -> K -> elem -> K -> mcid.
        COSDictionary deepLeaf = typed("StructElem");
        deepLeaf.setItem(COSName.K, COSInteger.get(11));
        COSDictionary deepMid = typed("StructElem");
        deepMid.setItem(COSName.K, deepLeaf);
        COSDictionary deepTop = new COSDictionary();
        deepTop.setItem(COSName.K, deepMid);
        run("k_deep", deepTop);

        COSDictionary kMcid = new COSDictionary();
        kMcid.setItem(COSName.K, COSInteger.get(5));
        run("k_mcid", kMcid);

        COSDictionary kFloat = new COSDictionary();
        kFloat.setItem(COSName.K, new COSFloat(2.5f));
        run("k_float", kFloat);

        // ---- PDMarkInfo corners ----
        runMark("absent", new COSDictionary());
        COSDictionary mTrue = new COSDictionary();
        mTrue.setBoolean(COSName.getPDFName("Marked"), true);
        mTrue.setBoolean(COSName.getPDFName("UserProperties"), true);
        mTrue.setBoolean(COSName.getPDFName("Suspects"), true);
        runMark("all_true", mTrue);
        COSDictionary mFalse = new COSDictionary();
        mFalse.setBoolean(COSName.getPDFName("Marked"), false);
        runMark("marked_false", mFalse);
        COSDictionary mNonBool = new COSDictionary();
        mNonBool.setItem(COSName.getPDFName("Marked"), COSInteger.get(1));
        mNonBool.setItem(COSName.getPDFName("Suspects"), new COSString("true"));
        runMark("nonbool", mNonBool);
    }
}
