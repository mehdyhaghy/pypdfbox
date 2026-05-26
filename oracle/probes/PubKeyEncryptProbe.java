import java.io.File;
import java.io.FileInputStream;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.PublicKeyProtectionPolicy;
import org.apache.pdfbox.pdmodel.encryption.PublicKeyRecipient;

/**
 * Live oracle probe: encrypt a PDF with Apache PDFBox's public-key
 * (certificate) security handler.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> PubKeyEncryptProbe \
 *        in.pdf out.pdf certDer.der <keyLengthBits> <preferAES:true|false>
 *
 * Loads the plaintext input, builds a PublicKeyProtectionPolicy with one
 * PublicKeyRecipient holding the supplied X.509 certificate (DER-encoded) and
 * the default (all-allowed) AccessPermission, selects the algorithm via
 * (keyLengthBits, preferAES) exactly as a PDFBox app would, and writes the
 * /Adobe.PubSec-encrypted result. No stdout framing. A parity test then asks
 * pypdfbox to open out.pdf with the matching private key and recover the same
 * content.
 *
 * Algorithm mapping (matches pypdfbox compute_version_number):
 *   128, true  -> AES-128 (V=4, R=4)
 *   256, *     -> AES-256 (V=5, R=6)
 *   128, false -> RC4-128 (V=2, R=3)
 *   40,  false -> RC4-40  (V=1, R=2)
 */
public final class PubKeyEncryptProbe {
    public static void main(String[] args) throws Exception {
        File in = new File(args[0]);
        File out = new File(args[1]);
        File certFile = new File(args[2]);
        int keyLength = Integer.parseInt(args[3]);
        boolean preferAES = Boolean.parseBoolean(args[4]);

        X509Certificate cert;
        try (FileInputStream certIn = new FileInputStream(certFile)) {
            CertificateFactory cf = CertificateFactory.getInstance("X.509");
            cert = (X509Certificate) cf.generateCertificate(certIn);
        }

        try (PDDocument doc = Loader.loadPDF(in)) {
            AccessPermission perms = new AccessPermission();
            PublicKeyRecipient recipient = new PublicKeyRecipient();
            recipient.setX509(cert);
            recipient.setPermission(perms);

            PublicKeyProtectionPolicy policy = new PublicKeyProtectionPolicy();
            policy.addRecipient(recipient);
            policy.setEncryptionKeyLength(keyLength);
            policy.setPreferAES(preferAES);

            doc.protect(policy);
            doc.save(out);
        }
    }
}
