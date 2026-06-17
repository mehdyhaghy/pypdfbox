import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.common.PDPageLabels;

/**
 * Live oracle probe: emit Apache PDFBox's per-page label STRINGS for a PDF,
 * focused on the number-rendering boundary forms.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PageLabelFormatProbe input.pdf
 *
 * Same canonical, line-oriented UTF-8 contract as {@code PageLabelProbe}:
 *
 *   count=<n>
 *   <index>\t<label>      (one line per page index, label may be empty)
 *
 * This probe is paired with a test that builds a /PageLabels number tree whose
 * ranges use large /St start values chosen to hit the high-value formatting
 * boundaries that {@code PageLabelProbe}'s small ranges do not exercise:
 *
 *   * roman subtractive forms 8->viii, 40->xl, 90->xc, 400->cd, 900->cm
 *   * the >=4000 "m-per-thousand" Acrobat quirk (4000 -> mmmm, 4999 -> mmmmcmxcix)
 *   * alphabetic doubling / tripling 26->z, 27->aa, 52->zz, 53->aaa
 *
 * The point is to pin pypdfbox's LabelGenerator number rendering against
 * Apache PDFBox 3.0.7 string-for-string at exactly these edges.
 */
public final class PageLabelFormatProbe {

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
