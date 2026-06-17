import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: emit Apache PDFBox's gap-driven word-separator output.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> WordGapSpaceProbe input.pdf [page]
 *
 * Targets the rule in {@code PDFTextStripper.writePage} whereby a single
 * word separator is inserted between two glyphs whose horizontal gap exceeds
 * a fraction of the space-character / average glyph width — independent of any
 * actual space glyph in the content stream — and is NOT inserted for a normal
 * inter-letter gap. A very large gap still yields exactly one separator, never
 * a run of them.
 *
 * The default word separator (a literal space) is overridden with a unique
 * sentinel token "|W|" so the exact count and placement of gap-driven word
 * breaks is observable in the extracted string rather than blurred into
 * ordinary whitespace. The line separator is likewise sentinelised so a
 * trailing newline does not masquerade as a word break.
 *
 * Output is the extracted string framed by sentinels, UTF-8 to stdout:
 *   <<<TEXT
 *   ...extracted text (with |W| word + |L| line separators)...
 *   TEXT>>>
 */
public final class WordGapSpaceProbe {
    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        final int page = args.length > 1 ? Integer.parseInt(args[1]) : 1;
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            stripper.setWordSeparator("|W|");
            stripper.setLineSeparator("|L|");
            stripper.setStartPage(page);
            stripper.setEndPage(page);
            String extracted = stripper.getText(doc);
            out.print("<<<TEXT\n");
            out.print(extracted);
            out.print("TEXT>>>\n");
        }
    }
}
