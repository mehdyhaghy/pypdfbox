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
 * Live oracle probe for the LZWDecode filter under malformed input
 * (wave 1523 LZW-specific decode fuzz).
 *
 * Targets the LZW-only edge cases the generic FilterFuzzProbe does not stress:
 * code-table growth, /EarlyChange boundary codes, code-width transitions
 * (9->10->11->12), the CLEAR_TABLE / EOD reserved codes, the KwKwK special
 * case vs an out-of-range code, premature EOF (missing EOD), EOD mid-stream,
 * and codes that reference the reserved null placeholders (256/257 as data).
 *
 * Like FilterFuzzProbe it reads raw (possibly corrupt) encoded bytes from a
 * file, decodes them with Apache PDFBox's {@code LZWDecode} filter, and prints
 * a stable projection of the OUTCOME rather than the raw bytes:
 *
 *   ok=true
 *   len=<decoded byte count>
 *   sha=<first 8 hex chars of SHA-256 of the decoded bytes>
 *
 * or the sole line
 *
 *   ok=false
 *
 * on ANY throw from {@code Filter.decode} (IOException, NullPointerException
 * from a null-placeholder code, OutOfMemoryError, ...). Throwable is caught so
 * every failure mode classifies cleanly; we never assert on the message.
 *
 * Usage:
 *   java -cp ... LzwDecodeFuzzProbe encoded.bin
 *   java -cp ... LzwDecodeFuzzProbe encoded.bin EarlyChange=0
 *   java -cp ... LzwDecodeFuzzProbe encoded.bin EarlyChange=1,Predictor=2,Columns=4
 *
 *   args[0] - path to a file holding the raw encoded LZW bytes.
 *   args[1] - OPTIONAL comma-separated integer /DecodeParms entries
 *             (e.g. "EarlyChange=0" or "Predictor=2,Columns=4"). Empty -> none.
 */
public final class LzwDecodeFuzzProbe {
    public static void main(String[] args) throws Exception {
        byte[] encoded = Files.readAllBytes(new File(args[0]).toPath());

        COSDictionary streamDict = new COSDictionary();
        streamDict.setItem(COSName.FILTER, COSName.getPDFName("LZWDecode"));

        if (args.length > 1 && !args[1].isEmpty()) {
            COSDictionary decodeParms = new COSDictionary();
            applyInts(decodeParms, args[1]);
            streamDict.setItem(COSName.DECODE_PARMS, decodeParms);
        }

        PrintStream out = System.out;
        Filter filter;
        try {
            filter = FilterFactory.INSTANCE.getFilter(COSName.getPDFName("LZWDecode"));
        } catch (Exception e) {
            out.print("ok=false\n");
            out.flush();
            return;
        }

        ByteArrayOutputStream decoded = new ByteArrayOutputStream();
        try {
            filter.decode(new ByteArrayInputStream(encoded), decoded, streamDict, 0);
        } catch (Throwable t) {
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
