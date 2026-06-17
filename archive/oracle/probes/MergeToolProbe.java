import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.tools.PDFMerger;

/**
 * Live oracle probe: drive Apache PDFBox's {@code org.apache.pdfbox.tools.PDFMerger}
 * CLI on N (>= 3) input PDFs and emit the structural result of the produced
 * merged file as JSON so a parity test can assert pypdfbox's {@code merge} CLI
 * produces an equivalent concatenated PDF.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> MergeToolProbe out.pdf in1.pdf in2.pdf in3.pdf ...
 *
 * Args:
 *   args[0]      = output path the merged document is written to.
 *   args[1..n-1] = the input PDFs to merge, in CLI order (two or more).
 *
 * Invokes the upstream CLI exactly as a shell call would. Upstream picocli
 * declares {@code -i} as a repeatable single-value option
 * ({@code -i=<infile> [-i=<infile>]...}), so each input gets its own flag:
 *   {@code PDFMerger -i in1 -i in2 -i in3 ... -o out}
 * via picocli's {@code CommandLine.execute}, which returns the
 * {@code Callable<Integer>} exit code (0 = success, 4 = I/O error). On success
 * the merged file is reloaded and one JSON object is printed:
 *
 *   {"exitCode":0,"pages":N,"text":["page0text","page1text",...]}
 *
 * The {@code text} array holds the per-page extracted text (PDFTextStripper run
 * over each single page), in merged page order — so a dropped, duplicated, or
 * reordered page shows up immediately. On a non-zero exit the page/text fields
 * report the failure shape ({@code pages:-1,text:[]}).
 */
public final class MergeToolProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String outPath = args[0];

        // Build the upstream CLI argument vector with one -i per input:
        //   -i in1 -i in2 -i in3 ... -o out
        int inputCount = args.length - 1;
        String[] argv = new String[inputCount * 2 + 2];
        int pos = 0;
        for (int i = 1; i < args.length; i++) {
            argv[pos++] = "-i";
            argv[pos++] = args[i];
        }
        argv[pos++] = "-o";
        argv[pos] = outPath;

        int exitCode = new picocli.CommandLine(new PDFMerger()).execute(argv);

        StringBuilder sb = new StringBuilder();
        sb.append("{\"exitCode\":").append(exitCode);
        if (exitCode == 0) {
            try (PDDocument doc = Loader.loadPDF(new File(outPath))) {
                int total = doc.getNumberOfPages();
                sb.append(",\"pages\":").append(total);
                sb.append(",\"text\":[");
                PDFTextStripper stripper = new PDFTextStripper();
                for (int i = 0; i < total; i++) {
                    stripper.setStartPage(i + 1);
                    stripper.setEndPage(i + 1);
                    String text = stripper.getText(doc).trim();
                    if (i > 0) {
                        sb.append(',');
                    }
                    sb.append('"').append(escape(text)).append('"');
                }
                sb.append("]");
            }
        } else {
            sb.append(",\"pages\":-1,\"text\":[]");
        }
        sb.append("}");
        out.print(sb.toString());
    }

    private static String escape(String s) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': b.append("\\\\"); break;
                case '"': b.append("\\\""); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        b.append(String.format("\\u%04x", (int) c));
                    } else {
                        b.append(c);
                    }
            }
        }
        return b.toString();
    }
}
