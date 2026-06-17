import java.awt.geom.Rectangle2D;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.text.PDFTextStripperByArea;

/**
 * Live oracle probe: emit Apache PDFBox's PDFTextStripperByArea output for a
 * single rectangular region on page 1 of a PDF.
 * Usage: java -cp <jar>:<build> TextAreaProbe input.pdf x y w h
 * Output: the region text, UTF-8, to stdout (no extra framing).
 */
public final class TextAreaProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        double x = Double.parseDouble(args[1]);
        double y = Double.parseDouble(args[2]);
        double w = Double.parseDouble(args[3]);
        double h = Double.parseDouble(args[4]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripperByArea stripper = new PDFTextStripperByArea();
            stripper.setSortByPosition(true);
            stripper.addRegion("r", new Rectangle2D.Double(x, y, w, h));
            PDPage page = doc.getPage(0);
            stripper.extractRegions(page);
            out.print(stripper.getTextForRegion("r"));
        }
    }
}
