import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.security.MessageDigest;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.filter.Filter;
import org.apache.pdfbox.filter.FilterFactory;

/**
 * Live oracle probe for the RunLengthDecode filter under malformed input
 * (wave 1524 RunLength-specific decode fuzz).
 *
 * PDF RunLength packets (ISO 32000-1 §7.4.5): a length byte L drives the next
 * operation -- L in 0..127 copies the next L+1 bytes verbatim; L in 129..255
 * repeats the next single byte (257 - L) times; L == 128 is end-of-data. This
 * probe stresses the codec's lenient EOF handling: empty input, EOD as the
 * first byte, literal runs that overrun the input, repeat runs with no
 * following byte, missing trailing EOD, multiple EOD bytes, data after EOD,
 * the max literal (127) and max repeat (129) runs, and interleaved runs.
 *
 * Like FilterFuzzProbe it reads raw (possibly corrupt) encoded bytes from a
 * file, decodes them with Apache PDFBox's {@code RunLengthDecode} filter, and
 * prints a stable projection of the OUTCOME rather than the raw bytes:
 *
 *   ok=true
 *   len=<decoded byte count>
 *   sha=<first 8 hex chars of SHA-256 of the decoded bytes>
 *
 * or the sole line
 *
 *   ok=false
 *
 * on ANY throw from {@code Filter.decode}. Throwable is caught so every
 * failure mode classifies cleanly; we never assert on the message.
 *
 * Usage:
 *   java -cp ... RunLengthDecodeFuzzProbe encoded.bin
 *
 *   args[0] - path to a file holding the raw encoded RunLength bytes.
 */
public final class RunLengthDecodeFuzzProbe {
    public static void main(String[] args) throws Exception {
        byte[] encoded = Files.readAllBytes(new File(args[0]).toPath());

        COSDictionary streamDict = new COSDictionary();
        streamDict.setItem(COSName.FILTER, COSName.getPDFName("RunLengthDecode"));

        PrintStream out = System.out;
        Filter filter;
        try {
            filter = FilterFactory.INSTANCE.getFilter(COSName.getPDFName("RunLengthDecode"));
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
