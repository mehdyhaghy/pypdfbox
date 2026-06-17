import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: emit Apache PDFBox's resolved boundary boxes and
 * {@code /UserUnit} for every page, focused on two facets the page-box
 * accessor parity hinges on (PDF 32000-1 §14.11.2 + §10.10.3):
 *
 *   1. The DEFAULT-PRECEDENCE + CLIP chain. CropBox defaults to MediaBox;
 *      Art/Trim/Bleed each default to the resolved CropBox; an explicit box
 *      that overflows the MediaBox is clipped (lower-left snaps up,
 *      upper-right snaps down) via upstream's private clipToMediaBox.
 *   2. {@code getUserUnit()} — default 1.0, and the upstream clamp where a
 *      non-positive stored value is treated as absent and reported as 1.0.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PageUserUnitBoxProbe input.pdf
 * Output (UTF-8, to stdout), one line per page index i:
 *   "page <i> media <4f> crop <4f> bleed <4f> trim <4f> art <4f> unit <f>"
 *
 * Floats are rendered canonically (see fmt) so the Python side compares the
 * resolved coordinates exactly. Locale.ROOT keeps '.' as the separator.
 */
public final class PageUserUnitBoxProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int count = doc.getNumberOfPages();
            for (int i = 0; i < count; i++) {
                PDPage page = doc.getPage(i);
                StringBuilder sb = new StringBuilder();
                sb.append("page ").append(i)
                  .append(" media ").append(box(page.getMediaBox()))
                  .append(" crop ").append(box(page.getCropBox()))
                  .append(" bleed ").append(box(page.getBleedBox()))
                  .append(" trim ").append(box(page.getTrimBox()))
                  .append(" art ").append(box(page.getArtBox()))
                  .append(" unit ").append(fmt(page.getUserUnit()));
                out.println(sb.toString());
            }
        }
    }

    private static String box(PDRectangle r) {
        return fmt(r.getLowerLeftX()) + " " + fmt(r.getLowerLeftY()) + " "
             + fmt(r.getUpperRightX()) + " " + fmt(r.getUpperRightY());
    }

    /**
     * Canonical float rendering: integral values without a trailing ".0",
     * non-integral values with up to 4 decimals, trailing zeros stripped.
     * Locale.ROOT so the decimal separator is always '.'.
     */
    private static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Long.toString((long) v);
        }
        String s = String.format(Locale.ROOT, "%.4f", v);
        int end = s.length();
        while (end > 0 && s.charAt(end - 1) == '0') {
            end--;
        }
        if (end > 0 && s.charAt(end - 1) == '.') {
            end--;
        }
        return s.substring(0, end);
    }
}
