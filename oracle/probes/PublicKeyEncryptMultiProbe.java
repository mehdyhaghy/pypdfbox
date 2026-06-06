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
 * (certificate) security handler for ONE OR MORE recipients, each carrying its
 * own permission mask.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> PublicKeyEncryptMultiProbe \
 *        in.pdf out.pdf <keyLengthBits> <preferAES:true|false> \
 *        <certDer1> <permInt1> [<certDer2> <permInt2> ...]
 *
 * Each (certDerN, permIntN) pair becomes a PublicKeyRecipient with the supplied
 * X.509 certificate (DER-encoded) and an AccessPermission seeded from the signed
 * 32-bit integer permIntN (AccessPermission(int) constructor). Recipients are
 * added to the policy in argument order — pinning the one-envelope-per-recipient
 * order against pypdfbox's write path.
 *
 * Algorithm mapping matches PublicKeyEncryptProbe / pypdfbox
 * compute_version_number:
 *   128, true  -> AES-128 (V=4, R=4)
 *   256, *     -> AES-256 (V=5, R=6)
 */
public final class PublicKeyEncryptMultiProbe {
    public static void main(String[] args) throws Exception {
        File in = new File(args[0]);
        File out = new File(args[1]);
        int keyLength = Integer.parseInt(args[2]);
        boolean preferAES = Boolean.parseBoolean(args[3]);

        PublicKeyProtectionPolicy policy = new PublicKeyProtectionPolicy();

        CertificateFactory cf = CertificateFactory.getInstance("X.509");
        for (int i = 4; i + 1 < args.length; i += 2) {
            File certFile = new File(args[i]);
            int permInt = Integer.parseInt(args[i + 1]);
            X509Certificate cert;
            try (FileInputStream certIn = new FileInputStream(certFile)) {
                cert = (X509Certificate) cf.generateCertificate(certIn);
            }
            AccessPermission perms = new AccessPermission(permInt);
            PublicKeyRecipient recipient = new PublicKeyRecipient();
            recipient.setX509(cert);
            recipient.setPermission(perms);
            policy.addRecipient(recipient);
        }

        policy.setEncryptionKeyLength(keyLength);
        policy.setPreferAES(preferAES);

        try (PDDocument doc = Loader.loadPDF(in)) {
            doc.protect(policy);
            doc.save(out);
        }
    }
}
