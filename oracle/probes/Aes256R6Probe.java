import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;
import org.apache.pdfbox.pdmodel.encryption.StandardProtectionPolicy;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the AES-256 (V5/R6) standard security handler — the
 * deep facets a basic round-trip does not exercise: the /Perms validation
 * block, the R6 Algorithm 2.B hardened hash with multi-byte passwords, and the
 * owner-only open path. Two modes, selected by argv[0]:
 *
 *   encrypt <in.pdf> <out.pdf> <ownerPw> <userPw> <pInt>
 *       Load the plaintext input, build a StandardProtectionPolicy at 256-bit
 *       (preferAES) with an AccessPermission derived from <pInt>, protect +
 *       save. PDFBox writes V=5/R=6 with /O /U /OE /UE and the /Perms block
 *       (EncryptMetadata defaults to true, so the /Perms byte 8 is 'T'). A
 *       parity test then opens out.pdf with pypdfbox and checks key recovery +
 *       /Perms validation.
 *
 *   inspect <in.pdf> <password>
 *       Open a (pypdfbox- or PDFBox-) encrypted V5/R6 file with PDFBox and emit
 *       a stable, framed report of everything an R6 reader validates:
 *         V:<n>
 *         R:<n>
 *         LENGTH:<bits>
 *         OWNER_AUTH:<true|false>     (did the owner password authenticate?)
 *         PERMS_INT:<signed /P>
 *         CAN_PRINT:<bool> ... (each AccessPermission predicate)
 *         PAGES:<n>
 *         TEXT:<full PDFTextStripper text>
 *       PDFBox validates /Perms internally during load (Algorithm 13); a /Perms
 *       that fails to decrypt-and-match makes PDFBox log a warning but still
 *       open, so we additionally surface OWNER_AUTH + the decoded permission
 *       bits so a parity test can confirm pypdfbox wrote a /Perms PDFBox honors.
 *       A wrong password throws InvalidPasswordException (non-zero exit).
 */
public final class Aes256R6Probe {

    private static void encrypt(String[] args) throws Exception {
        File in = new File(args[1]);
        File out = new File(args[2]);
        String ownerPw = args[3];
        String userPw = args[4];
        int pInt = Integer.parseInt(args[5]);

        try (PDDocument doc = Loader.loadPDF(in)) {
            AccessPermission perms = new AccessPermission(pInt);
            StandardProtectionPolicy policy =
                    new StandardProtectionPolicy(ownerPw, userPw, perms);
            policy.setEncryptionKeyLength(256);
            policy.setPreferAES(true);
            doc.protect(policy);
            doc.save(out);
        }
    }

    private static void inspect(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File in = new File(args[1]);
        String password = args.length > 2 ? args[2] : "";
        try (PDDocument doc = Loader.loadPDF(in, password)) {
            PDEncryption enc = doc.getEncryption();
            AccessPermission ap = doc.getCurrentAccessPermission();
            out.println("V:" + enc.getVersion());
            out.println("R:" + enc.getRevision());
            out.println("LENGTH:" + enc.getLength());
            // Owner auth grants the all-permissions owner AccessPermission;
            // user auth yields a read-only-flagged restricted set. PDFBox marks
            // the owner case via isOwnerPermission().
            out.println("OWNER_AUTH:" + ap.isOwnerPermission());
            out.println("PERMS_INT:" + ap.getPermissionBytes());
            out.println("CAN_PRINT:" + ap.canPrint());
            out.println("CAN_MODIFY:" + ap.canModify());
            out.println("CAN_EXTRACT:" + ap.canExtractContent());
            out.println("CAN_FILLFORM:" + ap.canFillInForm());
            out.println("CAN_ASSEMBLE:" + ap.canAssembleDocument());
            out.println("CAN_PRINT_FAITHFUL:" + ap.canPrintFaithful());
            out.println("CAN_EXTRACT_ACCESSIBILITY:" + ap.canExtractForAccessibility());
            out.println("CAN_MODIFY_ANNOT:" + ap.canModifyAnnotations());
            out.println("PAGES:" + doc.getNumberOfPages());
            out.print("TEXT:");
            out.print(new PDFTextStripper().getText(doc));
        }
    }

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        if ("encrypt".equals(mode)) {
            encrypt(args);
        } else if ("inspect".equals(mode)) {
            inspect(args);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }
}
