import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageTree;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: structural page-tree mutation on an UNBALANCED, multi
 * level /Kids tree. Complements PageTreeProbe (which only checks the flat
 * post-mutation page traversal) by dumping the internal tree shape — every
 * intermediate /Pages node's /Count, the /Parent back-pointer integrity, and
 * the leaf page ordering (identified by a unique integer width baked into each
 * page's MediaBox) — so /Count propagation up multiple levels and /Parent
 * re-targeting after an insert/remove/add are verified, not just the linear
 * page order.
 *
 * The tree is built from scratch identically on both the Java and Python side
 * so the comparison does not depend on any fixture. Shape (depth-first):
 *
 *   root /Pages
 *     A /Pages
 *       p0  (MediaBox width 100)
 *       p1  (101)
 *       B /Pages
 *         p2 (102)
 *         p3 (103)
 *         p4 (104)
 *     p5  (105)
 *
 * Usage:
 *   java ... PageTreeMutateProbe <op> <arg> <out.pdf>
 * ops (arg = target page width):
 *   build                      no mutation, just save+reload the built tree
 *   insert_after  <width>      insert a fresh page (width 200) after that page
 *   insert_before <width>      insert a fresh page (width 200) before that page
 *   add                        addPage a fresh page (width 200) to the tree
 *   remove        <width>      removePage(indexOf(page with that width))
 *
 * After the mutation the doc is saved, reloaded, and the reloaded tree's
 * canonical structure dump is printed to stdout.
 */
public final class PageTreeMutateProbe {

    private static final float[] WIDTHS = {100, 101, 102, 103, 104, 105};

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String op = args[0];
        File outFile = new File(args[args.length - 1]);

        try (PDDocument doc = new PDDocument()) {
            build(doc);
            applyMutation(doc, op, args);
            doc.save(outFile);
        }
        try (PDDocument reloaded = Loader.loadPDF(outFile)) {
            out.print(dump(reloaded));
        }
    }

    /** Build the fixed unbalanced multi-level tree described above. */
    private static void build(PDDocument doc) {
        COSDictionary root = doc.getPages().getCOSObject();
        // Start from an empty root: clear whatever the new-doc default holds.
        root.setItem(COSName.KIDS, new COSArray());
        root.setItem(COSName.COUNT, COSInteger.get(0));

        COSDictionary a = pagesNode(root);
        COSDictionary b = pagesNode(a);

        addKid(a, page(100));
        addKid(a, page(101));
        addKid(b, page(102));
        addKid(b, page(103));
        addKid(b, page(104));
        addKid(a, b);
        addKid(root, a);
        addKid(root, page(105));

        // Set /Count bottom-up to the true leaf counts.
        b.setItem(COSName.COUNT, COSInteger.get(3));
        a.setItem(COSName.COUNT, COSInteger.get(5));
        root.setItem(COSName.COUNT, COSInteger.get(6));
    }

    private static COSDictionary pagesNode(COSDictionary parent) {
        COSDictionary n = new COSDictionary();
        n.setItem(COSName.TYPE, COSName.PAGES);
        n.setItem(COSName.KIDS, new COSArray());
        n.setItem(COSName.COUNT, COSInteger.get(0));
        n.setItem(COSName.PARENT, parent);
        return n;
    }

    private static COSDictionary page(float width) {
        PDPage p = new PDPage(new PDRectangle(width, 200));
        return p.getCOSObject();
    }

    private static void addKid(COSDictionary parent, COSDictionary kid) {
        COSArray kids = (COSArray) parent.getDictionaryObject(COSName.KIDS);
        kids.add(kid);
        kid.setItem(COSName.PARENT, parent);
    }

    private static void applyMutation(PDDocument doc, String op, String[] args) {
        PDPageTree tree = doc.getPages();
        if ("build".equals(op)) {
            return;
        }
        if ("add".equals(op)) {
            doc.addPage(new PDPage(new PDRectangle(200, 200)));
            return;
        }
        float width = Float.parseFloat(args[1]);
        PDPage target = pageByWidth(tree, width);
        if ("remove".equals(op)) {
            doc.removePage(target);
        } else if ("insert_after".equals(op)) {
            tree.insertAfter(new PDPage(new PDRectangle(200, 200)), target);
        } else if ("insert_before".equals(op)) {
            tree.insertBefore(new PDPage(new PDRectangle(200, 200)), target);
        } else {
            throw new IllegalArgumentException("unknown op: " + op);
        }
    }

    private static PDPage pageByWidth(PDPageTree tree, float width) {
        for (PDPage p : tree) {
            if (Math.abs(p.getMediaBox().getWidth() - width) < 0.001f) {
                return p;
            }
        }
        throw new IllegalStateException("no page of width " + width);
    }

    /**
     * Canonical structure dump of the page tree. Pre-order DFS from the root
     * /Pages node. One line per node:
     *   node depth=<d> type=<Pages|Page> count=<n|-> kids=<k|-> parentok=<0|1> w=<width|->
     * parentok is 1 when this node's /Parent identity equals the node we
     * descended from (root's parent must be the catalog or null -> reported as
     * the literal "root"). Leaf pages report their MediaBox width as identity.
     */
    private static String dump(PDDocument doc) {
        StringBuilder sb = new StringBuilder();
        COSDictionary root = doc.getPages().getCOSObject();
        sb.append("pages ").append(doc.getNumberOfPages()).append('\n');
        walk(root, null, 0, sb);
        return sb.toString();
    }

    private static void walk(COSDictionary node, COSDictionary expectedParent, int depth, StringBuilder sb) {
        boolean isPages = COSName.PAGES.equals(node.getCOSName(COSName.TYPE))
                || node.containsKey(COSName.KIDS);
        String type = isPages ? "Pages" : "Page";

        String count = "-";
        if (node.containsKey(COSName.COUNT)) {
            count = Integer.toString(node.getInt(COSName.COUNT));
        }

        COSArray kidsArr = isPages ? (COSArray) node.getDictionaryObject(COSName.KIDS) : null;
        String kids = kidsArr == null ? "-" : Integer.toString(kidsArr.size());

        int parentok;
        if (expectedParent == null) {
            parentok = 1; // root: not checked against a descended-from node
        } else {
            COSBase parent = node.getDictionaryObject(COSName.PARENT);
            parentok = (parent == expectedParent) ? 1 : 0;
        }

        String w = "-";
        if (!isPages) {
            PDPage p = new PDPage(node);
            w = fmt(p.getMediaBox().getWidth());
        }

        sb.append("node depth=").append(depth)
          .append(" type=").append(type)
          .append(" count=").append(count)
          .append(" kids=").append(kids)
          .append(" parentok=").append(parentok)
          .append(" w=").append(w)
          .append('\n');

        if (kidsArr != null) {
            for (int i = 0; i < kidsArr.size(); i++) {
                COSBase kid = kidsArr.getObject(i);
                if (kid instanceof COSDictionary) {
                    walk((COSDictionary) kid, node, depth + 1, sb);
                }
            }
        }
    }

    private static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Long.toString((long) v);
        }
        return Float.toString(v);
    }
}
