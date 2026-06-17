import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionGoTo;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionURI;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDNamedDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageXYZDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineNode;

/**
 * Live oracle probe: emit a CANONICAL, deterministic per-item dump of an
 * outline's ``/A`` action and ``/Dest`` destination accessors, as Apache
 * PDFBox parses them.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OutlineActionDestProbe input.pdf
 *
 * Output (UTF-8, LF-terminated lines): one line per outline item, in a stable
 * depth-first pre-order walk (children visited in /First -> /Next chain order):
 *
 *   <depth>\t<title>\t<action>\t<destination>
 *
 * Where:
 *   - depth        = 0-based nesting depth (top-level items are depth 0).
 *   - title        = getTitle(), with backslash/newline/CR/tab escaped;
 *                    "null" when /Title is absent.
 *   - action       = ``none`` when getAction() is null. Otherwise:
 *                      * URI    -> ``URI:uri=<uri>``
 *                      * GoTo   -> ``GoTo:dest=<resolved>`` (resolved per
 *                        ``resolveDest`` — ``page<idx>`` for explicit page
 *                        destinations, ``named:<name>`` for named, ``none``
 *                        when absent / unresolvable).
 *                      * other  -> ``<subtype>``.
 *   - destination  = ``none`` when getDestination() is null. Otherwise:
 *                      * PDNamedDestination     -> ``named:<name>``
 *                      * PDPageXYZDestination   -> ``XYZ:page=<idx>,left=<l>,top=<t>,zoom=<z>``
 *                      * other PDPageDestination -> ``<typeName>:page=<idx>``
 *
 * The "both present" case (an item that carries /A and /Dest at the same time)
 * is the high-value differential — PDF §12.3.3 allows both, and the two
 * accessors must independently round-trip.
 */
public final class OutlineActionDestProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDDocumentOutline outline = catalog.getDocumentOutline();
            StringBuilder sb = new StringBuilder();
            if (outline != null) {
                walk(doc, outline, 0, sb);
            }
            out.print(sb);
        }
    }

    private static void walk(PDDocument doc, PDOutlineNode node, int depth, StringBuilder sb)
            throws Exception {
        for (PDOutlineItem item : node.children()) {
            sb.append(depth).append('\t')
              .append(escape(item.getTitle())).append('\t')
              .append(actionStr(doc, item.getAction())).append('\t')
              .append(destinationStr(doc, item.getDestination())).append('\n');
            walk(doc, item, depth + 1, sb);
        }
    }

    private static String actionStr(PDDocument doc, PDAction action) {
        if (action == null) {
            return "none";
        }
        if (action instanceof PDActionURI) {
            String uri = ((PDActionURI) action).getURI();
            return "URI:uri=" + (uri == null ? "" : uri);
        }
        if (action instanceof PDActionGoTo) {
            try {
                PDDestination dest = ((PDActionGoTo) action).getDestination();
                return "GoTo:dest=" + resolveDest(doc, dest);
            } catch (Exception e) {
                return "GoTo:dest=none";
            }
        }
        String sub = action.getSubType();
        return sub == null ? "null" : sub;
    }

    private static String destinationStr(PDDocument doc, PDDestination dest) {
        if (dest == null) {
            return "none";
        }
        if (dest instanceof PDNamedDestination) {
            String n = ((PDNamedDestination) dest).getNamedDestination();
            return "named:" + (n == null ? "" : n);
        }
        if (dest instanceof PDPageXYZDestination) {
            PDPageXYZDestination xyz = (PDPageXYZDestination) dest;
            int idx = resolvePageIndex(doc, xyz);
            // Read slots directly from the /D array so the "unset" state
            // matches pypdfbox's `None` rather than PDFBox's -1 sentinel.
            COSArray d = xyz.getCOSObject();
            return "XYZ:page=" + idx
                    + ",left=" + slot(d, 2)
                    + ",top=" + slot(d, 3)
                    + ",zoom=" + slot(d, 4);
        }
        if (dest instanceof PDPageDestination) {
            PDPageDestination pd = (PDPageDestination) dest;
            String type = pd.getClass().getSimpleName();
            return type + ":page=" + resolvePageIndex(doc, pd);
        }
        return "none";
    }

    private static String resolveDest(PDDocument doc, PDDestination dest) {
        if (dest == null) {
            return "none";
        }
        if (dest instanceof PDNamedDestination) {
            String n = ((PDNamedDestination) dest).getNamedDestination();
            return "named:" + (n == null ? "" : n);
        }
        if (dest instanceof PDPageDestination) {
            return "page" + resolvePageIndex(doc, (PDPageDestination) dest);
        }
        return "none";
    }

    private static int resolvePageIndex(PDDocument doc, PDPageDestination pageDest) {
        PDPage page = pageDest.getPage();
        if (page != null) {
            int idx = doc.getPages().indexOf(page);
            if (idx >= 0) {
                return idx;
            }
        }
        return pageDest.getPageNumber();
    }

    /**
     * Canonical numeric repr for a /D-array slot at index ``i``: "null" when
     * the slot is absent or is COSNull (which is both how pypdfbox represents
     * "unset" and what the PDF spec encodes), otherwise "<n>" with a trailing
     * ".0" dropped so 0.0 -> "0". We bypass PDFBox's typed getters
     * (which return -1 for unset) because pypdfbox returns None — reading the
     * raw COS slot lets the canonical line compare byte-for-byte.
     */
    private static String slot(COSArray array, int i) {
        if (array == null || i >= array.size()) {
            return "null";
        }
        COSBase v = array.getObject(i);
        if (!(v instanceof COSNumber)) {
            return "null";
        }
        float f = ((COSNumber) v).floatValue();
        if (f == Math.rint(f) && !Float.isInfinite(f)) {
            return Long.toString((long) f);
        }
        return Float.toString(f);
    }

    private static String escape(String s) {
        if (s == null) {
            return "null";
        }
        return s.replace("\\", "\\\\")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
