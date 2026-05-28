import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.common.COSObjectable;
import org.apache.pdfbox.pdmodel.common.PDNameTreeNode;
import org.apache.pdfbox.pdmodel.common.PDNumberTreeNode;

/**
 * Live oracle probe: load a PDF written by pypdfbox that carries a MULTI-LEVEL
 * generic name tree (catalog /Names /JavaScript) and a multi-level number tree
 * (catalog /PageLabels), then exercise PDNameTreeNode / PDNumberTreeNode
 * traversal against the re-parsed COS.
 *
 * Unlike NameNumTreeProbe (which builds the COS in-process), this probe reads
 * the tree back from a saved file, so it pins pypdfbox's *serialization* of a
 * balanced /Kids+/Limits tree: the writer's indirect-reference layout, the
 * sorted /Names / /Nums arrays and the /Limits [lo hi] arrays must all survive
 * the round trip so PDFBox can descend through them identically.
 *
 * The same saved file is loaded on the pypdfbox side and the identical report
 * is rebuilt, so the two compare string-for-string.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> NameNumTreeRoundTripProbe input.pdf
 */
public final class NameNumTreeRoundTripProbe {

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
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();
            COSDictionary names = (COSDictionary) catalog.getDictionaryObject(COSName.NAMES);
            COSDictionary jsRoot =
                (COSDictionary) names.getDictionaryObject(COSName.getPDFName("JavaScript"));
            COSDictionary pageLabels =
                (COSDictionary) catalog.getDictionaryObject(COSName.getPDFName("PageLabels"));

            out.println("# name tree");
            reportName(out, new StrNode(jsRoot), new String[] {
                "alpha", "bravo", "delta", "echo", "golf", "hotel", "kilo", "lima",
                "charlie", "foxtrot", "india", "zulu", "aaa", "echo", "golf"
            });

            out.println("# num tree");
            reportNum(out, new IntNode(pageLabels), new int[] {
                0, 2, 10, 12, 20, 25, 30, 33, 40, 47, 1, 11, 26, 35, -5, 50, 100
            });
        }
    }

    private static void reportName(PrintStream out, StrNode node, String[] keys) throws Exception {
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

    private static void reportNum(PrintStream out, IntNode node, int[] keys) throws Exception {
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
