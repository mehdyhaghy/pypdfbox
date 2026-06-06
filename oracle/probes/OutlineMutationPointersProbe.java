import java.io.PrintStream;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineNode;

/**
 * Live oracle probe for the wave-1501 surface: the raw COS POINTER projection
 * ({@code /First /Last /Next /Prev /Parent /Count}) of an outline tree after a
 * fixed mutation sequence, captured directly off the in-memory COSDictionary
 * (no PDF save/load round-trip). Where {@code OutlineCountProbe} dumps only the
 * signed {@code /Count} and {@code OutlineTraversalProbe} dumps wrapper titles
 * after a save/reload, this probe verifies the doubly-linked-list rewiring
 * itself: which node each pointer points at after insert-after / insert-before
 * on first / middle / last positions, parent rewiring on cross-parent re-add,
 * and add_first / add_last interleaving.
 *
 * Each node carries a unique single-letter /Title used as its stable id. For
 * every node we emit a line:
 *
 *   <title>:parent=<t>,first=<t>,last=<t>,next=<t>,prev=<t>,count=<n>
 *
 * where each pointer is the /Title of the directly-referenced COSDictionary
 * (read straight from the COS layer, NOT via the typed wrapper) or "-" when the
 * key is absent. count is the raw /Count or "-" when absent. The outline root is
 * emitted as title "ROOT". Lines are emitted in scenario order; scenarios are
 * separated by a "== <name> ==" header line. UTF-8, trailing newline per line.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OutlineMutationPointersProbe
 */
public final class OutlineMutationPointersProbe {

    static final COSName FIRST = COSName.getPDFName("First");
    static final COSName LAST = COSName.getPDFName("Last");
    static final COSName NEXT = COSName.getPDFName("Next");
    static final COSName PREV = COSName.getPDFName("Prev");
    static final COSName PARENT = COSName.getPDFName("Parent");
    static final COSName COUNT = COSName.getPDFName("Count");
    static final COSName TITLE = COSName.getPDFName("Title");
    static final COSName TYPE = COSName.getPDFName("Type");

