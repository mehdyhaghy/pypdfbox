import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;
import org.apache.pdfbox.pdmodel.encryption.StandardProtectionPolicy;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the ``/StrF`` defaults-to-``/Identity`` rule
 * (PDF 32000-1 §7.6.4.4 Table 20). When ``/Encrypt`` declares ``/V 4`` (or
 * ``/V 5``) with ``/StmF /StdCF`` but omits ``/StrF``, the spec says
 * strings stay cleartext (``/Identity`` cipher); only stream bodies are
 * enciphered through ``/StdCF``. Companion to ``CryptRoutingProbe`` (wave
 * 1439, mixed routing where BOTH ``/StmF`` and ``/StrF`` are explicit) —
 * this probe targets the *absent-slot default* facet not covered there.
 *
 * Sub-commands:
 *
 *   encrypt-strf-absent <in.pdf> <out.pdf> <owner> <user>
 *                       <keyBits> <preferAES>
 *       Encrypt the input with a StandardProtectionPolicy, stamp a probe
 *       string ``/StrFDefaultMarker`` into the catalog, then REMOVE the
 *       ``/StrF`` entry from the live ``/Encrypt`` dict before saving.
 *       PDFBox 3.0.7's writer re-stamps both ``/StmF`` and ``/StrF`` at
 *       save time even after a post-protect patch (verified — see
 *       wave 1439's CryptRoutingProbe note), so the absent-/StrF file is
 *       authored by pypdfbox instead; this Java sub-command exists for
 *       symmetry and so a future PDFBox release with a writer-side seam
 *       has a probe ready.
 *
 *   inspect <in.pdf> <password>
 *       Open an encrypted PDF and print, one field per line:
 *         STMF:<name|->
 *         STRF:<name|->            — Apache's getStringFilterName() coerces
 *                                    an absent /StrF to Identity, so this
 *                                    reads ``Identity`` for the spec default.
 *         STRING_VALUE:<base16 of decrypted /StrFDefaultMarker, or ->
 *         PAGES:<n>
 *         TEXT:<page text>
 */
public final class StrFDefaultProbe {
    private static final COSName MARKER_KEY =
            COSName.getPDFName("StrFDefaultMarker");
    private static final COSName STM_F = COSName.getPDFName("StmF");
    private static final COSName STR_F = COSName.getPDFName("StrF");

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String cmd = args[0];
        switch (cmd) {
            case "encrypt-strf-absent":
                encryptStrFAbsent(args);
                break;
            case "inspect":
                inspect(out, args[1], args[2]);
                break;
            default:
                throw new IllegalArgumentException("unknown command: " + cmd);
        }
    }

    private static void encryptStrFAbsent(String[] args) throws Exception {
        File in = new File(args[1]);
        File outFile = new File(args[2]);
        String ownerPw = args[3];
        String userPw = args[4];
        int keyLength = Integer.parseInt(args[5]);
        boolean preferAES = Boolean.parseBoolean(args[6]);

        try (PDDocument doc = Loader.loadPDF(in)) {
            doc.getDocumentCatalog().getCOSObject().setItem(
                    MARKER_KEY,
                    new COSString("StrFDefaultMarker1451"));
            AccessPermission perms = new AccessPermission();
            StandardProtectionPolicy policy =
                    new StandardProtectionPolicy(ownerPw, userPw, perms);
            policy.setEncryptionKeyLength(keyLength);
            policy.setPreferAES(preferAES);
            doc.protect(policy);
            PDEncryption enc = doc.getEncryption();
            COSDictionary encDict = enc.getCOSObject();
            // Remove /StrF so the absent-slot default rule kicks in. PDFBox
            // 3.0.7's writer re-stamps it at save anyway (kept for symmetry).
            encDict.removeItem(STR_F);
            encDict.setItem(STM_F, COSName.getPDFName("StdCF"));
            doc.save(outFile);
        }
    }

    private static void inspect(PrintStream out, String in, String password)
            throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(in), password)) {
            PDEncryption enc = doc.getEncryption();
            out.print("STMF:");
            out.print(nameOrDash(enc.getStreamFilterName()));
            out.print("\n");
            out.print("STRF:");
            out.print(nameOrDash(enc.getStringFilterName()));
            out.print("\n");

            COSBase strVal = doc.getDocumentCatalog().getCOSObject()
                    .getDictionaryObject(MARKER_KEY);
            out.print("STRING_VALUE:");
            if (strVal instanceof COSString) {
                out.print(hex(((COSString) strVal).getBytes()));
            } else {
                out.print("-");
            }
            out.print("\n");
            out.print("PAGES:");
            out.print(doc.getNumberOfPages());
            out.print("\n");
            out.print("TEXT:");
            out.print(new PDFTextStripper().getText(doc));
        }
    }

    private static String nameOrDash(COSName n) {
        return n == null ? "-" : n.getName();
    }

    private static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder(data.length * 2);
        for (byte b : data) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }
}
