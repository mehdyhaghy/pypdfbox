import java.awt.geom.Rectangle2D;
import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.text.PDFTextStripperByArea;

/**
 * Live oracle probe for PDFTextStripperByArea with MULTIPLE named regions on a
 * single page — covering disjoint regions (each captures its own glyphs) and
 * OVERLAPPING regions (a glyph in the shared zone must land in BOTH regions'
 * output). Upstream's processTextPosition iterates every entry of regionArea
 * and adds the position to each region whose Rectangle2D contains the origin,
 * so a single glyph can be binned into several regions at once.
 *
 * Usage:
 *   java ... TextMultiRegionProbe input.pdf [--no-suppress] name1 x1 y1 w1 h1 \
 *        [name2 x2 y2 w2 h2 ...]
 *
 * When the optional first flag is --no-suppress the probe disables
 * setSuppressDuplicateOverlappingText so an overlap glyph lands in EVERY
 * matching region (the shared page-wide dedup is off). Without the flag the
 * upstream default (suppression ON) applies.
 *
 * Each rect is an AWT Rectangle2D (top-left origin, y-down), matching the AWT
 * convention the upstream API takes directly.
 *
 * Output (UTF-8, one line per region, in the order the regions were added):
 *   &lt;name&gt;\t&lt;escaped-text&gt;
 * Newlines/carriage-returns/backslashes in the text are escaped so each
 * region's payload stays on one line; the Python side reverses the escape.
 */
public final class TextMultiRegionProbe {
    private static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r");
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripperByArea stripper = new PDFTextStripperByArea();
            stripper.setSortByPosition(true);
            int start = 1;
            if (args.length > 1 && "--no-suppress".equals(args[1])) {
                stripper.setSuppressDuplicateOverlappingText(false);
                start = 2;
            }
            for (int i = start; i + 4 < args.length; i += 5) {
                String name = args[i];
                double x = Double.parseDouble(args[i + 1]);
                double y = Double.parseDouble(args[i + 2]);
                double w = Double.parseDouble(args[i + 3]);
                double h = Double.parseDouble(args[i + 4]);
                stripper.addRegion(name, new Rectangle2D.Double(x, y, w, h));
            }
            PDPage page = doc.getPage(0);
            stripper.extractRegions(page);
            List<String> regions = stripper.getRegions();
            for (String name : regions) {
                out.print(name + "\t" + esc(stripper.getTextForRegion(name)) + "\n");
            }
        }
    }
}
