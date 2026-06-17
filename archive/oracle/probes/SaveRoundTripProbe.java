import java.io.File;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe: load args[0], full-save it to args[1] via PDFBox.
 * Usage: java -cp <pdfbox-app.jar>:<build> SaveRoundTripProbe in.pdf out.pdf
 * Produces Java PDFBox's re-saved bytes so a parity test can compare its
 * structure (page count, catalog keys, xref style, object count) against
 * pypdfbox's full save of the same input. No stdout framing.
 */
public final class SaveRoundTripProbe {
    public static void main(String[] args) throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            doc.save(new File(args[1]));
        }
    }
}
