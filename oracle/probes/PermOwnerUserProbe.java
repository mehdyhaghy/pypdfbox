import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;

/**
 * Live oracle probe for the OWNER-vs-USER access-permission split that
 * {@code StandardSecurityHandler#prepareForDecryption} applies, plus the raw
 * {@code /P} integer the encrypt dictionary carries on the wire.
 *
 * The sibling PermProbe pins the pure {@code AccessPermission(int)} bit decode
 * and a predicate-only round-trip. This probe pins the three values that decode
 * test deliberately excludes:
 *
 *   - the RAW {@code getPermissionBytes()} integer of the
 *     {@code getCurrentAccessPermission()} object (signed two's-complement /P);
 *   - {@code isReadOnly()} — true only when the USER password authenticated
 *     (the policy is already applied, so the live view is locked);
 *   - {@code isOwnerPermission()} — true only when the OWNER password
 *     authenticated (full DEFAULT bits regardless of /P).
 *
 * Per PDF 32000-1 §7.6.4.4 / PDFBox, when the OWNER password unlocks a doc the
 * handler installs {@code AccessPermission.getOwnerAccessPermission()} (all
 * DEFAULT bits, raw bytes 0xFFFFFFFC = -4, NOT read-only); when the USER
 * password unlocks it the handler installs {@code new AccessPermission(/P)}
 * with {@code setReadOnly()} applied (raw bytes == the /P value, read-only).
 *
 * Sub-command:
 *
 *   inspect <encrypted.pdf> <password>
 *       Print, one per line:
 *         WIRE_P:<int>          -- /Encrypt /P as PDEncryption.getPermissions()
 *         CUR_BYTES:<int>       -- getCurrentAccessPermission().getPermissionBytes()
 *         CUR_READONLY:<bool>   -- getCurrentAccessPermission().isReadOnly()
 *         CUR_OWNER:<bool>      -- getCurrentAccessPermission().isOwnerPermission()
 *
 * A wrong password makes Loader throw InvalidPasswordException (non-zero exit),
 * surfaced via the harness's CalledProcessError contract.
 */
public final class PermOwnerUserProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String cmd = args[0];
        if ("inspect".equals(cmd)) {
            File in = new File(args[1]);
            String password = args.length > 2 ? args[2] : "";
            try (PDDocument doc = Loader.loadPDF(in, password)) {
                PDEncryption enc = doc.getEncryption();
                int wireP = enc != null ? enc.getPermissions() : 0;
                AccessPermission ap = doc.getCurrentAccessPermission();
                out.println("WIRE_P:" + wireP);
                out.println("CUR_BYTES:" + ap.getPermissionBytes());
                out.println("CUR_READONLY:" + ap.isReadOnly());
                out.println("CUR_OWNER:" + ap.isOwnerPermission());
            }
            return;
        }
        throw new IllegalArgumentException("unknown command: " + cmd);
    }
}
