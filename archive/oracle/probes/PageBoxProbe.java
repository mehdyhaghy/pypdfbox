import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: emit Apache PDFBox's fully-resolved page boundary boxes.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PageBoxProbe input.pdf
 * Output (UTF-8, to stdout):
 *   line 1: "pages <count>"
 *   then one line per page index i:
 *     "page <i> media <4f> crop <4f> bleed <4f> trim <4f> art <4f> unit <f>"
 *
 * Every box is read through the public PDPage accessors, so each line
 * exercises upstream's default + clip + inheritable-attribute logic exactly:
 *   - getMediaBox()  walks the /Parent chain; US Letter when absent.
 *   - getCropBox()   /CropBox (inheritable) clipped to MediaBox, else MediaBox.
 *   - getBleedBox()  /BleedBox (own) clipped to MediaBox, else CropBox.
 *   - getTrimBox()   /TrimBox  (own) clipped to MediaBox, else CropBox.
 *   - getArtBox()    /ArtBox   (own) clipped to MediaBox, else CropBox.
 *   - getUserUnit()  /UserUnit, default 1.0, non-positive -> 1.0.
 *
 * Floats are rendered canonically (see fmt) so the Python side can compare
 * the resolved coordinates exactly. Locale.ROOT keeps '.' as the separator.
 */
public final class PageBoxProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int count = doc.getNumberOfPages();
            out.println("pages " + count);
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
     * Canonical float rendering: print integral values without a trailing
     * ".0" and non-integral values with up to 4 decimals, trailing zeros
     * stripped. Locale.ROOT so the decimal separator is always '.'.
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
