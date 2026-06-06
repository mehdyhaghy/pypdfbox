import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.tools.PrintPDF;

/**
 * Live oracle probe: drive Apache PDFBox's {@code org.apache.pdfbox.tools.PrintPDF}
 * CLI through picocli's {@code CommandLine.execute} and emit ONLY the exit code
 * as JSON.
 *
 * IMPORTANT — this probe is deliberately restricted to the *non-printing* error
 * surfaces of the CLI: parameter-validation failures (missing required {@code -i},
 * an unknown {@code -orientation} / {@code -duplex} enum value → picocli exit 2)
 * and {@code call()} paths that fail and return 4 *before* a {@code PrinterJob}
 * is ever constructed (a missing / unloadable input file, or a
 * permission-restricted document whose {@code canPrint()} is false). The caller
 * must never hand this probe a loadable, printable PDF — that would reach the
 * real print spooler.
 *
 * Usage:
 *   java -cp <jar>:<build> PrintPdfFlagProbe <args...>
 *
 * Emits one JSON object:
 *   {"exitCode":<n>}
 */
public final class PrintPdfFlagProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        List<String> argv = new ArrayList<>();
        for (String a : args) {
            argv.add(a);
        }
        int exitCode = new picocli.CommandLine(new PrintPDF())
                .execute(argv.toArray(new String[0]));
        out.println("{\"exitCode\":" + exitCode + "}");
    }
}
