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
 * Live oracle probe: emit a deterministic JSON tree of a PDF's document
 * outline (bookmarks) for the wave-1454 surface — children() iteration via
 * /First -> /Next, signed /Count semantics (sign = open/closed, magnitude =
 * subtree size), and destination resolution (explicit /Dest, named /Dest, /A
 * GoTo fallback), all as Apache PDFBox parses them.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OutlineTreeProbe input.pdf
 *
 * Output: a single JSON document on stdout (UTF-8, no trailing newline). The
 * root object always carries:
 *
 *   {
 *     "open_count": <signed int>,        // outline-root getOpenCount() (always >= 0)
 *     "child_count": <int>,              // number of immediate children iterated
 *     "children": [ <item>, <item>, ... ]
 *   }
 *
 * Each item is:
 *
 *   {
 *     "title": "<string>"|null,          // PDOutlineItem.getTitle()
 *     "count": <signed int>|null,        // raw /Count from the dict, null when absent
 *     "is_open": <bool>,                 // PDOutlineItem.isNodeOpen()
 *     "dest": <int>,                     // 0-based resolved page index; -1 when unresolved
 *     "child_count": <int>,              // number of immediate children iterated
 *     "children": [ <item>, ... ]
 *   }
 *
 * Children are listed in /First -> /Next chain order. JSON is emitted in a
 * canonical (single-line, key-order-fixed) form so it diffs cleanly against a
 * Python json.dumps(...) on the pypdfbox side.
 */
public final class OutlineTreeProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDDocumentOutline outline = catalog.getDocumentOutline();
            StringBuilder sb = new StringBuilder();
            if (outline == null) {
                sb.append("null");
            } else {
                emitRoot(doc, outline, sb);
            }
            out.print(sb);
        }
    }

    private static void emitRoot(PDDocument doc, PDDocumentOutline outline, StringBuilder sb) {
        sb.append('{');
        sb.append("\"open_count\":").append(outline.getOpenCount()).append(',');
        int childCount = countChildren(outline);
        sb.append("\"child_count\":").append(childCount).append(',');
        sb.append("\"children\":");
        emitChildren(doc, outline, sb);
        sb.append('}');
    }

    private static void emitItem(PDDocument doc, PDOutlineItem item, StringBuilder sb) {
        sb.append('{');
        sb.append("\"title\":").append(jsonStringOrNull(item.getTitle())).append(',');
        sb.append("\"count\":").append(rawCount(item)).append(',');
        sb.append("\"is_open\":").append(item.isNodeOpen() ? "true" : "false").append(',');
        sb.append("\"dest\":").append(resolvePageIndex(doc, item)).append(',');
        int childCount = countChildren(item);
        sb.append("\"child_count\":").append(childCount).append(',');
        sb.append("\"children\":");
        emitChildren(doc, item, sb);
        sb.append('}');
    }

    private static void emitChildren(PDDocument doc, PDOutlineNode node, StringBuilder sb) {
        sb.append('[');
        boolean first = true;
        for (PDOutlineItem child : node.children()) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            emitItem(doc, child, sb);
        }
        sb.append(']');
    }

    private static int countChildren(PDOutlineNode node) {
        int n = 0;
        for (PDOutlineItem child : node.children()) {
            n++;
            // Reference child to silence unused-warnings on strict javac configs.
            if (child == null) {
                break;
            }
        }
        return n;
    }

    /** Raw /Count integer as a JSON token: a signed decimal, or "null" when absent. */
    private static String rawCount(PDOutlineItem item) {
        org.apache.pdfbox.cos.COSBase c =
                item.getCOSObject().getDictionaryObject(org.apache.pdfbox.cos.COSName.COUNT);
        if (!(c instanceof org.apache.pdfbox.cos.COSNumber)) {
            return "null";
        }
        return Integer.toString(((org.apache.pdfbox.cos.COSNumber) c).intValue());
    }

    /**
     * Resolve an item's /Dest, or its /A GoTo action's destination, to a
     * 0-based page index. Named destinations are chased through the catalog
     * (the /Names/Dests name tree, then the legacy /Dests dictionary).
     * Returns -1 when no page target resolves.
     */
    private static int resolvePageIndex(PDDocument doc, PDOutlineItem item) {
        try {
            PDDestination dest = item.getDestination();
            if (dest == null) {
                PDAction action = item.getAction();
                if (action instanceof PDActionGoTo) {
                    dest = ((PDActionGoTo) action).getDestination();
                }
            }
            if (dest == null) {
                return -1;
            }
            PDPageDestination pageDest;
            if (dest instanceof PDNamedDestination) {
                pageDest = doc.getDocumentCatalog()
                        .findNamedDestinationPage((PDNamedDestination) dest);
            } else if (dest instanceof PDPageDestination) {
                pageDest = (PDPageDestination) dest;
            } else {
                return -1;
            }
            if (pageDest == null) {
                return -1;
            }
            PDPage page = pageDest.getPage();
            if (page != null) {
                int idx = doc.getPages().indexOf(page);
                if (idx >= 0) {
                    return idx;
                }
            }
            return pageDest.getPageNumber();
        } catch (Exception e) {
            return -1;
        }
    }

    /** Render a Java String as a canonical JSON string literal, or the bare token "null". */
    private static String jsonStringOrNull(String s) {
        if (s == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder(s.length() + 2);
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            switch (ch) {
                case '\\':
                    sb.append("\\\\");
                    break;
                case '"':
                    sb.append("\\\"");
                    break;
                case '\b':
                    sb.append("\\b");
                    break;
                case '\f':
                    sb.append("\\f");
                    break;
                case '\n':
                    sb.append("\\n");
                    break;
                case '\r':
                    sb.append("\\r");
                    break;
                case '\t':
                    sb.append("\\t");
                    break;
                default:
                    if (ch < 0x20) {
                        sb.append(String.format("\\u%04x", (int) ch));
                    } else {
                        sb.append(ch);
                    }
            }
        }
        sb.append('"');
        return sb.toString();
    }
}
