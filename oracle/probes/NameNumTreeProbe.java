import java.io.PrintStream;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.COSObjectable;
import org.apache.pdfbox.pdmodel.common.PDNameTreeNode;
import org.apache.pdfbox.pdmodel.common.PDNumberTreeNode;

/**
 * Live oracle probe: exercise the generic name-tree / number-tree traversal
 * (PDNameTreeNode / PDNumberTreeNode) against COS structures built in-probe.
 *
 * No PDF file is loaded. The probe hand-builds (a) single-level leaf trees and
 * (b) multi-level balanced trees with intermediate /Kids nodes carrying
 * /Limits, then emits a canonical text report covering:
 *   - the flattened, sorted key->value mapping (getNames / getNumbers)
 *   - each node's lower/upper /Limits (getLowerLimit / getUpperLimit), walked
 *     in document order
 *   - the result of get(key) for a battery of present / absent / boundary keys
 *
 * The same COS shapes are rebuilt verbatim on the pypdfbox side so the two
 * reports compare string-for-string.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> NameNumTreeProbe
 */
public final class NameNumTreeProbe {

    // ---- name-tree value type: a COSObjectable wrapping a COSString ----
    static final class StrVal implements COSObjectable {
        final COSString s;
        StrVal(COSBase b) { this.s = (COSString) b; }
        public COSBase getCOSObject() { return s; }
        String value() { return s.getString(); }
    }

    static final class StrNode extends PDNameTreeNode<StrVal> {
        StrNode() { super(); }
        StrNode(COSDictionary d) { super(d); }
        @Override protected StrVal convertCOSToPD(COSBase base) { return new StrVal(base); }
        @Override protected PDNameTreeNode<StrVal> createChildNode(COSDictionary d) { return new StrNode(d); }
    }

    // ---- number-tree value type: a COSObjectable wrapping a COSInteger ----
    static final class IntVal implements COSObjectable {
        final COSInteger v;
        IntVal(COSBase b) { this.v = (COSInteger) b; }
        public COSBase getCOSObject() { return v; }
        long value() { return v.longValue(); }
    }

    static final class IntNode extends PDNumberTreeNode {
        IntNode() { super(IntVal.class); }
        IntNode(COSDictionary d) { super(d, IntVal.class); }
        @Override protected COSObjectable convertCOSToPD(COSBase base) { return new IntVal(base); }
        @Override protected PDNumberTreeNode createChildNode(COSDictionary d) { return new IntNode(d); }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // ===== NAME TREES =====

        // (1) single-level leaf
        out.println("# name single");
        StrNode nSingle = new StrNode(nameLeaf(new String[][] {
            {"apple", "A"}, {"mango", "M"}, {"pear", "P"}
        }));
        reportName(out, nSingle,
            new String[] {"apple", "mango", "pear", "kiwi", "aardvark", "zebra"});

        // (2) multi-level (2 deep): root -> 3 leaves
        out.println("# name multi2");
        StrNode nMulti2 = new StrNode(nameIntermediate(new COSDictionary[] {
            nameLeafLimited(new String[][] {{"alpha", "1"}, {"bravo", "2"}}),
            nameLeafLimited(new String[][] {{"delta", "3"}, {"echo", "4"}}),
            nameLeafLimited(new String[][] {{"golf", "5"}, {"hotel", "6"}})
        }));
        reportName(out, nMulti2, new String[] {
            "alpha", "bravo", "delta", "echo", "golf", "hotel",
            "charlie", "foxtrot", "zulu", "aaa", "echo", "golf"
        });

        // (3) multi-level (3 deep): root -> 2 intermediates -> leaves
        out.println("# name multi3");
        COSDictionary nLeft = nameIntermediate(new COSDictionary[] {
            nameLeafLimited(new String[][] {{"ant", "a"}, {"bee", "b"}}),
            nameLeafLimited(new String[][] {{"cat", "c"}, {"dog", "d"}})
        });
        COSDictionary nRight = nameIntermediate(new COSDictionary[] {
            nameLeafLimited(new String[][] {{"eel", "e"}, {"fox", "f"}}),
            nameLeafLimited(new String[][] {{"goat", "g"}, {"hen", "h"}})
        });
        StrNode nMulti3 = new StrNode(nameIntermediate(new COSDictionary[] {nLeft, nRight}));
        reportName(out, nMulti3, new String[] {
            "ant", "dog", "eel", "hen", "bee", "goat",
            "bird", "elk", "zzz", "aaa", "cat", "fox"
        });

