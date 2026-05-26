import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: open a password-encrypted PDF with Apache PDFBox and prove
 * it decrypted by recovering its content.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> DecryptProbe in.pdf <password>
 *
 * Loads the encrypted input with the supplied password (empty string allowed),
 * then prints two framed lines to stdout:
 *   PAGES:<n>
 *   followed by the full PDFTextStripper text (UTF-8).
 *
 * A wrong password makes Loader.loadPDF throw InvalidPasswordException, which
 * exits non-zero — the parity test asserts on that to verify rejection. A
 * correct password lets a parity test compare the recovered page count + text
 * against pypdfbox's encryption round-trip.
 */
public final class DecryptProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File in = new File(args[0]);
        String password = args.length > 1 ? args[1] : "";
        try (PDDocument doc = Loader.loadPDF(in, password)) {
            out.print("PAGES:");
            out.print(doc.getNumberOfPages());
            out.print("\n");
            out.print(new PDFTextStripper().getText(doc));
        }
    }
}
