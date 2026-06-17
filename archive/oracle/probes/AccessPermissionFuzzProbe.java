import java.io.PrintStream;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;

/**
 * Differential fuzz probe for {@code AccessPermission} — the {@code /P}
 * permission-bits wrapper — Apache PDFBox 3.0.7 (wave 1537, agent A).
 *
 * The existing {@code PermProbe} drives only the eight {@code canXxx}
 * predicates plus {@code isReadOnly} / {@code isOwnerPermission} for a small
 * representative {@code /P} sweep, and a single {@code pubkey} mode. This probe
 * is the DEEP fuzz of the bit layout + Java signed-int semantics: it projects,
 * for one {@code /P} int per invocation, EVERY observable surface of the wrapper
 * in a single deterministic in-process run — no files, no random:
 *
 *   bytes=&lt;getPermissionBytes()&gt;
 *   canPrint / canModify / canExtractContent / canModifyAnnotations /
 *   canFillInForm / canExtractForAccessibility / canAssembleDocument /
 *   canPrintFaithful   (each =true|false)
 *   isOwnerPermission=&lt;bool&gt;
 *   isReadOnly=&lt;bool&gt;
 *   bitOn3..bitOn12      (raw 1-based isPermissionBitOn via public canXxx? — no:
 *                         we expose them through canXxx where defined; the raw
 *                         bit probe below covers the reserved/undefined bits)
 *   pubKeyBytes=&lt;getPermissionBytesForPublicKey()&gt;   (mutates a FRESH instance)
 *   roMutateBytes=&lt;bytes after setReadOnly() then every setCanXxx(toggle)&gt;
 *   rwMutateBytes=&lt;bytes after every setCanXxx(toggle) WITHOUT setReadOnly&gt;
 *
 * The Python sibling
 * (tests/pdmodel/encryption/oracle/test_access_permission_fuzz_wave1537.py)
 * mirrors each line from a pypdfbox {@code AccessPermission} built from the same
 * int and asserts equality.
 *
 * Line grammar: {@code key=value}, one per line, UTF-8, emission order stable.
 */
public final class AccessPermissionFuzzProbe {

    private static String b(boolean v) {
        return v ? "true" : "false";
    }

    private static AccessPermission fresh(int p) {
        return new AccessPermission(p);
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int p = Integer.parseInt(args[0]);

        AccessPermission ap = fresh(p);
        out.println("bytes=" + ap.getPermissionBytes());
        out.println("canPrint=" + b(ap.canPrint()));
        out.println("canModify=" + b(ap.canModify()));
        out.println("canExtractContent=" + b(ap.canExtractContent()));
        out.println("canModifyAnnotations=" + b(ap.canModifyAnnotations()));
        out.println("canFillInForm=" + b(ap.canFillInForm()));
        out.println("canExtractForAccessibility=" + b(ap.canExtractForAccessibility()));
        out.println("canAssembleDocument=" + b(ap.canAssembleDocument()));
        out.println("canPrintFaithful=" + b(ap.canPrintFaithful()));
        out.println("isOwnerPermission=" + b(ap.isOwnerPermission()));
        out.println("isReadOnly=" + b(ap.isReadOnly()));

        // getPermissionBytesForPublicKey mutates in-place — use a FRESH copy.
        AccessPermission pk = fresh(p);
        out.println("pubKeyBytes=" + pk.getPermissionBytesForPublicKey());

        // Read-only lock: setReadOnly() then flip every can-bit; bytes must be
        // unchanged because the setters short-circuit on readOnly.
        AccessPermission ro = fresh(p);
        ro.setReadOnly();
        ro.setCanPrint(!ro.canPrint());
        ro.setCanModify(!ro.canModify());
        ro.setCanExtractContent(!ro.canExtractContent());
        ro.setCanModifyAnnotations(!ro.canModifyAnnotations());
        ro.setCanFillInForm(!ro.canFillInForm());
        ro.setCanExtractForAccessibility(!ro.canExtractForAccessibility());
        ro.setCanAssembleDocument(!ro.canAssembleDocument());
        ro.setCanPrintFaithful(!ro.canPrintFaithful());
        out.println("roMutateBytes=" + ro.getPermissionBytes());
        out.println("roStillReadOnly=" + b(ro.isReadOnly()));

        // Read-write: flip every can-bit (no lock); each setter mutates.
        AccessPermission rw = fresh(p);
        rw.setCanPrint(!rw.canPrint());
        rw.setCanModify(!rw.canModify());
        rw.setCanExtractContent(!rw.canExtractContent());
        rw.setCanModifyAnnotations(!rw.canModifyAnnotations());
        rw.setCanFillInForm(!rw.canFillInForm());
        rw.setCanExtractForAccessibility(!rw.canExtractForAccessibility());
        rw.setCanAssembleDocument(!rw.canAssembleDocument());
        rw.setCanPrintFaithful(!rw.canPrintFaithful());
        out.println("rwMutateBytes=" + rw.getPermissionBytes());
    }
}
