import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for multi-line text extraction on a page whose /Rotate is
 * a right angle. Two modes:
 *
 *   build <out.pdf> <rotate>
 *       Produce a single-page LETTER PDF whose page /Rotate is <rotate>
 *       (0/90/180/270) painting several lines of text in *unrotated*
 *       user-space coordinates: a heading line, two body lines, an indented
 *       paragraph-start line, and a blank-line-separated second paragraph.
 *       The text matrix itself is the identity (no Tm rotation) so the only
 *       rotation is the page /Rotate — exactly the case where upstream's
 *       LegacyPDFStreamEngine folds the page rotation into the CTM and the
 *       TextPositions arrive direction-adjusted.
 *
 *   extract <in.pdf>
 *       Emit Apache PDFBox's PDFTextStripper().getText(doc) for the file,
 *       UTF-8, no framing.
 */
public final class RotatedMultiLineProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("build".equals(mode)) {
            int rotate = Integer.parseInt(args[2]);
            try (PDDocument doc = new PDDocument()) {
                PDPage page = new PDPage(PDRectangle.LETTER);
                page.setRotation(rotate);
                doc.addPage(page);
                PDType1Font font =
                    new PDType1Font(Standard14Fonts.FontName.HELVETICA);
                try (PDPageContentStream cs =
                        new PDPageContentStream(doc, page)) {
                    cs.beginText();
                    cs.setFont(font, 12);
                    // Heading
                    cs.newLineAtOffset(100, 700);
                    cs.showText("Heading Title");
                    // Body line 1 (same left margin)
                    cs.newLineAtOffset(0, -20);
                    cs.showText("First body line here");
                    // Body line 2 (same left margin)
                    cs.newLineAtOffset(0, -15);
                    cs.showText("Second body line continues");
                    // Indented paragraph start (+25 indent, blank-line drop)
                    cs.newLineAtOffset(25, -35);
                    cs.showText("Indented new paragraph begins");
                    // Continuation of indented paragraph (back to margin)
                    cs.newLineAtOffset(-25, -15);
                    cs.showText("and wraps onto the next line");
                    cs.endText();
                }
                doc.save(new File(args[1]));
            }
            return;
        }
        if ("extract".equals(mode)) {
            try (PDDocument doc = Loader.loadPDF(new File(args[1]))) {
                out.print(new PDFTextStripper().getText(doc));
            }
            return;
        }
        throw new IllegalArgumentException("unknown mode: " + mode);
    }
}
