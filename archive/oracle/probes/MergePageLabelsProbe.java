import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.multipdf.PDFMergerUtility;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.common.PDPageLabels;

/**
 * Live oracle probe: merge N source PDFs that each carry a {@code /PageLabels}
 * number tree via Apache PDFBox's {@link PDFMergerUtility#mergeDocuments}, save
 * and reload the result, then emit the MERGED page-label list (one label per
 * page, in page order). This pins {@code PDFMergerUtility}'s page-label merge:
 * the second source's range keys must be re-based by the running destination
 * page count so the concatenated label sequence is correct.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> MergePageLabelsProbe out.pdf in1.pdf in2.pdf ...
 *
 * Args:
 *   args[0]      = output path the merged document is written to.
 *   args[1..n-1] = the source PDFs to merge, in order.
 *
 * Output (UTF-8, LF-terminated lines):
 *   pages <totalPageCount>
 *   label <i> <escapedLabel>     (one line per merged page, 0-based index i;
 *                                  the computed page label, escaped so it stays
 *                                  one line: \\, \n, \r, \t)
 *
 * If the merged catalog has no /PageLabels the probe emits an empty label for
 * every page (the same fallback the python side uses), so a "labels dropped"
 * regression still diverges from a document that carried them.
 */
public final class MergePageLabelsProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File output = new File(args[0]);

        PDFMergerUtility merger = new PDFMergerUtility();
        for (int i = 1; i < args.length; i++) {
            merger.addSource(new File(args[i]));
        }
        merger.setDestinationFileName(output.getAbsolutePath());
        merger.mergeDocuments(null);

        try (PDDocument merged = Loader.loadPDF(output)) {
            int total = merged.getNumberOfPages();
            StringBuilder sb = new StringBuilder();
            sb.append("pages ").append(total).append('\n');

            PDDocumentCatalog catalog = merged.getDocumentCatalog();
            PDPageLabels labels = catalog.getPageLabels();
            String[] computed = new String[total];
            String[] arr = labels == null ? null : labels.getLabelsByPageIndices();
            for (int i = 0; i < total; i++) {
                computed[i] = (arr != null && i < arr.length && arr[i] != null)
                        ? arr[i]
                        : "";
            }
            for (int i = 0; i < total; i++) {
                sb.append("label ").append(i).append(' ')
                        .append(esc(computed[i])).append('\n');
            }
            out.print(sb);
        }
    }

    private static String esc(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
