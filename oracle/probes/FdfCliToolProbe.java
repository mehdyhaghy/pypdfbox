import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.tools.DecompressObjectstreams;
import org.apache.pdfbox.tools.ExportFDF;
import org.apache.pdfbox.tools.ExportXFDF;
import org.apache.pdfbox.tools.ImportFDF;
import org.apache.pdfbox.tools.ImportXFDF;

/**
 * Live oracle probe: drive Apache PDFBox's FDF/XFDF import/export and
 * {@code DecompressObjectstreams} CLI tools through picocli's
 * {@code CommandLine.execute} (which returns the {@code Callable} exit code)
 * and emit only the exit code as JSON.
 *
 * The produced output files (imported PDF, exported FDF/XFDF, decompressed PDF)
 * are left on disk at the paths the test passed in, so the parity test reloads
 * them with pypdfbox and compares the parsed-equivalent structure against the
 * pypdfbox-tool output for the same input. Keeping the comparison on the Python
 * side (rather than re-implementing an FDF dumper here) mirrors the established
 * {@code PdfSplitToolProbe} pattern: the probe reports the CLI's exit code, the
 * test owns the structural comparison.
 *
 * Usage:
 *   java -cp <jar>:<build> FdfCliToolProbe <tool> <args...>
 *
 * Where {@code <tool>} is one of:
 *   importfdf  | importxfdf | exportfdf | exportxfdf | decompress
 * and {@code <args...>} are forwarded verbatim to that tool's picocli command
 * (e.g. "-i" "in.pdf" "--data" "data.fdf" "-o" "out.pdf").
 *
 * Emits one JSON object:
 *   {"exitCode":<n>}
 */
public final class FdfCliToolProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String tool = args[0];

        List<String> argv = new ArrayList<>();
        for (int i = 1; i < args.length; i++) {
            argv.add(args[i]);
        }
        String[] cliArgs = argv.toArray(new String[0]);

        int exitCode;
        switch (tool) {
            case "importfdf":
                exitCode = new picocli.CommandLine(new ImportFDF()).execute(cliArgs);
                break;
            case "importxfdf":
                exitCode = new picocli.CommandLine(new ImportXFDF()).execute(cliArgs);
                break;
            case "exportfdf":
                exitCode = new picocli.CommandLine(new ExportFDF()).execute(cliArgs);
                break;
            case "exportxfdf":
                exitCode = new picocli.CommandLine(new ExportXFDF()).execute(cliArgs);
                break;
            case "decompress":
                exitCode = new picocli.CommandLine(new DecompressObjectstreams())
                        .execute(cliArgs);
                break;
            default:
                throw new IllegalArgumentException("unknown tool: " + tool);
        }

        out.println("{\"exitCode\":" + exitCode + "}");
    }
}
