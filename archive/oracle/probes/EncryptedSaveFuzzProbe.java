import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the encrypted COSWriter save path (wave 1558).
 *
 * Reloads a file pypdfbox produced via
 * {@code PDDocument.protect(StandardProtectionPolicy)} + {@code save()},
 * authenticating with the supplied password, and emits a STABLE JSON shape
 * the parity test asserts against:
 *
 *   - decrypts-ok flag,
 *   - the {@code /Encrypt} {@code /V} / {@code /R} / {@code /Length} / {@code /P},
 *   - presence of {@code /U} / {@code /O} / {@code /UE} / {@code /OE},
 *   - {@code /StmF} / {@code /StrF} + the StdCF {@code /CFM} (AES routing),
 *   - the resolved {@code /EncryptMetadata} flag,
 *   - the decrypted document /Info /Title (a string that exercises the
 *     write-side string-escaping + per-object encryption path),
 *   - the decrypted page text (a stream that exercises stream encryption),
 *   - the {@code AccessPermission} bits PDFBox reconstructs from /P.
 *
 * This proves cross-impl interop: a pypdfbox-encrypted file is loadable AND
 * correctly decryptable by Apache PDFBox 3.0.7, and the on-the-wire /Encrypt
 * dictionary matches the spec shape per key-length family. We compare
 * structural + round-trip facts, never exact ciphertext bytes (which differ
 * by random salt / IV every save).
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> EncryptedSaveFuzzProbe enc.pdf <password>
 */
public final class EncryptedSaveFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String in = args[0];
        String password = args.length > 1 ? args[1] : "";

        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(in), password)) {
            AccessPermission ap = doc.getCurrentAccessPermission();
            COSDictionary enc = doc.getDocument().getEncryptionDictionary();

            sb.append("{\"opened\":true");
            sb.append(",\"isEncrypted\":").append(doc.isEncrypted());
            sb.append(",\"pages\":").append(doc.getNumberOfPages());
            sb.append(",\"version\":").append(intEntry(enc, COSName.V, -1));
            sb.append(",\"revision\":").append(intEntry(enc, COSName.R, -1));
            sb.append(",\"length\":").append(intEntry(enc, COSName.LENGTH, -1));
            sb.append(",\"p\":").append(intEntry(enc, COSName.P, 0));
            sb.append(",\"hasU\":").append(enc.getDictionaryObject(COSName.U) instanceof COSString);
            sb.append(",\"hasO\":").append(enc.getDictionaryObject(COSName.O) instanceof COSString);
            sb.append(",\"hasUE\":").append(enc.getDictionaryObject(COSName.UE) instanceof COSString);
            sb.append(",\"hasOE\":").append(enc.getDictionaryObject(COSName.OE) instanceof COSString);

            COSName stmF = enc.getCOSName(COSName.STM_F);
            COSName strF = enc.getCOSName(COSName.STR_F);
            sb.append(",\"stmF\":").append(quote(stmF == null ? null : stmF.getName()));
            sb.append(",\"strF\":").append(quote(strF == null ? null : strF.getName()));

            String cfm = null;
            COSBase cf = enc.getDictionaryObject(COSName.CF);
            if (cf instanceof COSDictionary && stmF != null) {
                COSBase named = ((COSDictionary) cf).getDictionaryObject(stmF);
                if (named instanceof COSDictionary) {
                    COSName m = ((COSDictionary) named).getCOSName(COSName.CFM);
                    cfm = m == null ? null : m.getName();
                }
            }
            sb.append(",\"cfm\":").append(quote(cfm));

            boolean encMeta = true;
            COSBase em = enc.getDictionaryObject(COSName.ENCRYPT_META_DATA);
            if (em != null) {
                encMeta = enc.getBoolean(COSName.ENCRYPT_META_DATA, true);
            }
            sb.append(",\"encryptMetadata\":").append(encMeta);

            sb.append(",\"canPrint\":").append(ap.canPrint());
            sb.append(",\"canModify\":").append(ap.canModify());
            sb.append(",\"canExtract\":").append(ap.canExtractContent());

            // Decrypted /Info /Title — a string round-tripped through the
            // write-side escaping + per-object encryption path.
            PDDocumentInformation info = doc.getDocumentInformation();
            String title = info == null ? null : info.getTitle();
            sb.append(",\"title\":").append(quote(title));

            doc.setAllSecurityToBeRemoved(true);
            String text = new PDFTextStripper().getText(doc);
            sb.append(",\"text\":\"").append(escape(text)).append("\"");
            sb.append("}");
        } catch (Exception e) {
            sb.setLength(0);
            sb.append("{\"opened\":false,\"error\":\"")
              .append(escape(e.getClass().getSimpleName() + ": " + e.getMessage()))
              .append("\"}");
        }
        out.print(sb.toString());
    }

    private static int intEntry(COSDictionary d, COSName key, int dflt) {
        COSBase b = d.getDictionaryObject(key);
        if (b instanceof COSNumber) {
            return ((COSNumber) b).intValue();
        }
        return dflt;
    }

    private static String quote(String s) {
        if (s == null) {
            return "null";
        }
        return "\"" + escape(s) + "\"";
    }

    private static String escape(String s) {
        if (s == null) {
            return "";
        }
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': b.append("\\\\"); break;
                case '"': b.append("\\\""); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        b.append(String.format("\\u%04x", (int) c));
                    } else {
                        b.append(c);
                    }
            }
        }
        return b.toString();
    }
}
