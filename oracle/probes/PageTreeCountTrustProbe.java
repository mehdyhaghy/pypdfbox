import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageTree;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: pin how Apache PDFBox's PDPageTree treats the stored
 * /Count when it DISAGREES with the actual leaf count, plus the exact
 * exception type/message thrown by get(index) for out-of-range indices.
 *
 * Upstream get(int) descends the tree trusting each node's stored /Count to
 * decide whether the requested page can possibly be under that node (see
 * PDPageTree.get(pageNum, node, encountered)). getCount() returns the raw
 * stored /Count of the root, O(1), no walk.
 *
 * Two scenarios:
 *   A) /Count UNDERCOUNTS: root /Count=1 but 2 real leaves exist.
 *      - getCount()  -> 1 (raw)
 *      - get(0)      -> succeeds (page 0, width 100)
 *      - get(1)      -> IndexOutOfBoundsException ("1-based index out of bounds: 2")
 *   B) /Count OVERCOUNTS: root /Count=5 but 2 real leaves exist.
 *      - getCount()  -> 5 (raw)
 *      - get(0),get(1) -> succeed
 *      - get(2)      -> IllegalStateException ("1-based index not found: 3")
 *        (count says a 3rd page should exist under root, but the /Kids walk
 *         runs out of kids -> falls through to "1-based index not found")
 *
 * Output (UTF-8, stdout): one JSON object.
 */
public final class PageTreeCountTrustProbe {

    private static PDPage leaf(PDDocument doc, COSDictionary parent, int width) {
        PDPage page = new PDPage(new PDRectangle(width, 200));
        COSDictionary d = page.getCOSObject();
        d.setItem(COSName.PARENT, parent);
        return page;
    }

    private static String describe(Runnable r) {
        try {
            r.run();
            return "NO_THROW";
        } catch (Exception e) {
            return e.getClass().getSimpleName() + ": " + e.getMessage();
        }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        sb.append("{");

        // ---- Scenario A: undercount (root /Count = 1, 2 real leaves) ----
        {
            PDDocument doc = new PDDocument();
            COSDictionary root = doc.getPages().getCOSObject();
            COSArray kids = (COSArray) root.getDictionaryObject(COSName.KIDS);
            PDPage p0 = leaf(doc, root, 100);
            PDPage p1 = leaf(doc, root, 101);
            kids.add(p0.getCOSObject());
            kids.add(p1.getCOSObject());
            root.setInt(COSName.COUNT, 1); // LIE: undercount

            PDPageTree tree = doc.getPages();
            sb.append("\"a_getCount\":").append(tree.getCount()).append(",");
            sb.append("\"a_get0_width\":").append(
                    (int) tree.get(0).getMediaBox().getWidth()).append(",");
            final PDPageTree t = tree;
            sb.append("\"a_get1\":\"").append(describe(() -> t.get(1))).append("\",");
            doc.close();
        }

        // ---- Scenario B: overcount (root /Count = 5, 2 real leaves) ----
        {
            PDDocument doc = new PDDocument();
            COSDictionary root = doc.getPages().getCOSObject();
            COSArray kids = (COSArray) root.getDictionaryObject(COSName.KIDS);
            PDPage p0 = leaf(doc, root, 200);
            PDPage p1 = leaf(doc, root, 201);
            kids.add(p0.getCOSObject());
            kids.add(p1.getCOSObject());
            root.setInt(COSName.COUNT, 5); // LIE: overcount

            PDPageTree tree = doc.getPages();
            sb.append("\"b_getCount\":").append(tree.getCount()).append(",");
            sb.append("\"b_get0_width\":").append(
                    (int) tree.get(0).getMediaBox().getWidth()).append(",");
            sb.append("\"b_get1_width\":").append(
                    (int) tree.get(1).getMediaBox().getWidth()).append(",");
            final PDPageTree t = tree;
            sb.append("\"b_get2\":\"").append(describe(() -> t.get(2))).append("\",");
            doc.close();
        }

        // ---- Scenario C: honest tree, plain out-of-range get ----
        {
            PDDocument doc = new PDDocument();
            doc.addPage(new PDPage(new PDRectangle(300, 200)));
            doc.addPage(new PDPage(new PDRectangle(301, 200)));
            PDPageTree tree = doc.getPages();
            sb.append("\"c_getCount\":").append(tree.getCount()).append(",");
            final PDPageTree t = tree;
            sb.append("\"c_get2\":\"").append(describe(() -> t.get(2))).append("\",");
            sb.append("\"c_get_neg1\":\"").append(describe(() -> t.get(-1))).append("\"");
            doc.close();
        }

        sb.append("}");
        out.println(sb.toString());
    }
}
