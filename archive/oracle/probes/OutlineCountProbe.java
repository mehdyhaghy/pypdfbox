import java.io.PrintStream;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem;

/**
 * Live oracle probe for the wave-1483 surface: signed /Count bookkeeping in
 * the document-outline tree (openNode / closeNode / addLast / addFirst
 * propagation through open vs closed ancestor chains, and the always-open
 * PDDocumentOutline root).
 *
 * Builds several outline trees fully in-memory (no PDF I/O), performs a fixed
 * open/close/add sequence on each, and prints the resulting getOpenCount() of
 * every node so the pypdfbox port can be asserted against PDFBox's actual
 * values. Output is one "scenario: a,b,c" line per scenario on stdout (UTF-8).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OutlineCountProbe
 */
public final class OutlineCountProbe
{
    public static void main(String[] args)
    {
        PrintStream out = new PrintStream(System.out, true);

        // Scenario A: deep chain (root -> child -> grandchild), all opened
        // bottom-up, then open a leaf under grandchild. Verifies contributions
        // bubble all the way to the root when every ancestor is open.
        {
            PDDocumentOutline root = new PDDocumentOutline();
            PDOutlineItem child = new PDOutlineItem();
            PDOutlineItem grandchild = new PDOutlineItem();
            PDOutlineItem leaf = new PDOutlineItem();
            child.addLast(grandchild);   // child Count = 1 (closed)
            root.addLast(child);         // root Count = 1
            child.openNode();            // child open: +1 -> child 1, root 2
            grandchild.addLast(leaf);    // grandchild closed: grandchild -1, child 2, root 3
            grandchild.openNode();       // grandchild open: grandchild 1, child 3, root 4
            out.println("A:" + root.getOpenCount() + "," + child.getOpenCount()
                    + "," + grandchild.getOpenCount() + "," + leaf.getOpenCount());
        }

        // Scenario B: a CLOSED middle ancestor must absorb the swing and stop
        // propagation. root(open) -> child(CLOSED) -> grandchild. Opening the
        // grandchild widens child's negative count but does NOT touch root.
        {
            PDDocumentOutline root = new PDDocumentOutline();
            PDOutlineItem child = new PDOutlineItem();
            PDOutlineItem grandchild = new PDOutlineItem();
            PDOutlineItem leaf = new PDOutlineItem();
            grandchild.addLast(leaf);    // grandchild Count = 1 (closed)
            child.addLast(grandchild);   // child Count = 1 (closed)
            root.addLast(child);         // root Count = 1
            // child stays CLOSED. open the grandchild:
            grandchild.openNode();       // grandchild 1, child closed so -1 -> child -2, root unchanged
            out.println("B:" + root.getOpenCount() + "," + child.getOpenCount()
                    + "," + grandchild.getOpenCount());
        }

        // Scenario C: addLast of an OPEN child-with-descendants into a CLOSED
        // parent. delta = 1 + child.getOpenCount(); closed parent subtracts it.
        {
            PDOutlineItem parent = new PDOutlineItem();   // closed (Count 0)
            PDOutlineItem openChild = new PDOutlineItem();
            openChild.addLast(new PDOutlineItem());
            openChild.addLast(new PDOutlineItem());       // openChild Count 2 (closed)
            openChild.openNode();                          // openChild Count 2 (open)
            parent.addLast(openChild);                     // delta = 1+2 = 3; parent closed -> -3
            out.println("C:" + parent.getOpenCount() + "," + openChild.getOpenCount());
        }

        // Scenario D: addFirst into an OPEN parent with an open child holding
        // descendants. Verifies addFirst uses the same updateParent path.
        {
            PDOutlineItem parent = new PDOutlineItem();
            parent.addLast(new PDOutlineItem());           // parent 1 (closed)
            parent.openNode();                              // parent 1 (open)
            PDOutlineItem newFirst = new PDOutlineItem();
            newFirst.addLast(new PDOutlineItem());          // newFirst 1 (closed)
            newFirst.openNode();                             // newFirst 1 (open)
            parent.addFirst(newFirst);                       // delta = 1+1 = 2; parent open -> 1+2 = 3
            out.println("D:" + parent.getOpenCount() + "," + newFirst.getOpenCount());
        }

        // Scenario E: PDDocumentOutline root /Count after opening a nested
        // closed item. Root is always-open, so the swing reaches the root's
        // positive Count.
        {
            PDDocumentOutline root = new PDDocumentOutline();
            PDOutlineItem a = new PDOutlineItem();
            PDOutlineItem b = new PDOutlineItem();
            a.addLast(b);                 // a Count 1 (closed)
            root.addLast(a);              // root Count 1
            a.openNode();                 // a open: a 1, root 2
            out.println("E:" + root.getOpenCount() + "," + a.getOpenCount()
                    + ",isNodeOpen=" + root.isNodeOpen());
        }

        // Scenario F: closeNode on a node deep in an OPEN chain removes its
        // visible descendants from every open ancestor.
        {
            PDDocumentOutline root = new PDDocumentOutline();
            PDOutlineItem child = new PDOutlineItem();
            PDOutlineItem grandchild = new PDOutlineItem();
            child.addLast(grandchild);
            root.addLast(child);
            child.openNode();
            grandchild.addLast(new PDOutlineItem());
            grandchild.addLast(new PDOutlineItem());
            grandchild.openNode();        // grandchild 2, child 1+1+2=... compute live
            // now close the grandchild
            grandchild.closeNode();
            out.println("F:" + root.getOpenCount() + "," + child.getOpenCount()
                    + "," + grandchild.getOpenCount());
        }

        // Scenario G: isNodeOpen / getOpenCount on a fresh item with no /Count.
        {
            PDOutlineItem absent = new PDOutlineItem();         // no Count
            out.println("G:absent=" + absent.isNodeOpen()
                    + ",count=" + absent.getOpenCount());
        }
    }
}
