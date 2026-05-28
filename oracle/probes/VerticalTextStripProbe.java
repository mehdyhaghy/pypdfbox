import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: emit Apache PDFBox's PDFTextStripper output for a PDF that
 * uses a vertical writing-mode (WMode 1) Type0 font (e.g. /Identity-V).
 *
 * PDFTextStripper consults the font's CMap WMode and steps each glyph DOWN the
 * page via the vertical displacement vector, so consecutive glyphs land on
 * successive baselines and the line-break heuristic emits one glyph per line
 * (top-to-bottom within a column, right-to-left across columns). This probe is
 * identical in shape to TextExtractProbe but exists as a named entry point for
 * the vertical-writing-mode reading-order surface.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> VerticalTextStripProbe input.pdf
 * Output: the extracted text, UTF-8, to stdout (no extra framing).
 */
public final class VerticalTextStripProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            out.print(new PDFTextStripper().getText(doc));
        }
    }
}
