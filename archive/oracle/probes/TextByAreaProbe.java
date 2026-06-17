import java.awt.geom.Rectangle2D;
import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.text.PDFTextStripperByArea;

/**
 * Live oracle probe for PDFTextStripperByArea focused on facets the existing
 * area probes (TextAreaProbe / TextSortAreaProbe / TextMultiRegionProbe) do NOT
 * exercise, using only clearly DISJOINT (non-overlapping) regions:
 *
 *   mode "split":
 *       Two disjoint rectangles over a SINGLE show_text run that physically
 *       crosses the boundary between them, so each glyph is binned by its own
 *       origin (per-glyph clipping inside one text-showing operation, not one
 *       region-per-word). Emits both regions' text.
 *
 *   mode "remove":
 *       addRegion("keep", ...) + addRegion("drop", ...), then
 *       removeRegion("drop"), then extractRegions. Confirms getRegions() no
 *       longer lists "drop" and getTextForRegion("drop") is "" (a removed
 *       region was never extracted, so its writer was never created), while
 *       "keep" still captures its glyph.
 *
 * Each rect is an AWT Rectangle2D (top-left origin, y-down), matching the AWT
 * convention the upstream API takes directly.
 *
 * Usage:
 *   java ... TextByAreaProbe split  input.pdf nameA xA yA wA hA nameB xB yB wB hB
 *   java ... TextByAreaProbe remove input.pdf keep xK yK wK hK drop xD yD wD hD
 *
 * Output (UTF-8, one line per surviving region, in addition order):
 *   &lt;name&gt;\t&lt;escaped-text&gt;
 * Newlines / carriage returns / backslashes are escaped so each region's
 * payload stays on one line; the Python side reverses the escape.
 */
public final class TextByAreaProbe {
    private static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r");
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        String file = args[1];
        try (PDDocument doc = Loader.loadPDF(new File(file))) {
            PDFTextStripperByArea stripper = new PDFTextStripperByArea();
            stripper.setSortByPosition(true);

            if ("regions".equals(mode)) {
                // Generic mode: any number of (name x y w h) 5-tuples follow the
                // file arg. Used by the rotated-page parity test which pins all
                // four /Rotate values against AWT-frame region rectangles.
                for (int i = 2; i + 4 < args.length; i += 5) {
                    stripper.addRegion(args[i], rect(args, i + 1));
                }
            } else {
                String nameA = args[2];
                stripper.addRegion(nameA, rect(args, 3));
                String nameB = args[7];
                stripper.addRegion(nameB, rect(args, 8));

                if ("remove".equals(mode)) {
                    stripper.removeRegion(nameB);
                }
            }

            PDPage page = doc.getPage(0);
            stripper.extractRegions(page);

            List<String> regions = stripper.getRegions();
            for (String name : regions) {
                out.print(name + "\t" + esc(stripper.getTextForRegion(name)) + "\n");
            }
        }
    }

    private static Rectangle2D rect(String[] a, int i) {
        return new Rectangle2D.Double(
                Double.parseDouble(a[i]),
                Double.parseDouble(a[i + 1]),
                Double.parseDouble(a[i + 2]),
                Double.parseDouble(a[i + 3]));
    }
}
