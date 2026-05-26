import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.OutputStream;
import java.nio.file.Files;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.filter.Filter;
import org.apache.pdfbox.filter.FilterFactory;

/**
 * Live oracle probe for the stream-filter ENCODE surface.
 *
 * Reads RAW (un-encoded) bytes from a file, encodes them with Apache
 * PDFBox's {@link Filter} for the named filter, and writes the ENCODED
 * bytes to stdout verbatim (raw bytes — the harness's {@code run_probe}
 * returns them as-is). This is the encode counterpart to
 * {@code FilterDecodeProbe}.
 *
 * Usage:
 *   java -cp ... FilterEncodeProbe raw.bin FlateDecode
 *   java -cp ... FilterEncodeProbe raw.bin FlateDecode Predictor=12,Columns=4
 *   java -cp ... FilterEncodeProbe raw.bin ASCIIHexDecode
 *
 *   args[0] - path to a file holding the raw (un-encoded) bytes.
 *   args[1] - filter name (FlateDecode | LZWDecode | ASCII85Decode |
 *             ASCIIHexDecode | RunLengthDecode); short names (Fl, LZW, A85,
 *             AHx, RL) also resolve via canonical().
 *   args[2] - OPTIONAL comma-separated integer /DecodeParms entries
 *             (e.g. "Predictor=12,Columns=4,Colors=1,BitsPerComponent=8").
 *             Each becomes a COSInteger under the /DecodeParms dictionary.
 *
 * The COSDictionary handed to {@code Filter.encode} mirrors a stream dict:
 * a single-name /Filter plus a single /DecodeParms dictionary, matching the
 * decode probe's shape so encode/decode round-trips share the same params.
 */
public final class FilterEncodeProbe {
    public static void main(String[] args) throws Exception {
        byte[] raw = Files.readAllBytes(new File(args[0]).toPath());
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

        ByteArrayOutputStream encoded = new ByteArrayOutputStream();
        filter.encode(new ByteArrayInputStream(raw), encoded, streamDict, 0);

        OutputStream out = System.out;
        out.write(encoded.toByteArray());
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
