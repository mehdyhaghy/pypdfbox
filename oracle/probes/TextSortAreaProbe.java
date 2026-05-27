import java.awt.geom.Rectangle2D;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.text.PDFTextStripperByArea;

/**
 * Live oracle probe for PDFTextStripper sort-by-position + page-range and
 * PDFTextStripperByArea region extraction.
 *
 * Two sub-commands, selected by args[0]:
 *
 *   sort &lt;pdf&gt;
 *     Runs PDFTextStripper twice on the whole document — once with
 *     setSortByPosition(true), once with (false) — and prints both,
 *     each prefixed by a stable marker so the Python side can split:
 *       SORTED:&lt;text&gt;
 *       UNSORTED:&lt;text&gt;
 *     Newlines inside the extracted text are escaped as "\n" so each
 *     payload stays on one line; the Python side reverses the escape.
 *
 *   range &lt;pdf&gt; &lt;startPage&gt; &lt;endPage&gt;
 *     Runs PDFTextStripper with setStartPage / setEndPage (1-based,
 *     inclusive) and setSortByPosition(true); prints the escaped text
 *     prefixed "RANGE:".
 *
 *   area &lt;pdf&gt; &lt;x&gt; &lt;y&gt; &lt;w&gt; &lt;h&gt;
 *     Runs PDFTextStripperByArea with one region (the AWT Rectangle2D
 *     uses a top-left origin, y-down) and setSortByPosition(true); prints
 *     getTextForRegion escaped, prefixed "AREA:".
 *
 * All output is UTF-8. No extra framing beyond the prefix + escaped text.
 */
public final class TextSortAreaProbe {
    private static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r");
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        try (PDDocument doc = Loader.loadPDF(new File(args[1]))) {
            if ("sort".equals(mode)) {
                PDFTextStripper sorted = new PDFTextStripper();
                sorted.setSortByPosition(true);
                out.print("SORTED:" + esc(sorted.getText(doc)) + "\n");
                PDFTextStripper unsorted = new PDFTextStripper();
                unsorted.setSortByPosition(false);
                out.print("UNSORTED:" + esc(unsorted.getText(doc)) + "\n");
            } else if ("range".equals(mode)) {
                int start = Integer.parseInt(args[2]);
                int end = Integer.parseInt(args[3]);
                PDFTextStripper s = new PDFTextStripper();
                s.setSortByPosition(true);
                s.setStartPage(start);
                s.setEndPage(end);
                out.print("RANGE:" + esc(s.getText(doc)) + "\n");
            } else if ("area".equals(mode)) {
                double x = Double.parseDouble(args[2]);
                double y = Double.parseDouble(args[3]);
                double w = Double.parseDouble(args[4]);
                double h = Double.parseDouble(args[5]);
                PDFTextStripperByArea s = new PDFTextStripperByArea();
                s.setSortByPosition(true);
                s.addRegion("r", new Rectangle2D.Double(x, y, w, h));
                PDPage page = doc.getPage(0);
                s.extractRegions(page);
                out.print("AREA:" + esc(s.getTextForRegion("r")) + "\n");
            } else {
                throw new IllegalArgumentException("unknown mode: " + mode);
            }
        }
    }
}
