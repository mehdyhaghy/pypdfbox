import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;

/**
 * Live oracle probe: emit Apache PDFBox's AccessPermission predicate decode.
 *
 * Two modes, selected by the first argv token:
 *
 *   decode <pInt>
 *       Construct {@code new AccessPermission(pInt)} and print every predicate
 *       as a canonical {@code name=true|false} line. Used to parity-check the
 *       pure /P bit decode independent of any file.
 *
 *   readback <file.pdf> <password>
 *       Open the (password-)encrypted PDF, fetch
 *       {@code doc.getCurrentAccessPermission()}, and print the same predicate
 *       lines. Used to confirm a /P value WRITTEN by pypdfbox is read back by
 *       PDFBox with the same bits.
 *
 * Output is a stable, sorted-by-emission set of {@code predicate=bool} lines
 * (UTF-8, one per line, no extra framing) plus the raw {@code permissionBytes}.
 */
public final class PermProbe {
    private static void emit(PrintStream out, AccessPermission ap) {
        out.println("permissionBytes=" + ap.getPermissionBytes());
        out.println("canPrint=" + ap.canPrint());
        out.println("canModify=" + ap.canModify());
        out.println("canExtractContent=" + ap.canExtractContent());
        out.println("canFillInForm=" + ap.canFillInForm());
        out.println("canAssembleDocument=" + ap.canAssembleDocument());
        out.println("canPrintFaithful=" + ap.canPrintFaithful());
        out.println("canExtractForAccessibility=" + ap.canExtractForAccessibility());
        out.println("canModifyAnnotations=" + ap.canModifyAnnotations());
        out.println("isReadOnly=" + ap.isReadOnly());
        out.println("isOwnerPermission=" + ap.isOwnerPermission());
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("decode".equals(mode)) {
            int p = Integer.parseInt(args[1]);
            emit(out, new AccessPermission(p));
        } else if ("readback".equals(mode)) {
            File in = new File(args[1]);
            String password = args.length > 2 ? args[2] : "";
            try (PDDocument doc = Loader.loadPDF(in, password)) {
                emit(out, doc.getCurrentAccessPermission());
            }
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }
}
