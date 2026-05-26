import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.text.TextPosition;

/**
 * Live oracle probe: emit Apache PDFBox per-glyph TextPosition geometry.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TextPosGeomProbe input.pdf [page]
 *
 * For each TextPosition delivered to writeString(String, List<TextPosition>)
 * we emit one canonical, tab-separated line per glyph:
 *
 *   unicode \t xDirAdj \t yDirAdj \t widthDirAdj \t heightDir \t fontSizeInPt
 *
 * Floats are rounded to 2 decimals with Locale.ROOT so the rendering is
 * stable across platforms / locales and directly comparable to pypdfbox's
 * own per-glyph dump. Output is UTF-8 to stdout, no extra framing.
 *
 * Restricting to a single page (default page 1, 1-based) keeps the diff
 * small and deterministic; page index is args[1] if present.
 */
public final class TextPosGeomProbe {
    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        final int page = args.length > 1 ? Integer.parseInt(args[1]) : 1;
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripper stripper = new PDFTextStripper() {
                @Override
                protected void writeString(String text, List<TextPosition> positions) {
                    for (TextPosition p : positions) {
                        out.printf(
                            Locale.ROOT,
                            "%s\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f%n",
                            p.getUnicode(),
                            p.getXDirAdj(),
                            p.getYDirAdj(),
                            p.getWidthDirAdj(),
                            p.getHeightDir(),
                            p.getFontSizeInPt());
                    }
                }
            };
            stripper.setSortByPosition(true);
            stripper.setStartPage(page);
            stripper.setEndPage(page);
            stripper.getText(doc);
        }
    }
}