        // ===== NUMBER TREES =====

        // (4) single-level leaf
        out.println("# num single");
        IntNode mSingle = new IntNode(numLeaf(new long[][] {
            {1, 100}, {5, 500}, {9, 900}
        }));
        reportNum(out, mSingle, new int[] {1, 5, 9, 0, 3, 12, -1});

        // (5) multi-level (2 deep): root -> 3 leaves
        out.println("# num multi2");
        IntNode mMulti2 = new IntNode(numIntermediate(new COSDictionary[] {
            numLeafLimited(new long[][] {{0, 1000}, {2, 1002}}),
            numLeafLimited(new long[][] {{10, 1010}, {12, 1012}}),
            numLeafLimited(new long[][] {{20, 1020}, {25, 1025}})
        }));
        reportNum(out, mMulti2, new int[] {
            0, 2, 10, 12, 20, 25, 1, 11, 15, 26, -5, 21
        });

        // (6) multi-level (3 deep): root -> 2 intermediates -> leaves
        out.println("# num multi3");
        COSDictionary mLeft = numIntermediate(new COSDictionary[] {
            numLeafLimited(new long[][] {{1, 11}, {3, 13}}),
            numLeafLimited(new long[][] {{5, 15}, {7, 17}})
        });
        COSDictionary mRight = numIntermediate(new COSDictionary[] {
            numLeafLimited(new long[][] {{10, 110}, {14, 114}}),
            numLeafLimited(new long[][] {{20, 120}, {28, 128}})
        });
        IntNode mMulti3 = new IntNode(numIntermediate(new COSDictionary[] {mLeft, mRight}));
        reportNum(out, mMulti3, new int[] {
            1, 7, 10, 28, 5, 20, 2, 8, 30, 0, 14, 100
        });
    }

    // ---------- name-tree report ----------

    private static void reportName(PrintStream out, StrNode node, String[] keys) throws Exception {
        // PDFBox's getNames() is NOT recursive: on an intermediate /Kids node
        // it returns null and yields only the leaf's own /Names. To produce a
        // flattened whole-tree mapping (the operation pypdfbox bakes into its
        // recursive get_names()) we recurse through getKids ourselves, exactly
        // as EmbedFilesProbe does.
        TreeMap<String, StrVal> sorted = new TreeMap<>();
        collectNames(node, sorted);
        out.println("flatten " + sorted.size());
        for (Map.Entry<String, StrVal> e : sorted.entrySet()) {
            out.println("  " + e.getKey() + " -> " + e.getValue().value());
        }
        out.println("limits");
        dumpNameLimits(out, node, 0);
        out.println("get");
        for (String k : keys) {
            StrVal v = node.getValue(k);
            out.println("  get(" + k + ") = " + (v == null ? "null" : v.value()));
        }
    }

    private static void collectNames(PDNameTreeNode<StrVal> node, TreeMap<String, StrVal> sink)
            throws Exception {
        Map<String, StrVal> leaf = node.getNames();
        if (leaf != null) {
            sink.putAll(leaf);
        }
        List<PDNameTreeNode<StrVal>> kids = node.getKids();
        if (kids != null) {
            for (PDNameTreeNode<StrVal> kid : kids) {
                collectNames(kid, sink);
            }
        }
    }

    private static void dumpNameLimits(PrintStream out, PDNameTreeNode<StrVal> node, int depth)
            throws Exception {
        out.println("  " + indent(depth) + lim(node.getLowerLimit()) + ".." + lim(node.getUpperLimit()));
        List<PDNameTreeNode<StrVal>> kids = node.getKids();
        if (kids != null) {
            for (PDNameTreeNode<StrVal> kid : kids) {
                dumpNameLimits(out, kid, depth + 1);
            }
        }
    }

    // ---------- number-tree report ----------

    private static void reportNum(PrintStream out, IntNode node, int[] keys) throws Exception {
        // getNumbers() is non-recursive (null on an intermediate /Kids node),
        // so flatten the whole tree by recursing through getKids ourselves.
        TreeMap<Integer, COSObjectable> sorted = new TreeMap<>();
        collectNumbers(node, sorted);
        out.println("flatten " + sorted.size());
        for (Map.Entry<Integer, COSObjectable> e : sorted.entrySet()) {
            out.println("  " + e.getKey() + " -> " + ((IntVal) e.getValue()).value());
        }
        out.println("limits");
        dumpNumLimits(out, node, 0);
        out.println("get");
        for (int k : keys) {
            Object v = node.getValue(k);
            out.println("  get(" + k + ") = " + (v == null ? "null" : ((IntVal) v).value()));
        }
    }

