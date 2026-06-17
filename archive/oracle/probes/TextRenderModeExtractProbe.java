import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: text extraction is independent of the text rendering
 * mode (<code>Tr</code>).
 *
 * PDF 32000-1 &sect;9.3.6 defines eight text rendering modes. Mode 3 paints
 * <em>nothing</em> (invisible text — the classic OCR-layer / searchable-image
 * technique: a scanned page image is drawn, and an invisible Mode-3 text layer
 * is overlaid so the text is selectable/searchable but never visibly painted).
 * Mode 7 adds the glyph outlines to the clipping path and paints nothing
 * either. Apache PDFBox's <code>PDFTextStripper</code> extracts text purely
 * from the content stream's show-text operators and the active font's
 * code-to-Unicode mapping; it never consults the rendering mode. So Mode-3 and
 * Mode-7 text MUST still appear in <code>getText()</code> output exactly as
 * visible (Mode-0) text does. A stripper that dropped invisible text would
 * silently lose the entire OCR layer of every scanned PDF.
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; TextRenderModeExtractProbe input.pdf
 *
 * Output (UTF-8, stdout): the full PDFTextStripper.getText() string, framed:
 *
 *   &lt;&lt;&lt;TEXT
 *   ...extracted text...
 *   TEXT&gt;&gt;&gt;
 */
public final class TextRenderModeExtractProbe {
    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            out.print("<<<TEXT\n");
            out.print(stripper.getText(doc));
            out.print("TEXT>>>\n");
        }
    }
}
