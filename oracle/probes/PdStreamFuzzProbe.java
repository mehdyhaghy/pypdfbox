import java.io.InputStream;
import java.io.OutputStream;
import java.security.MessageDigest;
import java.util.Arrays;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.io.IOUtils;
import org.apache.pdfbox.pdmodel.common.PDStream;

/**
 * Live oracle probe for the DECODE / RAW byte-level read path of
 * {@code org.apache.pdfbox.pdmodel.common.PDStream}. Wave 1563, agent B.
 *
 * <p>Complements:
 * <ul>
 *   <li>{@code PdStreamEncodeProbe} — the encode-on-write constructor;</li>
 *   <li>{@code PdStreamFilterChainFuzzProbe} (wave 1529) — the pure
 *       dictionary-shape {@code /Filter} / {@code /DecodeParms} accessors
 *       (no body bytes).</li>
 * </ul>
 *
 * This probe plants <em>real already-encoded body bytes</em> into a bare
 * {@code COSStream} via {@code createRawOutputStream()} (the parser-populated
 * shape — bytes are stored verbatim, not re-encoded), records a fuzzed
 * {@code /Filter} chain and a fuzzed {@code /Length}, wraps it in a
 * {@code PDStream}, then projects:
 *
 * <pre>
 *   createInputStream()                    -&gt; decoded len + sha256
 *   getCOSObject().createRawInputStream()  -&gt; raw len + sha256
 *   getFilters()                           -&gt; ordered name list
 *   getLength()                            -&gt; the dictionary /Length int
 * </pre>
 *
 * <h2>Output grammar</h2> (one line per case id, args order):
 * <pre>
 *   CASE &lt;id&gt; dec=&lt;len|ERR:Exc&gt;/&lt;sha8&gt; raw=&lt;len|ERR:Exc&gt;/&lt;sha8&gt; filters=&lt;...&gt; length=&lt;int&gt;
 * </pre>
 * {@code dec}/{@code raw} render {@code ERR:<ExcSimpleName>} when the
 * corresponding stream construction/read throws; otherwise {@code <len>/<sha8>}
 * where sha8 is the first 8 hex chars of the SHA-256 of the bytes.
 * {@code filters} is {@code name,name,...} ({@code -} when empty).
 */
public final class PdStreamFuzzProbe {

    static final COSName FILTER = COSName.FILTER;
    static final COSName LENGTH = COSName.LENGTH;

    // Pre-computed encoded payloads shared bit-for-bit with the Python test.
    // FlateDecode of "Hello, PDFBox!" (14 decoded bytes).
    static final byte[] FLATE_HELLO = hex("789cf348cdc9c9d75108707173caaf50040022410465");
    // FlateDecode of "" (0 decoded bytes).
    static final byte[] FLATE_EMPTY = hex("789c030000000001");
    // ASCIIHexDecode of "Hi" -> "4869>" (5 raw bytes, 2 decoded).
    static final byte[] AHX_HI = "4869>".getBytes();
    // ASCIIHexDecode then FlateDecode: take FLATE_HELLO bytes, hex-encode them,
    // append '>' EOD -> a two-filter chain [ASCIIHexDecode, FlateDecode].
    static final byte[] AHX_FLATE_HELLO = asciiHexEncode(FLATE_HELLO);
    // Truncated/garbage flate body (invalid zlib stream).
    static final byte[] BAD_FLATE = hex("789cffff00");

