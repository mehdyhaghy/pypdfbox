import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;
import org.apache.pdfbox.pdmodel.encryption.StandardProtectionPolicy;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the "empty / null owner password defaults to user
 * password" branch of Apache PDFBox's StandardSecurityHandler.
 *
 * Three subcommands, dispatched on argv[0]:
 *
 *   ENCRYPT <in> <out> <ownerPw> <userPw> <keyLengthBits> <preferAES>
 *     Encrypts <in> to <out>. The sentinel "__NULL__" maps the matching
 *     password argument to a Java ``null`` reference (passing null on the
 *     command line is otherwise impossible). Anything else is taken as-is,
 *     including the empty string "" — which is exactly what we want to
 *     exercise the "owner empty → defaults to user" branch in
 *     StandardSecurityHandler#prepareDocumentForEncryption (PDFBox 3.0.7
 *     line ~116 of the decompiled bytecode: ``if (ownerPw.isEmpty())
 *     ownerPw = userPw;``).
 *
 *   DECRYPT <in> <password>
 *     Opens <in> with the supplied password and prints the same
 *     PAGES:<n>\\n<text> framing as DecryptProbe. A wrong password exits
 *     non-zero (InvalidPasswordException).
 *
 *   DUMP <in> <password>
 *     Opens <in> with the supplied password, then prints the encryption
 *     dictionary's raw /O and /U byte strings as hex on two lines:
 *       O:<hex>
 *       U:<hex>
 *     followed by V:<int>\\nR:<int>\\nLEN:<int>. The hex framing makes /O
 *     comparison between engines deterministic across newline / binary
 *     bytes. /OE and /UE are added (when present, R>=5) on lines
 *     OE:<hex>\\nUE:<hex>.
 *
 * No stdout framing beyond the labelled lines documented above; stderr is
 * unused. The parity test on the Python side parses the framed lines.
 */
public final class DefaultOwnerProbe {
    private static final String NULL_SENTINEL = "__NULL__";

    private static String coerce(String raw) {
        return NULL_SENTINEL.equals(raw) ? null : raw;
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("ENCRYPT".equals(mode)) {
            File in = new File(args[1]);
            File outFile = new File(args[2]);
            String ownerPw = coerce(args[3]);
            String userPw = coerce(args[4]);
            int keyLength = Integer.parseInt(args[5]);
            boolean preferAES = Boolean.parseBoolean(args[6]);
            try (PDDocument doc = Loader.loadPDF(in)) {
                AccessPermission perms = new AccessPermission();
                StandardProtectionPolicy policy =
                        new StandardProtectionPolicy(ownerPw, userPw, perms);
                policy.setEncryptionKeyLength(keyLength);
                policy.setPreferAES(preferAES);
                doc.protect(policy);
                doc.save(outFile);
            }
            return;
        }
        if ("DECRYPT".equals(mode)) {
            File in = new File(args[1]);
            String password = args.length > 2 ? args[2] : "";
            try (PDDocument doc = Loader.loadPDF(in, password)) {
                out.print("PAGES:");
                out.print(doc.getNumberOfPages());
                out.print("\n");
                out.print(new PDFTextStripper().getText(doc));
            }
            return;
        }
        if ("DUMP".equals(mode)) {
            File in = new File(args[1]);
            String password = args.length > 2 ? args[2] : "";
            try (PDDocument doc = Loader.loadPDF(in, password)) {
                PDEncryption enc = doc.getEncryption();
                COSDictionary d = enc.getCOSObject();
                byte[] o = ((COSString) d.getDictionaryObject(COSName.O)).getBytes();
                byte[] u = ((COSString) d.getDictionaryObject(COSName.U)).getBytes();
                out.print("O:");
                out.print(toHex(o));
                out.print("\n");
                out.print("U:");
                out.print(toHex(u));
                out.print("\n");
                out.print("V:");
                out.print(enc.getVersion());
                out.print("\n");
                out.print("R:");
                out.print(enc.getRevision());
                out.print("\n");
                out.print("LEN:");
                out.print(enc.getLength());
                out.print("\n");
                if (enc.getRevision() >= 5) {
                    byte[] oe = ((COSString) d.getDictionaryObject(COSName.OE)).getBytes();
                    byte[] ue = ((COSString) d.getDictionaryObject(COSName.UE)).getBytes();
                    out.print("OE:");
                    out.print(toHex(oe));
                    out.print("\n");
                    out.print("UE:");
                    out.print(toHex(ue));
                    out.print("\n");
                }
            }
            return;
        }
        throw new IllegalArgumentException("unknown mode: " + mode);
    }

    private static String toHex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xff));
        }
        return sb.toString();
    }
}
