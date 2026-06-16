import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.tools.PDFText2HTML;
import org.apache.pdfbox.tools.PDFText2Markdown;

/**
 * Live oracle probe fuzzing the HTML/Markdown text-output formatters.
 *
 * Both {@code PDFText2HTML} and {@code PDFText2Markdown} are
 * {@code PDFTextStripper} subclasses behind the {@code ExtractText -html} /
 * {@code -md} CLI paths. This probe drives whichever converter is requested
 * over a caller-supplied PDF and prints the formatted output verbatim, so a
 * pytest can diff the escaping + page/article/paragraph structure against
 * pypdfbox on byte-identical input.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> TextFormatterFuzzProbe html input.pdf
 *   java -cp <pdfbox-app.jar>:<build> TextFormatterFuzzProbe md   input.pdf
 *
 * Output: the formatted HTML or Markdown string, UTF-8, to stdout (no extra
 * framing). On a converter exception the probe prints "EXC:" + the exception
 * class simple name so the divergence (vs a pypdfbox crash) is observable.
 */
public final class TextFormatterFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        File file = new File(args[1]);
        try (PDDocument doc = Loader.loadPDF(file)) {
            String result;
            if ("md".equals(mode)) {
                result = new PDFText2Markdown().getText(doc);
            } else {
                result = new PDFText2HTML().getText(doc);
            }
            out.print(result);
        } catch (Exception e) {
            out.print("EXC:" + e.getClass().getSimpleName());
        }
    }
}
