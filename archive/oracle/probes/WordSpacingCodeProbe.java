import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.text.TextPosition;

/**
 * Live oracle probe: word-spacing (<code>Tw</code>) applicability rule of
 * PDF 32000-1 &sect;9.3.3 — word spacing is added to the glyph advance
 * <em>only</em> when the show-text byte string yields the single-byte
 * character code 32 (the ASCII space). It must NOT apply to:
 *
 *   * a 2-byte code 32 in a composite (Type 0) font, even though the
 *     low byte equals 0x20, and
 *   * any single-byte code other than 32.
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; WordSpacingCodeProbe input.pdf [page]
 *
 * Output (UTF-8, stdout), two framed sections:
 *
 *   1. The full PDFTextStripper.getText() string (sort-by-position on):
 *        &lt;&lt;&lt;TEXT
 *        ...extracted text...
 *        TEXT&gt;&gt;&gt;
 *
 *   2. One canonical tab-separated line per glyph in reading order:
 *        unicode \t xDirAdj \t widthDirAdj
 *      Floats rounded to %.2f with Locale.ROOT for cross-platform stability.
 *      The per-glyph X stream proves where (and whether) Tw widened the
 *      advance: in the composite-font case the gaps between adjacent
 *      2-byte codes must equal the bare glyph advances (no +Tw leak).
 */
public final class WordSpacingCodeProbe {
    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        final int page = args.length > 1 ? Integer.parseInt(args[1]) : 1;
        final StringBuilder glyphs = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripper stripper = new PDFTextStripper() {
                @Override
                protected void writeString(String text, List<TextPosition> positions)
                        throws java.io.IOException {
                    for (TextPosition p : positions) {
                        glyphs.append(String.format(
                            Locale.ROOT,
                            "%s\t%.2f\t%.2f%n",
                            p.getUnicode(),
                            p.getXDirAdj(),
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
