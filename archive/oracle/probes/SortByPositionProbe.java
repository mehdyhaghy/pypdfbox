import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for PDFTextStripper.setSortByPosition over content whose
 * show-text operators are emitted OUT of visual reading order.
 *
 * The companion PDF (built by pypdfbox) lays out a TWO-COLUMN page: the
 * right-hand column's lines are emitted in the content stream BEFORE the
 * left-hand column's, and within each column the lines may be drawn
 * bottom-to-top. With setSortByPosition(true) the stripper must reconstruct
 * left-column-top-to-bottom then right-column-top-to-bottom; with (false) it
 * keeps content-stream order.
 *
 * Usage: java -cp ... SortByPositionProbe &lt;pdf&gt;
 *
 * Output (UTF-8), newlines inside payloads escaped as "\n" so each marker
 * stays on one line; the Python side reverses the escape:
 *   SORTED:&lt;text&gt;
 *   UNSORTED:&lt;text&gt;
 */
public final class SortByPositionProbe {
    private static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r");
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripper sorted = new PDFTextStripper();
            sorted.setSortByPosition(true);
            out.print("SORTED:" + esc(sorted.getText(doc)) + "\n");
            PDFTextStripper unsorted = new PDFTextStripper();
            unsorted.setSortByPosition(false);
            out.print("UNSORTED:" + esc(unsorted.getText(doc)) + "\n");
        }
    }
}
