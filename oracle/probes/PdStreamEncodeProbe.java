import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.InputStream;
import java.nio.file.Files;
import java.security.MessageDigest;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.io.IOUtils;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.common.PDStream;

/**
 * Live oracle probe for the encode-on-write constructor
 * {@code PDStream(PDDocument, InputStream, COSName filter)} (and the
 * {@code COSArray} multi-filter variant).
 *
 * Upstream reads ALL bytes from the input stream and writes them through
 * {@code stream.createOutputStream(filters)}, so the body is ENCODED with the
 * given filter chain on the way in. The probe then reports:
 *   - the decoded round-trip bytes (length + sha256) via createInputStream()
 *   - the raw/encoded body bytes (length + sha256) via createRawInputStream()
 *   - the /Filter chain recorded on the dictionary
 *   - getLength() (the recorded /Length)
 *
 * Usage:
 *   java ... PdStreamEncodeProbe payload.bin FlateDecode
 *   java ... PdStreamEncodeProbe payload.bin ASCII85Decode,FlateDecode
 *   java ... PdStreamEncodeProbe payload.bin NONE        (no-filter ctor)
 *
 *   args[0] - path to a file holding the DECODED payload bytes.
 *   args[1] - comma-separated filter names, or "NONE" for the no-filter ctor.
 *
 * Output (UTF-8 text, 4 lines):
 *   decoded <len> <sha256hex>
 *   raw <len> <sha256hex>
 *   filters <name>,<name>,...        (or "filters" alone when empty)
 *   length <int>
 */
public final class PdStreamEncodeProbe {
    public static void main(String[] args) throws Exception {
        byte[] payload = Files.readAllBytes(new File(args[0]).toPath());
        String filterSpec = args[1];

        try (PDDocument doc = new PDDocument()) {
            PDStream pdStream;
            if ("NONE".equals(filterSpec)) {
                pdStream = new PDStream(doc, new ByteArrayInputStream(payload));
            } else {
                String[] names = filterSpec.split(",");
                if (names.length == 1) {
                    pdStream = new PDStream(doc, new ByteArrayInputStream(payload),
                            COSName.getPDFName(names[0]));
                } else {
                    COSArray arr = new COSArray();
                    for (String n : names) {
                        arr.add(COSName.getPDFName(n));
                    }
                    pdStream = new PDStream(doc, new ByteArrayInputStream(payload), arr);
                }
            }

            byte[] decoded;
            try (InputStream is = pdStream.createInputStream()) {
                decoded = IOUtils.toByteArray(is);
            }
            byte[] raw;
            try (InputStream is = pdStream.getCOSObject().createRawInputStream()) {
                raw = IOUtils.toByteArray(is);
            }

            StringBuilder sb = new StringBuilder();
            sb.append("decoded ").append(decoded.length).append(' ')
                    .append(sha256(decoded)).append('\n');
            sb.append("raw ").append(raw.length).append(' ')
                    .append(sha256(raw)).append('\n');
            sb.append("filters");
            for (COSName f : pdStream.getFilters()) {
                sb.append(' ').append(f.getName());
            }
            sb.append('\n');
            sb.append("length ").append(pdStream.getLength()).append('\n');
            System.out.print(sb);
        }
    }

    private static String sha256(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] d = md.digest(data);
        StringBuilder sb = new StringBuilder();
        for (byte b : d) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }
}