    static COSStream build(String id) throws Exception {
        COSStream s = new COSStream();
        switch (id) {
            case "no_filter_plain":
                // No /Filter: createInputStream returns the raw bytes verbatim.
                writeRaw(s, "plain-body".getBytes());
                break;
            case "flate_single_name":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, COSName.FLATE_DECODE);
                break;
            case "flate_array_one":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, arr(COSName.FLATE_DECODE));
                break;
            case "asciihex_single":
                writeRaw(s, AHX_HI);
                s.setItem(FILTER, COSName.ASCII_HEX_DECODE);
                break;
            case "chain_ahx_flate":
                // Two-filter chain, applied left-to-right.
                writeRaw(s, AHX_FLATE_HELLO);
                s.setItem(FILTER, arr(COSName.ASCII_HEX_DECODE, COSName.FLATE_DECODE));
                break;
            case "flate_empty_body":
                writeRaw(s, FLATE_EMPTY);
                s.setItem(FILTER, COSName.FLATE_DECODE);
                break;
            case "empty_no_body_no_filter":
                // Never set any body at all.
                break;
            case "empty_no_body_with_filter":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                break;
            case "length_correct":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(LENGTH, COSInteger.get(FLATE_HELLO.length));
                break;
            case "length_wrong_small":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(LENGTH, COSInteger.get(3));
                break;
            case "length_wrong_huge":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(LENGTH, COSInteger.get(999999));
                break;
            case "length_negative":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(LENGTH, COSInteger.get(-5));
                break;
            case "length_absent_with_body":
                // Body present but no /Length entry written explicitly.
                // (createRawOutputStream sets /Length on close, so remove it.)
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.removeItem(LENGTH);
                break;
            case "raw_no_filter":
                writeRaw(s, FLATE_HELLO);
                // No /Filter set: decoded == raw (verbatim passthrough).
                break;
            case "bad_flate_body":
                writeRaw(s, BAD_FLATE);
                s.setItem(FILTER, COSName.FLATE_DECODE);
                break;
            case "filter_unknown_name":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, COSName.getPDFName("BogusDecode"));
                break;
            case "filter_string_wrongtype":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, new COSString("FlateDecode"));
                break;
            case "filter_int_wrongtype":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, COSInteger.get(7));
                break;
            case "filter_array_empty":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, new COSArray());
                break;
            case "double_flate_chain":
                // Encode "Hello, PDFBox!" through Flate twice -> [Flate, Flate].
                writeRaw(s, flateEncode(FLATE_HELLO));
                s.setItem(FILTER, arr(COSName.FLATE_DECODE, COSName.FLATE_DECODE));
                break;
            default:
                throw new IllegalArgumentException("unknown case " + id);
        }
        return s;
    }

    static void writeRaw(COSStream s, byte[] data) throws Exception {
        try (OutputStream os = s.createRawOutputStream()) {
            os.write(data);
        }
    }

    static byte[] flateEncode(byte[] decoded) throws Exception {
        COSStream tmp = new COSStream();
        try (OutputStream os = tmp.createOutputStream(COSName.FLATE_DECODE)) {
            os.write(decoded);
        }
        try (InputStream is = tmp.createRawInputStream()) {
            return IOUtils.toByteArray(is);
        }
    }

    static byte[] asciiHexEncode(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            sb.append(String.format("%02x", b & 0xff));
        }
        sb.append('>');
        return sb.toString().getBytes();
    }

    static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase b : items) {
            a.add(b);
        }
        return a;
    }

    static byte[] hex(String s) {
        int n = s.length() / 2;
        byte[] out = new byte[n];
        for (int i = 0; i < n; i++) {
            out[i] = (byte) Integer.parseInt(s.substring(2 * i, 2 * i + 2), 16);
        }
        return out;
    }

    static String sha8(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] d = md.digest(data);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 4; i++) {
            sb.append(String.format("%02x", d[i]));
        }
        return sb.toString();
    }

    static String decProj(PDStream pd) {
        try (InputStream is = pd.createInputStream()) {
            byte[] b = IOUtils.toByteArray(is);
            return b.length + "/" + sha8(b);
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String rawProj(PDStream pd) {
        try (InputStream is = pd.getCOSObject().createRawInputStream()) {
            byte[] b = IOUtils.toByteArray(is);
            return b.length + "/" + sha8(b);
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String filtersProj(PDStream pd) {
        try {
            java.util.List<COSName> fs = pd.getFilters();
            if (fs.isEmpty()) {
                return "-";
            }
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < fs.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(fs.get(i).getName());
            }
            return sb.toString();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String lengthProj(PDStream pd) {
        try {
            return Integer.toString(pd.getLength());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    public static void main(String[] args) {
        StringBuilder out = new StringBuilder();
        for (String id : args) {
            String dec;
            String raw;
            String filters;
            String length;
            try {
                PDStream pd = new PDStream(build(id));
                dec = decProj(pd);
                raw = rawProj(pd);
                filters = filtersProj(pd);
                length = lengthProj(pd);
            } catch (Exception e) {
                dec = "BUILD:" + e.getClass().getSimpleName();
                raw = "-";
                filters = "-";
                length = "-";
            }
            out.append("CASE ").append(id)
                    .append(" dec=").append(dec)
                    .append(" raw=").append(raw)
                    .append(" filters=").append(filters)
                    .append(" length=").append(length)
                    .append('\n');
        }
        System.out.print(out);
        // Silence unused-import warnings deterministically.
        if (args.length < 0) {
            System.out.println(Arrays.toString(args));
        }
    }
}
