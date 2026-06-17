import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.text.TextPosition;

/**
 * Live oracle probe: horizontal text scaling (<code>Tz</code>) and its
 * effect on word-break detection in <code>PDFTextStripper.getText()</code>.
 *
 * PDF 32000-1 &sect;9.3.4: the <code>Tz</code> operand is a percentage that
 * scales the horizontal component of every glyph displacement, of character
 * spacing (<code>Tc</code>), and of word spacing (<code>Tw</code>) by
 * <code>Tz/100</code>. A condensed run (<code>Tz 50</code>) halves the gap
 * the stripper sees between two adjacent show-text runs; an expanded run
 * (<code>Tz 200</code>) doubles it. Because the stripper decides whether to
 * insert a word separator from the inter-run gap, a non-100 <code>Tz</code>
 * can flip a <code>TJ</code>-array jump from above to below (or vice versa)
 * the word-break threshold relative to the same jump at 100%.
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; TextHorizScalingProbe input.pdf [page]
 *
 * Output (UTF-8, stdout), two framed sections:
 *
 *   1. The full PDFTextStripper.getText() string (sort-by-position on):
 *        &lt;&lt;&lt;TEXT
 *        ...extracted text...
 *        TEXT&gt;&gt;&gt;
 *
 *   2. One canonical tab-separated line per glyph in reading order:
 *        unicode \t xDirAdj \t yDirAdj \t widthDirAdj
 *      Floats rounded to %.2f with Locale.ROOT for cross-platform stability.
 *      The per-glyph X stream proves how Tz scaled each advance.
 */
public final class TextHorizScalingProbe {
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
