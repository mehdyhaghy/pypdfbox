import java.util.List;
import java.util.Map;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureNode;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureTreeRoot;

/** Differential malformed tagged-PDF structure-tree read probe (wave 1518). */
public final class StructureTreeParseFuzzProbe {
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

    private static String kidTag(Object value) {
        if (value == null) return "null";
        if (value instanceof Integer) return "int:" + value;
        if (value instanceof COSBase) return "cos:" + value.getClass().getSimpleName();
        return value.getClass().getSimpleName();
    }

    private static String valueTag(Object value) {
        if (value == null) return "null";
        if (value instanceof String) return "str:" + value;
        return value.getClass().getSimpleName();
    }

    private static void run(String name, COSDictionary dictionary) {
        try {
            PDStructureTreeRoot root = new PDStructureTreeRoot(dictionary);
            List<Object> kids = root.getKids();
            StringBuilder kidDump = new StringBuilder();
            for (int i = 0; i < kids.size(); i++) {
                if (i > 0) kidDump.append(',');
                kidDump.append(kidTag(kids.get(i)));
            }
            Map<String, Object> roles = root.getRoleMap();
            Map<String, Object> classes = root.getClassMap();
            System.out.println("CASE " + name + " type=" + root.getType()
                    + " kids=" + kidDump + " role=" + valueTag(roles.get("Custom"))
                    + " class=" + valueTag(classes.get("C"))
                    + " next=" + root.getParentTreeNextKey());
        } catch (Exception e) {
            System.out.println("CASE " + name + " ERR:" + e.getClass().getSimpleName());
        }
    }

    private static void create(String name, COSDictionary dictionary) {
        try {
            PDStructureNode node = PDStructureNode.create(dictionary);
            System.out.println("CREATE " + name + " class=" + node.getClass().getSimpleName());
        } catch (Exception e) {
            System.out.println("CREATE " + name + " ERR:" + e.getClass().getSimpleName());
        }
    }

    public static void main(String[] args) {
        run("empty", new COSDictionary());

        COSDictionary singleInt = new COSDictionary();
        singleInt.setItem(COSName.K, COSInteger.get(7));
        run("single_int", singleInt);

        COSDictionary mixed = new COSDictionary();
        mixed.setItem(COSName.K, array(COSInteger.get(1), typed("StructElem"),
                typed("MCR"), typed("OBJR"), typed("Bogus"), new COSString("bad")));
        run("mixed_kids", mixed);

        COSDictionary roleName = new COSDictionary();
        COSDictionary rm = new COSDictionary();
        rm.setItem(COSName.getPDFName("Custom"), COSName.P);
        roleName.setItem(COSName.ROLE_MAP, rm);
        run("role_name", roleName);

        COSDictionary roleString = new COSDictionary();
        COSDictionary rmString = new COSDictionary();
        rmString.setItem(COSName.getPDFName("Custom"), new COSString("P"));
        roleString.setItem(COSName.ROLE_MAP, rmString);
        run("role_string", roleString);

        COSDictionary classDict = new COSDictionary();
        COSDictionary cm = new COSDictionary();
        cm.setItem(COSName.getPDFName("C"), new COSDictionary());
        classDict.setItem(COSName.CLASS_MAP, cm);
        run("class_dict", classDict);

        COSDictionary classArray = new COSDictionary();
        COSDictionary cmArray = new COSDictionary();
        cmArray.setItem(COSName.getPDFName("C"), array(new COSDictionary(), new COSDictionary()));
        classArray.setItem(COSName.CLASS_MAP, cmArray);
        run("class_array", classArray);

        COSDictionary nextFloat = new COSDictionary();
        nextFloat.setItem(COSName.PARENT_TREE_NEXT_KEY, new COSFloat(4.9f));
        run("next_float", nextFloat);
        COSDictionary nextString = new COSDictionary();
        nextString.setItem(COSName.PARENT_TREE_NEXT_KEY, new COSString("4"));
        run("next_string", nextString);

        create("root", typed("StructTreeRoot"));
        create("elem", typed("StructElem"));
        create("missing", typed(null));
        create("unknown", typed("Bogus"));
    }
}
