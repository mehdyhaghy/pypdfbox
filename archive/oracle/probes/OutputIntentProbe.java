import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.PrintStream;
import java.security.MessageDigest;
import java.util.List;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.graphics.color.PDOutputIntent;

/**
 * Live oracle probe: emit Apache PDFBox's view of every /OutputIntent in a PDF.
 * Usage: java -cp <pdfbox-app.jar>:<build> OutputIntentProbe input.pdf
 *
 * Output: canonical, one section per output intent, framed by index. Fields:
 *   intent <i>
 *   condition=<getOutputCondition()>
 *   conditionIdentifier=<getOutputConditionIdentifier()>
 *   registryName=<getRegistryName()>
 *   info=<getInfo()>
 *   icc.len=<DestOutputProfile decoded byte length, or -1 if absent>
 *   icc.sha1=<SHA-1 hex of those bytes, or - if absent>
 *
 * Null string fields are emitted as the literal token "null" so the Python
 * side can map them to None unambiguously.
 */
public final class OutputIntentProbe {
    private static String s(String v) {
        return v == null ? "null" : v;
    }

    private static String sha1Hex(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-1");
        byte[] digest = md.digest(data);
        StringBuilder sb = new StringBuilder(digest.length * 2);
        for (byte b : digest) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            List<PDOutputIntent> intents = catalog.getOutputIntents();
            out.println("count=" + intents.size());
            for (int i = 0; i < intents.size(); i++) {
                PDOutputIntent oi = intents.get(i);
                out.println("intent " + i);
                out.println("condition=" + s(oi.getOutputCondition()));
                out.println("conditionIdentifier=" + s(oi.getOutputConditionIdentifier()));
                out.println("registryName=" + s(oi.getRegistryName()));
                out.println("info=" + s(oi.getInfo()));
                byte[] icc = null;
                COSStream profile = oi.getDestOutputIntent();
                if (profile != null) {
                    ByteArrayOutputStream baos = new ByteArrayOutputStream();
                    try (InputStream in = profile.createInputStream()) {
                        byte[] buf = new byte[8192];
                        int read;
                        while ((read = in.read(buf)) != -1) {
                            baos.write(buf, 0, read);
                        }
                    }
                    icc = baos.toByteArray();
                }
                if (icc == null) {
                    out.println("icc.len=-1");
                    out.println("icc.sha1=-");
                } else {
                    out.println("icc.len=" + icc.length);
                    out.println("icc.sha1=" + sha1Hex(icc));
                }
            }
        }
    }
}
