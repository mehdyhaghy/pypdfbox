import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.security.MessageDigest;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.filter.Filter;
import org.apache.pdfbox.filter.FilterFactory;

/**
 * Differential-fuzz oracle for the CCITTFaxDecode filter against malformed /
 * edge-case encoded blobs and /DecodeParms permutations.
 *
 * Unlike CcittDecodeProbe (byte-exact decode of valid strips) and
 * CcittRowsProbe (/Rows-vs-/Height reconciliation), this probe is built to be
 * driven over MANY synthetic / malformed cases and to never abort the run on a
 * decode exception: each case is self-describing on the command line and the
 * probe emits ONE summary line per case so a Python test can pin the outcome.
 *
 * The case bytes and parameters are passed entirely on the command line so the
 * probe stays a pure stdin-free oracle (the Python test owns the corpus):
 *
 *   java -cp ... CcittFaxFuzzProbe <hexEncoded> <params>
 *
 *   args[0] - the raw encoded CCITT strip as a hex string ("" = empty body).
 *   args[1] - comma-separated /DecodeParms. Integer keys: K, Columns, Rows,
 *             Height (Height goes on the STREAM DICT, the rest in /DecodeParms).
 *             Boolean keys (0/1): BlackIs1, EncodedByteAlign, EndOfLine,
 *             EndOfBlock. A key named "NoParms=1" omits /DecodeParms entirely
 *             (defaults path). A key "NoColumns=1" omits /Columns. A key
 *             "NoHeight=1" / Height=0 omits /Height. A key "NoRows=1" /
 *             Rows omitted omits /Rows.
 *
 * Output (one UTF-8 line): on success
 *     "OK len=<n> sha=<hex>"
 * on a decode exception
 *     "ERR <ExceptionSimpleName>"
 *
 * The decoded byte length + SHA-256 fully fingerprint the decoded buffer
 * without dumping (possibly large) raw bytes, and the ERR class name pins the
 * "does PDFBox throw here" axis. For tiny outputs the Python side can also
 * re-derive the bytes and SHA them, so the fingerprint is a complete contract.
 */
public final class CcittFaxFuzzProbe {
    private static final java.util.Set<String> BOOLEAN_KEYS = java.util.Set.of(
            "BlackIs1", "EncodedByteAlign", "EndOfLine", "EndOfBlock");

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] encoded = hexToBytes(args.length > 0 ? args[0] : "");

        boolean noParms = false;
        boolean noColumns = false;
        boolean noHeight = false;
        Integer columns = null;
        Integer rows = null;
        Integer height = null;

        COSDictionary decodeParms = new COSDictionary();
        if (args.length > 1 && !args[1].isEmpty()) {
            for (String pair : args[1].split(",")) {
                int eq = pair.indexOf('=');
                if (eq < 0) {
                    continue;
                }
                String key = pair.substring(0, eq).trim();
                String raw = pair.substring(eq + 1).trim();
                if (key.equals("NoParms")) {
                    noParms = raw.equals("1");
                    continue;
                }
                if (key.equals("NoColumns")) {
                    noColumns = raw.equals("1");
                    continue;
                }
                if (key.equals("NoHeight")) {
                    noHeight = raw.equals("1");
                    continue;
                }
                if (BOOLEAN_KEYS.contains(key)) {
                    boolean value = raw.equals("1") || raw.equalsIgnoreCase("true");
                    decodeParms.setItem(COSName.getPDFName(key),
                            value ? COSBoolean.TRUE : COSBoolean.FALSE);
                } else if (key.equals("Height")) {
                    height = Integer.parseInt(raw);
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
        if (!noParms) {
            streamDict.setItem(COSName.DECODE_PARMS, decodeParms);
        }
        // /Width mirrors /Columns on the stream dict (real image XObject). If
        // /Columns was omitted from /DecodeParms but caller still wants the
        // filter default, leave /Width off too (NoColumns).
        if (!noColumns && columns != null && columns > 0) {
            streamDict.setInt(COSName.WIDTH, columns);
        }
        if (!noHeight && height != null && height > 0) {
            streamDict.setInt(COSName.HEIGHT, height);
        }

        Filter filter = FilterFactory.INSTANCE.getFilter(
                COSName.getPDFName("CCITTFaxDecode"));

        try {
            ByteArrayOutputStream decoded = new ByteArrayOutputStream();
            filter.decode(new ByteArrayInputStream(encoded), decoded, streamDict, 0);
            byte[] result = decoded.toByteArray();
            out.println("OK len=" + result.length + " sha=" + sha256(result));
        } catch (Throwable t) {
            out.println("ERR " + t.getClass().getSimpleName());
        }
        out.flush();
    }

    private static byte[] hexToBytes(String hex) {
        hex = hex.trim();
        if (hex.isEmpty()) {
            return new byte[0];
        }
        int n = hex.length() / 2;
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) {
            b[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        }
        return b;
    }

    private static String sha256(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] digest = md.digest(data);
        StringBuilder sb = new StringBuilder();
        for (byte x : digest) {
            sb.append(String.format("%02x", x));
        }
        return sb.toString();
    }
}
