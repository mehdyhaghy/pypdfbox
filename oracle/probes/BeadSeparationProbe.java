import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for PDFTextStripper.setShouldSeparateByBeads over a page
 * that actually carries thread beads (articles).
 *
 * The companion PDF (built by pypdfbox so glyph metrics resolve identically)
 * lays out a TWO-COLUMN page whose /B array declares one bead per column.
 * The show-text operators are emitted RIGHT column first, then LEFT column,
 * so the visual reading order differs from the content-stream order.
 *
 * With setSortByPosition(true):
 *   - setShouldSeparateByBeads(true)  -> text is grouped by article: the
 *     whole left column (top-to-bottom) then the whole right column.
 *   - setShouldSeparateByBeads(false) -> the beads are ignored and the
 *     geometric sort interleaves both columns per shared baseline.
 *
 * Usage: java -cp ... BeadSeparationProbe &lt;pdf&gt;
 *
 * Output (UTF-8), newlines inside payloads escaped as "\n" so each marker
 * stays on one line; the Python side reverses the escape:
 *   BEADS_ON:&lt;text&gt;
 *   BEADS_OFF:&lt;text&gt;
 *   BEADS_ON_AMF:&lt;text&gt;  (beads on + setAddMoreFormatting(true))
 */
public final class BeadSeparationProbe {
    private static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r");
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripper on = new PDFTextStripper();
            on.setSortByPosition(true);
            on.setShouldSeparateByBeads(true);
            out.print("BEADS_ON:" + esc(on.getText(doc)) + "\n");

            PDFTextStripper off = new PDFTextStripper();
            off.setSortByPosition(true);
            off.setShouldSeparateByBeads(false);
            out.print("BEADS_OFF:" + esc(off.getText(doc)) + "\n");

            PDFTextStripper amf = new PDFTextStripper();
            amf.setSortByPosition(true);
            amf.setShouldSeparateByBeads(true);
            amf.setAddMoreFormatting(true);
            out.print("BEADS_ON_AMF:" + esc(amf.getText(doc)) + "\n");
        }
    }
}
