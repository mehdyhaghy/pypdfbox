import java.io.PrintStream;
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
 * Live oracle probe: pin the precise <code>getValue</code> /Limits descent
 * narrowing of the generic name-tree / number-tree (PDNameTreeNode /
 * PDNumberTreeNode) on shapes the existing NameNumTreeProbe deliberately does
 * NOT exercise.
 *
 * NameNumTreeProbe used "dense" leaves whose /Limits exactly bracket their
 * only two keys, so every query either matched a leaf's whole span or fell
 * into a between-leaf gap. This probe targets the harder cases:
 *
 *   (1) SPARSE leaves — a leaf's /Limits span [lo .. hi] is wide but the leaf
 *       holds keys strictly inside the span that are NOT present (a hole). A
 *       query for a hole key lands inside exactly one kid's range, descends,
 *       misses, and must return null WITHOUT spuriously matching a sibling.
 *   (2) Boundary keys equal to a kid's lower OR upper /Limits value (==lo,
 *       ==hi) where that boundary key IS or IS NOT actually present.
 *   (3) ADJACENT (touching) ranges where one kid's upper limit equals the
 *       next kid's lower-1 / next-string — the descent must pick the right
 *       kid with no overlap ambiguity.
 *   (4) Negative-keyed number leaves and keys spanning the negative/zero
 *       boundary, to pin signed integer comparison in the descent.
 *
 * Output: a canonical text report; pypdfbox rebuilds the identical COS and
 * compares string-for-string.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> NameNumTreeRangeProbe
 */
public final class NameNumTreeRangeProbe {

    static final class StrVal implements COSObjectable {
        final COSString s;
        StrVal(COSBase b) { this.s = (COSString) b; }
        public COSBase getCOSObject() { return s; }
        String value() { return s.getString(); }
    }

    static final class StrNode extends PDNameTreeNode<StrVal> {
        StrNode(COSDictionary d) { super(d); }
        @Override protected StrVal convertCOSToPD(COSBase base) { return new StrVal(base); }
        @Override protected PDNameTreeNode<StrVal> createChildNode(COSDictionary d) { return new StrNode(d); }
    }

    static final class IntVal implements COSObjectable {
        final COSInteger v;
        IntVal(COSBase b) { this.v = (COSInteger) b; }
        public COSBase getCOSObject() { return v; }
        long value() { return v.longValue(); }
    }

    static final class IntNode extends PDNumberTreeNode {
        IntNode(COSDictionary d) { super(d, IntVal.class); }
        @Override protected COSObjectable convertCOSToPD(COSBase base) { return new IntVal(base); }
        @Override protected PDNumberTreeNode createChildNode(COSDictionary d) { return new IntNode(d); }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // ===== NAME TREE: sparse leaves with explicit /Limits spans =====
        // Leaf A span [alpha .. golf] holds {alpha, charlie, golf} — "bravo",
        // "delta", "echo" are HOLES inside the span. Leaf B span [india .. zulu]
        // holds {india, mike, zulu}. The two spans are non-overlapping with a
        // gap (golf .. india).
        out.println("# name sparse");
        COSDictionary leafA = nameLeaf(new String[][] {
            {"alpha", "1"}, {"charlie", "3"}, {"golf", "7"}
        }, "alpha", "golf");
        COSDictionary leafB = nameLeaf(new String[][] {
            {"india", "9"}, {"mike", "13"}, {"zulu", "26"}
        }, "india", "zulu");
        StrNode sparse = new StrNode(nameIntermediate(new COSDictionary[] {leafA, leafB}, "alpha", "zulu"));
        reportName(out, sparse, new String[] {
            // present keys spanning both kids
            "alpha", "charlie", "golf", "india", "mike", "zulu",
            // hole keys inside leaf A's span (present in NEITHER leaf)
            "bravo", "delta", "echo", "foxtrot",
            // gap key between the two spans
            "hotel",
            // boundary keys equal to a /Limits value (all present here)
            // out-of-range below and above
            "aaa", "zzzz",
        });

