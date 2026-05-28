import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.security.MessageDigest;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.filter.Filter;
import org.apache.pdfbox.filter.FilterFactory;

/**
 * Live oracle probe for the stream-filter ENCODE-VERIFY surface.
 *
 * Feeds an already-encoded byte stream to Apache PDFBox's {@link Filter}
 * decoder and emits a compact text line:
 *
 *     {@code <sha256-hex-of-decoded>:<decoded-length>}
 *
 * This is the asymmetric counterpart to {@code FilterEncodeProbe} /
 * {@code FilterDecodeProbe}: it lets a test encode bytes with pypdfbox,
 * hand them to PDFBox for decoding, and compare the recovered SHA-256 + length
 * against the original payload. A match across every filter proves the
 * pypdfbox encoder produced spec-conformant bytes that PDFBox's decoder
 * reverses losslessly.
 *
 * Usage:
 *   java -cp ... FilterEncodeVerifyProbe encoded.bin FlateDecode
 *   java -cp ... FilterEncodeVerifyProbe encoded.bin FlateDecode Predictor=12,Columns=4
 *   java -cp ... FilterEncodeVerifyProbe encoded.bin LZWDecode  EarlyChange=1
 *
 *   args[0] - path to a file holding the ENCODED bytes (typically produced by
 *             pypdfbox's filter.encode and staged to a temp file by the test).
 *   args[1] - filter name (FlateDecode | LZWDecode | ASCII85Decode |
 *             ASCIIHexDecode | RunLengthDecode). Short ISO 32000-1 Table 6
 *             abbreviations (Fl, LZW, A85, AHx, RL) also resolve.
 *   args[2] - OPTIONAL comma-separated integer /DecodeParms entries
 *             (e.g. "Predictor=12,Columns=4,Colors=1,BitsPerComponent=8").
 *             Each becomes a COSInteger under the /DecodeParms dictionary.
 *
 * The COSDictionary handed to {@code Filter.decode} mirrors a real stream
 * dictionary shape (single-name /Filter plus a /DecodeParms sub-dict) so the
 * filter's own {@code getDecodeParams(dict, 0)} resolves the predictor params
 * exactly as it would for a stream object in a parsed PDF.
 */
public final class FilterEncodeVerifyProbe {
    public static void main(String[] args) throws Exception {
        byte[] encoded = Files.readAllBytes(new File(args[0]).toPath());
        String filterName = args[1];

        COSDictionary streamDict = new COSDictionary();
        streamDict.setItem(COSName.FILTER, COSName.getPDFName(filterName));

        if (args.length > 2 && !args[2].isEmpty()) {
            COSDictionary decodeParms = new COSDictionary();
            for (String pair : args[2].split(",")) {
                int eq = pair.indexOf('=');
                if (eq < 0) {
                    continue;
                }
                String key = pair.substring(0, eq).trim();
                long value = Long.parseLong(pair.substring(eq + 1).trim());
                decodeParms.setItem(COSName.getPDFName(key), COSInteger.get(value));
            }
            streamDict.setItem(COSName.DECODE_PARMS, decodeParms);
        }

        Filter filter = FilterFactory.INSTANCE.getFilter(
                COSName.getPDFName(canonical(filterName)));

        ByteArrayOutputStream decoded = new ByteArrayOutputStream();
        filter.decode(new java.io.ByteArrayInputStream(encoded), decoded,
                streamDict, 0);

        byte[] raw = decoded.toByteArray();
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] digest = md.digest(raw);

        StringBuilder hex = new StringBuilder(digest.length * 2);
        for (byte b : digest) {
            hex.append(String.format("%02x", b & 0xff));
        }

        PrintStream out = System.out;
        out.print(hex.toString());
        out.print(':');
        out.print(raw.length);
        out.flush();
    }

    /**
     * FilterFactory.getFilter expects the long PDF name. Map the standard
     * abbreviations (ISO 32000-1 Table 6) so the probe accepts either form.
     */
    private static String canonical(String name) {
        switch (name) {
            case "Fl":  return "FlateDecode";
            case "LZW": return "LZWDecode";
            case "A85": return "ASCII85Decode";
            case "AHx": return "ASCIIHexDecode";
            case "RL":  return "RunLengthDecode";
            default:    return name;
        }
    }
}
