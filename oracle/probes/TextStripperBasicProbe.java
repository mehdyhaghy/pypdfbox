import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: Apache PDFBox PDFTextStripper *basic* horizontal text
 * extraction — word/line segmentation and output ordering over tiny, fully
 * controlled synthetic content streams.
 *
 * Companion to VerticalTextStripProbe (vertical writing mode) and
 * TextSortInlineProbe (intra-line re-sort): this probe isolates the
 * horizontal-extraction reading-order surface on deterministic single-page
 * documents (empty page, whitespace-positioned text, wide-gap word break,
 * two-line break, overlapping glyphs, multi-Tj stream order) so the output
 * is byte-stable across runs.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TextStripperBasicProbe input.pdf
 *
 * Output (UTF-8): two escaped projections of the extracted text, one with
 * sortByPosition off (content-stream order) and one with it on
 * (position-sorted reading order). Newlines / carriage returns inside the
 * payload are escaped so each marker stays on one physical line; the Python
 * side reverses the escape and compares byte-for-byte:
 *
 *   UNSORTED:<escaped text>
 *   SORTED:<escaped text>
 *
 * Each mode loads the document FRESH (its own Loader.loadPDF) — a
 * PDFTextStripper run mutates per-page parser state that the next stripper
 * on the same PDDocument inherits, so reusing one handle across the two
 * modes makes the second mode's reading order depend on the first. Loading
 * a clean document per mode is the deterministic, mode-independent
 * comparison the parity test needs.
 */
public final class TextStripperBasicProbe {
    private static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r");
    }

    private static String extract(String path, boolean sort) throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(path))) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(sort);
            return stripper.getText(doc);
        }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        out.print("UNSORTED:" + esc(extract(args[0], false)) + "\n");
        out.print("SORTED:" + esc(extract(args[0], true)) + "\n");
    }
}
