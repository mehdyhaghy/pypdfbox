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
 * Live oracle probe for the lenient stream-filter DECODE contract under
 * malformed input (wave 1505 differential filter-decode fuzz).
 *
 * Reads raw (encoded, possibly corrupt) bytes from a file, decodes them with
 * Apache PDFBox's {@link Filter} for the named filter, and prints a stable
 * projection of the OUTCOME rather than the raw bytes:
 *
 *   ok=true
 *   len=<decoded byte count>
 *   sha=<first 8 hex chars of SHA-256 of the decoded bytes>
 *
 * or the sole line
 *
 *   ok=false
 *
 * on any throw from {@code Filter.decode}. This mirrors the wave-1503/1504
 * fuzz projection convention (an ok/shape fingerprint, not raw bytes) so the
 * pypdfbox side can reproduce it exactly and the parity assertion is a single
 * string compare.
 *
 * Usage:
 *   java -cp ... FilterFuzzProbe encoded.bin FlateDecode
 *   java -cp ... FilterFuzzProbe encoded.bin FlateDecode "" Predictor=12,Columns=4
 *   java -cp ... FilterFuzzProbe encoded.bin LZWDecode  "" EarlyChange=0
 *   java -cp ... FilterFuzzProbe encoded.bin CCITTFaxDecode Width=8,Height=2 K=-1,Columns=8,Rows=2
 *
 *   args[0] - path to a file holding the raw encoded bytes.
 *   args[1] - filter name (long PDF name, e.g. FlateDecode, LZWDecode,
 *             ASCII85Decode, ASCIIHexDecode, RunLengthDecode, CCITTFaxDecode,
 *             DCTDecode).
 *   args[2] - OPTIONAL comma-separated integer STREAM-LEVEL entries placed
 *             directly on the stream dictionary (e.g. "Width=8,Height=2" for
 *             CCITT / DCT). Empty string -> none.
 *   args[3] - OPTIONAL comma-separated integer /DecodeParms entries
 *             (e.g. "Predictor=12,Columns=4"). Empty -> none.
 *
 * The decoded bytes are buffered fully (the fuzz corpus is tiny) so we can
 * length-and-hash them deterministically.
 */
public final class FilterFuzzProbe {
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
            out.print("ok=false\n");
            out.flush();
            return;
        }

        ByteArrayOutputStream decoded = new ByteArrayOutputStream();
        try {
            filter.decode(new ByteArrayInputStream(encoded), decoded, streamDict, 0);
        } catch (Throwable t) {
            // Any decode-time throw (IOException and friends) is the
            // "ok=false" outcome. Throwable so an OutOfMemoryError from a
            // pathological /Columns*/Rows allocation also classifies cleanly
            // (we never assert on the message, only ok/len/sha).
            out.print("ok=false\n");
            out.flush();
            return;
        }

        byte[] bytes = decoded.toByteArray();
        out.print("ok=true\n");
        out.print("len=" + bytes.length + "\n");
        out.print("sha=" + shaPrefix(bytes) + "\n");
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
