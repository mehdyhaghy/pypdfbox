import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.common.PDMetadata;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.PDCryptFilterDictionary;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;
import org.apache.pdfbox.pdmodel.encryption.StandardProtectionPolicy;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for crypt-filter granularity + /EncryptMetadata parity.
 *
 * Sub-commands (first arg):
 *
 *   introspect <in.pdf> <password>
 *       Open an encrypted PDF and print, one per line:
 *         V:<int>            -- /V
 *         R:<int>            -- /R
 *         STMF:<name|->      -- /StmF (default stream crypt-filter name)
 *         STRF:<name|->      -- /StrF (default string crypt-filter name)
 *         CF:<name=cfm,...|-> -- each /CF entry as name=CFM (CFM "-" if absent)
 *         ENCRYPTMETA:<true|false> -- PDEncryption.isEncryptMetaData()
 *
 *   meta <in.pdf> <password>
 *       Open an encrypted PDF, decrypt it, and print:
 *         ENCRYPTMETA:<true|false>
 *         META:<base16 of the catalog /Metadata stream bytes, "-" if none>
 *         TEXT:<PDFTextStripper text>
 *
 *   encrypt-md-off <in.pdf> <out.pdf> <owner> <user> <keyBits> <preferAES>
 *       Encrypt with a StandardProtectionPolicy and then force
 *       /EncryptMetadata=false on the live /Encrypt dictionary BEFORE save,
 *       and mark the catalog /Metadata stream's /Filter to keep it cleartext
 *       via the /Identity crypt filter on a per-stream /Crypt entry. Used for
 *       the "Java encrypts metadata-off -> pypdfbox reads" direction.
 *
 * A wrong password makes Loader throw InvalidPasswordException (non-zero exit).
 */
public final class CryptFilterProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String cmd = args[0];
        switch (cmd) {
            case "introspect":
                introspect(out, args[1], args[2]);
                break;
            case "meta":
                meta(out, args[1], args[2]);
                break;
            case "encrypt-md-off":
                encryptMetadataOff(args);
                break;
            default:
                throw new IllegalArgumentException("unknown command: " + cmd);
        }
    }

    private static void introspect(PrintStream out, String in, String password)
            throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(in), password)) {
            PDEncryption enc = doc.getEncryption();
            out.print("V:");
            out.print(enc.getVersion());
            out.print("\n");
            out.print("R:");
            out.print(enc.getRevision());
            out.print("\n");
            out.print("STMF:");
            out.print(nameOrDash(enc.getStreamFilterName()));
            out.print("\n");
            out.print("STRF:");
            out.print(nameOrDash(enc.getStringFilterName()));
            out.print("\n");
            out.print("CF:");
            out.print(cfSummary(enc));
            out.print("\n");
            out.print("ENCRYPTMETA:");
            out.print(enc.isEncryptMetaData());
            out.print("\n");
        }
    }

    private static void meta(PrintStream out, String in, String password)
            throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(in), password)) {
            PDEncryption enc = doc.getEncryption();
            out.print("ENCRYPTMETA:");
            out.print(enc.isEncryptMetaData());
            out.print("\n");
            out.print("META:");
            PDMetadata md = doc.getDocumentCatalog().getMetadata();
            if (md == null) {
                out.print("-");
            } else {
                out.print(hex(readAll(md.exportXMPMetadata())));
            }
            out.print("\n");
            out.print("TEXT:");
            out.print(new PDFTextStripper().getText(doc));
        }
    }

    private static void encryptMetadataOff(String[] args) throws Exception {
        File in = new File(args[1]);
        File outFile = new File(args[2]);
        String ownerPw = args[3];
        String userPw = args[4];
        int keyLength = Integer.parseInt(args[5]);
        boolean preferAES = Boolean.parseBoolean(args[6]);

        try (PDDocument doc = Loader.loadPDF(in)) {
            AccessPermission perms = new AccessPermission();
            StandardProtectionPolicy policy =
                    new StandardProtectionPolicy(ownerPw, userPw, perms);
            policy.setEncryptionKeyLength(keyLength);
            policy.setPreferAES(preferAES);
            doc.protect(policy);

            // PDFBox 3.0.7's StandardProtectionPolicy has no setEncryptMetadata,
            // so flip the flag directly on the live /Encrypt dictionary. For
            // R6 (AES-256) the file-encryption key does NOT depend on this flag
            // (PDF 32000-2 Algorithm 2.A), so the doc stays decryptable. The
            // catalog /Metadata stream is given a per-stream /Crypt /Identity
            // override so PDFBox writes it in cleartext.
            PDEncryption enc = doc.getEncryption();
            enc.getCOSObject().setBoolean(COSName.ENCRYPT_META_DATA, false);

            PDMetadata md = doc.getDocumentCatalog().getMetadata();
            if (md != null) {
                COSDictionary streamDict = md.getCOSObject();
                // /Filter [/Crypt] + /DecodeParms [<< /Name /Identity >>]
                org.apache.pdfbox.cos.COSArray filters =
                        new org.apache.pdfbox.cos.COSArray();
                filters.add(COSName.getPDFName("Crypt"));
                org.apache.pdfbox.cos.COSArray parms =
                        new org.apache.pdfbox.cos.COSArray();
                COSDictionary cryptParm = new COSDictionary();
                cryptParm.setItem(COSName.getPDFName("Name"),
                        COSName.getPDFName("Identity"));
                parms.add(cryptParm);
                streamDict.setItem(COSName.FILTER, filters);
                streamDict.setItem(COSName.DECODE_PARMS, parms);
            }
            doc.save(outFile);
        }
    }

    private static String nameOrDash(COSName n) {
        return n == null ? "-" : n.getName();
    }

    private static String cfSummary(PDEncryption enc) {
        COSBase cfBase = enc.getCOSObject().getDictionaryObject(COSName.CF);
        if (!(cfBase instanceof COSDictionary)) {
            return "-";
        }
        COSDictionary cf = (COSDictionary) cfBase;
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        for (COSName key : cf.keySet()) {
            if (!first) {
                sb.append(",");
            }
            first = false;
            sb.append(key.getName());
            sb.append("=");
            PDCryptFilterDictionary cfd = enc.getCryptFilterDictionary(key);
            COSName cfm = cfd == null ? null
                    : (COSName) cfd.getCOSObject()
                            .getDictionaryObject(COSName.CFM);
            sb.append(cfm == null ? "-" : cfm.getName());
        }
        return sb.length() == 0 ? "-" : sb.toString();
    }

    private static byte[] readAll(InputStream is) throws Exception {
        try (InputStream in = is) {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) != -1) {
                bos.write(buf, 0, n);
            }
            return bos.toByteArray();
        }
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
