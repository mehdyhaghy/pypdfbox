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
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe: load a PDF and, for every indirect object that resolves to
 * a COSStream, emit the RECOVERED raw (encoded) body — its byte length and a
 * SHA-256 of the bytes. This is the gold standard for stream-length / endstream
 * recovery: when a stream's /Length is wrong / missing / indirect, PDFBox
 * recovers the real body by scanning to ``endstream`` and rewrites /Length. The
 * SHA + length therefore capture exactly which bytes PDFBox decided are "the
 * stream body".
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> StreamLenRecoverProbe input.pdf
 *
 * Output (UTF-8, LF-terminated), one line per stream object, sorted by
 * (objNum, genNum):
 *
 *   <objNum> <genNum>: rawlen=<n> sha=<hex> length=<resolved-/Length-or-none>
 *
 * Where <resolved-/Length> is the value PDFBox ended up with in the stream's
 * /Length entry after parsing (PDFBox overwrites a wrong /Length with the
 * recovered length), or "none" if absent.
 */
public final class StreamLenRecoverProbe {

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
