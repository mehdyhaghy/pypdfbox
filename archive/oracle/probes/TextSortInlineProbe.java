import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for PDFTextStripper.setSortByPosition over glyphs that are
 * painted OUT of left-to-right order WITHIN a single visual line.
 *
 * The companion PDF (built by pypdfbox) draws two words sharing one baseline:
 * the right-hand word's Tj is emitted BEFORE the left-hand word's, so
 * content-stream order is the reverse of visual reading order. With
 * setSortByPosition(true) the stripper must re-order them left-to-right; with
 * (false) it keeps stream order.
 *
 * Usage: java -cp ... TextSortInlineProbe &lt;pdf&gt;
 *
 * Output (UTF-8), newlines inside payloads escaped as "\n" so each marker
 * stays on one line; the Python side reverses the escape:
 *   SORTED:&lt;text&gt;
 *   UNSORTED:&lt;text&gt;
 */
public final class TextSortInlineProbe {
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
