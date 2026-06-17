import java.io.File;
import java.io.FileOutputStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;

/**
 * Live oracle probe: load args[0], mutate the catalog (flag it dirty),
 * incremental-save (append-only) to args[1] via PDFBox saveIncremental.
 * Usage: java -cp <pdfbox-app.jar>:<build> SaveIncrementalProbe in.pdf out.pdf
 *
 * The output must begin with the original source bytes (append-only) and
 * carry an appended xref with a /Prev back-pointer. A parity test compares
 * that invariant against pypdfbox's save_incremental on the same input.
 */
public final class SaveIncrementalProbe {
    public static void main(String[] args) throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            // Touch a harmless catalog entry so there is at least one dirty
            // object to append; mirrors the pypdfbox test mutation.
            catalog.getCOSObject().setInt(COSName.getPDFName("Version"), 1);
            catalog.getCOSObject().setNeedToBeUpdated(true);
            try (FileOutputStream out = new FileOutputStream(new File(args[1]))) {
                doc.saveIncremental(out);
            }
        }
    }
}
