import java.io.PrintStream;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.common.COSObjectable;
import org.apache.pdfbox.pdmodel.common.PDNumberTreeNode;

/**
 * Live oracle probe: exercise the SETTER side of PDNumberTreeNode
 * (setNumbers / setKids) and dump the raw COS dictionary that results — the
 * presence and exact contents of /Nums, /Kids and /Limits. The existing
 * NameNumTree probes only build COS by hand and read it back; this one drives
 * PDFBox's own writers so we can pin (or detect divergence from) how PDFBox
 * stamps /Limits onto a node after a set call.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> NumberTreeSetterProbe
 */
public final class NumberTreeSetterProbe {

    static final class IntVal implements COSObjectable {
        final COSInteger v;
        IntVal(COSBase b) { this.v = (COSInteger) b; }
        public COSBase getCOSObject() { return v; }
    }

    static final class IntNode extends PDNumberTreeNode {
        IntNode() { super(IntVal.class); }
        IntNode(COSDictionary d) { super(d, IntVal.class); }
        @Override protected COSObjectable convertCOSToPD(COSBase base) { return new IntVal(base); }
        @Override protected PDNumberTreeNode createChildNode(COSDictionary d) { return new IntNode(d); }
    }

    static String dumpEntry(COSBase b) {
        if (b == null) {
            return "null";
        }
        if (b instanceof COSInteger) {
            return Long.toString(((COSInteger) b).longValue());
        }
        return b.getClass().getSimpleName();
    }

    static void dump(PrintStream out, String label, COSDictionary node, boolean isRoot) {
        out.println("# " + label + " (root=" + isRoot + ")");
        // /Nums presence + raw keys
        COSArray nums = node.getCOSArray(COSName.NUMS);
        if (nums == null) {
            out.println("  Nums: absent");
        } else {
            StringBuilder sb = new StringBuilder("  Nums:");
            for (int i = 0; i < nums.size(); i += 2) {
                sb.append(" ").append(dumpEntry(nums.getObject(i)));
            }
            out.println(sb.toString());
        }
        // /Kids presence + count
        COSArray kids = node.getCOSArray(COSName.KIDS);
        if (kids == null) {
            out.println("  Kids: absent");
        } else {
            out.println("  Kids: count=" + kids.size());
        }
        // /Limits presence + the two entries verbatim (null vs int)
        COSArray lim = node.getCOSArray(COSName.LIMITS);
        if (lim == null) {
            out.println("  Limits: absent");
        } else {
            out.println("  Limits: [" + dumpEntry(lim.get(0)) + " " + dumpEntry(lim.get(1)) + "]");
        }
    }

    public static void main(String[] args) {
        PrintStream out = System.out;

        // 1. setNumbers on a ROOT node (no parent) with a non-empty map.
        IntNode root1 = new IntNode();
        Map<Integer, COSObjectable> m1 = new LinkedHashMap<>();
        m1.put(30, new IntVal(COSInteger.get(300)));
        m1.put(10, new IntVal(COSInteger.get(100)));
        m1.put(20, new IntVal(COSInteger.get(200)));
        root1.setNumbers(m1);
        dump(out, "setNumbers root non-empty", root1.getCOSObject(), true);

        // 2. setNumbers on a root with an EMPTY map.
        IntNode root2 = new IntNode();
        root2.setNumbers(new LinkedHashMap<>());
        dump(out, "setNumbers root empty-map", root2.getCOSObject(), true);

        // 3. setNumbers(null) on a root that previously had numbers.
        IntNode root3 = new IntNode();
        Map<Integer, COSObjectable> m3 = new LinkedHashMap<>();
        m3.put(5, new IntVal(COSInteger.get(50)));
        root3.setNumbers(m3);
        root3.setNumbers(null);
        dump(out, "setNumbers root then null", root3.getCOSObject(), true);

        // 4. setKids on a root, two leaves each carrying /Limits.
        IntNode leafA = new IntNode();
        Map<Integer, COSObjectable> ma = new LinkedHashMap<>();
        ma.put(1, new IntVal(COSInteger.get(11)));
        ma.put(2, new IntVal(COSInteger.get(22)));
        leafA.setNumbers(ma);
        IntNode leafB = new IntNode();
        Map<Integer, COSObjectable> mb = new LinkedHashMap<>();
        mb.put(100, new IntVal(COSInteger.get(1100)));
        mb.put(200, new IntVal(COSInteger.get(2200)));
        leafB.setNumbers(mb);
        IntNode root4 = new IntNode();
        root4.setKids(List.of(leafA, leafB));
        dump(out, "setKids root", root4.getCOSObject(), true);
        dump(out, "setKids leafA", leafA.getCOSObject(), false);

        // 5. setNumbers then setKids on the SAME node — does /Nums survive?
        IntNode root5 = new IntNode();
        Map<Integer, COSObjectable> m5 = new LinkedHashMap<>();
        m5.put(7, new IntVal(COSInteger.get(70)));
        root5.setNumbers(m5);
        IntNode kid5 = new IntNode();
        Map<Integer, COSObjectable> mk5 = new LinkedHashMap<>();
        mk5.put(9, new IntVal(COSInteger.get(90)));
        kid5.setNumbers(mk5);
        root5.setKids(List.of(kid5));
        dump(out, "setNumbers then setKids same node", root5.getCOSObject(), true);

        // 6. setKids with empty list on a node that had numbers — /Nums kept?
        IntNode root6 = new IntNode();
        Map<Integer, COSObjectable> m6 = new LinkedHashMap<>();
        m6.put(3, new IntVal(COSInteger.get(30)));
        root6.setNumbers(m6);
        root6.setKids(List.of());
        dump(out, "setNumbers then setKids empty-list", root6.getCOSObject(), true);
    }
}
