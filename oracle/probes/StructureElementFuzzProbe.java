import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDAttributeObject;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureElement;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureNode;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.Revisions;

/**
 * Differential malformed structure-element accessor probe (wave 1531).
 *
 * Mirrors StructureTreeParseFuzzProbe but targets the PDStructureElement
 * accessor surface: getStructureType (/S), getStandardStructureType (/RoleMap
 * resolution), getParent (/P typed dispatch), getKids (/K polymorphism),
 * getRevisionNumber (/R), getTitle / getLanguage / getAlternateDescription /
 * getExpandedForm / getActualText (string slots), getElementIdentifier (/ID),
 * getAttributes (/A), and getPage (/Pg) — each driven with deliberately
 * type-confused values.
 */
public final class StructureElementFuzzProbe {

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
        List<Object> kidList = elem.getKids();
        if (kidList == null || kidList.isEmpty()) return "-";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < kidList.size(); i++) {
            if (i > 0) sb.append(',');
            sb.append(kidKind(kidList.get(i)));
        }
        return sb.toString();
    }

    private static String parent(PDStructureElement elem) {
        try {
            PDStructureNode p = elem.getParent();
            return p == null ? "null" : p.getClass().getSimpleName();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    private static String attrs(PDStructureElement elem) {
        try {
            Revisions<PDAttributeObject> rev = elem.getAttributes();
            if (rev == null) return "null";
            StringBuilder sb = new StringBuilder();
            sb.append(rev.size());
            for (int i = 0; i < rev.size(); i++) {
                PDAttributeObject ao = rev.getObject(i);
                sb.append('|').append(ao == null ? "-" : nv(ao.getOwner()));
                sb.append('@').append(rev.getRevisionNumber(i));
            }
            return sb.toString();
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
        sb.append(" attr=").append(attrs(elem));
        System.out.println(sb.toString());
    }

    public static void main(String[] args) {
        // Empty element.
        run("empty", new COSDictionary());

        // /S non-name (a string) vs missing.
        COSDictionary sString = new COSDictionary();
        sString.setItem(COSName.S, new COSString("P"));
        run("s_string", sString);

        COSDictionary sInt = new COSDictionary();
        sInt.setItem(COSName.S, COSInteger.get(3));
        run("s_int", sInt);

        // /S resolved via parent StructTreeRoot /RoleMap (name -> name).
        COSDictionary rmRoot = typed("StructTreeRoot");
        COSDictionary rm = new COSDictionary();
        rm.setItem(COSName.getPDFName("Custom"), COSName.P);
        rmRoot.setItem(COSName.ROLE_MAP, rm);
        COSDictionary roleElem = new COSDictionary();
        roleElem.setName(COSName.S, "Custom");
        roleElem.setItem(COSName.P, rmRoot);
        run("role_name", roleElem);

        // /RoleMap maps to a non-name (string) value.
        COSDictionary rmRoot2 = typed("StructTreeRoot");
        COSDictionary rm2 = new COSDictionary();
        rm2.setItem(COSName.getPDFName("Custom"), new COSString("P"));
        rmRoot2.setItem(COSName.ROLE_MAP, rm2);
        COSDictionary roleElem2 = new COSDictionary();
        roleElem2.setName(COSName.S, "Custom");
        roleElem2.setItem(COSName.P, rmRoot2);
        run("role_string", roleElem2);

        // /RoleMap with an integer value (instanceof String is false -> /S kept).
        COSDictionary rmRoot3 = typed("StructTreeRoot");
        COSDictionary rm3 = new COSDictionary();
        rm3.setItem(COSName.getPDFName("Custom"), COSInteger.get(7));
        rmRoot3.setItem(COSName.ROLE_MAP, rm3);
        COSDictionary roleElem3 = new COSDictionary();
        roleElem3.setName(COSName.S, "Custom");
        roleElem3.setItem(COSName.P, rmRoot3);
        run("role_int", roleElem3);

        // /RoleMap with an unconvertible value (array) -> whole map empty.
        COSDictionary rmRoot4 = typed("StructTreeRoot");
        COSDictionary rm4 = new COSDictionary();
        rm4.setItem(COSName.getPDFName("Custom"), COSName.P);
        rm4.setItem(COSName.getPDFName("Other"), array(COSInteger.get(1)));
        rmRoot4.setItem(COSName.ROLE_MAP, rm4);
        COSDictionary roleElem4 = new COSDictionary();
        roleElem4.setName(COSName.S, "Custom");
        roleElem4.setItem(COSName.P, rmRoot4);
        run("role_badmap", roleElem4);

        // String slots holding a NAME instead of a string.
        COSDictionary nameSlots = new COSDictionary();
        nameSlots.setName(COSName.T, "Title");
        nameSlots.setName(COSName.LANG, "en");
        nameSlots.setName(COSName.getPDFName("Alt"), "alt");
        nameSlots.setName(COSName.getPDFName("E"), "exp");
        nameSlots.setName(COSName.getPDFName("ActualText"), "act");
        nameSlots.setName(COSName.getPDFName("ID"), "id1");
        run("name_slots", nameSlots);

        // String slots holding proper strings.
        COSDictionary strSlots = new COSDictionary();
        strSlots.setString(COSName.T, "Title");
        strSlots.setString(COSName.LANG, "en");
        strSlots.setString(COSName.getPDFName("Alt"), "alt");
        strSlots.setString(COSName.getPDFName("E"), "exp");
        strSlots.setString(COSName.getPDFName("ActualText"), "act");
        strSlots.setString(COSName.getPDFName("ID"), "id1");
        run("str_slots", strSlots);

        // /R non-int (float, string, negative).
        COSDictionary rFloat = new COSDictionary();
        rFloat.setItem(COSName.R, new COSFloat(2.9f));
        run("r_float", rFloat);
        COSDictionary rString = new COSDictionary();
        rString.setItem(COSName.R, new COSString("5"));
        run("r_string", rString);
        COSDictionary rNeg = new COSDictionary();
        rNeg.setItem(COSName.R, COSInteger.get(-3));
        run("r_neg", rNeg);

        // /P missing / wrong type (string / array).
        COSDictionary pString = new COSDictionary();
        pString.setItem(COSName.P, new COSString("nope"));
        run("p_string", pString);
        COSDictionary pArray = new COSDictionary();
        pArray.setItem(COSName.P, array(COSInteger.get(1)));
        run("p_array", pArray);
        // /P pointing at an element (not a root).
        COSDictionary pElem = new COSDictionary();
        pElem.setItem(COSName.P, typed("StructElem"));
        run("p_elem", pElem);

        // /K polymorphism: single int (MCID).
        COSDictionary kInt = new COSDictionary();
        kInt.setItem(COSName.K, COSInteger.get(4));
        run("k_int", kInt);
        // /K single dict (StructElem).
        COSDictionary kDict = new COSDictionary();
        kDict.setItem(COSName.K, typed("StructElem"));
        run("k_dict", kDict);
        // /K mixed array: int, elem, MCR, OBJR, bogus type, string.
        COSDictionary kMixed = new COSDictionary();
        kMixed.setItem(COSName.K, array(COSInteger.get(2), typed("StructElem"),
                typed("MCR"), typed("OBJR"), typed("Bogus"), new COSString("x")));
        run("k_mixed", kMixed);

        // /A wrong type (string), bare dict, array forms.
        COSDictionary aString = new COSDictionary();
        aString.setItem(COSName.A, new COSString("nope"));
        run("a_string", aString);
        COSDictionary aDict = new COSDictionary();
        COSDictionary aoDict = new COSDictionary();
        aoDict.setName(COSName.O, "Layout");
        aDict.setItem(COSName.A, aoDict);
        run("a_dict", aDict);
        COSDictionary aArr = new COSDictionary();
        COSDictionary ao1 = new COSDictionary();
        ao1.setName(COSName.O, "Layout");
        COSDictionary ao2 = new COSDictionary();
        ao2.setName(COSName.O, "List");
        aArr.setItem(COSName.A, array(ao1, COSInteger.get(2), ao2));
        run("a_array", aArr);
        // /A array starting with an orphan integer (no preceding dict).
        COSDictionary aOrphan = new COSDictionary();
        aOrphan.setItem(COSName.A, array(COSInteger.get(9), ao1));
        run("a_orphan_int", aOrphan);

        // /Pg non-dict (string) and proper dict.
        COSDictionary pgString = new COSDictionary();
        pgString.setItem(COSName.PG, new COSString("nope"));
        run("pg_string", pgString);
        COSDictionary pgDict = new COSDictionary();
        pgDict.setItem(COSName.PG, new COSDictionary());
        run("pg_dict", pgDict);
    }
}
