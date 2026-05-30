import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the ExtractText CLI's page-range + sort surface.
 *
 * Mirrors the body of org.apache.pdfbox.tools.ExtractText.extractPages /
 * ExtractText.call: set sort-by-position, set the start page, clamp the end
 * page to the document page count (Math.min(endPage, getNumberOfPages())),
 * set the end page, then write PDFTextStripper.getText. This is exactly the
 * sequence the CLI runs after parsing -startPage / -endPage / -sort.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> \
 *            ExtractTextRangeProbe input.pdf startPage endPage sort
 *   startPage, endPage : 1-based ints (endPage may exceed page count)
 *   sort               : "true" | "false"
 * Output: the extracted text, UTF-8, to stdout (no extra framing).
 */
public final class ExtractTextRangeProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File file = new File(args[0]);
        int startPage = Integer.parseInt(args[1]);
        int endPage = Integer.parseInt(args[2]);
        boolean sort = Boolean.parseBoolean(args[3]);
        try (PDDocument doc = Loader.loadPDF(file)) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(sort);
            stripper.setStartPage(startPage);
            // Upstream ExtractText clamps the end page to the page count.
            stripper.setEndPage(Math.min(endPage, doc.getNumberOfPages()));
            out.print(stripper.getText(doc));
        }
    }
}
