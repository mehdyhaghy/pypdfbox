import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.tools.OverlayPDF;

/**
 * Live oracle probe: drive Apache PDFBox's
 * {@code org.apache.pdfbox.tools.OverlayPDF} CLI and emit the per-page extracted
 * text of the produced output as JSON, so a parity test can assert pypdfbox's
 * {@code OverlayPDF} CLI stacks the same overlay file onto the same pages.
 *
 * The overlay stacking order (which selector wins on a given page) is the
 * load-bearing behaviour: upstream resolves first/last with higher precedence
 * than odd/even, falling back to the default overlay. Because PDFTextStripper
 * concatenates the overlay glyph runs ahead of the base page glyph runs, the
 * per-page text string (e.g. "FIRSTBASE1") encodes exactly which overlay landed
 * on which page.
 *
 * Usage:
 *   java -cp <jar>:<build> OverlayToolProbe <outfile> <infile> [CLI args...]
 *
 * Args:
 *   args[0]     = output path the overlaid document is written to (also forwarded
 *                 to the CLI via -o).
 *   args[1]     = input PDF (forwarded via -i).
 *   args[2..n]  = extra overlay-selector CLI args forwarded verbatim, e.g.
 *                 "-default" "over.pdf", or
 *                 "-odd" "odd.pdf" "-even" "even.pdf" "-first" "f.pdf" "-last" "l.pdf".
 *
 * Emits one JSON object:
 *   {"exitCode":0,"text":["page0text","page1text",...]}
 * with one entry per page in page order. On non-zero exit: text is [].
 */
public final class OverlayToolProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String outfile = args[0];
        String infile = args[1];

        List<String> argv = new ArrayList<>();
        argv.add("-i");
        argv.add(infile);
        argv.add("-o");
        argv.add(outfile);
        for (int i = 2; i < args.length; i++) {
            argv.add(args[i]);
        }

        int exitCode = new picocli.CommandLine(new OverlayPDF())
                .execute(argv.toArray(new String[0]));

        StringBuilder sb = new StringBuilder();
        sb.append("{\"exitCode\":").append(exitCode);
        sb.append(",\"text\":[");
        if (exitCode == 0) {
            try (PDDocument doc = Loader.loadPDF(new File(outfile))) {
                int total = doc.getNumberOfPages();
                for (int p = 1; p <= total; p++) {
                    PDFTextStripper stripper = new PDFTextStripper();
                    stripper.setStartPage(p);
                    stripper.setEndPage(p);
                    String t = stripper.getText(doc).trim();
                    if (p > 1) {
                        sb.append(',');
                    }
                    sb.append('"');
                    for (int c = 0; c < t.length(); c++) {
                        char ch = t.charAt(c);
                        if (ch == '"' || ch == '\\') {
                            sb.append('\\').append(ch);
                        } else if (ch == '\n') {
                            sb.append("\\n");
                        } else if (ch == '\r') {
                            sb.append("\\r");
                        } else {
                            sb.append(ch);
                        }
                    }
                    sb.append('"');
                }
            }
        }
        sb.append("]}");
        out.println(sb.toString());
    }
}
