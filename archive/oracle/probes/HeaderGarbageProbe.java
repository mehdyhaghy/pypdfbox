import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for leading-garbage tolerance before the {@code %PDF-}
 * header.
 *
 * Apache PDFBox's {@code COSParser.parsePDFHeader} scans a bounded window from
 * the start of the file for the {@code %PDF-} marker; the byte offset of the
 * marker becomes the document's "header offset" and every subsequent xref /
 * object byte offset is implicitly relative to it. This probe loads a file
 * whose body is a known-good PDF with N junk bytes prepended (the harness
 * crafts the bytes) and reports whether the load + text strip succeeded, the
 * page count, and the extracted text. The harness sweeps N to find the exact
 * tolerance boundary.
 *
 * Output (UTF-8, LF-terminated):
 *   ok=<true|false>
 *   pages=<n>          (only when ok)
 *   text=<escaped>     (only when ok)
 * or, on any failure:
 *   ok=false
 */
public final class HeaderGarbageProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pages = doc.getNumberOfPages();
            String text = new PDFTextStripper().getText(doc);
            out.print("ok=true\n");
            out.print("pages=" + pages + "\n");
            out.print("text=" + escape(text) + "\n");
        } catch (Throwable t) {
            out.print("ok=false\n");
        }
    }

    private static String escape(String s) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\n') {
                b.append("\\n");
            } else if (c == '\r') {
                b.append("\\r");
            } else if (c == '\\') {
                b.append("\\\\");
            } else {
                b.append(c);
            }
        }
        return b.toString();
    }
}
