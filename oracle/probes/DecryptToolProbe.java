import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.tools.Decrypt;

/**
 * Live oracle probe: drive Apache PDFBox's {@code org.apache.pdfbox.tools.Decrypt}
 * CLI on an encrypted input and emit the structural result of the produced file
 * as JSON so a parity test can assert pypdfbox's Decrypt tool produces an
 * equivalent unencrypted PDF.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> DecryptToolProbe in.pdf out.pdf <password>
 *
 * Invokes {@code Decrypt.main(["-i", in, "-o", out, "-password", pw])} — the
 * exact upstream CLI surface (picocli {@code Callable<Integer>}). It then
 * reloads {@code out} with NO password and prints one JSON object:
 *
 *   {"exitCode":0,"isEncrypted":false,"pages":1,"text":"..."}
 *
 * {@code exitCode} is the value returned by the picocli command (0 = success,
 * 1 = not-encrypted / non-owner password, 4 = IO error). When the tool exits
 * non-zero the output file is not reloaded and the encryption/page/text fields
 * report the failure shape ({@code isEncrypted:null,pages:-1,text:""}). A
 * correct owner password yields {@code isEncrypted:false} on a file that opens
 * with no password — the load-bearing parity claim.
 */
public final class DecryptToolProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String in = args[0];
        String outPath = args[1];
        String password = args.length > 2 ? args[2] : "";

        // Drive the upstream CLI exactly as a shell invocation would. picocli's
        // CommandLine.execute returns the Callable's Integer exit code; we go
        // through Decrypt's own picocli wiring by constructing the command.
        Integer exitCode = runDecrypt(in, outPath, password);

        StringBuilder sb = new StringBuilder();
        sb.append("{\"exitCode\":").append(exitCode);
        if (exitCode != null && exitCode == 0) {
            try (PDDocument doc = Loader.loadPDF(new File(outPath))) {
                sb.append(",\"isEncrypted\":").append(doc.isEncrypted());
                sb.append(",\"pages\":").append(doc.getNumberOfPages());
                String text = new PDFTextStripper().getText(doc);
                sb.append(",\"text\":\"").append(escape(text)).append("\"");
            }
        } else {
            sb.append(",\"isEncrypted\":null,\"pages\":-1,\"text\":\"\"");
        }
        sb.append("}");
        out.print(sb.toString());
    }

    private static Integer runDecrypt(String in, String outPath, String password)
            throws Exception {
        // picocli builds the command from the Decrypt instance; execute returns
        // the Callable<Integer> result as the process exit code.
        picocli.CommandLine cmd = new picocli.CommandLine(new Decrypt());
        return cmd.execute("-i", in, "-o", outPath, "-password", password);
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
