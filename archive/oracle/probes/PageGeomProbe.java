import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.cos.COSName;

/**
 * Live oracle probe: emit Apache PDFBox's resolved page-tree geometry.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PageGeomProbe input.pdf
 * Output (UTF-8, to stdout), one section then per-page lines:
 *   line 1: "pages <count>"
 *   then one line per page index i:
 *     "page <i> media <llx> <lly> <urx> <ury> crop <llx> <lly> <urx> <ury> "
 *       + "rotate <deg> fonts <n> xobjects <m>"
 *
 * All floats are rendered canonically (see fmt) so the Python side can
 * compare them exactly. MediaBox/CropBox are read through the public
 * accessors so the inheritable-attribute resolution (walking /Parent) is
 * exercised, matching PDPage.getMediaBox()/getCropBox(). Rotation is the
 * normalised getRotation() value. Font / XObject counts come from the
 * resolved PDResources name sets.
 */
public final class PageGeomProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int count = doc.getNumberOfPages();
            out.println("pages " + count);
            for (int i = 0; i < count; i++) {
                PDPage page = doc.getPage(i);
                PDRectangle media = page.getMediaBox();
                PDRectangle crop = page.getCropBox();
                int rotate = page.getRotation();
                int fonts = 0;
                int xobjects = 0;
                PDResources res = page.getResources();
                if (res != null) {
                    for (COSName n : res.getFontNames()) {
                        fonts++;
                    }
                    for (COSName n : res.getXObjectNames()) {
                        xobjects++;
                    }
                }
                StringBuilder sb = new StringBuilder();
                sb.append("page ").append(i)
                  .append(" media ").append(box(media))
                  .append(" crop ").append(box(crop))
                  .append(" rotate ").append(rotate)
                  .append(" fonts ").append(fonts)
                  .append(" xobjects ").append(xobjects);
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
        // Strip trailing zeros (and a dangling dot) from the fixed format.
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
