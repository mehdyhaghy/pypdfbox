import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: isolate Apache PDFBox PDFTextStripper's *line-break*
 * (newline) insertion decision.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TextLineBreakProbe input.pdf
 *
 * The default line separator ("\n") collapses onto ordinary whitespace, so a
 * misplaced newline is invisible in a default-config diff. This probe leaves
 * the word separator at its default (" ") but overrides ONLY the line
 * separator with a distinctive "|L|" sentinel (no trailing newline) and leaves
 * the paragraph start/end empty (default). The net effect is that the exact
 * insertion point of every vertical-baseline line break becomes observable
 * while word breaks stay as plain spaces — letting a parity test assert that a
 * baseline drop produces a line break exactly where Java PDFBox produces one,
 * and that two runs on the SAME baseline get a space (or nothing) but never a
 * "|L|".
 *
 * sortByPosition is on so the comparison is against the position-sorted
 * reading order both engines share. Output is the extracted text, UTF-8, to
 * stdout with no extra framing.
 */
public final class TextLineBreakProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            stripper.setLineSeparator("|L|");
            out.print(stripper.getText(doc));
        }
    }
}
