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
 * Live oracle probe for crypt-filter ROUTING parity — the per-string-vs-
 * per-stream dispatch of /StmF and /StrF, and the /Identity pass-through.
 *
 * Wave 1427's CryptFilterProbe covered /CF names, /CFM values and
 * /EncryptMetadata. This probe targets the routing facet not covered there:
 * a document where /StmF and /StrF point at *different* crypt filters (one
 * /StdCF, the other /Identity), and we confirm each object type is
 * enciphered or left cleartext according to its slot. On-the-wire
 * cleartext/ciphertext is asserted on the Python side (which controls the
 * disk markers); the Java side proves it can READ the mixed-routing file and
 * recover content, and reports the routing names + the decrypted probe
 * string for byte-equality with pypdfbox.
 *
 * Sub-commands (first arg):
 *
 *   encrypt-mixed <in.pdf> <out.pdf> <owner> <user> <keyBits> <preferAES>
 *                 <stmf> <strf>
 *       Encrypt with a StandardProtectionPolicy, stamp a probe string
 *       /CryptRoutingStr into the catalog, then override /StmF and /StrF on
 *       the live /Encrypt dictionary to the requested names ("StdCF" /
 *       "Identity") before save. PDFBox 3.0.7's policy always installs StdCF
 *       for both; flipping a slot to /Identity after protect() is lossless
 *       for R4 (AES-128) and R6 (AES-256) because the file-encryption key
 *       does not depend on /StmF / /StrF. The result is a genuine
 *       mixed-routing document the pypdfbox reader must honour.
 *
 *   inspect <in.pdf> <password>
 *       Open an encrypted PDF and print, one per line:
 *         STMF:<name|->
 *         STRF:<name|->
 *         STRING_VALUE:<base16 of decrypted /CryptRoutingStr, or ->
 *         PAGES:<n>
 *         TEXT:<extracted text>
 */
public final class CryptRoutingProbe {
    private static final COSName CRYPT_ROUTING_STR =
            COSName.getPDFName("CryptRoutingStr");
    private static final COSName STM_F = COSName.getPDFName("StmF");
    private static final COSName STR_F = COSName.getPDFName("StrF");

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String cmd = args[0];
        switch (cmd) {
            case "encrypt-mixed":
                encryptMixed(args);
                break;
            case "inspect":
                inspect(out, args[1], args[2]);
                break;
            default:
                throw new IllegalArgumentException("unknown command: " + cmd);
        }
    }

    private static void encryptMixed(String[] args) throws Exception {
        File in = new File(args[1]);
        File outFile = new File(args[2]);
        String ownerPw = args[3];
        String userPw = args[4];
        int keyLength = Integer.parseInt(args[5]);
        boolean preferAES = Boolean.parseBoolean(args[6]);
        String stmf = args[7];
        String strf = args[8];

        try (PDDocument doc = Loader.loadPDF(in)) {
            // Stamp a probe string into the catalog so the routing of /StrF
            // is observable independently of the page content stream (/StmF).
            doc.getDocumentCatalog().getCOSObject().setItem(
                    CRYPT_ROUTING_STR,
                    new COSString("CryptRoutingStringMarker1439"));

            AccessPermission perms = new AccessPermission();
            StandardProtectionPolicy policy =
                    new StandardProtectionPolicy(ownerPw, userPw, perms);
            policy.setEncryptionKeyLength(keyLength);
            policy.setPreferAES(preferAES);
            doc.protect(policy);

            // Override the default-filter routing on the live /Encrypt dict.
            // For R4/R6 the file key is independent of these names, so the
            // document stays decryptable while the slots now disagree.
            PDEncryption enc = doc.getEncryption();
            COSDictionary encDict = enc.getCOSObject();
            encDict.setItem(STM_F, COSName.getPDFName(stmf));
            encDict.setItem(STR_F, COSName.getPDFName(strf));

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
                    .getDictionaryObject(CRYPT_ROUTING_STR);
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