    public static void main(String[] args) {
        PrintStream out = new PrintStream(System.out, true);

        // Scenario 1: insert_sibling_after on the MIDDLE node of a 3-chain.
        // root -> A -> B -> C ; B.insertSiblingAfter(X) -> A B X C
        {
            out.println("== insert_after_middle ==");
            PDDocumentOutline root = mkRoot();
            PDOutlineItem a = mk("A");
            PDOutlineItem b = mk("B");
            PDOutlineItem c = mk("C");
            root.addLast(a);
            root.addLast(b);
            root.addLast(c);
            PDOutlineItem x = mk("X");
            b.insertSiblingAfter(x);
            dump(out, root);
        }

        // Scenario 2: insert_sibling_before on the MIDDLE node.
        // root -> A -> B -> C ; B.insertSiblingBefore(X) -> A X B C
        {
            out.println("== insert_before_middle ==");
            PDDocumentOutline root = mkRoot();
            PDOutlineItem a = mk("A");
            PDOutlineItem b = mk("B");
            PDOutlineItem c = mk("C");
            root.addLast(a);
            root.addLast(b);
            root.addLast(c);
            PDOutlineItem x = mk("X");
            b.insertSiblingBefore(x);
            dump(out, root);
        }

        // Scenario 3: insert_sibling_after on the LAST node (tail rewiring,
        // parent /Last must follow).
        {
            out.println("== insert_after_last ==");
            PDDocumentOutline root = mkRoot();
            PDOutlineItem a = mk("A");
            PDOutlineItem b = mk("B");
            root.addLast(a);
            root.addLast(b);
            PDOutlineItem x = mk("X");
            b.insertSiblingAfter(x);
            dump(out, root);
        }

        // Scenario 4: insert_sibling_before on the FIRST node (head rewiring,
        // parent /First must follow).
        {
            out.println("== insert_before_first ==");
            PDDocumentOutline root = mkRoot();
            PDOutlineItem a = mk("A");
            PDOutlineItem b = mk("B");
            root.addLast(a);
            root.addLast(b);
            PDOutlineItem x = mk("X");
            a.insertSiblingBefore(x);
            dump(out, root);
        }

        // Scenario 5: add_first then add_last interleaving on a fresh root.
        // add_last(A); add_first(B); add_last(C); add_first(D) -> D B A C
        {
            out.println("== add_first_last_interleave ==");
            PDDocumentOutline root = mkRoot();
            root.addLast(mk("A"));
            root.addFirst(mk("B"));
            root.addLast(mk("C"));
            root.addFirst(mk("D"));
            dump(out, root);
        }

        // Scenario 6: cross-parent re-add. P1 has only child A. addLast A to P2.
        // Upstream addLast -> requireSingleNode(A) passes (A has no Next/Prev as
        // an only child), then append sets A.Parent=P2 and P2.First=P2.Last=A,
        // but P1.First / P1.Last STILL point at A (stale). Capture both parents.
        {
            out.println("== cross_parent_readd ==");
            PDDocumentOutline rootHolder = mkRoot();
            PDOutlineItem p1 = mk("P");   // P1
            PDOutlineItem p2 = mk("Q");   // P2
            rootHolder.addLast(p1);
            rootHolder.addLast(p2);
            PDOutlineItem a = mk("A");
            p1.addLast(a);                // A under P1
            p2.addLast(a);                // re-add A under P2 without detach
            dump(out, rootHolder);
        }

        // Scenario 7: insert_sibling_after when the node has NO parent (root
        // sibling). root has no /Parent; X becomes root's /Next but no parent
        // /Last fixup since parent is null.
        {
            out.println("== insert_after_no_parent ==");
            PDOutlineItem lone = mk("L");
            PDOutlineItem x = mk("X");
            lone.insertSiblingAfter(x);
            dumpNode(out, lone, "L");
            dumpNode(out, x, "X");
        }
    }

    private static PDDocumentOutline mkRoot() {
        PDDocumentOutline root = new PDDocumentOutline();
        root.getCOSObject().setName(TITLE, "ROOT");
        return root;
    }

    private static PDOutlineItem mk(String title) {
        PDOutlineItem item = new PDOutlineItem();
        item.setTitle(title);
        return item;
    }

    private static void dump(PrintStream out, PDOutlineNode root) {
        dumpNode(out, root, titleOf(root.getCOSObject()));
        dumpChildren(out, root);
    }

    private static void dumpChildren(PrintStream out, PDOutlineNode node) {
        for (PDOutlineItem child : node.children()) {
            dumpNode(out, child, titleOf(child.getCOSObject()));
            dumpChildren(out, child);
        }
    }

    private static void dumpNode(PrintStream out, PDOutlineNode node, String id) {
        COSDictionary d = node.getCOSObject();
        out.println(id
                + ":parent=" + ptr(d, PARENT)
                + ",first=" + ptr(d, FIRST)
                + ",last=" + ptr(d, LAST)
                + ",next=" + ptr(d, NEXT)
                + ",prev=" + ptr(d, PREV)
                + ",count=" + count(d));
    }

    private static String ptr(COSDictionary d, COSName key) {
        COSDictionary target = (COSDictionary) d.getDictionaryObject(key);
        if (target == null) {
            return "-";
        }
        return titleOf(target);
    }

    private static String titleOf(COSDictionary d) {
        String t = d.getString(TITLE);
        if (t != null) {
            return t;
        }
        // No title — distinguish the outline root by /Type.
        COSName type = (COSName) d.getDictionaryObject(TYPE);
        if (type != null && "Outlines".equals(type.getName())) {
            return "ROOT";
        }
        return "?";
    }

    private static String count(COSDictionary d) {
        if (d.getDictionaryObject(COUNT) == null) {
            return "-";
        }
        return Integer.toString(d.getInt(COUNT));
    }
}
