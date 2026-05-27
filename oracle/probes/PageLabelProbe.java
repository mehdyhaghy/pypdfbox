import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.common.PDPageLabels;

/**
 * Live oracle probe: emit Apache PDFBox's per-page label strings for a PDF.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PageLabelProbe input.pdf
 *
 * Loads the PDF, fetches the catalog's /PageLabels number tree via
 * getDocumentCatalog().getPageLabels(), and renders every page label with
 * getLabelsByPageIndices(). Emits canonical, line-oriented UTF-8 stdout:
 *
 *   count=<n>
 *   <index>\t<label>      (one line per page index, label may be empty)
 *
 * A missing /PageLabels renders as "count=0" with no label lines. This
 * mirrors what pypdfbox's get_page_labels().get_labels_by_page_indices()
 * produces so the differential test can compare string-for-string.
 */
public final class PageLabelProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPageLabels labels = doc.getDocumentCatalog().getPageLabels();
            if (labels == null) {
                out.println("count=0");
                return;
            }
            String[] arr = labels.getLabelsByPageIndices();
            out.println("count=" + arr.length);
            for (int i = 0; i < arr.length; i++) {
                String label = arr[i] == null ? "" : arr[i];
                out.println(i + "\t" + label);
            }
        }
    }
}
