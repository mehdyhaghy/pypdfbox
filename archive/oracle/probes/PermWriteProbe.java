import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;
import org.apache.pdfbox.pdmodel.encryption.StandardProtectionPolicy;

/**
 * Live oracle probe for the encryption-permission WRITE round-trip.
 *
 * The sibling EncryptProbe always writes the DEFAULT (all-allowed)
 * AccessPermission, and PermOwnerUserProbe only READS a file pypdfbox wrote.
 * This probe pins the missing surface: Apache PDFBox WRITING a deliberately
 * RESTRICTED permission set, so a parity test can prove pypdfbox writes the
 * byte-identical {@code /Encrypt /P} integer (and that each side reads the
 * other's restricted /P back to the same predicates) — across both AES-128 V4
 * and AES-256 R6.
 *
 * The restricted set is fixed and identical to the Python helper:
 *   setCanPrint(false)            -- bit 3 off
 *   setCanModify(false)           -- bit 4 off
 *   setCanExtractContent(false)   -- bit 5 off
 *   setCanFillInForm(false)       -- bit 9 off
 *   setCanPrintFaithful(false)    -- bit 12 off (degraded print only)
 *   setCanModifyAnnotations(true) -- bit 6 on
 *   setCanExtractForAccessibility(true) -- bit 10 on
 *   setCanAssembleDocument(true)  -- bit 11 on
 *
 * Sub-commands:
 *
 *   write <in.pdf> <out.pdf> <ownerPw> <userPw> <keyLenBits> <preferAES>
 *       Apply the restricted policy and save out.pdf. No stdout framing.
 *
 *   wirep <file.pdf> <password>
 *       Open the encrypted file and print, one per line:
 *         WIRE_P:<int>      -- PDEncryption.getPermissions() (raw /Encrypt /P)
 *         then every predicate of {@code new AccessPermission(WIRE_P)} as
 *         {@code <name>=<bool>}. This decodes the on-disk /P independent of
 *         which password authenticated, so it is the canonical WRITE round-trip
 *         view (no owner-bit upgrade, no readOnly).
 *
 * Algorithm mapping matches pypdfbox compute_revision_number:
 *   128, true  -> AES-128 (V4/R4); 256, * -> AES-256 (V5/R6).
 */
public final class PermWriteProbe {

    private static AccessPermission restricted() {
        AccessPermission ap = new AccessPermission();
        ap.setCanPrint(false);
        ap.setCanModify(false);
        ap.setCanExtractContent(false);
        ap.setCanFillInForm(false);
        ap.setCanPrintFaithful(false);
        ap.setCanModifyAnnotations(true);
        ap.setCanExtractForAccessibility(true);
        ap.setCanAssembleDocument(true);
        return ap;
    }

    private static void emitPredicates(PrintStream out, int wireP) {
        AccessPermission ap = new AccessPermission(wireP);
        out.println("WIRE_P:" + wireP);
        out.println("canPrint=" + ap.canPrint());
        out.println("canModify=" + ap.canModify());
        out.println("canExtractContent=" + ap.canExtractContent());
        out.println("canModifyAnnotations=" + ap.canModifyAnnotations());
        out.println("canFillInForm=" + ap.canFillInForm());
        out.println("canExtractForAccessibility=" + ap.canExtractForAccessibility());
        out.println("canAssembleDocument=" + ap.canAssembleDocument());
        out.println("canPrintFaithful=" + ap.canPrintFaithful());
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String cmd = args[0];
        if ("write".equals(cmd)) {
            File in = new File(args[1]);
            File outFile = new File(args[2]);
            String ownerPw = args[3];
            String userPw = args[4];
            int keyLength = Integer.parseInt(args[5]);
            boolean preferAES = Boolean.parseBoolean(args[6]);
            try (PDDocument doc = Loader.loadPDF(in)) {
                StandardProtectionPolicy policy =
                        new StandardProtectionPolicy(ownerPw, userPw, restricted());
                policy.setEncryptionKeyLength(keyLength);
                policy.setPreferAES(preferAES);
                doc.protect(policy);
                doc.save(outFile);
            }
            return;
        }
        if ("wirep".equals(cmd)) {
            File in = new File(args[1]);
            String password = args.length > 2 ? args[2] : "";
            try (PDDocument doc = Loader.loadPDF(in, password)) {
                PDEncryption enc = doc.getEncryption();
                int wireP = enc != null ? enc.getPermissions() : 0;
                emitPredicates(out, wireP);
            }
            return;
        }
        throw new IllegalArgumentException("unknown command: " + cmd);
    }
}
