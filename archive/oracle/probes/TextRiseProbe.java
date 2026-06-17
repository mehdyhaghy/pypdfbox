import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.text.TextPosition;

/**
 * Live oracle probe: emit Apache PDFBox text-rise (Ts) extraction geometry.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TextRiseProbe input.pdf [page]
 *
 * Targets the text-rise parameter Ts (PDF 32000-1 §9.3.7): Ts raises or
 * lowers the baseline of subsequent glyphs (superscript / subscript) by
 * shifting the text-rendering matrix origin vertically by the rise. A
 * superscript run (e.g. ``4 Ts``) sits slightly above the surrounding
 * baseline; PDFTextStripper should still extract it inline (the rise is
 * within the line tolerance, so no spurious newline) and the glyph
 * Y-positions reflect the rise.
 *
 * Output is two sections, both UTF-8 to stdout:
 *
 *   1. A "TEXT" section: the full extracted string (sort-by-position on)
 *      framed by sentinels so the test recovers whitespace / line breaks
 *      exactly. The line separator is overridden to the distinctive
 *      sentinel "|L|" so any spurious newline introduced by the rise is
 *      directly observable (the default "\n" would hide inside whitespace):
 *        <<<TEXT
 *        ...extracted text...
 *        TEXT>>>
 *
 *   2. A "GLYPHS" section: one canonical tab-separated line per glyph in
 *      reading order:
 *        unicode \t yDirAdj
 *      The Y (direction-adjusted, measured from the page top) per glyph
 *      makes the Ts-driven baseline shift directly comparable: a raised
 *      run's glyphs report a smaller yDirAdj (higher on the page) than the
 *      surrounding baseline glyphs by exactly the rise.
 *      Floats rounded to %.2f with Locale.ROOT so the rendering is stable
 *      across platforms / locales.
 */
public final class TextRiseProbe {
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
                            "%s\t%.2f%n",
                            p.getUnicode(),
                            p.getYDirAdj()));
                    }
                    super.writeString(text, positions);
                }
            };
            stripper.setSortByPosition(true);
            stripper.setLineSeparator("|L|");
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
