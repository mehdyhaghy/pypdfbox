import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;

/**
 * Live oracle probe: emit Apache PDFBox's normalised /Rotate value for every
 * page of an input PDF whose pages deliberately carry malformed or out-of-spec
 * /Rotate integers (negative angles, values >= 360, non-multiples-of-90, etc.).
 *
 * Per PDF 32000-1 §14.8.4, /Rotate must be a multiple of 90 in {0, 90, 180,
 * 270}. PDFBox 3.0.7's PDPage.getRotation() normalises a COSNumber whose
 * intValue() is a multiple of 90 via ((v % 360) + 360) % 360, and returns 0
 * for anything else (non-COSNumber, or value % 90 != 0).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> RotateNormProbe input.pdf
 *
 * Output (UTF-8, to stdout):
 *   line 1: "count <getNumberOfPages>"
 *   then one line per page index i (document traversal order):
 *     "page <i> rotate <int>"
 */
public final class RotateNormProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int count = doc.getNumberOfPages();
            out.println("count " + count);
            int i = 0;
            for (PDPage page : doc.getPages()) {
                out.println("page " + i + " rotate " + page.getRotation());
                i++;
            }
        }
    }
}
