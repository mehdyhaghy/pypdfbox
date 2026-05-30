import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.common.PDPageLabels;

/**
 * Live oracle probe: emit the computed page-label string for every physical
 * page of a PDF, exercising the catalog {@code /PageLabels} number tree.
 *
 * Apache PDFBox computes the per-page label via
 * {@code PDPageLabels.getLabelsByPageIndices()} which returns a
 * {@code String[]} indexed by 0-based physical page. We dump one line per
 * page as {@code <pageIndex>\t<label>} so pypdfbox can compare byte-for-byte.
 *
 * This pins the multi-range number-tree walk plus every numbering style:
 *   /S D  (decimal), /S R / r (upper/lower Roman),
 *   /S A / a (upper/lower letters with A..Z, AA..ZZ wraparound),
 *   a /P prefix and a /St start offset.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PageLabelsProbe input.pdf
 *
 * Output: UTF-8, one "<index>\t<label>\n" line per page, no trailing extra.
 * When /PageLabels is absent we emit nothing (matches "null labels").
 */
public final class PageLabelsProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDPageLabels labels = catalog.getPageLabels();
            if (labels != null) {
                String[] arr = labels.getLabelsByPageIndices();
                for (int i = 0; i < arr.length; i++) {
                    String label = arr[i];
                    sb.append(i).append('\t');
                    sb.append(label == null ? "" : label);
                    sb.append('\n');
                }
            }
        }
        out.print(sb);
    }
}
