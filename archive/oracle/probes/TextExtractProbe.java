import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: emit Apache PDFBox's PDFTextStripper output for a PDF.
 * Usage: java -cp <pdfbox-app.jar>:<build> TextExtractProbe input.pdf
 * Output: the extracted text, UTF-8, to stdout (no extra framing).
 */
public final class TextExtractProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            out.print(new PDFTextStripper().getText(doc));
        }
    }
}
