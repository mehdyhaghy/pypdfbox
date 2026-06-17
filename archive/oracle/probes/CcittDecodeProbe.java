import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.OutputStream;
import java.nio.file.Files;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.filter.Filter;
import org.apache.pdfbox.filter.FilterFactory;

/**
 * Live oracle probe for the CCITTFaxDecode filter — byte-exact decode.
 *
 * Reads raw (still-encoded) CCITT fax bytes from a file, builds a stream
 * COSDictionary mirroring a real image XObject (/Filter /CCITTFaxDecode plus a
 * /DecodeParms dictionary and the geometry keys /Width /Height that
 * CCITTFaxFilter consults), runs Apache PDFBox's CCITTFaxFilter.decode, and
 * writes the DECODED scanline bytes to stdout verbatim. The harness's
 * run_probe returns them as raw bytes, so a parity test can SHA-256 / length /
 * byte-compare them against pypdfbox's decoded output.
 *
 * Usage:
 *   java -cp ... CcittDecodeProbe encoded.bin K=-1,Columns=344,Rows=287
 *   java -cp ... CcittDecodeProbe encoded.bin K=0,Columns=344,Rows=287,EndOfLine=1
 *   java -cp ... CcittDecodeProbe encoded.bin K=2,Columns=24,Rows=6,BlackIs1=1
 *
 *   args[0] - path to a file holding the raw encoded CCITT strip bytes.
 *   args[1] - comma-separated params. Integer keys: K, Columns, Rows.
 *             Boolean keys (value 0/1): BlackIs1, EncodedByteAlign, EndOfLine,
 *             EndOfBlock. /Columns and /Rows are placed both in /DecodeParms
 *             and (as /Width /Height) on the stream dict so the filter's
 *             rows = max(rows, height) reconciliation is deterministic.
 *
 * CCITTFaxFilter.decode reads /Height off the stream dict and does
 * rows = max(rows, height); we set /Height == /Rows so the effective row count
 * is exactly the value we pass — making the decoded buffer size deterministic
 * and directly comparable to pypdfbox (which trims to rows*rowBytes).
 */
public final class CcittDecodeProbe {
    private static final java.util.Set<String> BOOLEAN_KEYS = java.util.Set.of(
            "BlackIs1", "EncodedByteAlign", "EndOfLine", "EndOfBlock");

    public static void main(String[] args) throws Exception {
        byte[] encoded = Files.readAllBytes(new File(args[0]).toPath());

        COSDictionary decodeParms = new COSDictionary();
        int columns = 1728;
        int rows = 0;
        if (args.length > 1 && !args[1].isEmpty()) {
            for (String pair : args[1].split(",")) {
                int eq = pair.indexOf('=');
                if (eq < 0) {
                    continue;
                }
                String key = pair.substring(0, eq).trim();
                String raw = pair.substring(eq + 1).trim();
                if (BOOLEAN_KEYS.contains(key)) {
                    boolean value = raw.equals("1") || raw.equalsIgnoreCase("true");
                    decodeParms.setItem(COSName.getPDFName(key),
                            value ? COSBoolean.TRUE : COSBoolean.FALSE);
                } else {
                    long value = Long.parseLong(raw);
                    decodeParms.setItem(COSName.getPDFName(key), COSInteger.get(value));
                    if (key.equals("Columns")) {
                        columns = (int) value;
                    } else if (key.equals("Rows")) {
                        rows = (int) value;
                    }
                }
            }
        }

        COSDictionary streamDict = new COSDictionary();
        streamDict.setItem(COSName.FILTER, COSName.getPDFName("CCITTFaxDecode"));
        streamDict.setItem(COSName.DECODE_PARMS, decodeParms);
        // Mirror a real image XObject: /Width and /Height live on the stream
        // dict. CCITTFaxFilter reads /Height; setting it == /Rows pins the
        // decoded buffer height deterministically.
        if (columns > 0) {
            streamDict.setInt(COSName.WIDTH, columns);
        }
        if (rows > 0) {
            streamDict.setInt(COSName.HEIGHT, rows);
        }

        Filter filter = FilterFactory.INSTANCE.getFilter(
                COSName.getPDFName("CCITTFaxDecode"));

        ByteArrayOutputStream decoded = new ByteArrayOutputStream();
        filter.decode(new ByteArrayInputStream(encoded), decoded, streamDict, 0);

        OutputStream raw = System.out;
        raw.write(decoded.toByteArray());
        raw.flush();
    }
}
