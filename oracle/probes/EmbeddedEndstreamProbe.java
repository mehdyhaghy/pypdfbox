import java.io.File;
import java.io.InputStream;
import java.io.PrintStream;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe for the EMBEDDED-{@code endstream} stream-length recovery
 * facet. A stream body whose bytes contain the literal token {@code endstream}
 * is the worst case for length recovery: the {@code endstream}-scan workaround
 * is a byte-substring search and will truncate the body at the FIRST embedded
 * occurrence.
 *
 * PDFBox's {@code parseCOSStream} only invokes that scan when {@code
 * validateStreamLength} fails — so a CORRECT {@code /Length} short-circuits the
 * scan and preserves the full body (the embedded token is harmless), while a
 * WRONG / MISSING {@code /Length} forces the scan and truncates at the embedded
 * token (and rewrites {@code /Length} to the truncated count). When that scan
 * lands the cursor mid-body, {@code parseFileObject} finds a non-{@code endobj}
 * trailing keyword and, in lenient mode, only WARNS — it must NOT discard the
 * recovered stream. This probe captures exactly which bytes PDFBox 3.0.7 keeps.
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; EmbeddedEndstreamProbe input.pdf
 *
 * Output (UTF-8, LF-terminated), one line per stream object, sorted by
 * (objNum, genNum):
 *
 *   &lt;objNum&gt; &lt;genNum&gt;: rawlen=&lt;n&gt; sha=&lt;hex&gt; length=&lt;resolved-/Length-or-none&gt;
 */
public final class EmbeddedEndstreamProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument pd = Loader.loadPDF(new File(args[0]))) {
            COSDocument doc = pd.getDocument();
            List<long[]> keys = new ArrayList<>();
            for (COSObjectKey key : doc.getXrefTable().keySet()) {
                keys.add(new long[] {key.getNumber(), key.getGeneration()});
            }
            keys.sort((a, b) -> a[0] != b[0] ? Long.compare(a[0], b[0])
                    : Long.compare(a[1], b[1]));
            StringBuilder sb = new StringBuilder();
            for (long[] k : keys) {
                COSObjectKey key = new COSObjectKey(k[0], (int) k[1]);
                COSBase resolved;
                try {
                    resolved = doc.getObjectFromPool(key).getObject();
                } catch (Exception ex) {
                    continue;
                }
                if (!(resolved instanceof COSStream)) {
                    continue;
                }
                COSStream s = (COSStream) resolved;
                byte[] raw = readAll(s);
                String sha = sha256(raw);
                COSBase lenItem = s.getDictionaryObject(COSName.LENGTH);
                String lenStr = "none";
                if (lenItem instanceof COSNumber) {
                    lenStr = Long.toString(((COSNumber) lenItem).longValue());
                }
                sb.append(k[0]).append(' ').append(k[1])
                        .append(": rawlen=").append(raw.length)
                        .append(" sha=").append(sha)
                        .append(" length=").append(lenStr)
                        .append('\n');
            }
            out.print(sb);
        }
    }

    private static byte[] readAll(COSStream s) throws Exception {
        try (InputStream in = s.createRawInputStream()) {
            java.io.ByteArrayOutputStream bos = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int r;
            while ((r = in.read(buf)) != -1) {
                bos.write(buf, 0, r);
            }
            return bos.toByteArray();
        }
    }

    private static String sha256(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] d = md.digest(data);
        StringBuilder sb = new StringBuilder();
        for (byte b : d) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }
}
