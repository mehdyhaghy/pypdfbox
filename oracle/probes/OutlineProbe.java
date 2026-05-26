import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionGoTo;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDNamedDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineNode;

/**
 * Live oracle probe: emit a CANONICAL, deterministic pre-order listing of a
 * PDF's document outline (bookmarks), as Apache PDFBox parses it.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OutlineProbe input.pdf
 *
 * Output (UTF-8, LF-terminated lines): one line per outline item, in a stable
 * depth-first pre-order walk (children visited in /First -> /Next chain
 * order), so the listing is independent of object-number layout:
 *
 *   <depth>\t<title>\t<pageIndex>
 *
 * Where:
 *   - depth     = 0-based nesting depth (top-level items are depth 0)
 *   - title     = getTitle(), newlines escaped to "\\n", carriage returns to
 *                 "\\r" and tabs to "\\t" so each record stays single-line;
 *                 "null" when /Title is absent
 *   - pageIndex = the 0-based page index the item points at, resolved from its
 *                 destination (/Dest) or, failing that, its /A GoTo action's
 *                 destination. Named destinations are resolved through the
 *                 catalog (/Names/Dests name tree, then /Dests dictionary).
 *                 Emits -1 when the item has no resolvable page target.
 *
 * When the document has no outline (or an empty one) the output is empty.
 */
public final class OutlineProbe {
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
              .append(resolvePageIndex(doc, item)).append('\n');
            walk(doc, item, depth + 1, sb);
        }
    }

    private static int resolvePageIndex(PDDocument doc, PDOutlineItem item) throws Exception {
        PDPageDestination pageDest = resolvePageDestination(doc, item);
        if (pageDest == null) {
            return -1;
        }
        // First try a direct page-object reference (local destination); fall
        // back to the explicit numeric page index (remote destination).
        PDPage page = pageDest.getPage();
        if (page != null) {
            int idx = doc.getPages().indexOf(page);
            if (idx >= 0) {
                return idx;
            }
        }
        return pageDest.getPageNumber();
    }

    /** Resolve an item's /Dest, or its /A GoTo action's destination, to a
     *  PDPageDestination — chasing named destinations through the catalog. */
    private static PDPageDestination resolvePageDestination(PDDocument doc, PDOutlineItem item)
            throws Exception {
        PDDestination dest = item.getDestination();
        if (dest == null) {
            PDAction action = item.getAction();
            if (action instanceof PDActionGoTo) {
                dest = ((PDActionGoTo) action).getDestination();
            }
        }
        if (dest == null) {
            return null;
        }
        if (dest instanceof PDNamedDestination) {
            return doc.getDocumentCatalog()
                      .findNamedDestinationPage((PDNamedDestination) dest);
        }
        if (dest instanceof PDPageDestination) {
            return (PDPageDestination) dest;
        }
        return null;
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
