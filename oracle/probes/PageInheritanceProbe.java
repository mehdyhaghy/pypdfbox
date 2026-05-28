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
 * per page, with sub-resource counts, so the pypdfbox PDPage inheritable-attr
 * walk can be compared field-for-field across the spec's seven cases:
 *
 *   1. /MediaBox set on root /Pages only           -> leaf inherits it.
 *   2. /MediaBox on intermediate node overrides root.
 *   3. /MediaBox absent everywhere                 -> US Letter default.
 *   4. /CropBox inheritance + default to MediaBox.
 *   5. /Rotate inheritance (multiples of 90, normalised).
 *   6. /Resources inheritance through ancestor.
 *   7. Negative: /Resources on a leaf does NOT bleed to a sibling.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PageInheritanceProbe input.pdf
 *
 * Output (UTF-8, to stdout):
 *   line 1: "count <getNumberOfPages>"
 *   then one line per page index i (document /Kids traversal order):
 *     "page <i> media <4f> crop <4f> rotate <int>"
 *     "  font_count <n> xobj_count <n>"
 *
 * Each value is read through public PDPage / PDResources accessors so every
 * line exercises upstream's inheritable-attribute resolution exactly. Sub-
 * resource counts (font_count / xobj_count) make the test sensitive to
 * merge-vs-replace semantics: PDFBox does NOT merge inherited Resources, it
 * returns the first one found walking up. A "merging" implementation would
 * over-report counts; a "stops too early" one would under-report. We
 * deliberately do NOT emit a "res" presence flag — pypdfbox materialises an
 * empty PDResources wrapper when no ancestor has /Resources while upstream
 * returns null, a structural divergence tracked separately (DEFERRED.md).
 * Counts capture the substantive content either way.
 *
 * Floats are rendered canonically (see fmt) so the Python side compares
 * resolved coordinates exactly; Locale.ROOT keeps '.' as the separator.
 */
public final class PageInheritanceProbe {

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
                int fontCount = 0;
                int xobjCount = 0;
                if (res != null) {
                    for (COSName name : res.getFontNames()) {
                        fontCount++;
                    }
                    for (COSName name : res.getXObjectNames()) {
                        xobjCount++;
                    }
                }
                out.println("page " + i
                    + " media " + box(media)
                    + " crop " + box(crop)
                    + " rotate " + rotate
                    + " font_count " + fontCount
                    + " xobj_count " + xobjCount);
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
