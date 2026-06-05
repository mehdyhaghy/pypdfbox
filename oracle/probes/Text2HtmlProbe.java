import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.tools.PDFText2HTML;

/**
 * Live oracle probe for org.apache.pdfbox.tools.PDFText2HTML.
 *
 * PDFText2HTML is a PDFTextStripper subclass that wraps stripped text in
 * minimal HTML (DOCTYPE/head/title/body, per-page div, per-paragraph p,
 * font-state b/i tags, and entity escaping). This probe runs the converter
 * exactly as the ExtractText -html CLI path does: construct PDFText2HTML and
 * call getText(doc), printing the resulting HTML to stdout verbatim.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Text2HtmlProbe input.pdf
 * Output: the HTML string, UTF-8, to stdout (no extra framing).
 */
public final class Text2HtmlProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File file = new File(args[0]);
        try (PDDocument doc = Loader.loadPDF(file)) {
            PDFText2HTML stripper = new PDFText2HTML();
            out.print(stripper.getText(doc));
        }
    }
}
