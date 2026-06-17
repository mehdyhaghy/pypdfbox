import java.io.File;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.StandardProtectionPolicy;

/**
 * Live oracle probe: encrypt a PDF with Apache PDFBox's StandardSecurityHandler.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> EncryptProbe \
 *        in.pdf out.pdf <ownerPw> <userPw> <keyLengthBits> <preferAES:true|false>
 *
 * Loads the plaintext input, applies a StandardProtectionPolicy with the given
 * owner/user passwords and the default (all-allowed) AccessPermission, selects
 * the algorithm via (keyLengthBits, preferAES) exactly as a PDFBox app would,
 * and writes the encrypted result. No stdout framing. A parity test then asks
 * pypdfbox to open out.pdf with userPw / ownerPw and recover the same content.
 *
 * Algorithm mapping (matches pypdfbox compute_revision_number):
 *   40,  false -> RC4-40  (R2)
 *   128, false -> RC4-128 (R3)
 *   128, true  -> AES-128 (R4)
 *   256, *     -> AES-256 (R6)
 */
public final class EncryptProbe {
    public static void main(String[] args) throws Exception {
        File in = new File(args[0]);
        File out = new File(args[1]);
        String ownerPw = args[2];
        String userPw = args[3];
        int keyLength = Integer.parseInt(args[4]);
        boolean preferAES = Boolean.parseBoolean(args[5]);

        try (PDDocument doc = Loader.loadPDF(in)) {
            AccessPermission perms = new AccessPermission();
            StandardProtectionPolicy policy =
                    new StandardProtectionPolicy(ownerPw, userPw, perms);
            policy.setEncryptionKeyLength(keyLength);
            policy.setPreferAES(preferAES);
            doc.protect(policy);
            doc.save(out);
        }
    }
}
