import java.io.File;
import java.io.PrintStream;
import java.security.MessageDigest;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.common.PDMetadata;

/**
 * Live oracle probe: emit Apache PDFBox's view of the *wire-level* facts of a
 * catalog /Metadata XMP stream — the facet not covered by MetaProbe (which only
 * hashes the decoded packet) or CatalogMetaProbe (presence only) or InfoXmpProbe
 * (parsed schema fields). Here we look at the raw COSStream dictionary as PDFBox
 * loaded it:
 *
 *   /Type     — should be "Metadata"
 *   /Subtype  — should be "XML"
 *   /Filter   — the raw, UNDECODED filter chain (US-joined names, or "none").
 *               A document-level XMP metadata stream is, by spec recommendation,
 *               stored uncompressed so a non-PDF reader can scrape it; PDFBox's
 *               PDMetadata writes it with no filter by default.
 *   raw.len   — length of the stored (still-encoded) stream bytes.
 *   decoded.len + decoded.sha1 — the XMP packet after PDMetadata decodes it.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> MetadataStreamProbe input.pdf
 *
 * Output: canonical, line-oriented (UTF-8, stdout, no framing). Null/absent
 * string fields render as the literal "null"; the filter chain as "none".
 */
public final class MetadataStreamProbe {

    private static final char US = (char) 0x1f;

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

    private static String filterChain(COSStream stream) {
        COSBase filter = stream.getDictionaryObject(COSName.FILTER);
        if (filter == null) {
            return "none";
        }
        if (filter instanceof COSName) {
            return ((COSName) filter).getName();
        }
        if (filter instanceof COSArray) {
            COSArray arr = (COSArray) filter;
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < arr.size(); i++) {
                if (i > 0) {
                    sb.append(US);
                }
                COSBase e = arr.getObject(i);
                sb.append(e instanceof COSName ? ((COSName) e).getName() : "?");
            }
            return sb.toString();
        }
        return "?";
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDMetadata metadata = catalog.getMetadata();
            if (metadata == null) {
                out.println("metadata NONE");
                return;
            }

            COSStream cos = metadata.getCOSObject();

            // /Type and /Subtype off the raw stream dictionary.
            COSBase type = cos.getDictionaryObject(COSName.TYPE);
            COSBase subtype = cos.getDictionaryObject(COSName.SUBTYPE);
            out.println("type="
                    + s(type instanceof COSName ? ((COSName) type).getName() : null));
            out.println("subtype="
                    + s(subtype instanceof COSName ? ((COSName) subtype).getName() : null));

            // Raw (still-encoded) filter chain + stored byte length.
            out.println("filter=" + filterChain(cos));
            byte[] raw = cos.createRawInputStream().readAllBytes();
            out.println("raw.len=" + raw.length);

            // Decoded XMP packet length + hash via the public accessor.
            byte[] decoded = metadata.exportXMPMetadata().readAllBytes();
            out.println("decoded.len=" + decoded.length);
            out.println("decoded.sha1=" + sha1Hex(decoded));
        }
    }
}
