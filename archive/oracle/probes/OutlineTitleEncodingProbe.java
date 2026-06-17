import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineNode;

/**
 * Live oracle probe: emit a CANONICAL, deterministic pre-order listing of a
 * PDF outline's TITLE-ENCODING characteristics, as Apache PDFBox parses them.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OutlineTitleEncodingProbe input.pdf
 *
 * Output (UTF-8, LF-terminated lines): one line per outline item in a stable
 * depth-first pre-order walk (children visited in /First -> /Next chain order).
 * Each line is:
 *
 *   <depth>\t<titleEscaped>\t<rawHex>
 *
 * Where:
 *   - depth        = 0-based nesting depth (top-level items are depth 0)
 *   - titleEscaped = getTitle() with backslash/newline/CR/tab escaped, and
 *                    any non-ASCII codepoint emitted as "\\uXXXX" (BMP) or
 *                    "\\UXXXXXXXX" (non-BMP) so the line stays pure ASCII
 *                    and survives any platform default encoding round-trip;
 *                    the literal token "null" is emitted when /Title is
 *                    absent and the literal token "empty" when present but
 *                    decoded to the empty string.
 *   - rawHex       = uppercase hex of the raw /Title COSString bytes
 *                    (cosString.getBytes()); the literal "absent" when the
 *                    /Title key is missing, and the literal "wrong-type"
 *                    when /Title is present but not a COSString.
 *
 * When the document has no outline (or an empty one) the output is empty.
 */
public final class OutlineTitleEncodingProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDDocumentOutline outline = catalog.getDocumentOutline();
            StringBuilder sb = new StringBuilder();
            if (outline != null) {
                walk(outline, 0, sb);
            }
            out.print(sb);
        }
    }

    private static void walk(PDOutlineNode node, int depth, StringBuilder sb) {
        for (PDOutlineItem item : node.children()) {
            sb.append(depth).append('\t')
              .append(escapeTitle(item.getTitle())).append('\t')
              .append(rawHex(item)).append('\n');
            walk(item, depth + 1, sb);
        }
    }

    private static String rawHex(PDOutlineItem item) {
        COSBase v = item.getCOSObject().getDictionaryObject(COSName.TITLE);
        if (v == null) {
            return "absent";
        }
        if (!(v instanceof COSString)) {
            return "wrong-type";
        }
        byte[] raw = ((COSString) v).getBytes();
        StringBuilder hex = new StringBuilder(raw.length * 2);
        for (byte b : raw) {
            hex.append(String.format("%02X", b & 0xFF));
        }
        return hex.toString();
    }

    private static String escapeTitle(String s) {
        if (s == null) {
            return "null";
        }
        if (s.isEmpty()) {
            return "empty";
        }
        StringBuilder out = new StringBuilder(s.length());
        int i = 0;
        while (i < s.length()) {
            int cp = s.codePointAt(i);
            if (cp == '\\') {
                out.append("\\\\");
            } else if (cp == '\n') {
                out.append("\\n");
            } else if (cp == '\r') {
                out.append("\\r");
            } else if (cp == '\t') {
                out.append("\\t");
            } else if (cp >= 0x20 && cp < 0x7F) {
                out.append((char) cp);
            } else if (cp <= 0xFFFF) {
                out.append(String.format("\\u%04X", cp));
            } else {
                out.append(String.format("\\U%08X", cp));
            }
            i += Character.charCount(cp);
        }
        return out.toString();
    }
}
