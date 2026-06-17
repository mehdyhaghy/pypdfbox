import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.multipdf.PDFMergerUtility;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: merge N input PDFs into one via PDFBox's
 * {@link PDFMergerUtility#mergeDocuments}, save to an output file, then reload
 * the merged result and emit a deterministic fingerprint of it so the pypdfbox
 * side can be compared against PDFBox's actual merge behaviour.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> MergeProbe out.pdf in1.pdf in2.pdf ...
 *
 * Args:
 *   args[0]      = output path the merged document is written to.
 *   args[1..n-1] = the input PDFs to merge, in order.
 *
 * Output (UTF-8, LF-terminated lines):
 *   pages <totalPageCount>
 *   page <i> <widthHexBits> <heightHexBits>      (one line per merged page,
 *                                                  0-based index i)
 *
 * Page dimensions are emitted as the IEEE-754 single-precision bit pattern in
 * hex (matching CosDumpProbe's fmtFloat) so the comparison is repr-independent
 * but still catches a real geometry divergence.
 */
public final class MergeProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File output = new File(args[0]);

        PDFMergerUtility merger = new PDFMergerUtility();
        for (int i = 1; i < args.length; i++) {
            merger.addSource(new File(args[i]));
        }
        merger.setDestinationFileName(output.getAbsolutePath());
        merger.mergeDocuments(null);

        // Reload the just-written merged document and fingerprint it.
        try (PDDocument merged = Loader.loadPDF(output)) {
            int total = merged.getNumberOfPages();
            StringBuilder sb = new StringBuilder();
            sb.append("pages ").append(total).append('\n');
            for (int i = 0; i < total; i++) {
                PDPage page = merged.getPage(i);
                PDRectangle box = page.getMediaBox();
                sb.append("page ").append(i).append(' ')
                        .append(fmtFloat(box.getWidth())).append(' ')
                        .append(fmtFloat(box.getHeight())).append('\n');
            }
            out.print(sb);
        }
    }

    private static String fmtFloat(float f) {
        return Integer.toHexString(Float.floatToIntBits(f));
    }
}
