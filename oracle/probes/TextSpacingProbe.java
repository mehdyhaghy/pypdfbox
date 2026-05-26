import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.text.TextPosition;

/**
 * Live oracle probe: emit Apache PDFBox text-state spacing geometry.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TextSpacingProbe input.pdf [page]
 *
 * Targets the text-state spacing parameters Tc / Tw / Tz / Ts and the TJ
 * array numeric adjustments, all of which shift glyph X positions and
 * govern where the stripper inserts word breaks.
 *
 * Output has two sections, both UTF-8 to stdout:
 *
 *   1. A "TEXT" section: the full extracted string (as PDFTextStripper
 *      delivers it, sort-by-position on) framed by sentinels so the test
 *      can recover whitespace / word breaks exactly:
 *        <<<TEXT
 *        ...extracted text...
 *        TEXT>>>
 *
 *   2. A "GLYPHS" section: one canonical tab-separated line per glyph in
 *      reading order:
 *        unicode \t xDirAdj \t yDirAdj \t widthDirAdj
 *      Floats rounded to %.2f with Locale.ROOT so the rendering is stable
 *      across platforms / locales. The X position + width per glyph make
 *      Tc/Tw/Tz/Ts/TJ-driven horizontal shifts directly comparable.
 *
 * Restricting to a single page (default page 1, 1-based) keeps the diff
 * small and deterministic; the page index is args[1] if present.
 */
public final class TextSpacingProbe {
    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        final int page = args.length > 1 ? Integer.parseInt(args[1]) : 1;
        final StringBuilder glyphs = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripper stripper = new PDFTextStripper() {
                @Override
                protected void writeString(String text, List<TextPosition> positions) throws java.io.IOException {
                    for (TextPosition p : positions) {
                        glyphs.append(String.format(
                            Locale.ROOT,
                            "%s\t%.2f\t%.2f\t%.2f%n",
                            p.getUnicode(),
                            p.getXDirAdj(),
                            p.getYDirAdj(),
                            p.getWidthDirAdj()));
                    }
                    super.writeString(text, positions);
                }
            };
            stripper.setSortByPosition(true);
            stripper.setStartPage(page);
            stripper.setEndPage(page);
            String extracted = stripper.getText(doc);
            out.print("<<<TEXT\n");
            out.print(extracted);
            out.print("TEXT>>>\n");
            out.print("<<<GLYPHS\n");
            out.print(glyphs);
            out.print("GLYPHS>>>\n");
        }
    }
}
