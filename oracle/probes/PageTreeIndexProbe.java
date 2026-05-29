import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageTree;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: pin Apache PDFBox's PDPageTree INDEX / LOOKUP query
 * surface on a multi-level, unbalanced /Kids tree built from scratch (no
 * fixture dependency). Complements PageTreeProbe (flat traversal + per-page
 * indexOf) and PageTreeMutateProbe (post-mutation structure) by isolating the
 * read-only query contract:
 *
 *   - getCount()                       O(1) stored /Count of the root
 *   - iteration order across the tree  document order yielded by Iterable
 *   - indexOf(PDPage) for every page   0-based position via the /Kids walk
 *   - indexOf(foreign page)            -1 for a page NOT in this tree
 *   - get(index) round-trip            get(indexOf(p)) is the same page (its
 *                                      MediaBox width matches), and a direct
 *                                      get(i) yields the page whose width we
 *                                      expect at that index
 *
 * Each page carries a unique integer MediaBox width so the Python side can
 * identify pages without relying on object identity across the JVM boundary.
 *
 * Tree shape (depth-first leaf order = widths 100..105):
 *
 *   root /Pages
 *     A /Pages
 *       p0  (width 100)
 *       p1  (width 101)
 *       B /Pages
 *         p2 (width 102)
 *         p3 (width 103)
 *         p4 (width 104)
 *     p5  (width 105)
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PageTreeIndexProbe
 *
 * Output (UTF-8, stdout): a single JSON object, e.g.
 *   {"count":6,"order":[100,101,102,103,104,105],
 *    "indexOf":[0,1,2,3,4,5],"getWidths":[100,101,102,103,104,105],
 *    "roundTrip":true,"foreignIndexOf":-1}
 */
public final class PageTreeIndexProbe {

    private static final int[] WIDTHS = {100, 101, 102, 103, 104, 105};

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = new PDDocument()) {
            List<PDPage> leaves = build(doc);
            PDPageTree tree = doc.getPages();

            int count = tree.getCount();

            // Iteration order: each yielded page's MediaBox width.
            List<Integer> order = new ArrayList<>();
            for (PDPage p : tree) {
                order.add((int) p.getMediaBox().getWidth());
            }

            // indexOf for every leaf, in our construction order (which equals
            // document order here): the result is the 0-based document index.
            List<Integer> indexOf = new ArrayList<>();
            for (PDPage p : leaves) {
                indexOf.add(tree.indexOf(p));
            }

            // get(i) widths, and the round-trip identity get(indexOf(p)) == p.
            List<Integer> getWidths = new ArrayList<>();
            boolean roundTrip = true;
            for (int i = 0; i < count; i++) {
                PDPage at = tree.get(i);
                getWidths.add((int) at.getMediaBox().getWidth());
            }
            for (PDPage p : leaves) {
                int idx = tree.indexOf(p);
                PDPage got = tree.get(idx);
                if (got.getCOSObject() != p.getCOSObject()) {
                    roundTrip = false;
                }
            }

            // A foreign page that was never added to the tree → indexOf == -1.
            PDPage foreign = new PDPage(new PDRectangle(999, 999));
            int foreignIndexOf = tree.indexOf(foreign);

            StringBuilder sb = new StringBuilder();
            sb.append('{');
            sb.append("\"count\":").append(count).append(',');
            sb.append("\"order\":").append(intList(order)).append(',');
            sb.append("\"indexOf\":").append(intList(indexOf)).append(',');
            sb.append("\"getWidths\":").append(intList(getWidths)).append(',');
            sb.append("\"roundTrip\":").append(roundTrip).append(',');
            sb.append("\"foreignIndexOf\":").append(foreignIndexOf);
            sb.append('}');
            out.println(sb.toString());
        }
    }

    /**
     * Build the unbalanced tree by hand-wiring COS dictionaries so the leaf
     * document order and the intermediate-node nesting are deterministic.
     * Returns the leaf pages in document order.
     */
    private static List<PDPage> build(PDDocument doc) {
        COSDictionary root = doc.getDocumentCatalog().getPages().getCOSObject();
        // Reset the auto-created root to a clean state.
        COSArray rootKids = new COSArray();
        root.setItem(COSName.KIDS, rootKids);

        COSDictionary a = pagesNode(root);
        COSDictionary b = pagesNode(a);

        List<PDPage> leaves = new ArrayList<>();
        // A: p0, p1, then B
        addLeaf(a, leaves, WIDTHS[0]);
        addLeaf(a, leaves, WIDTHS[1]);
        // B nested under A
        addNode(a, b);
        addLeaf(b, leaves, WIDTHS[2]);
        addLeaf(b, leaves, WIDTHS[3]);
        addLeaf(b, leaves, WIDTHS[4]);
        // root: A, then p5
        addNode(root, a);
        addLeaf(root, leaves, WIDTHS[5]);

        // /Count on every intermediate node: B=3, A=2+3=5, root=5+1=6.
        b.setInt(COSName.COUNT, 3);
        a.setInt(COSName.COUNT, 5);
        root.setInt(COSName.COUNT, 6);
        return leaves;
    }

    private static COSDictionary pagesNode(COSDictionary parent) {
        COSDictionary node = new COSDictionary();
        node.setItem(COSName.TYPE, COSName.PAGES);
        node.setItem(COSName.KIDS, new COSArray());
        node.setItem(COSName.PARENT, parent);
        return node;
    }

    private static void addNode(COSDictionary parent, COSDictionary child) {
        COSArray kids = (COSArray) parent.getDictionaryObject(COSName.KIDS);
        kids.add(child);
        child.setItem(COSName.PARENT, parent);
    }

    private static void addLeaf(COSDictionary parent, List<PDPage> leaves, int width) {
        COSDictionary pageDict = new COSDictionary();
        pageDict.setItem(COSName.TYPE, COSName.PAGE);
        pageDict.setItem(COSName.PARENT, parent);
        PDPage page = new PDPage(pageDict);
        page.setMediaBox(new PDRectangle(width, width));
        COSArray kids = (COSArray) parent.getDictionaryObject(COSName.KIDS);
        kids.add(pageDict);
        leaves.add(page);
    }

    private static String intList(List<Integer> values) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < values.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(values.get(i));
        }
        sb.append(']');
        return sb.toString();
    }
}
