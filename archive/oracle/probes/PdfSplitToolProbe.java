import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.tools.PDFSplit;

/**
 * Live oracle probe: drive Apache PDFBox's
 * {@code org.apache.pdfbox.tools.PDFSplit} CLI on a single input PDF and emit
 * the observable result — exit code, the list of produced output files (in the
 * {@code <prefix>-<n>.pdf} naming convention, sorted), and the page count of
 * each produced file — as JSON, so a parity test can assert pypdfbox's
 * {@code PDFSplit} CLI produces the same set of output files with the same
 * per-file page counts.
 *
 * Usage:
 *   java -cp <jar>:<build> PdfSplitToolProbe <prefix> <infile> [extra CLI args...]
 *
 * Args:
 *   args[0]     = the output prefix (also passed to the CLI via -outputPrefix),
 *                 so the probe knows where to find / clean up the produced files.
 *   args[1]     = the input PDF to split.
 *   args[2..n]  = extra CLI args forwarded verbatim (e.g. "-split" "2" or
 *                 "-startPage" "2" "-endPage" "4").
 *
 * The CLI invocation is:
 *   PDFSplit -i <infile> -outputPrefix <prefix> [extra...]
 * run via picocli's {@code CommandLine.execute} (returns the Callable exit
 * code; 0 = success, 4 = I/O error).
 *
 * Emits one JSON object:
 *   {"exitCode":0,"files":["<prefix>-1","<prefix>-2",...],"pages":[1,1,...]}
 * where "files" holds just the basename stems (no directory, no ".pdf"
 * suffix) in ascending split-index order, and "pages" the page count of each.
 */
public final class PdfSplitToolProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String prefix = args[0];
        String infile = args[1];

        List<String> argv = new ArrayList<>();
        argv.add("-i");
        argv.add(infile);
        argv.add("-outputPrefix");
        argv.add(prefix);
        for (int i = 2; i < args.length; i++) {
            argv.add(args[i]);
        }

        int exitCode = new picocli.CommandLine(new PDFSplit())
                .execute(argv.toArray(new String[0]));

        StringBuilder sb = new StringBuilder();
        sb.append("{\"exitCode\":").append(exitCode);

        if (exitCode == 0) {
            File prefixFile = new File(prefix);
            File dir = prefixFile.getAbsoluteFile().getParentFile();
            String stem = prefixFile.getName();
            // Collect <stem>-<n>.pdf in ascending n until a gap.
            List<String> names = new ArrayList<>();
            List<Integer> pages = new ArrayList<>();
            int n = 1;
            while (true) {
                File f = new File(dir, stem + "-" + n + ".pdf");
                if (!f.isFile()) {
                    break;
                }
                names.add(stem + "-" + n);
                try (PDDocument doc = Loader.loadPDF(f)) {
                    pages.add(doc.getNumberOfPages());
                }
                n++;
            }
            sb.append(",\"files\":[");
            for (int i = 0; i < names.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append('"').append(names.get(i)).append('"');
            }
            sb.append("],\"pages\":[");
            for (int i = 0; i < pages.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(pages.get(i));
            }
            sb.append(']');
        } else {
            sb.append(",\"files\":[],\"pages\":[]");
        }
        sb.append('}');
        out.println(sb.toString());
    }
}
