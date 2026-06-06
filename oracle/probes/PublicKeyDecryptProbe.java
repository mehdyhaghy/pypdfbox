import java.io.File;
import java.io.FileInputStream;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: open a public-key (certificate) encrypted PDF with Apache
 * PDFBox using a PKCS#12 keystore + the matching private key, and prove it
 * decrypted by recovering its content.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> PublicKeyDecryptProbe \
 *        in.pdf keystore.p12 <keystorePassword> <alias>
 *
 * Loads the encrypted input through
 *   Loader.loadPDF(File, String password, InputStream keyStore, String alias)
 * — PDFBox reads the InputStream as a PKCS#12 KeyStore, looks up the private
 * key + certificate under <alias>, and decrypts the /Recipients envelope with
 * it. Then prints framed lines to stdout:
 *   PAGES:<n>
 *   PERMS:<currentAccessPermission.getPermissionBytes() as signed int>
 *   followed by the full PDFTextStripper text (UTF-8).
 *
 * The PERMS line surfaces the AccessPermission mask PDFBox recovered for the
 * opening recipient's own envelope, so a multi-recipient parity test can assert
 * each recipient sees their own distinct permission mask.
 *
 * A wrong key (keystore whose cert matches no recipient) makes loadPDF throw,
 * which exits non-zero — the parity test asserts on that for rejection. A
 * correct key lets a parity test compare the recovered page count + text
 * against pypdfbox's public-key encryption round-trip.
 */
public final class PublicKeyDecryptProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File in = new File(args[0]);
        File keystore = new File(args[1]);
        String keystorePassword = args[2];
        String alias = args[3];

        try (FileInputStream ksIn = new FileInputStream(keystore);
                PDDocument doc =
                        Loader.loadPDF(in, keystorePassword, ksIn, alias)) {
            out.print("PAGES:");
            out.print(doc.getNumberOfPages());
            out.print("\n");
            AccessPermission perms = doc.getCurrentAccessPermission();
            out.print("PERMS:");
            out.print(perms.getPermissionBytes());
            out.print("\n");
            out.print(new PDFTextStripper().getText(doc));
        }
    }
}
