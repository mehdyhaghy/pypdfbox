import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineNode;

/**
 * Live oracle probe: emit a FLAT pre-order traversal of a PDF's document
 * outline (bookmarks), one JSON object per visited node, capturing the
 * linked-list navigation surface that {@code OutlineTreeProbe} does not:
 *
 *   - first/last child title (the /First and /Last pointer targets),
 *   - next/previous sibling title (the /Next and /Prev pointer targets),
 *   - hasChildren(),
 *   - isNodeOpen() and the signed getOpenCount(),
 *   - findDestinationPage(doc) resolved to a 0-based page index.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OutlineTraversalProbe input.pdf
 *
 * Output: a single canonical (single-line, key-order-fixed, no-whitespace)
 * JSON array on stdout (UTF-8, no trailing newline). Each element is:
 *
 *   {
 *     "depth": <int>,                 // 0 == immediate child of the root
 *     "title": <string>|null,
 *     "has_children": <bool>,
 *     "is_open": <bool>,              // isNodeOpen()
 *     "open_count": <signed int>,     // getOpenCount()
 *     "first_child": <string>|null,   // getFirstChild().getTitle()
 *     "last_child": <string>|null,    // getLastChild().getTitle()
 *     "next": <string>|null,          // getNextSibling().getTitle()
 *     "prev": <string>|null,          // getPreviousSibling().getTitle()
 *     "find_dest": <int>              // findDestinationPage page index, -1 unresolved
 *   }
 *
 * Pre-order means: for each node we visit it, then recurse into its children
 * (via getFirstChild() -> getNextSibling()) before moving to the next sibling.
 * The traversal therefore exercises both the child pointers and the sibling
 * chain. An empty array is emitted when the outline is absent or childless.
 */
public final class OutlineTraversalProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        sb.append('[');
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDDocumentOutline outline = catalog.getDocumentOutline();
            if (outline != null) {
                State st = new State();
                visitChildren(doc, outline, 0, sb, st);
            }
        }
        sb.append(']');
        out.print(sb);
    }

    private static final class State {
        boolean first = true;
    }

    private static void visitChildren(
            PDDocument doc, PDOutlineNode node, int depth, StringBuilder sb, State st) {
        for (PDOutlineItem child : node.children()) {
            emit(doc, child, depth, sb, st);
            visitChildren(doc, child, depth + 1, sb, st);
        }
    }

    private static void emit(
            PDDocument doc, PDOutlineItem item, int depth, StringBuilder sb, State st) {
        if (!st.first) {
            sb.append(',');
        }
        st.first = false;
        sb.append('{');
        sb.append("\"depth\":").append(depth).append(',');
        sb.append("\"title\":").append(jsonStringOrNull(item.getTitle())).append(',');
        sb.append("\"has_children\":").append(item.hasChildren() ? "true" : "false").append(',');
        sb.append("\"is_open\":").append(item.isNodeOpen() ? "true" : "false").append(',');
        sb.append("\"open_count\":").append(item.getOpenCount()).append(',');
        sb.append("\"first_child\":").append(titleOf(item.getFirstChild())).append(',');
        sb.append("\"last_child\":").append(titleOf(item.getLastChild())).append(',');
        sb.append("\"next\":").append(titleOf(item.getNextSibling())).append(',');
        sb.append("\"prev\":").append(titleOf(item.getPreviousSibling())).append(',');
        sb.append("\"find_dest\":").append(findDest(doc, item));
        sb.append('}');
    }

    private static String titleOf(PDOutlineItem item) {
        if (item == null) {
            return "null";
        }
        return jsonStringOrNull(item.getTitle());
    }

    private static int findDest(PDDocument doc, PDOutlineItem item) {
        try {
            PDPage page = item.findDestinationPage(doc);
            if (page == null) {
                return -1;
            }
            int idx = doc.getPages().indexOf(page);
            return idx;
        } catch (Exception e) {
            return -1;
        }
    }

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
