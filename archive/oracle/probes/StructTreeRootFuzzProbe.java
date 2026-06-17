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
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDNumberTreeNode;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureTreeRoot;

/**
 * Differential structure-tree-root RESOLUTION probe (wave 1545).
 *
 * Distinct from StructureTreeRootFuzzProbe (wave 1533, which projects each
 * accessor SHAPE — getK/getKids/getIDTree/getParentTree/getRoleMap size /
 * getClassMap entry shape) and StructParentTreeProbe (loads a real tagged PDF
 * and dumps the whole /ParentTree). This probe drills into TWO surfaces the
 * wave-1533 probe only touched at "size" granularity:
 *
 *   getRoleMap()  CONTENT — exact key->value conversion of every basic COS
 *                 type (Name/String/Integer/Float/Boolean) plus the
 *                 all-or-nothing collapse to {} when an unconvertible value
 *                 (Array/Dictionary/Null) is present, plus cyclic / self /
 *                 chain / dangling mappings (whose CONTENT is unchanged by
 *                 resolution — getRoleMap returns the raw converted pairs).
 *
 *   getParentTree().getValue(k) — number-tree value LOOKUP over malformed
 *                 /Nums arrays: out-of-order keys, duplicate keys, odd-size
 *                 array, non-integer key slot (collapses the leaf), negative
 *                 keys, dict-vs-array leaf values, and absent-key lookups.
 *
 * Output: one "CASE <name> ..." line per case, UTF-8.
 */
public final class StructTreeRootFuzzProbe {

    private static COSArray array(COSBase... values) {
        COSArray out = new COSArray();
        for (COSBase value : values) out.add(value);
        return out;
    }

    private static COSDictionary roleMapDict(Object... kv) {
        COSDictionary rm = new COSDictionary();
        for (int i = 0; i + 1 < kv.length; i += 2) {
            rm.setItem(COSName.getPDFName((String) kv[i]), (COSBase) kv[i + 1]);
        }
        return rm;
    }

    /** Canonical, locale-independent rendering of a getRoleMap() value. */
    private static String valTag(Object value) {
        if (value == null) return "null";
        if (value instanceof String) return "str:" + value;
        if (value instanceof Integer) return "int:" + value;
        if (value instanceof Float) return "float:" + value;
        if (value instanceof Boolean) return "bool:" + value;
        return "other:" + value.getClass().getSimpleName();
    }

    // ---- /RoleMap getRoleMap() content ----

    private static void runRole(String name, COSBase roleMap) {
        try {
            COSDictionary root = new COSDictionary();
            if (roleMap != null) root.setItem(COSName.ROLE_MAP, roleMap);
            PDStructureTreeRoot tree = new PDStructureTreeRoot(root);
            Map<String, Object> rm = tree.getRoleMap();
            // Sort for deterministic ordering across JVM/CPython hash order.
            TreeMap<String, Object> sorted = new TreeMap<>(rm);
            StringBuilder sb = new StringBuilder();
            for (Map.Entry<String, Object> e : sorted.entrySet()) {
                if (sb.length() > 0) sb.append(',');
                sb.append(e.getKey()).append('=').append(valTag(e.getValue()));
            }
            System.out.println("ROLE " + name + " size=" + rm.size() + " {" + sb + "}");
        } catch (Exception e) {
            System.out.println("ROLE " + name + " ERR:" + e.getClass().getSimpleName());
        }
    }

    // ---- /ParentTree getValue() lookup ----

    private static void runParent(String name, COSArray nums, int[] lookups) {
        try {
            COSDictionary root = new COSDictionary();
            COSDictionary pt = new COSDictionary();
            if (nums != null) pt.setItem(COSName.getPDFName("Nums"), nums);
            root.setItem(COSName.PARENT_TREE, pt);
            PDStructureTreeRoot tree = new PDStructureTreeRoot(root);
            PDNumberTreeNode node = tree.getParentTree();
            StringBuilder sb = new StringBuilder();
            for (int k : lookups) {
                if (sb.length() > 0) sb.append(',');
                Object v;
                try {
                    v = node == null ? null : node.getValue(k);
                } catch (Exception e) {
                    sb.append(k).append("->ERR:").append(e.getClass().getSimpleName());
                    continue;
                }
                sb.append(k).append("->").append(leafTag(v));
            }
            System.out.println("PT " + name + " {" + sb + "}");
        } catch (Exception e) {
            System.out.println("PT " + name + " ERR:" + e.getClass().getSimpleName());
        }
    }

