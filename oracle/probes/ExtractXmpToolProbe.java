import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;

/**
 * Live oracle probe: drive Apache PDFBox's
 * {@code org.apache.pdfbox.tools.ExtractXMP} CLI in {@code -console} mode and
 * emit the result — exit code plus the exact XMP payload bytes (Base64) the tool
 * wrote to stdout — as JSON, so a parity test can assert pypdfbox's
 * {@code ExtractXMP} CLI emits the same bytes / exit code / "no metadata" and
 * "page doesn't exist" failure shapes.
 *
 * Upstream {@code ExtractXMP} exposes only {@code public static void main(...)},
 * which calls {@code System.exit(...)} (the {@code Callable} and the picocli
 * command are package-private). Java 21 removed the {@code SecurityManager}
 * exit-trap, so the probe drives the tool as a real subprocess
 * ({@code java -cp <classpath> org.apache.pdfbox.tools.ExtractXMP ...}) and
 * harvests the child's real exit code and captured stdout. This is the most
 * faithful "drive the actual CLI" path — it is literally the shell invocation.
 *
 * Usage:
 *   java -cp <jar>:<build> ExtractXmpToolProbe <infile> [extra CLI args...]
 *
 * Args:
 *   args[0]     = the input PDF (forwarded via -i).
 *   args[1..n]  = extra CLI args forwarded verbatim (e.g. "-page" "2").
 *
 * Emits one JSON object:
 *   {"exitCode":0,"xmpBase64":"<base64 of child stdout bytes>"}
 */
public final class ExtractXmpToolProbe {
    public static void main(String[] args) throws Exception {
        String infile = args[0];

        List<String> cmd = new ArrayList<>();
        cmd.add(System.getProperty("java.home") + File.separator + "bin"
                + File.separator + "java");
        cmd.add("-cp");
        cmd.add(System.getProperty("java.class.path"));
        cmd.add("org.apache.pdfbox.tools.ExtractXMP");
        cmd.add("-i");
        cmd.add(infile);
        cmd.add("-console");
        for (int i = 1; i < args.length; i++) {
            cmd.add(args[i]);
        }

        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.redirectErrorStream(false);
        Process proc = pb.start();

        ByteArrayOutputStream captured = new ByteArrayOutputStream();
        try (InputStream is = proc.getInputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = is.read(buf)) != -1) {
                captured.write(buf, 0, n);
            }
        }
        // Drain stderr so the child can't block on a full pipe.
        try (InputStream es = proc.getErrorStream()) {
            byte[] buf = new byte[8192];
            while (es.read(buf) != -1) {
                // discard
            }
        }
        int exitCode = proc.waitFor();

        String b64 = Base64.getEncoder().encodeToString(captured.toByteArray());
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        out.println("{\"exitCode\":" + exitCode + ",\"xmpBase64\":\"" + b64 + "\"}");
    }
}
