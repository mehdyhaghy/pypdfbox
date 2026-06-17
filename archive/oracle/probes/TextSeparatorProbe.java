import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: emit Apache PDFBox PDFTextStripper output with every
 * separator overridden to a distinctive non-default token.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TextSeparatorProbe input.pdf
 *
 * Default separators (word=" ", line="\n", pageEnd="\n", page/paragraph
 * start = "") all collapse onto whitespace, so a misplaced separator is
 * invisible in a default-config diff. Replacing each one with a unique
 * sentinel makes the exact insertion point of every word break, line
 * break, page break, and paragraph break observable, and therefore
 * directly comparable to pypdfbox's PDFTextStripper. Output is the
 * extracted text, UTF-8, to stdout with no extra framing.
 */
public final class TextSeparatorProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            stripper.setWordSeparator("|W|");
            stripper.setLineSeparator("|L|\n");
            stripper.setPageStart("<<PAGE>>");
            stripper.setPageEnd("<</PAGE>>\n");
            stripper.setParagraphStart("[P]");
            stripper.setParagraphEnd("[/P]");
            out.print(stripper.getText(doc));
        }
    }
}
