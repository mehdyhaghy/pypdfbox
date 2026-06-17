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
 * Live oracle probe for CCITTFaxDecode's /Rows-vs-/Height reconciliation.
 *
 * Unlike CcittDecodeProbe (which pins /Height == /Rows so the decoded buffer
 * size is deterministic), this probe lets the caller set the /DecodeParms
 * /Rows and the stream-dict /Height INDEPENDENTLY, so a parity test can pin
 * Apache PDFBox's ``rows = Math.max(rows, height)`` reconciliation
 * (CCITTFaxFilter.decode): /Rows in /DecodeParms, /Height (alias /H) on the
 * stream dict, and the larger of the two wins. /Rows or /Height of 0 means
 * "omit that key entirely".
 *
 * PDFBox allocates a fixed ``effectiveRows * rowBytes`` buffer, decodes the
 * rows it can, and zero-fills the tail (then inverts for /BlackIs1 false), so
 * the decoded byte count is always ``effectiveRows * ((columns + 7) / 8)``.
 * We write the decoded scanline bytes to stdout verbatim for a byte-exact
 * compare against pypdfbox.
 *
 * Usage:
 *   java -cp ... CcittRowsProbe encoded.bin K=-1,Columns=344,Rows=0,Height=287
 *   java -cp ... CcittRowsProbe encoded.bin K=-1,Columns=344,Rows=100,Height=287
 *   java -cp ... CcittRowsProbe encoded.bin K=-1,Columns=344,Rows=400,Height=287
 *
 *   args[0] - path to a file holding the raw encoded CCITT strip bytes.
 *   args[1] - comma-separated params. Integer keys placed in /DecodeParms:
 *             K, Columns, Rows. Integer key placed on the stream dict:
 *             Height (alias for /Height). Boolean keys (0/1) in /DecodeParms:
 *             BlackIs1, EncodedByteAlign, EndOfLine, EndOfBlock. A value of 0
 *             for Rows or Height omits that key.
 */
public final class CcittRowsProbe {
    private static final java.util.Set<String> BOOLEAN_KEYS = java.util.Set.of(
            "BlackIs1", "EncodedByteAlign", "EndOfLine", "EndOfBlock");

    public static void main(String[] args) throws Exception {
        byte[] encoded = Files.readAllBytes(new File(args[0]).toPath());

        COSDictionary decodeParms = new COSDictionary();
        int columns = 1728;
        int height = 0;
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
                } else if (key.equals("Height")) {
                    height = Integer.parseInt(raw);
                } else {
                    long value = Long.parseLong(raw);
                    if (key.equals("Rows") && value == 0) {
                        // Rows=0 means "omit /Rows from /DecodeParms".
                        continue;
                    }
                    decodeParms.setItem(COSName.getPDFName(key), COSInteger.get(value));
                    if (key.equals("Columns")) {
                        columns = (int) value;
                    }
                }
            }
        }

        COSDictionary streamDict = new COSDictionary();
        streamDict.setItem(COSName.FILTER, COSName.getPDFName("CCITTFaxDecode"));
        streamDict.setItem(COSName.DECODE_PARMS, decodeParms);
        if (columns > 0) {
            streamDict.setInt(COSName.WIDTH, columns);
        }
        // /Height drives PDFBox's rows = max(rows, height); Height=0 omits it.
        if (height > 0) {
            streamDict.setInt(COSName.HEIGHT, height);
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
