import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: open a PDF that pypdfbox's {@code Encrypt} CLI produced,
 * authenticating with the supplied password, and emit the decrypted shape as
 * JSON so a parity test can assert Apache PDFBox 3.0.7 accepts the standard
 * security handler's {@code /U} / {@code /O} / {@code /P} entries pypdfbox
 * wrote and round-trips to the same decrypted content + permission bits.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> EncryptToolProbe enc.pdf &lt;password&gt;
 *
 * {@code Loader.loadPDF(file, password)} runs the standard handler's
 * password validation (algorithm 6 for r2-r4, algorithm 11 for r5/r6). If the
 * {@code /U} / {@code /O} entries pypdfbox wrote are malformed (bad padding,
 * wrong {@code /R}, mis-signed {@code /P}, wrong {@code /Length}) PDFBox throws
 * {@code InvalidPasswordException} and the probe reports {@code opened:false}.
 *
 * On success the probe prints one JSON object:
 *
 *   {"opened":true,"isEncrypted":true,"pages":1,"revision":3,
 *    "canPrint":true,"canModify":true,"canExtract":true,"canAssemble":true,
 *    "text":"..."}
 *
 * The permission booleans come from the AccessPermission PDFBox reconstructs
 * from the decrypted {@code /P} bits — the parity claim is that they match the
 * {@code -can*} flags pypdfbox's Encrypt tool was driven with.
 */
public final class EncryptToolProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String in = args[0];
        String password = args.length > 1 ? args[1] : "";

        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(in), password)) {
            AccessPermission ap = doc.getCurrentAccessPermission();
            int revision = doc.getEncryption() != null
                    ? doc.getEncryption().getRevision() : -1;
            sb.append("{\"opened\":true");
            sb.append(",\"isEncrypted\":").append(doc.isEncrypted());
            sb.append(",\"pages\":").append(doc.getNumberOfPages());
            sb.append(",\"revision\":").append(revision);
            sb.append(",\"canPrint\":").append(ap.canPrint());
            sb.append(",\"canModify\":").append(ap.canModify());
            sb.append(",\"canExtract\":").append(ap.canExtractContent());
            sb.append(",\"canAssemble\":").append(ap.canAssembleDocument());
            // Decrypted text — proves the file key derived from the password
            // actually deciphers the content stream PDFBox reads.
            doc.setAllSecurityToBeRemoved(true);
            String text = new PDFTextStripper().getText(doc);
            sb.append(",\"text\":\"").append(escape(text)).append("\"");
            sb.append("}");
        } catch (Exception e) {
            sb.setLength(0);
            sb.append("{\"opened\":false,\"error\":\"")
              .append(escape(e.getClass().getSimpleName() + ": " + e.getMessage()))
              .append("\"}");
        }
        out.print(sb.toString());
    }

    private static String escape(String s) {
        if (s == null) {
            return "";
        }
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
