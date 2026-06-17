import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.StandardProtectionPolicy;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the DECRYPT-ON-LOAD path of Apache PDFBox 3.0.7's
 * {@code StandardSecurityHandler} (wave 1562, agent D).
 *
 * Sibling probes already cover other facets:
 *   - {@code EncryptProbe}/{@code DecryptProbe}     — page-text interop round trip
 *   - {@code DecryptDataFuzzProbe}                  — raw cipher dispatch on bad bytes
 *   - {@code StandardSecurityHandlerFuzzProbe}      — key derivation + auth
 *   - {@code EncryptMetadataWire}                   — /EncryptMetadata wire bytes
 *
 * NEITHER projects the *decrypted high-level content* recovered through a real
 * document open: the decrypted {@code /Info /Title} string, the auth ROLE
 * (owner vs user) that the open resolved, an EMPTY user password open, and a
 * wrong-password rejection's exception class. That is this probe's surface.
 *
 * The probe is self-contained: it ENCRYPTS a tiny one-page document (with a
 * known {@code /Info /Title} and one line of page text) in-memory for each
 * algorithm/permission/metadata variant via PDFBox's own
 * {@code StandardProtectionPolicy}, writes it to a temp file, then RE-OPENS it
 * with the supplied password and projects what decrypt-on-load recovered. The
 * Python parity test re-opens the very same PDFBox-encrypted bytes with
 * pypdfbox and compares the projection, and vice-versa.
 *
 * Usage (one case per argv token; manifest order preserved):
 *   java -cp ... DecryptOnLoadFuzzProbe make &lt;outdir&gt; \
 *        keylen preferAes ownerPw userPw encryptMeta canPrint
 *   -> builds an encrypted file at &lt;outdir&gt;/&lt;manifest&gt;.pdf, prints nothing.
 *
 *   java -cp ... DecryptOnLoadFuzzProbe open &lt;file&gt; &lt;password&gt;
 *   -> prints one line projecting the decrypt-on-load result:
 *        OK|owner=&lt;bool&gt;|title=&lt;str&gt;|text=&lt;firstline&gt;|canprint=&lt;bool&gt;
 *      or, on a rejected/failed open:
 *        ERR:&lt;ExceptionSimpleName&gt;
 *
 * The split make/open invocation keeps the encrypted bytes on disk so the
 * Python side opens the IDENTICAL ciphertext PDFBox produced.
 */
public final class DecryptOnLoadFuzzProbe {

    static final String TITLE = "Confidential © 2026 — decrypt me";
    static final String TEXT = "Hello encrypted world.";

    static PrintStream out;

    private static void make(String[] a) throws Exception {
        // a: make outdir name keylen preferAes ownerPw userPw
        // NB: PDFBox 3.0.7's StandardProtectionPolicy has no setEncryptMetadata,
        // so the Java-made files are always /EncryptMetadata true (spec default).
        // The /EncryptMetadata-false decrypt-on-load case is built on the
        // pypdfbox write side and opened by THIS probe (open verb).
        File outDir = new File(a[1]);
        String name = a[2];
        int keyLen = Integer.parseInt(a[3]);
        boolean preferAes = Boolean.parseBoolean(a[4]);
        String ownerPw = a[5];
        String userPw = a[6];
        // Optional 8th token: "noprint" restricts the user role (canPrint=false)
        // so the owner-vs-user open ROLE is observable. Default: all allowed.
        boolean restrictPrint = a.length > 7 && "noprint".equals(a[7]);

        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.beginText();
                cs.setFont(new PDType1Font(Standard14Fonts.FontName.HELVETICA), 12);
                cs.newLineAtOffset(72, 700);
                cs.showText(TEXT);
                cs.endText();
            }
            PDDocumentInformation info = new PDDocumentInformation();
            info.setTitle(TITLE);
            doc.setDocumentInformation(info);

            AccessPermission perms = new AccessPermission();
            if (restrictPrint) {
                perms.setCanPrint(false);
            }
            StandardProtectionPolicy policy =
                    new StandardProtectionPolicy(ownerPw, userPw, perms);
            policy.setEncryptionKeyLength(keyLen);
            policy.setPreferAES(preferAes);
            doc.protect(policy);
            doc.save(new File(outDir, name + ".pdf"));
        }
    }

    private static String esc(String s) {
        if (s == null) {
            return "<null>";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("|", "\\p");
    }

    private static void open(String[] a) {
        File in = new File(a[1]);
        String password = a.length > 2 ? a[2] : "";
        try (PDDocument doc = Loader.loadPDF(in, password)) {
            AccessPermission ap = doc.getCurrentAccessPermission();
            boolean owner = ap.isOwnerPermission();
            boolean canPrint = ap.canPrint();
            String title = null;
            PDDocumentInformation info = doc.getDocumentInformation();
            if (info != null) {
                title = info.getTitle();
            }
            String text = new PDFTextStripper().getText(doc);
            String firstLine = text == null ? "" : text.split("\\R", 2)[0].trim();
            out.println("OK|owner=" + owner + "|title=" + esc(title)
                    + "|text=" + esc(firstLine) + "|canprint=" + canPrint);
        } catch (Exception e) {
            out.println("ERR:" + e.getClass().getSimpleName());
        }
    }

    public static void main(String[] args) throws Exception {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        out = new PrintStream(buf, true, "UTF-8");
        if ("make".equals(args[0])) {
            make(args);
        } else if ("open".equals(args[0])) {
            open(args);
        } else {
            throw new IllegalArgumentException("first arg must be make|open");
        }
        out.flush();
        System.out.write(buf.toByteArray());
        System.out.flush();
    }
}
