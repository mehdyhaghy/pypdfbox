import java.io.OutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;

/**
 * Live oracle probe for {@link COSStream} length + filter write round-trip.
 *
 * Drives Apache PDFBox 3.0.7's {@code COSStream} directly (no document, no
 * parser) to pin the encode-on-write contract the spec implies and pypdfbox
 * must match byte-for-byte:
 *
 *   1. {@code createOutputStream(COSName.FLATE_DECODE)} — write a known
 *      decoded payload, close, then observe that {@code getLength()} now
 *      reports the ENCODED (compressed) length, NOT the decoded length, and
 *      that the {@code /Length} dictionary entry equals {@code getLength()}.
 *   2. {@code /Filter} is recorded as a single bare {@code COSName} (compact
 *      shape) for a one-element chain.
 *   3. {@code createRawInputStream()} yields the raw encoded bytes (length ==
 *      getLength()); {@code createInputStream()} yields the decoded bytes
 *      equal to the original payload — the round-trip invariant.
 *   4. A two-filter chain {@code [/ASCII85Decode /FlateDecode]} records the
 *      array shape and still round-trips decoded-equal.
 *   5. {@code createOutputStream()} with no filter stores the payload verbatim
 *      (raw length == decoded length == payload length, no /Filter).
 *
 * Usage: java -cp ... CosStreamLenProbe
 *
 * Output: a single JSON object. The decoded payload is fixed in the probe so
 * both sides operate on identical input bytes; lengths are emitted as numbers
 * and the SHA-free comparison relies on decoded bytes being reproduced by the
 * Python side from the same constant. Filter shapes are emitted as strings.
 */
public final class CosStreamLenProbe {

    // Fixed, compressible payload — repeated text so FlateDecode shrinks it,
    // making encoded length strictly less than decoded length (so a test that
    // accidentally reported the decoded length would diverge visibly).
    private static final byte[] PAYLOAD = buildPayload();

    private static byte[] buildPayload() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 64; i++) {
            sb.append("BT /F1 12 Tf 100 700 Td (Hello COSStream Length) Tj ET\n");
        }
        return sb.toString().getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder b = new StringBuilder();
        b.append('{');

        rawkv(b, "payload_len", Integer.toString(PAYLOAD.length));
        b.append(',');

        // --- Case 1+2+3: single FlateDecode filter ---
        COSStream flate = new COSStream();
        try (OutputStream os = flate.createOutputStream(COSName.FLATE_DECODE)) {
            os.write(PAYLOAD);
        }
        long flateLen = flate.getLength();
        long flateLengthEntry = flate.getLong(COSName.LENGTH);
        byte[] flateRaw = flate.createRawInputStream().readAllBytes();
        byte[] flateDecoded = flate.createInputStream().readAllBytes();

        rawkv(b, "flate_length", Long.toString(flateLen));
        b.append(',');
        rawkv(b, "flate_length_entry", Long.toString(flateLengthEntry));
        b.append(',');
        rawkv(b, "flate_raw_len", Integer.toString(flateRaw.length));
        b.append(',');
        rawkv(b, "flate_decoded_len", Integer.toString(flateDecoded.length));
        b.append(',');
        rawkv(b, "flate_decoded_equals_payload",
                Boolean.toString(java.util.Arrays.equals(flateDecoded, PAYLOAD)));
        b.append(',');
        rawkv(b, "flate_encoded_lt_decoded",
                Boolean.toString(flateLen < flateDecoded.length));
        b.append(',');
        kv(b, "flate_filter_shape", filterShape(flate.getFilters()));
        b.append(',');
        kv(b, "flate_filter_list", filterList(flate));
        b.append(',');
        flate.close();

        // --- Case 4: two-filter chain ASCII85 + Flate ---
        COSStream chain = new COSStream();
        COSArray filters = new COSArray();
        filters.add(COSName.ASCII85_DECODE);
        filters.add(COSName.FLATE_DECODE);
        try (OutputStream os = chain.createOutputStream(filters)) {
            os.write(PAYLOAD);
        }
        long chainLen = chain.getLength();
        byte[] chainDecoded = chain.createInputStream().readAllBytes();
        rawkv(b, "chain_length", Long.toString(chainLen));
        b.append(',');
        rawkv(b, "chain_decoded_equals_payload",
                Boolean.toString(java.util.Arrays.equals(chainDecoded, PAYLOAD)));
        b.append(',');
        kv(b, "chain_filter_shape", filterShape(chain.getFilters()));
        b.append(',');
        kv(b, "chain_filter_list", filterList(chain));
        b.append(',');
        chain.close();

        // --- Case 5: no filter — verbatim ---
        COSStream raw = new COSStream();
        try (OutputStream os = raw.createOutputStream()) {
            os.write(PAYLOAD);
        }
        long rawLen = raw.getLength();
        byte[] rawRaw = raw.createRawInputStream().readAllBytes();
        byte[] rawDecoded = raw.createInputStream().readAllBytes();
        rawkv(b, "raw_length", Long.toString(rawLen));
        b.append(',');
        rawkv(b, "raw_raw_len", Integer.toString(rawRaw.length));
        b.append(',');
        rawkv(b, "raw_decoded_len", Integer.toString(rawDecoded.length));
        b.append(',');
        kv(b, "raw_filter_shape", filterShape(raw.getFilters()));
        raw.close();

        b.append('}');
        out.print(b);
    }

    private static String filterShape(COSBase filters) {
        if (filters == null) {
            return "none";
        }
        if (filters instanceof COSName) {
            return "name";
        }
        if (filters instanceof COSArray) {
            return "array";
        }
        return "other";
    }

    private static String filterList(COSStream s) {
        COSBase filters = s.getFilters();
        StringBuilder sb = new StringBuilder();
        if (filters instanceof COSName n) {
            sb.append(n.getName());
        } else if (filters instanceof COSArray arr) {
            for (int i = 0; i < arr.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(((COSName) arr.get(i)).getName());
            }
        }
        return sb.toString();
    }

    private static void kv(StringBuilder b, String key, String value) {
        emitString(b, key);
        b.append(':');
        emitString(b, value);
    }

    private static void rawkv(StringBuilder b, String key, String value) {
        emitString(b, key);
        b.append(':');
        b.append(value);
    }

    private static void emitString(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\b': sb.append("\\b"); break;
                case '\f': sb.append("\\f"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
    }
}
