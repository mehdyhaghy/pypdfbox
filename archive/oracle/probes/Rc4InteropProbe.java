import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;
import org.apache.pdfbox.pdmodel.encryption.StandardProtectionPolicy;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for RC4 (revisions 2 &amp; 3) standard-security interop.
 *
 * The generic EncryptProbe / DecryptProbe cover RC4 round-trips with an
 * all-allowed permission set, but they do not (a) write a *restrictive*
 * permission set, (b) accept an empty user password (owner-only protection),
 * or (c) report the on-the-wire /V, /R, /Length and /P values a reader sees.
 * This RC4-specific probe fills those gaps so a parity test can assert the
 * exact revision / key-length / permission bits — not merely that the content
 * round-trips.
 *
 * Modes (first argv token):
 *
 *   encrypt &lt;in.pdf&gt; &lt;out.pdf&gt; &lt;ownerPw&gt; &lt;userPw&gt; &lt;keyBits&gt; &lt;restrict&gt;
 *       Load the plaintext input and apply a StandardProtectionPolicy at the
 *       given RC4 key length (40 -&gt; R2, 128 -&gt; R3; preferAES is always
 *       false here). When &lt;restrict&gt; is "true" the permission set denies
 *       modify / content-extraction / annotation-edit / assembly while keeping
 *       print + form-fill + accessibility-extraction; otherwise all-allowed.
 *       An empty userPw ("") yields owner-only protection (opens with no
 *       password). Saves the encrypted result. No stdout.
 *
 *   inspect &lt;in.pdf&gt; &lt;password&gt;
 *       Open the encrypted PDF with the supplied password (empty allowed) and
 *       print, one per line:
 *         V:&lt;int&gt;            -- /V
 *         R:&lt;int&gt;            -- /R
 *         LENGTH:&lt;int&gt;       -- /Length (key length in bits)
 *         P:&lt;int&gt;            -- getCurrentAccessPermission().getPermissionBytes()
 *         PAGES:&lt;int&gt;        -- page count (proves the body decrypted)
 *         TEXT:&lt;PDFTextStripper text&gt;  (UTF-8, trailing — everything after the
 *                                       "TEXT:" marker is the stripped text)
 *       A wrong password makes Loader throw InvalidPasswordException -&gt;
 *       non-zero exit, which a parity test uses to assert rejection.
 */
public final class Rc4InteropProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("encrypt".equals(mode)) {
            encrypt(args);
        } else if ("inspect".equals(mode)) {
            inspect(out, args[1], args.length > 2 ? args[2] : "");
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void encrypt(String[] args) throws Exception {
        File in = new File(args[1]);
        File outFile = new File(args[2]);
        String ownerPw = args[3];
        String userPw = args[4];
        int keyLength = Integer.parseInt(args[5]);
        boolean restrict = Boolean.parseBoolean(args[6]);

        try (PDDocument doc = Loader.loadPDF(in)) {
            AccessPermission perms = new AccessPermission();
            if (restrict) {
                perms.setCanModify(false);
                perms.setCanExtractContent(false);
                perms.setCanModifyAnnotations(false);
                perms.setCanAssembleDocument(false);
                perms.setCanPrint(true);
                perms.setCanFillInForm(true);
                perms.setCanExtractForAccessibility(true);
                perms.setCanPrintFaithful(true);
            }
            StandardProtectionPolicy policy =
                    new StandardProtectionPolicy(ownerPw, userPw, perms);
            policy.setEncryptionKeyLength(keyLength);
            policy.setPreferAES(false);
            doc.protect(policy);
            doc.save(outFile);
        }
    }

    private static void inspect(PrintStream out, String in, String password)
            throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(in), password)) {
            PDEncryption enc = doc.getEncryption();
            AccessPermission ap = doc.getCurrentAccessPermission();
            out.print("V:");
            out.print(enc.getVersion());
            out.print("\n");
            out.print("R:");
            out.print(enc.getRevision());
            out.print("\n");
            out.print("LENGTH:");
            out.print(enc.getLength());
            out.print("\n");
            out.print("P:");
            out.print(ap.getPermissionBytes());
            out.print("\n");
            out.print("PAGES:");
            out.print(doc.getNumberOfPages());
            out.print("\n");
            out.print("TEXT:");
            out.print(new PDFTextStripper().getText(doc));
        }
    }
}
