import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.PrintStream;
import java.security.MessageDigest;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.common.PDMetadata;
import org.apache.pdfbox.pdmodel.encryption.PDEncryption;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the standard-security-handler {@code /EncryptMetadata
 * false} READ path. Opens an encrypted PDF with the supplied password and
 * emits, as a small framed report, the three signals a parity test compares
 * against pypdfbox's reader:
 *
 * <pre>
 *   ENCRYPTMETA:false
 *   METADATA_SHA256:&lt;hex sha-256 of the /Metadata stream bytes&gt;
 *   METADATA_LEN:&lt;decimal length of those bytes&gt;
 *   TEXT:&lt;decrypted page text, may span further lines&gt;
 * </pre>
 *
 * The contract under test: when the {@code /Encrypt} dictionary carries
 * {@code /EncryptMetadata false}, PDFBox's reader (a) derives the file key on
 * the false branch of Algorithm 2 — for R3/R4 that means appending the four
 * {@code 0xFF} bytes to the MD5 input — so the document still decrypts, and
 * (b) leaves the catalog {@code /Metadata} stream UNTOUCHED on read because
 * the producer left it cleartext on disk. {@code PDMetadata#exportXMPMetadata}
 * therefore returns the literal on-disk XMP bytes. The SHA-256 over those
 * bytes is the comparable signal — pypdfbox must produce the identical digest
 * (same plaintext recovered) and the identical decrypted page text.
 *
 * Usage:
 *   java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; EncryptMetadataFlagProbe enc.pdf &lt;password&gt;
 *
 * On a password / key-derivation failure the probe prints
 * {@code OPENED:false} followed by the exception class so the test can assert
 * the same rejection pypdfbox produces (parity on the negative path too).
 */
public final class EncryptMetadataFlagProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String in = args[0];
        String password = args.length > 1 ? args[1] : "";

        try (PDDocument doc = Loader.loadPDF(new File(in), password)) {
            PDEncryption enc = doc.getEncryption();
            out.print("OPENED:true\n");
            out.print("ENCRYPTMETA:");
            out.print(enc != null ? enc.isEncryptMetaData() : "null");
            out.print("\n");

            PDMetadata md = doc.getDocumentCatalog().getMetadata();
            byte[] metaBytes = md == null ? new byte[0] : readAll(md.exportXMPMetadata());
            out.print("METADATA_SHA256:");
            out.print(sha256(metaBytes));
            out.print("\n");
            out.print("METADATA_LEN:");
            out.print(metaBytes.length);
            out.print("\n");
            out.print("TEXT:");
            out.print(new PDFTextStripper().getText(doc));
        } catch (Exception e) {
            out.print("OPENED:false\n");
            out.print("ERROR:");
            out.print(e.getClass().getSimpleName());
        }
    }

    private static byte[] readAll(InputStream in) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) != -1) {
            bos.write(buf, 0, n);
        }
        in.close();
        return bos.toByteArray();
    }

    private static String sha256(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] digest = md.digest(data);
        StringBuilder sb = new StringBuilder(digest.length * 2);
        for (byte b : digest) {
            sb.append(String.format("%02x", b & 0xff));
        }
        return sb.toString();
    }
}
