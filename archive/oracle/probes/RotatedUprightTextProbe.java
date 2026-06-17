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
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for the *upright-reading* rotated-page case: the page
 * /Rotate is a right angle AND the text matrix is counter-rotated by the same
 * angle so the text reads upright on the (display-rotated) page. This is the
 * common real-world rotated document — unlike RotatedMultiLineProbe, which
 * paints unrotated (identity-Tm) text on a /Rotate page.
 *
 *   build <out.pdf> <rotate>
 *       Single-page LETTER PDF whose /Rotate is <rotate> (0/90/180/270) with a
 *       short multi-line block whose text matrix is rotated by <rotate> so it
 *       reads upright once the viewer applies the page rotation. The
 *       TextPositions then carry getDir() == <rotate> and the direction-adjusted
 *       coordinates reconstruct the upright reading order.
 *
 *   extract <in.pdf>
 *       Emit Apache PDFBox's PDFTextStripper().getText(doc), UTF-8, no framing.
 */
public final class RotatedUprightTextProbe {

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
                // Place the upright block roughly centred for each rotation so
                // every line stays on the media box.
                float w = PDRectangle.LETTER.getWidth();   // 612
                float h = PDRectangle.LETTER.getHeight();   // 792
                String[] lines = {
                    "Upright heading line",
                    "Second upright line",
                    "Third upright line here",
                };
                try (PDPageContentStream cs =
                        new PDPageContentStream(doc, page)) {
                    cs.beginText();
                    cs.setFont(font, 12);
                    // Counter-rotate the text matrix by the page rotation so the
                    // glyphs read upright after the viewer rotates the page.
                    Matrix m = Matrix.getRotateInstance(
                            Math.toRadians(rotate), 0, 0);
                    // Anchor the first line at a rotation-appropriate origin.
                    float ox;
                    float oy;
                    switch (rotate) {
                        case 90:  ox = 150; oy = 100; break;
                        case 180: ox = w - 100; oy = h - 100; break;
                        case 270: ox = w - 150; oy = h - 100; break;
                        default:  ox = 100; oy = h - 100; break;
                    }
                    m.setValue(2, 0, ox);
                    m.setValue(2, 1, oy);
                    cs.setTextMatrix(m);
                    for (int i = 0; i < lines.length; i++) {
                        if (i > 0) {
                            cs.newLineAtOffset(0, -16);
                        }
                        cs.showText(lines[i]);
                    }
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
