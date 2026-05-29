import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.text.TextPosition;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for TextPosition.getDir() on text drawn with a rotated
 * text matrix (Tm rotating 0 / 90 / 180 / 270 degrees) on an UN-rotated page.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> RotatedTextDirProbe build   out.pdf
 *   java -cp <pdfbox-app.jar>:<build> RotatedTextDirProbe extract in.pdf
 *
 * "build" writes a single un-rotated LETTER page that paints four short
 * runs, each with a text matrix rotated by a different multiple of 90
 * degrees about its own origin (via Matrix.getRotateInstance):
 *   - "Zero"    at 0   degrees, origin (250, 600)
 *   - "Ninety"  at 90  degrees, origin (300, 300)
 *   - "OneEighty" at 180 degrees, origin (350, 500)
 *   - "TwoSeventy" at 270 degrees, origin (200, 400)
 * The page /Rotate stays 0, so the only rotation is in the text matrix —
 * this isolates TextPosition.getDir() (text direction) from page rotation.
 *
 * "extract" runs PDFTextStripper twice:
 *   <<<TEXT ... TEXT>>>   the full getText(doc) (sort-by-position on),
 *                         so glyph grouping + ordering by direction is
 *                         exercised end to end.
 *   <<<DIRS ... DIRS>>>   one tab-separated line per delivered TextPosition:
 *                             unicode \t getDir()
 *                         with getDir() rendered "%.1f" (Locale.ROOT). This
 *                         is the per-glyph direction stream pypdfbox must
 *                         reproduce at run granularity.
 */
public final class RotatedTextDirProbe {
    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        final String mode = args[0];
        if ("build".equals(mode)) {
            build(new File(args[1]));
            return;
        }
        try (PDDocument doc = Loader.loadPDF(new File(args[1]))) {
            PDFTextStripper textStripper = new PDFTextStripper();
            textStripper.setSortByPosition(true);
            out.print("<<<TEXT\n");
            out.print(textStripper.getText(doc));
            out.print("TEXT>>>\n");
        }
        try (PDDocument doc = Loader.loadPDF(new File(args[1]))) {
            PDFTextStripper dirStripper = new PDFTextStripper() {
                @Override
                protected void writeString(String text, List<TextPosition> positions) {
                    for (TextPosition p : positions) {
                        out.printf(
                            Locale.ROOT,
                            "%s\t%.1f%n",
                            p.getUnicode(),
                            p.getDir());
                    }
                }
            };
            dirStripper.setSortByPosition(true);
            out.print("<<<DIRS\n");
            dirStripper.getText(doc);
            out.print("DIRS>>>\n");
        }
    }

    private static void build(File target) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.LETTER);
            doc.addPage(page);
            PDType1Font helv = new PDType1Font(Standard14Fonts.FontName.HELVETICA);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                show(cs, helv, "Zero", 0, 250, 600);
                show(cs, helv, "Ninety", 90, 300, 300);
                show(cs, helv, "OneEighty", 180, 350, 500);
                show(cs, helv, "TwoSeventy", 270, 200, 400);
            }
            doc.save(target);
        }
    }

    private static void show(
            PDPageContentStream cs,
            PDType1Font font,
            String text,
            int degrees,
            float x,
            float y) throws Exception {
        cs.beginText();
        cs.setFont(font, 18);
        Matrix m = Matrix.getRotateInstance(Math.toRadians(degrees), x, y);
        cs.setTextMatrix(m);
        cs.showText(text);
        cs.endText();
    }
}
