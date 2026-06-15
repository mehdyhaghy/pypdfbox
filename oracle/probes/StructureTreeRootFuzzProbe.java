import java.util.List;
import java.util.Map;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDNameTreeNode;
import org.apache.pdfbox.pdmodel.common.PDNumberTreeNode;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureTreeRoot;

/**
 * Differential malformed structure-tree-root ACCESSOR probe (wave 1533).
 *
 * Distinct from StructureTreeParseFuzzProbe (wave 1518, which dumps kids /
 * role / class / next together) and StructParentTreeProbe (which loads a real
 * tagged PDF and dumps the /ParentTree number-tree): this probe constructs
 * malformed /StructTreeRoot dictionaries in-memory and projects each OTHER
 * accessor independently —
 *   getK()              shape: null / COS class name
 *   getKids()           count + per-kid tag for malformed /K
 *   getIDTree()         null vs present
 *   getParentTree()     null vs present
 *   getParentTreeNextKey()  int (default when absent / non-int)
 *   getRoleMap()        size + "Custom" lookup on non-dict /RoleMap
 *   getClassMap()       null vs present + entry shape (single vs array vs wrong)
 *
 * Output: one "CASE <name> ..." line per case, UTF-8.
 */
public final class StructureTreeRootFuzzProbe {

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

    private static String cosTag(COSBase base) {
        if (base == null) return "null";
        return base.getClass().getSimpleName();
    }

    private static String kidTag(Object value) {
        if (value == null) return "null";
        if (value instanceof Integer) return "int:" + value;
        if (value instanceof COSBase) return "cos:" + value.getClass().getSimpleName();
        return value.getClass().getSimpleName();
    }

    private static String classMapTag(Map<String, Object> cm) {
        // Upstream getClassMap() never returns null — it returns an (empty)
        // Map even when /ClassMap is absent or a non-dictionary. pypdfbox's
        // typed getClassMap() returns None in those cases (see CHANGES.md
        // wave 1533, unalignable divergence: typed wrapper vs Map). Normalise
        // the empty/absent container to the same "empty" tag so the probe
        // compares observable ENTRY content, not container nullness.
        if (cm == null || cm.isEmpty()) return "empty";
        Object value = cm.get("C");
        if (value == null) return "size=" + cm.size() + ":absent";
        if (value instanceof List) return "size=" + cm.size() + ":List";
        return "size=" + cm.size() + ":" + value.getClass().getSimpleName();
    }

    private static String roleMapTag(Map<String, Object> rm) {
        if (rm == null) return "null";
        Object value = rm.get("Custom");
        String v = value == null ? "null" : value.getClass().getSimpleName();
        return "size=" + rm.size() + ":Custom=" + v;
    }

    private static void run(String name, COSDictionary dictionary) {
        try {
            PDStructureTreeRoot root = new PDStructureTreeRoot(dictionary);

            COSBase k = root.getK();
            List<Object> kids = root.getKids();
            StringBuilder kidDump = new StringBuilder();
            for (int i = 0; i < kids.size(); i++) {
                if (i > 0) kidDump.append(',');
                kidDump.append(kidTag(kids.get(i)));
            }

            PDNameTreeNode idTree = root.getIDTree();
            PDNumberTreeNode parentTree = root.getParentTree();
            int nextKey = root.getParentTreeNextKey();
            Map<String, Object> roleMap = root.getRoleMap();
            Map<String, Object> classMap = root.getClassMap();

            System.out.println("CASE " + name
                    + " k=" + cosTag(k)
                    + " kidn=" + kids.size()
                    + " kids=" + kidDump
                    + " idtree=" + (idTree == null ? "null" : "present")
                    + " ptree=" + (parentTree == null ? "null" : "present")
                    + " next=" + nextKey
                    + " role=" + roleMapTag(roleMap)
                    + " class=" + classMapTag(classMap));
        } catch (Exception e) {
            System.out.println("CASE " + name + " ERR:" + e.getClass().getSimpleName());
        }
    }

