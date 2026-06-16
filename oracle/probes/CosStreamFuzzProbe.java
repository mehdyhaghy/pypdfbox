import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;

/**
 * Live oracle probe: differential-fuzz Apache PDFBox 3.0.7's {@link COSStream}
 * filtered / unfiltered access and the lazy decode lifecycle.
 *
 * Complementary to CosStreamLenProbe (encode-on-write contract + filter shape)
 * and StreamWireFormatProbe (COSWriter byte image): this probe targets facets
 * NOT covered there — the READ side and the stream lifecycle around raw vs
 * decoded access:
 *
 *   - raw bytes set verbatim with NO filter: createRawInputStream() and
 *     createInputStream() yield byte-IDENTICAL output (the no-filter shortcut);
 *   - raw bytes set verbatim with /Filter present: createRawInputStream() is
 *     the encoded bytes, createInputStream() decodes them; they differ;
 *   - DOUBLE createInputStream(): a second decode reproduces the same bytes
 *     (decode is non-destructive — re-reads from the raw buffer each time);
 *   - getFilters() shape across none / single-name / two-element-array;
 *   - getLength() == raw body length after a verbatim write (NOT the /Filter
 *     decoded length, NOT a stale /Length value);
 *   - the /Length DICTIONARY entry does NOT override getLength(): we set a
 *     bogus /Length integer that disagrees with the body and confirm
 *     getLength() ignores it and reports the real raw length;
 *   - empty stream (constructed, never written): getLength()==0, getFilters()
 *     null, hasData() false, and createInputStream()/createRawInputStream()
 *     both throw IOException;
 *   - a single FlateDecode chain set on raw-encoded bytes round-trips decoded;
 *   - a two-filter chain [/ASCII85Decode /FlateDecode] decodes back to payload;
 *   - toTextString() on a UTF-16BE-BOM body returns the decoded text;
 *   - toTextString() on an empty (no-data) stream returns "" (swallowed).
 *
 * To set raw bytes WITHOUT re-encoding through a filter (so we can drive the
 * decode side independently) we use createRawOutputStream() and then attach
 * /Filter directly via setItem(COSName.FILTER, ...). The encoded bytes are
 * produced once up front (FlateDecode of a fixed payload) by writing them
 * through a throwaway COSStream's createOutputStream(FlateDecode) and reading
 * back createRawInputStream() — guaranteeing the raw bytes are a valid Flate
 * stream PDFBox itself produced.
 *
 * Output: a single JSON object of facts (lengths, booleans, shapes, decoded
 * text, exception class names). The Python side reconstructs the same fixed
 * payload so both engines compare on identical input bytes.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> CosStreamFuzzProbe
 */
public final class CosStreamFuzzProbe {

    // Fixed, compressible decoded payload — matched verbatim on the Python side.
    private static final byte[] PAYLOAD = buildPayload();