    private static void collectNumbers(PDNumberTreeNode node, TreeMap<Integer, COSObjectable> sink)
            throws Exception {
        Map<Integer, COSObjectable> leaf = node.getNumbers();
        if (leaf != null) {
            sink.putAll(leaf);
        }
        List<PDNumberTreeNode> kids = node.getKids();
        if (kids != null) {
            for (PDNumberTreeNode kid : kids) {
                collectNumbers(kid, sink);
            }
        }
    }

    private static void dumpNumLimits(PrintStream out, PDNumberTreeNode node, int depth)
            throws Exception {
        out.println("  " + indent(depth) + lim(node.getLowerLimit()) + ".." + lim(node.getUpperLimit()));
        List<PDNumberTreeNode> kids = node.getKids();
        if (kids != null) {
            for (PDNumberTreeNode kid : kids) {
                dumpNumLimits(out, kid, depth + 1);
            }
        }
    }

    // ---------- COS builders ----------

    private static COSDictionary nameLeaf(String[][] pairs) {
        COSDictionary d = new COSDictionary();
        COSArray names = new COSArray();
        for (String[] p : pairs) {
            names.add(new COSString(p[0]));
            names.add(new COSString(p[1]));
        }
        d.setItem(COSName.getPDFName("Names"), names);
        return d;
    }

    private static COSDictionary nameLeafLimited(String[][] pairs) {
        COSDictionary d = nameLeaf(pairs);
        COSArray limits = new COSArray();
        limits.add(new COSString(pairs[0][0]));
        limits.add(new COSString(pairs[pairs.length - 1][0]));
        d.setItem(COSName.getPDFName("Limits"), limits);
        return d;
    }

    private static COSDictionary nameIntermediate(COSDictionary[] children) {
        COSDictionary d = new COSDictionary();
        COSArray kids = new COSArray();
        for (COSDictionary c : children) {
            kids.add(c);
        }
        d.setItem(COSName.KIDS, kids);
        // Limits span first child's lower to last child's upper.
        COSArray firstLim = (COSArray) children[0].getDictionaryObject(COSName.getPDFName("Limits"));
        COSArray lastLim =
            (COSArray) children[children.length - 1].getDictionaryObject(COSName.getPDFName("Limits"));
        COSArray limits = new COSArray();
        limits.add(firstLim.get(0));
        limits.add(lastLim.get(1));
        d.setItem(COSName.getPDFName("Limits"), limits);
        return d;
    }

    private static COSDictionary numLeaf(long[][] pairs) {
        COSDictionary d = new COSDictionary();
        COSArray nums = new COSArray();
        for (long[] p : pairs) {
            nums.add(COSInteger.get(p[0]));
            nums.add(COSInteger.get(p[1]));
        }
        d.setItem(COSName.getPDFName("Nums"), nums);
        return d;
    }

    private static COSDictionary numLeafLimited(long[][] pairs) {
        COSDictionary d = numLeaf(pairs);
        COSArray limits = new COSArray();
        limits.add(COSInteger.get(pairs[0][0]));
        limits.add(COSInteger.get(pairs[pairs.length - 1][0]));
        d.setItem(COSName.getPDFName("Limits"), limits);
        return d;
    }

    private static COSDictionary numIntermediate(COSDictionary[] children) {
        COSDictionary d = new COSDictionary();
        COSArray kids = new COSArray();
        for (COSDictionary c : children) {
            kids.add(c);
        }
        d.setItem(COSName.KIDS, kids);
        COSArray firstLim = (COSArray) children[0].getDictionaryObject(COSName.getPDFName("Limits"));
        COSArray lastLim =
            (COSArray) children[children.length - 1].getDictionaryObject(COSName.getPDFName("Limits"));
        COSArray limits = new COSArray();
        limits.add(firstLim.get(0));
        limits.add(lastLim.get(1));
        d.setItem(COSName.getPDFName("Limits"), limits);
        return d;
    }

    // ---------- formatting ----------

    private static String lim(Object o) {
        return o == null ? "null" : String.valueOf(o);
    }

    private static String indent(int depth) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < depth; i++) {
            sb.append("  ");
        }
        return sb.toString();
    }
}