        // ===== NUMBER TREE: sparse leaves, negative keys, touching ranges =====
        // Leaf P span [-10 .. 20] holds {-10, 0, 5, 20} — holes at -5, 3, 10, 19.
        // Leaf Q span [21 .. 50] holds {21, 30, 50} — touches P (20 then 21).
        out.println("# num sparse");
        COSDictionary leafP = numLeaf(new long[][] {
            {-10, 100}, {0, 200}, {5, 250}, {20, 300}
        }, -10, 20);
        COSDictionary leafQ = numLeaf(new long[][] {
            {21, 310}, {30, 400}, {50, 500}
        }, 21, 50);
        IntNode numSparse = new IntNode(numIntermediate(new COSDictionary[] {leafP, leafQ}, -10, 50));
        reportNum(out, numSparse, new int[] {
            // present, spanning both kids and the negative/zero boundary
            -10, 0, 5, 20, 21, 30, 50,
            // hole keys inside a kid's span (present in NEITHER leaf)
            -5, 3, 10, 19, 22, 40,
            // touching-range boundary: 20 is P's upper, 21 is Q's lower
            // out-of-range below and above
            -11, 51, 1000,
        });
    }

    private static void reportName(PrintStream out, StrNode node, String[] keys) throws Exception {
        out.println("limits");
        dumpNameLimits(out, node, 0);
        out.println("get");
        for (String k : keys) {
            StrVal v = node.getValue(k);
            out.println("  get(" + k + ") = " + (v == null ? "null" : v.value()));
        }
    }

    private static void dumpNameLimits(PrintStream out, PDNameTreeNode<StrVal> node, int depth)
            throws Exception {
        out.println("  " + indent(depth) + lim(node.getLowerLimit()) + ".." + lim(node.getUpperLimit()));
        java.util.List<PDNameTreeNode<StrVal>> kids = node.getKids();
        if (kids != null) {
            for (PDNameTreeNode<StrVal> kid : kids) {
                dumpNameLimits(out, kid, depth + 1);
            }
        }
    }

    private static void reportNum(PrintStream out, IntNode node, int[] keys) throws Exception {
        out.println("limits");
        dumpNumLimits(out, node, 0);
        out.println("get");
        for (int k : keys) {
            Object v = node.getValue(k);
            out.println("  get(" + k + ") = " + (v == null ? "null" : ((IntVal) v).value()));
        }
    }

    private static void dumpNumLimits(PrintStream out, PDNumberTreeNode node, int depth)
            throws Exception {
        out.println("  " + indent(depth) + lim(node.getLowerLimit()) + ".." + lim(node.getUpperLimit()));
        java.util.List<PDNumberTreeNode> kids = node.getKids();
        if (kids != null) {
            for (PDNumberTreeNode kid : kids) {
                dumpNumLimits(out, kid, depth + 1);
            }
        }
    }

    // ---------- COS builders (explicit /Limits so leaves can be sparse) ----------

    private static COSDictionary nameLeaf(String[][] pairs, String lo, String hi) {
        COSDictionary d = new COSDictionary();
        COSArray names = new COSArray();
        for (String[] p : pairs) {
            names.add(new COSString(p[0]));
            names.add(new COSString(p[1]));
        }
        d.setItem(COSName.getPDFName("Names"), names);
        COSArray limits = new COSArray();
        limits.add(new COSString(lo));
        limits.add(new COSString(hi));
        d.setItem(COSName.getPDFName("Limits"), limits);
        return d;
    }

    private static COSDictionary nameIntermediate(COSDictionary[] children, String lo, String hi) {
        COSDictionary d = new COSDictionary();
        COSArray kids = new COSArray();
        for (COSDictionary c : children) {
            kids.add(c);
        }
        d.setItem(COSName.KIDS, kids);
        COSArray limits = new COSArray();
        limits.add(new COSString(lo));
        limits.add(new COSString(hi));
        d.setItem(COSName.getPDFName("Limits"), limits);
        return d;
    }

    private static COSDictionary numLeaf(long[][] pairs, long lo, long hi) {
        COSDictionary d = new COSDictionary();
        COSArray nums = new COSArray();
        for (long[] p : pairs) {
            nums.add(COSInteger.get(p[0]));
            nums.add(COSInteger.get(p[1]));
        }
        d.setItem(COSName.getPDFName("Nums"), nums);
        COSArray limits = new COSArray();
        limits.add(COSInteger.get(lo));
        limits.add(COSInteger.get(hi));
        d.setItem(COSName.getPDFName("Limits"), limits);
        return d;
    }

    private static COSDictionary numIntermediate(COSDictionary[] children, long lo, long hi) {
        COSDictionary d = new COSDictionary();
        COSArray kids = new COSArray();
        for (COSDictionary c : children) {
            kids.add(c);
        }
        d.setItem(COSName.KIDS, kids);
        COSArray limits = new COSArray();
        limits.add(COSInteger.get(lo));
        limits.add(COSInteger.get(hi));
        d.setItem(COSName.getPDFName("Limits"), limits);
        return d;
    }

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
