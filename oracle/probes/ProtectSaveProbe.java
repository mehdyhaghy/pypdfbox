import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the API-level encrypt-on-save path: open a PDF that
 * pypdfbox produced via {@code PDDocument.protect(StandardProtectionPolicy)}
 * followed by {@code save()}, authenticating with the supplied password, and
 * emit the decrypted shape AND the raw {@code /Encrypt} dictionary structure as
 * JSON so a parity test can assert Apache PDFBox 3.0.7 both accepts the
 * standard handler's credential entries and reads the same {@code /V} /
 * {@code /R} / {@code /Length} / {@code /P} (+ the {@code /CF} / {@code /StmF}
 * / {@code /StrF} crypt-filter wiring for AES) pypdfbox wrote.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> ProtectSaveProbe enc.pdf &lt;password&gt;
 *
 * On success the probe prints one JSON object:
 *
 *   {"opened":true,"isEncrypted":true,"pages":1,"revision":6,"version":5,
 *    "length":256,"p":-3392,"hasU":true,"hasO":true,"hasUE":true,"hasOE":true,
 *    "stmF":"StdCF","strF":"StdCF","cfm":"AESV3","encryptMetadata":true,
 *    "canPrint":true,"canModify":true,"canExtract":true,"text":"..."}
 */
public final class ProtectSaveProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String in = args[0];
        String password = args.length > 1 ? args[1] : "";

        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(in), password)) {
            AccessPermission ap = doc.getCurrentAccessPermission();
            COSDictionary enc = doc.getDocument().getEncryptionDictionary();

            int version = intEntry(enc, COSName.V, -1);
            int revision = intEntry(enc, COSName.R, -1);
            int length = intEntry(enc, COSName.LENGTH, -1);
            int p = intEntry(enc, COSName.P, 0);

            sb.append("{\"opened\":true");
            sb.append(",\"isEncrypted\":").append(doc.isEncrypted());
            sb.append(",\"pages\":").append(doc.getNumberOfPages());
            sb.append(",\"version\":").append(version);
            sb.append(",\"revision\":").append(revision);
            sb.append(",\"length\":").append(length);
            sb.append(",\"p\":").append(p);
            sb.append(",\"hasU\":").append(enc.getDictionaryObject(COSName.U) instanceof COSString);
            sb.append(",\"hasO\":").append(enc.getDictionaryObject(COSName.O) instanceof COSString);
            sb.append(",\"hasUE\":").append(enc.getDictionaryObject(COSName.UE) instanceof COSString);
            sb.append(",\"hasOE\":").append(enc.getDictionaryObject(COSName.OE) instanceof COSString);

            // Crypt-filter wiring (AES / V4+). Absent for RC4 V1/V2.
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
