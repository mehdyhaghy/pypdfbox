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
 * Live oracle probe for the ASCII85Decode / ASCIIHexDecode lenient DECODE
 * contract under malformed input (wave 1523 differential fuzz).
 *
 * Deeper than the generic {@code FilterFuzzProbe}: the corpus is hand-built
 * to hit the ASCII85- and ASCIIHex-specific edge cases — {@code <~} intro,
 * {@code ~>} EOD presence/absence, {@code z} shorthand at/away from a group
 * boundary, partial final groups (1..4 chars), 5-char group overflow past
 * 2^32, chars outside {@code !}..{@code u}, embedded control bytes, ASCIIHex
 * odd-digit padding, whitespace splitting a hex pair, case folding, EOD-only,
 * empty.
 *
 * It prints the same stable projection {@code FilterFuzzProbe} uses so the
 * pypdfbox side reproduces it byte-for-byte and the parity assertion is a
 * single string compare:
 *
 *   ok=true
 *   len=<decoded byte count>
 *   sha=<first 8 hex chars of SHA-256 of the decoded bytes>
 *
 * or the sole line {@code ok=false} on any decode-time throw.
 *
 * Usage:
 *   java -cp ... Ascii85HexDecodeFuzzProbe encoded.bin ASCII85Decode
 *   java -cp ... Ascii85HexDecodeFuzzProbe encoded.bin ASCIIHexDecode
 *
 *   args[0] - path to a file holding the raw encoded bytes.
 *   args[1] - filter name (ASCII85Decode or ASCIIHexDecode).
 */
public final class Ascii85HexDecodeFuzzProbe {
    public static void main(String[] args) throws Exception {
        byte[] encoded = Files.readAllBytes(new File(args[0]).toPath());
        String filterName = args[1];

        COSDictionary streamDict = new COSDictionary();
        streamDict.setItem(COSName.FILTER, COSName.getPDFName(filterName));

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
