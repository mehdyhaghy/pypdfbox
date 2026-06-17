import java.io.PrintStream;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.COSObjectable;
import org.apache.pdfbox.pdmodel.common.PDNameTreeNode;

/**
 * Live oracle probe: exercise the SETTER side of the string-keyed
 * PDNameTreeNode (setNames / setKids) and dump the raw COS dictionary that
 * results — the presence and exact contents of /Names, /Kids and /Limits.
 *
 * Companion to NumberTreeSetterProbe (the integer-keyed PDNumberTreeNode). The
 * /Limits on a name tree are COSString lower/upper rather than COSInteger, and
 * setNames sorts its keys via Collections.sort (Java natural String order), so
 * this probe additionally pins the sort order PDFBox writes.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> NameTreeSetterProbe
 */
public final class NameTreeSetterProbe {

    static final class StrVal implements COSObjectable {
        final COSString v;
        StrVal(COSBase b) { this.v = (COSString) b; }
        StrVal(String s) { this.v = new COSString(s); }
        public COSBase getCOSObject() { return v; }
    }

    static final class StrNode extends PDNameTreeNode<StrVal> {
        StrNode() { super(); }
        StrNode(COSDictionary d) { super(d); }
        @Override protected StrVal convertCOSToPD(COSBase base) { return new StrVal(base); }
        @Override protected PDNameTreeNode<StrVal> createChildNode(COSDictionary d) { return new StrNode(d); }
    }

    static String dumpEntry(COSBase b) {
        if (b == null) {
            return "null";
        }
        if (b instanceof COSString) {
            return ((COSString) b).getString();
        }
        return b.getClass().getSimpleName();
    }

    static void dump(PrintStream out, String label, COSDictionary node, boolean isRoot) {
        out.println("# " + label + " (root=" + isRoot + ")");
        // /Names presence + raw keys
        COSArray names = node.getCOSArray(COSName.NAMES);
        if (names == null) {
            out.println("  Names: absent");
        } else {
            StringBuilder sb = new StringBuilder("  Names:");
            for (int i = 0; i < names.size(); i += 2) {
                sb.append(" ").append(dumpEntry(names.getObject(i)));
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
        // /Limits presence + the two entries verbatim (null vs string)
        COSArray lim = node.getCOSArray(COSName.LIMITS);
        if (lim == null) {
            out.println("  Limits: absent");
        } else {
            out.println("  Limits: [" + dumpEntry(lim.get(0)) + " " + dumpEntry(lim.get(1)) + "]");
        }
    }

    static Map<String, StrVal> m(String... kv) {
        Map<String, StrVal> map = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) {
            map.put(kv[i], new StrVal(kv[i + 1]));
        }
        return map;
    }

    public static void main(String[] args) {
        PrintStream out = System.out;

        // 1. setNames on a ROOT node (no parent) with a non-empty, unsorted map.
        StrNode root1 = new StrNode();
        root1.setNames(m("gamma", "G", "alpha", "A", "beta", "B"));
        dump(out, "setNames root non-empty", root1.getCOSObject(), true);

        // 2. setNames on a root with an EMPTY map.
        StrNode root2 = new StrNode();
        root2.setNames(new LinkedHashMap<>());
        dump(out, "setNames root empty-map", root2.getCOSObject(), true);

        // 3. setNames(null) on a root that previously had names.
        StrNode root3 = new StrNode();
        root3.setNames(m("solo", "S"));
        root3.setNames(null);
        dump(out, "setNames root then null", root3.getCOSObject(), true);

        // 4. setKids on a root, two leaves each carrying /Limits.
        StrNode leafA = new StrNode();
        leafA.setNames(m("apple", "1", "banana", "2"));
        StrNode leafB = new StrNode();
        leafB.setNames(m("mango", "3", "pear", "4"));
        StrNode root4 = new StrNode();
        root4.setKids(List.of(leafA, leafB));
        dump(out, "setKids root", root4.getCOSObject(), true);
        dump(out, "setKids leafA", leafA.getCOSObject(), false);

        // 5. setNames then setKids on the SAME node — does /Names survive?
        StrNode root5 = new StrNode();
        root5.setNames(m("keepme", "K"));
        StrNode kid5 = new StrNode();
        kid5.setNames(m("kidname", "K2"));
        root5.setKids(List.of(kid5));
        dump(out, "setNames then setKids same node", root5.getCOSObject(), true);

        // 6. setKids with empty list on a node that had names — /Names kept?
        StrNode root6 = new StrNode();
        root6.setNames(m("survive", "S"));
        root6.setKids(List.of());
        dump(out, "setNames then setKids empty-list", root6.getCOSObject(), true);

        // 7. setNames then setKids on a NON-ROOT node — /Names survives upstream
        //    because setKids only clears /Names when isRootNode(). Attach root7
        //    as a kid under a parent first so it is non-root, then drive
        //    setNames + setKids on it.
        StrNode parent7 = new StrNode();
        StrNode child7 = new StrNode();
        child7.setNames(m("ph", "PH"));
        parent7.setKids(List.of(child7));   // child7 now has a parent (non-root)
        child7.setNames(m("nrkeep", "NK")); // re-populate /Names on the non-root
        StrNode gk7 = new StrNode();
        gk7.setNames(m("gk", "GK"));
        child7.setKids(List.of(gk7));       // non-root setKids: /Names should survive
        dump(out, "non-root setNames then setKids", child7.getCOSObject(), false);

        // 8. Sort order: a mixed-case / digit / symbol key set so the natural
        //    String ordering PDFBox uses is visible in /Names and /Limits.
        StrNode root8 = new StrNode();
        root8.setNames(m("Zebra", "1", "apple", "2", "Apple", "3", "10", "4", "2", "5", "_under", "6"));
        dump(out, "setNames sort order", root8.getCOSObject(), true);
    }
}
