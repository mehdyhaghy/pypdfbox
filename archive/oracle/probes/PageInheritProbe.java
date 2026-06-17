import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: emit Apache PDFBox's RESOLVED inheritable page attributes
 * so the pypdfbox PDPage inheritable-attribute walk can be compared
 * field-for-field on a multi-level /Pages tree.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PageInheritProbe input.pdf
 *
 * Output (UTF-8, to stdout):
 *   line 1: "count <getNumberOfPages>"
 *   then one line per page index i (document /Kids traversal order):
 *     "page <i> media <4f> crop <4f> rotate <int> res <0|1> font <0|1> xobj <0|1>"
 *
 * Each field is read through the public PDPage accessors so every line
 * exercises upstream's inheritable-attribute resolution exactly:
 *   - getMediaBox()  walks /Parent up to the nearest ancestor /Pages node
 *                    that defines /MediaBox (US Letter when absent).
 *   - getCropBox()   /CropBox (inheritable) clipped to MediaBox, else the
 *                    effective (possibly inherited) MediaBox.
 *   - getRotation()  /Rotate (inheritable), normalised mod 360.
 *   - getResources() walks /Parent for /Resources; "res 1" when non-null.
 *     "font"/"xobj" are 1 when the resolved resources expose at least one
 *     /Font resp. /XObject name (so inherited /Resources from an intermediate
 *     node is detected).
 *
 * Floats are rendered canonically (see fmt) so the Python side compares the
 * resolved coordinates exactly; Locale.ROOT keeps '.' as the separator.
 */
public final class PageInheritProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int count = doc.getNumberOfPages();
            out.println("count " + count);
            int i = 0;
            for (PDPage page : doc.getPages()) {
                PDRectangle media = page.getMediaBox();
                PDRectangle crop = page.getCropBox();
                int rotate = page.getRotation();
                PDResources res = page.getResources();
                int resFlag = res != null ? 1 : 0;
                int fontFlag = 0;
                int xobjFlag = 0;
                if (res != null) {
                    for (COSName name : res.getFontNames()) {
                        fontFlag = 1;
                        break;
                    }
                    for (COSName name : res.getXObjectNames()) {
                        xobjFlag = 1;
                        break;
                    }
                }
                out.println("page " + i
                    + " media " + box(media)
                    + " crop " + box(crop)
                    + " rotate " + rotate
                    + " res " + resFlag
                    + " font " + fontFlag
                    + " xobj " + xobjFlag);
                i++;
            }
        }
    }

    private static String box(PDRectangle r) {
        return fmt(r.getLowerLeftX()) + " " + fmt(r.getLowerLeftY()) + " "
             + fmt(r.getUpperRightX()) + " " + fmt(r.getUpperRightY());
    }

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
