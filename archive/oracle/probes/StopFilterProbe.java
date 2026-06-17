import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.PDStream;

/**
 * Live oracle probe for PARTIAL (stop-filter) chain decode —
 * {@code PDStream.createInputStream(List&lt;String&gt; stopFilters)}.
 *
 * Per upstream {@code PDStream.createInputStream(java.util.List)}: the
 * {@code /Filter} chain is walked in order, and the FIRST filter whose name is
 * contained in {@code stopFilters} HALTS decoding — that filter and every
 * filter after it is left un-applied, so the returned bytes are the partially
 * decoded body (everything up to, but not including, the stop filter). If the
 * collected (pre-stop) filter list is empty, the RAW stream bytes are returned
 * verbatim. If no filter name matches {@code stopFilters} (or it is null/empty),
 * the whole chain decodes — identical to {@code createInputStream()}.
 *
 * The probe builds a real {@link COSStream} from raw (already-encoded) bytes,
 * sets {@code /Filter} (array or single name) and an optional PARALLEL
 * {@code /DecodeParms} array (with {@code null} for param-less filters) exactly
 * as a parsed PDF would carry them, wraps it in a {@link PDStream}, then drives
 * {@code createInputStream(stopFilters)} — the same code path image XObjects use
 * to short-circuit DCT/JBIG2 decoding. It emits the partially-decoded bytes'
 * length and SHA-256 so the pypdfbox side asserts byte-exact parity without
 * piping raw binary.
 *
 * Usage:
 *   java -cp ... StopFilterProbe raw.bin "ASCII85Decode,FlateDecode" "" "FlateDecode"
 *   java -cp ... StopFilterProbe raw.bin "ASCIIHexDecode,FlateDecode" \
 *         "null;Predictor=2,Colors=3,Columns=4,BitsPerComponent=8" "FlateDecode"
 *
 *   args[0] - path to a file holding the raw (encoded) stream bytes.
 *   args[1] - comma-separated filter names in /Filter array order.
 *   args[2] - /DecodeParms spec: ';'-separated, one segment per filter (aligned
 *             to args[1]); each segment is "null" (-> COSNull) or a comma-list
 *             of integer "Key=Value" pairs (-> COSDictionary). Empty arg = none.
 *   args[3] - OPTIONAL stop-filter spec: comma-separated filter names that halt
 *             decode. Empty / absent = stop nothing (full decode). The literal
 *             "__NULL__" passes a Java null List to exercise the null guard.
 *
 * Output (UTF-8 text, single line): "&lt;decodedLength&gt; &lt;sha256hex&gt;".
 */
public final class StopFilterProbe {
    public static void main(String[] args) throws Exception {
        byte[] rawEncoded = Files.readAllBytes(new File(args[0]).toPath());
        String[] filterNames = args[1].split(",");

        COSStream stream = new COSStream();
        try {
            try (OutputStream rawOut = stream.createRawOutputStream()) {
                rawOut.write(rawEncoded);
            }

            // /Filter array (or single name when only one filter is given).
            if (filterNames.length == 1) {
                stream.setItem(COSName.FILTER, COSName.getPDFName(filterNames[0].trim()));
            } else {
                COSArray filterArray = new COSArray();
                for (String name : filterNames) {
                    filterArray.add(COSName.getPDFName(name.trim()));
                }
                stream.setItem(COSName.FILTER, filterArray);
            }

            // /DecodeParms: a parallel array (or a bare dict for one filter).
            if (args.length > 2 && !args[2].isEmpty()) {
                String[] segments = args[2].split(";", -1);
                if (filterNames.length == 1 && segments.length == 1
                        && !"null".equals(segments[0].trim())) {
                    stream.setItem(COSName.DECODE_PARMS, parseParms(segments[0]));
                } else {
                    COSArray parmsArray = new COSArray();
                    for (String segment : segments) {
                        if ("null".equals(segment.trim()) || segment.trim().isEmpty()) {
                            parmsArray.add(COSNull.NULL);
                        } else {
                            parmsArray.add(parseParms(segment));
                        }
                    }
                    stream.setItem(COSName.DECODE_PARMS, parmsArray);
                }
            }

            // Stop-filter list. "__NULL__" -> Java null (exercises the guard
            // that swaps a null arg for Collections.emptyList()).
            List<String> stopFilters;
            if (args.length > 3 && !args[3].isEmpty()) {
                if ("__NULL__".equals(args[3])) {
                    stopFilters = null;
                } else {
                    stopFilters = new ArrayList<>();
                    for (String name : args[3].split(",")) {
                        stopFilters.add(name.trim());
                    }
                }
            } else {
                stopFilters = Collections.emptyList();
            }

            PDStream pdStream = new PDStream(stream);
            byte[] decoded;
            try (InputStream in = pdStream.createInputStream(stopFilters)) {
                ByteArrayOutputStream sink = new ByteArrayOutputStream();
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) > 0) {
                    sink.write(buf, 0, n);
                }
                decoded = sink.toByteArray();
            }

            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(decoded);
            StringBuilder hex = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                hex.append(Character.forDigit((b >> 4) & 0xF, 16));
                hex.append(Character.forDigit(b & 0xF, 16));
            }

            OutputStream out = System.out;
            out.write((decoded.length + " " + hex).getBytes("UTF-8"));
            out.flush();
        } finally {
            stream.close();
        }
    }

    /** Parse a comma-separated "Key=Value" integer list into a COSDictionary. */
    private static org.apache.pdfbox.cos.COSDictionary parseParms(String spec) {
        org.apache.pdfbox.cos.COSDictionary dict = new org.apache.pdfbox.cos.COSDictionary();
        for (String pair : spec.split(",")) {
            int eq = pair.indexOf('=');
            if (eq < 0) {
                continue;
            }
            String key = pair.substring(0, eq).trim();
            long value = Long.parseLong(pair.substring(eq + 1).trim());
            dict.setItem(COSName.getPDFName(key), COSInteger.get(value));
        }
        return dict;
    }
}
