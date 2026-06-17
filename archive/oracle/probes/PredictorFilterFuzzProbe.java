import java.io.ByteArrayInputStream;
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
 * Live oracle probe for the stream-filter DECODE + PNG/TIFF predictor
 * post-processing surface (wave 1543 differential predictor / Flate / LZW /
 * ASCII85 / ASCIIHex / RunLength decode fuzz).
 *
 * Reads raw (encoded, possibly corrupt) bytes from a file, decodes them with
 * Apache PDFBox's {@link Filter} for the named filter (optionally carrying
 * /DecodeParms predictor geometry), and prints a stable, BYTE-EXACT projection
 * of the outcome:
 *
 *   len=&lt;decoded byte count&gt;
 *   hex=&lt;full lowercase hex of the decoded bytes when &le; 64 bytes&gt;
 *   sha=&lt;first 8 hex chars of SHA-256 of the decoded bytes when &gt; 64 bytes&gt;
 *
 * or the sole line
 *
 *   ERR:&lt;simple exception class name&gt;
 *
 * on any throw from {@code Filter.decode}. Emitting the FULL decoded bytes for
 * the (short) predictor fuzz outputs — rather than just an ok/len/sha
 * fingerprint — is the point of this probe: predictor geometry bugs corrupt the
 * decoded *content* while keeping the length identical, so a length-only
 * fingerprint would miss them. The pypdfbox side reproduces the same projection
 * and the parity assertion is a single string compare.
 *
 * Usage:
 *   java -cp ... PredictorFilterFuzzProbe encoded.bin FlateDecode "" Predictor=12,Columns=4
 *   java -cp ... PredictorFilterFuzzProbe encoded.bin LZWDecode   "" EarlyChange=0
 *   java -cp ... PredictorFilterFuzzProbe encoded.bin ASCII85Decode
 *
 *   args[0] - path to a file holding the raw encoded bytes.
 *   args[1] - filter name (long PDF name).
 *   args[2] - OPTIONAL comma-separated integer STREAM-LEVEL entries placed
 *             directly on the stream dictionary. Empty string -&gt; none.
 *   args[3] - OPTIONAL comma-separated integer /DecodeParms entries
 *             (e.g. "Predictor=12,Columns=4,Colors=3,BitsPerComponent=4").
 *             Empty -&gt; none.
 */
public final class PredictorFilterFuzzProbe {
    public static void main(String[] args) throws Exception {
        byte[] encoded = Files.readAllBytes(new File(args[0]).toPath());
        String filterName = args[1];

        COSDictionary streamDict = new COSDictionary();
        streamDict.setItem(COSName.FILTER, COSName.getPDFName(filterName));

        if (args.length > 2 && !args[2].isEmpty()) {
            applyInts(streamDict, args[2]);
        }
        if (args.length > 3 && !args[3].isEmpty()) {
            COSDictionary decodeParms = new COSDictionary();
            applyInts(decodeParms, args[3]);
            streamDict.setItem(COSName.DECODE_PARMS, decodeParms);
        }

        PrintStream out = System.out;
        Filter filter;
        try {
            filter = FilterFactory.INSTANCE.getFilter(COSName.getPDFName(filterName));
        } catch (Exception e) {
            out.print("ERR:" + e.getClass().getSimpleName() + "\n");
            out.flush();
            return;
        }

        ByteArrayOutputStream decoded = new ByteArrayOutputStream();
        try {
            filter.decode(new ByteArrayInputStream(encoded), decoded, streamDict, 0);
        } catch (Throwable t) {
            out.print("ERR:" + t.getClass().getSimpleName() + "\n");
            out.flush();
            return;
        }

        byte[] bytes = decoded.toByteArray();
        out.print("len=" + bytes.length + "\n");
        if (bytes.length <= 64) {
            out.print("hex=" + hex(bytes) + "\n");
        } else {
            out.print("sha=" + shaPrefix(bytes) + "\n");
        }
        out.flush();
    }

    private static void applyInts(COSDictionary dict, String spec) {
        for (String pair : spec.split(",")) {
            int eq = pair.indexOf('=');
            if (eq < 0) {
                continue;
            }
            String key = pair.substring(0, eq).trim();
            long value = Long.parseLong(pair.substring(eq + 1).trim());
            dict.setItem(COSName.getPDFName(key), COSInteger.get(value));
        }
    }

    private static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            sb.append(Character.forDigit((b >> 4) & 0xf, 16));
            sb.append(Character.forDigit(b & 0xf, 16));
        }
        return sb.toString();
    }

    private static String shaPrefix(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] digest = md.digest(data);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 4; i++) {
            sb.append(String.format("%02x", digest[i]));
        }
        return sb.toString();
    }
}
