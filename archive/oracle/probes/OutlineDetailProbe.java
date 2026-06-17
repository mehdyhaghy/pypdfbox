import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
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
 * PDF's document outline (bookmarks) DETAIL, as Apache PDFBox parses it.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OutlineDetailProbe input.pdf
 *
 * Output (UTF-8, LF-terminated lines): one line per outline item in a stable
 * depth-first pre-order walk (children visited in /First -> /Next chain order):
 *
 *   <depth>\t<title>\t<rawCount>\t<isNodeOpen>\t<openCount>\t<color>\t<bold>\t<italic>\t<target>
 *
 * Where:
 *   - depth      = 0-based nesting depth (top-level items are depth 0)
 *   - title      = getTitle(), with backslash/newline/CR/tab escaped; "null"
 *                  when /Title is absent
 *   - rawCount   = the raw signed /Count integer on the item dictionary
 *                  (positive = open with N visible descendants, negative =
 *                  closed with |N| descendants, 0 = leaf); "none" when absent
 *   - isNodeOpen = isNodeOpen() boolean (true/false)
 *   - openCount  = getOpenCount() (the count getter; signed)
 *   - color      = getTextColor() RGB components as "r,g,b" (PDFBox materializes
 *                  [0,0,0] when /C absent); raw float repr
 *   - bold       = item.isBold() boolean
 *   - italic     = item.isItalic() boolean
 *   - target     = "dest:<pageIndex>" when the item resolves to a page via
 *                  /Dest or an /A GoTo action; "action:<subtype>" when the item
 *                  carries an /A action that is not a resolvable GoTo;
 *                  "none" when neither
 */
public final class OutlineDetailProbe {
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
              .append(rawCount(item)).append('\t')
              .append(item.isNodeOpen()).append('\t')
              .append(item.getOpenCount()).append('\t')
              .append(color(item)).append('\t')
              .append(item.isBold()).append('\t')
              .append(item.isItalic()).append('\t')
              .append(target(doc, item)).append('\n');
            walk(doc, item, depth + 1, sb);
        }
    }

    private static String rawCount(PDOutlineItem item) {
        COSBase c = item.getCOSObject().getDictionaryObject(COSName.COUNT);
        if (!(c instanceof COSNumber)) {
            return "none";
        }
        return Integer.toString(((COSNumber) c).intValue());
    }

    private static String color(PDOutlineItem item) {
        PDColor c = item.getTextColor();
        float[] comps = c.getComponents();
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < comps.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(fmt(comps[i]));
        }
        return sb.toString();
    }

    private static String fmt(float v) {
        // Canonical numeric repr: drop a trailing ".0" so 0.0 -> "0", 1.0 -> "1".
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Long.toString((long) v);
        }
        return Float.toString(v);
    }

    private static String target(PDDocument doc, PDOutlineItem item) throws Exception {
        PDDestination dest = item.getDestination();
        PDAction action = item.getAction();
        if (dest == null && action instanceof PDActionGoTo) {
            dest = ((PDActionGoTo) action).getDestination();
        }
        if (dest != null) {
            PDPageDestination pageDest = null;
            if (dest instanceof PDNamedDestination) {
                pageDest = doc.getDocumentCatalog()
                              .findNamedDestinationPage((PDNamedDestination) dest);
            } else if (dest instanceof PDPageDestination) {
                pageDest = (PDPageDestination) dest;
            }
            if (pageDest != null) {
                return "dest:" + resolvePageIndex(doc, pageDest);
            }
        }
        if (action != null) {
            String sub = action.getSubType();
            return "action:" + (sub == null ? "null" : sub);
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
