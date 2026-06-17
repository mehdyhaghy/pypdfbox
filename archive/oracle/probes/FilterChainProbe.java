import java.io.File;
import java.io.OutputStream;
import java.nio.file.Files;
import java.security.MessageDigest;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.io.IOUtils;

/**
 * Live oracle probe for the MULTI-FILTER chain decode surface — a stream whose
 * {@code /Filter} is an ARRAY and whose {@code /DecodeParms} is a PARALLEL
 * ARRAY (one entry per filter, with {@code null} allowed for filters that take
 * no params).
 *
 * The probe builds a real {@link COSStream}, writes the raw (already-encoded)
 * bytes into it via {@code createRawOutputStream()}, sets {@code /Filter} and
 * {@code /DecodeParms} exactly as a parsed PDF stream would carry them, then
 * decodes the whole chain through {@code createInputStream()} — the same code
 * path a real document uses. It emits the decoded bytes' length and SHA-256 so
 * the pypdfbox side can assert byte-exact parity without piping raw binary.
 *
 * Usage:
 *   java -cp ... FilterChainProbe raw.bin "ASCII85Decode,FlateDecode"
 *   java -cp ... FilterChainProbe raw.bin "FlateDecode" "Predictor=12,Columns=4"
 *   java -cp ... FilterChainProbe raw.bin "ASCIIHexDecode,FlateDecode" \
 *         "null;Predictor=2,Colors=3,Columns=4,BitsPerComponent=8"
 *
 *   args[0] - path to a file holding the raw (encoded) stream bytes.
 *   args[1] - comma-separated filter names in /Filter array order.
 *   args[2] - OPTIONAL /DecodeParms spec: ';'-separated, one segment per
 *             filter (aligned to args[1]). Each segment is either the literal
 *             "null" (-> COSNull entry, param-less filter) or a comma-separated
 *             list of integer "Key=Value" pairs (-> a COSDictionary entry).
 *             When args[1] names a single filter and args[2] has a single
 *             non-null segment, /DecodeParms is set as a bare dictionary
 *             (the single-filter shape) rather than a one-element array.
 *
 * Output (UTF-8 text, single line): "<decodedLength> <sha256hex>".
 */
public final class FilterChainProbe {
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

            byte[] decoded;
            try (java.io.InputStream in = stream.createInputStream()) {
                decoded = IOUtils.toByteArray(in);
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