    private static byte[] buildPayload() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 40; i++) {
            sb.append("q 1 0 0 1 0 0 cm (decode lifecycle fuzz) Tj Q\n");
        }
        return sb.toString().getBytes(StandardCharsets.ISO_8859_1);
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder b = new StringBuilder();
        b.append('{');

        rawkv(b, "payload_len", Integer.toString(PAYLOAD.length));
        b.append(',');

        // Produce a valid FlateDecode-encoded copy of PAYLOAD (PDFBox-made).
        byte[] flateEncoded = encodeFlate(PAYLOAD);
        byte[] chainEncoded = encodeChain(PAYLOAD);

        rawkv(b, "flate_encoded_len", Integer.toString(flateEncoded.length));
        b.append(',');
        rawkv(b, "chain_encoded_len", Integer.toString(chainEncoded.length));
        b.append(',');

        // --- Case A: verbatim raw, NO filter — raw == decoded ---
        COSStream a = new COSStream();
        try (OutputStream os = a.createRawOutputStream()) {
            os.write(PAYLOAD);
        }
        byte[] aRaw = a.createRawInputStream().readAllBytes();
        byte[] aDecoded = a.createInputStream().readAllBytes();
        rawkv(b, "a_length", Long.toString(a.getLength()));
        b.append(',');
        rawkv(b, "a_has_data", Boolean.toString(a.hasData()));
        b.append(',');
        rawkv(b, "a_raw_equals_decoded",
                Boolean.toString(java.util.Arrays.equals(aRaw, aDecoded)));
        b.append(',');
        rawkv(b, "a_raw_equals_payload",
                Boolean.toString(java.util.Arrays.equals(aRaw, PAYLOAD)));
        b.append(',');
        kv(b, "a_filter_shape", filterShape(a.getFilters()));
        b.append(',');
        a.close();

        // --- Case B: raw encoded bytes + /Filter FlateDecode set directly ---
        COSStream bb = new COSStream();
        try (OutputStream os = bb.createRawOutputStream()) {
            os.write(flateEncoded);
        }
        bb.setItem(COSName.FILTER, COSName.FLATE_DECODE);
        byte[] bRaw = bb.createRawInputStream().readAllBytes();
        byte[] bDecoded1 = bb.createInputStream().readAllBytes();
        byte[] bDecoded2 = bb.createInputStream().readAllBytes(); // double decode
        rawkv(b, "b_length", Long.toString(bb.getLength()));
        b.append(',');
        rawkv(b, "b_raw_len", Integer.toString(bRaw.length));
        b.append(',');
        rawkv(b, "b_raw_differs_decoded",
                Boolean.toString(!java.util.Arrays.equals(bRaw, bDecoded1)));
        b.append(',');
        rawkv(b, "b_decoded_equals_payload",
                Boolean.toString(java.util.Arrays.equals(bDecoded1, PAYLOAD)));
        b.append(',');
        rawkv(b, "b_double_decode_stable",
                Boolean.toString(java.util.Arrays.equals(bDecoded1, bDecoded2)));
        b.append(',');
        kv(b, "b_filter_shape", filterShape(bb.getFilters()));
        b.append(',');
        bb.close();

        // --- Case C: stale /Length disagrees with body ---
        COSStream c = new COSStream();
        try (OutputStream os = c.createRawOutputStream()) {
            os.write(PAYLOAD);
        }
        // Plant a bogus /Length the body does not match.
        c.setItem(COSName.LENGTH, COSInteger.get(999999));
        rawkv(b, "c_get_length", Long.toString(c.getLength()));
        b.append(',');
        rawkv(b, "c_length_entry", Long.toString(c.getLong(COSName.LENGTH)));
        b.append(',');
        rawkv(b, "c_get_length_equals_body",
                Boolean.toString(c.getLength() == PAYLOAD.length));
        b.append(',');
        c.close();

        // --- Case D: empty stream — never written ---
        COSStream d = new COSStream();
        rawkv(b, "d_length", Long.toString(d.getLength()));
        b.append(',');
        rawkv(b, "d_has_data", Boolean.toString(d.hasData()));
        b.append(',');
        kv(b, "d_filter_shape", filterShape(d.getFilters()));
        b.append(',');
        kv(b, "d_raw_input_exc", excClass(() -> d.createRawInputStream()));
        b.append(',');
        kv(b, "d_input_exc", excClass(() -> d.createInputStream()));
        b.append(',');
        kv(b, "d_to_text", d.toTextString());
        b.append(',');
        d.close();

        // --- Case E: two-filter chain on raw bytes ---
        COSStream e = new COSStream();
        try (OutputStream os = e.createRawOutputStream()) {
            os.write(chainEncoded);
        }
        COSArray chainFilters = new COSArray();
        chainFilters.add(COSName.ASCII85_DECODE);
        chainFilters.add(COSName.FLATE_DECODE);
        e.setItem(COSName.FILTER, chainFilters);
        byte[] eDecoded = e.createInputStream().readAllBytes();
        rawkv(b, "e_decoded_equals_payload",
                Boolean.toString(java.util.Arrays.equals(eDecoded, PAYLOAD)));
        b.append(',');
        kv(b, "e_filter_shape", filterShape(e.getFilters()));
        b.append(',');
        kv(b, "e_filter_list", filterList(e));
        b.append(',');
        e.close();

        // --- Case F: toTextString() with a UTF-16BE BOM body, no filter ---
        COSStream f = new COSStream();
        byte[] u16 = new byte[] {
            (byte) 0xFE, (byte) 0xFF, 0x00, 'H', 0x00, 'i', 0x00, '!'
        };
        try (OutputStream os = f.createRawOutputStream()) {
            os.write(u16);
        }
        kv(b, "f_to_text", f.toTextString());
        f.close();

        b.append('}');
        out.print(b);
    }

    private static byte[] encodeFlate(byte[] payload) throws Exception {
        COSStream tmp = new COSStream();
        try (OutputStream os = tmp.createOutputStream(COSName.FLATE_DECODE)) {
            os.write(payload);
        }
        byte[] enc = tmp.createRawInputStream().readAllBytes();
        tmp.close();
        return enc;
    }

    private static byte[] encodeChain(byte[] payload) throws Exception {
        COSStream tmp = new COSStream();
        COSArray filters = new COSArray();
        filters.add(COSName.ASCII85_DECODE);
        filters.add(COSName.FLATE_DECODE);
        try (OutputStream os = tmp.createOutputStream(filters)) {
            os.write(payload);
        }
        byte[] enc = tmp.createRawInputStream().readAllBytes();
        tmp.close();
        return enc;
    }

    private interface ThrowingRun {
        void run() throws Exception;
    }

    private static String excClass(ThrowingRun r) {
        try {
            r.run();
            return "none";
        } catch (Exception ex) {
            return ex.getClass().getName();
        }
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