    public static void main(String[] args) {
        // ---- /K shape ----
        run("k_absent", new COSDictionary());

        COSDictionary kSingle = new COSDictionary();
        kSingle.setItem(COSName.K, typed("StructElem"));
        run("k_single_dict", kSingle);

        COSDictionary kArray = new COSDictionary();
        kArray.setItem(COSName.K, array(typed("StructElem"), typed("StructElem")));
        run("k_array", kArray);

        COSDictionary kInt = new COSDictionary();
        kInt.setItem(COSName.K, COSInteger.get(5));
        run("k_int", kInt);

        COSDictionary kString = new COSDictionary();
        kString.setItem(COSName.K, new COSString("oops"));
        run("k_string", kString);

        COSDictionary kName = new COSDictionary();
        kName.setItem(COSName.K, COSName.getPDFName("oops"));
        run("k_name", kName);

        COSDictionary kEmptyArray = new COSDictionary();
        kEmptyArray.setItem(COSName.K, new COSArray());
        run("k_empty_array", kEmptyArray);

        COSDictionary kArrNested = new COSDictionary();
        kArrNested.setItem(COSName.K, array(COSInteger.get(2), new COSString("x"),
                COSName.getPDFName("y"), typed("StructElem")));
        run("k_array_mixed", kArrNested);

        // ---- /IDTree ----
        COSDictionary idAbsent = new COSDictionary();
        run("idtree_absent", idAbsent);

        COSDictionary idDict = new COSDictionary();
        idDict.setItem(COSName.getPDFName("IDTree"), new COSDictionary());
        run("idtree_dict", idDict);

        COSDictionary idArr = new COSDictionary();
        idArr.setItem(COSName.getPDFName("IDTree"), new COSArray());
        run("idtree_array", idArr);

        COSDictionary idInt = new COSDictionary();
        idInt.setItem(COSName.getPDFName("IDTree"), COSInteger.get(1));
        run("idtree_int", idInt);

        // ---- /ParentTree ----
        COSDictionary ptDict = new COSDictionary();
        ptDict.setItem(COSName.PARENT_TREE, new COSDictionary());
        run("ptree_dict", ptDict);

        COSDictionary ptArr = new COSDictionary();
        ptArr.setItem(COSName.PARENT_TREE, new COSArray());
        run("ptree_array", ptArr);

        COSDictionary ptInt = new COSDictionary();
        ptInt.setItem(COSName.PARENT_TREE, COSInteger.get(0));
        run("ptree_int", ptInt);

        // ---- /ParentTreeNextKey ----
        run("next_absent", new COSDictionary());

        COSDictionary nextInt = new COSDictionary();
        nextInt.setItem(COSName.PARENT_TREE_NEXT_KEY, COSInteger.get(42));
        run("next_int", nextInt);

        COSDictionary nextFloat = new COSDictionary();
        nextFloat.setItem(COSName.PARENT_TREE_NEXT_KEY, new COSFloat(4.9f));
        run("next_float", nextFloat);

        COSDictionary nextString = new COSDictionary();
        nextString.setItem(COSName.PARENT_TREE_NEXT_KEY, new COSString("4"));
        run("next_string", nextString);

        COSDictionary nextName = new COSDictionary();
        nextName.setItem(COSName.PARENT_TREE_NEXT_KEY, COSName.getPDFName("x"));
        run("next_name", nextName);

        COSDictionary nextNeg = new COSDictionary();
        nextNeg.setItem(COSName.PARENT_TREE_NEXT_KEY, COSInteger.get(-3));
        run("next_neg", nextNeg);

        // ---- /RoleMap non-dict ----
        COSDictionary roleArr = new COSDictionary();
        roleArr.setItem(COSName.ROLE_MAP, new COSArray());
        run("role_array", roleArr);

        COSDictionary roleInt = new COSDictionary();
        roleInt.setItem(COSName.ROLE_MAP, COSInteger.get(1));
        run("role_int", roleInt);

        COSDictionary roleEmpty = new COSDictionary();
        roleEmpty.setItem(COSName.ROLE_MAP, new COSDictionary());
        run("role_empty", roleEmpty);

        COSDictionary roleName = new COSDictionary();
        COSDictionary rm = new COSDictionary();
        rm.setItem(COSName.getPDFName("Custom"), COSName.P);
        roleName.setItem(COSName.ROLE_MAP, rm);
        run("role_name", roleName);

        // ---- /ClassMap shapes ----
        COSDictionary cmAbsent = new COSDictionary();
        run("class_absent", cmAbsent);

        COSDictionary cmArrType = new COSDictionary();
        cmArrType.setItem(COSName.CLASS_MAP, new COSArray());
        run("class_array_type", cmArrType);

        COSDictionary cmInt = new COSDictionary();
        cmInt.setItem(COSName.CLASS_MAP, COSInteger.get(1));
        run("class_int", cmInt);

        COSDictionary cmSingle = new COSDictionary();
        COSDictionary cm1 = new COSDictionary();
        cm1.setItem(COSName.getPDFName("C"), new COSDictionary());
        cmSingle.setItem(COSName.CLASS_MAP, cm1);
        run("class_single_attr", cmSingle);

        COSDictionary cmMulti = new COSDictionary();
        COSDictionary cm2 = new COSDictionary();
        cm2.setItem(COSName.getPDFName("C"), array(new COSDictionary(), new COSDictionary()));
        cmMulti.setItem(COSName.CLASS_MAP, cm2);
        run("class_array_attr", cmMulti);

        COSDictionary cmWrong = new COSDictionary();
        COSDictionary cm3 = new COSDictionary();
        cm3.setItem(COSName.getPDFName("C"), new COSString("nope"));
        cmWrong.setItem(COSName.CLASS_MAP, cm3);
        run("class_wrong_entry", cmWrong);

        COSDictionary cmEmpty = new COSDictionary();
        cmEmpty.setItem(COSName.CLASS_MAP, new COSDictionary());
        run("class_empty", cmEmpty);
    }
}