    private static String leafTag(Object value) {
        if (value == null) return "null";
        if (value instanceof COSArray) return "arr:" + ((COSArray) value).size();
        if (value instanceof COSDictionary) return "dict";
        if (value instanceof COSBase) return "cos:" + ((COSBase) value).getClass().getSimpleName();
        return value.getClass().getSimpleName();
    }

    public static void main(String[] args) {
        // ===== /RoleMap content =====
        runRole("absent", null);
        runRole("non_dict_array", new COSArray());
        runRole("non_dict_int", COSInteger.get(7));
        runRole("empty", new COSDictionary());

        // basic type conversions
        runRole("name_value", roleMapDict("Custom", COSName.getPDFName("P")));
        runRole("string_value", roleMapDict("Custom", new COSString("Sect")));
        runRole("int_value", roleMapDict("Custom", COSInteger.get(3)));
        runRole("float_value", roleMapDict("Custom", new COSFloat(2.5f)));
        runRole("bool_value", roleMapDict("Custom", COSBoolean.TRUE));

        // mixed convertible map
        runRole("mixed", roleMapDict(
                "A", COSName.getPDFName("P"),
                "B", new COSString("Sect"),
                "C", COSInteger.get(1)));

        // unconvertible value -> upstream collapses whole map to {}
        runRole("array_value", roleMapDict("Custom", new COSArray()));
        runRole("dict_value", roleMapDict("Custom", new COSDictionary()));
        runRole("null_value", roleMapDict("Custom", COSNull.NULL));
        runRole("one_bad_among_good", roleMapDict(
                "A", COSName.getPDFName("P"),
                "Bad", new COSArray(),
                "B", COSName.getPDFName("Sect")));

        // resolution-shaped maps: getRoleMap CONTENT is the raw converted pairs
        // regardless of cycles/chains (resolution is a separate, single-hop
        // operation on getStandardStructureType, exercised elsewhere).
        runRole("self_map", roleMapDict("A", COSName.getPDFName("A")));
        runRole("cycle_ab", roleMapDict(
                "A", COSName.getPDFName("B"),
                "B", COSName.getPDFName("A")));
        runRole("chain", roleMapDict(
                "A", COSName.getPDFName("B"),
                "B", COSName.getPDFName("C"),
                "C", COSName.getPDFName("P")));
        runRole("dangling", roleMapDict("A", COSName.getPDFName("Missing")));

        // ===== /ParentTree number-tree getValue() =====
        int[] probe = {0, 1, 2, 5, -1};

        // well-formed, in order
        runParent("ordered", array(
                COSInteger.get(0), array(new COSDictionary()),
                COSInteger.get(1), array(new COSDictionary(), new COSDictionary())),
                probe);

        // out-of-order keys
        runParent("out_of_order", array(
                COSInteger.get(2), array(new COSDictionary()),
                COSInteger.get(0), array(new COSDictionary())),
                probe);

        // duplicate keys (last wins in a map)
        runParent("dup_keys", array(
                COSInteger.get(1), array(new COSDictionary()),
                COSInteger.get(1), array(new COSDictionary(), new COSDictionary())),
                probe);

        // dict leaf value (annotation/xobject style) vs array leaf
        runParent("dict_leaf", array(
                COSInteger.get(0), new COSDictionary(),
                COSInteger.get(1), array(new COSDictionary())),
                probe);

        // odd-size /Nums (trailing key without value)
        runParent("odd_size", array(
                COSInteger.get(0), array(new COSDictionary()),
                COSInteger.get(1)),
                probe);

        // non-integer key slot (a key that is a Name) collapses the leaf
        runParent("non_int_key", array(
                COSName.getPDFName("x"), array(new COSDictionary()),
                COSInteger.get(1), array(new COSDictionary())),
                probe);

        // negative key present
        runParent("negative_key", array(
                COSInteger.get(-1), array(new COSDictionary()),
                COSInteger.get(0), array(new COSDictionary())),
                new int[] {-1, 0, 1});

        // empty /Nums
        runParent("empty_nums", new COSArray(), probe);

        // /Nums absent (no Nums, no Kids)
        runParent("no_nums", null, probe);
    }
}
