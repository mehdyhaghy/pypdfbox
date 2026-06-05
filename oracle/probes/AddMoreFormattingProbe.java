import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: emit Apache PDFBox's PDFTextStripper output with
 * setAddMoreFormatting(true). This promotes paragraphEnd / pageStart /
 * articleStart / articleEnd to the line separator, so the per-page and
 * per-paragraph newline cadence becomes visible in the extracted text.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> AddMoreFormattingProbe input.pdf
 * Output: the extracted text, UTF-8, to stdout (no extra framing).
 */
public final class AddMoreFormattingProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setAddMoreFormatting(true);
            out.print(stripper.getText(doc));
        }
    }
}
