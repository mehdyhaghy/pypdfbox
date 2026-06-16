import java.io.InputStream;
import java.io.OutputStream;
import java.security.MessageDigest;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.io.IOUtils;

/**
 * Live oracle probe for {@code COSStream}'s {@code /Filter} resolution +
 * decode path. Wave 1564, agent A.
 *
 * <p>Targets two specific {@code COSStream.getFilterList()} /
 * {@code Filter.decode} behaviours that pypdfbox previously diverged on
 * (flagged by wave 1563, see DEFERRED.md):
 *
 * <ol>
 *   <li><b>Non-name {@code /Filter}</b> — a {@code COSString} /
 *       {@code COSInteger} / {@code COSBoolean} scalar is treated leniently
 *       as "no filters": {@code getFilterList()} returns an empty list, so
 *       {@code createInputStream()} passes the raw body through verbatim
 *       ({@code dec == raw}). A non-name <em>element inside</em> a
 *       {@code /Filter} array is the opposite — it throws
 *       {@code IOException("Forbidden type in filter array: ...")}.</li>
 *   <li><b>Duplicate filters</b> — {@code Filter.decode} dedups the chain
 *       (keyed on the resolved {@code Filter} instance, so abbreviated names
 *       collapse onto their long form), keeping the first occurrence, logs
 *       "Removed duplicated filter entries", and decodes the deduped chain
 *       once. So {@code [FlateDecode, FlateDecode]} decodes a single time.</li>
 * </ol>
 *
 * <h2>Output grammar</h2> (one line per case id, args order):
 * <pre>
 *   CASE &lt;id&gt; filters=&lt;...&gt; dec=&lt;len|ERR:Exc&gt;/&lt;sha8&gt; raw=&lt;len&gt;/&lt;sha8&gt;
 * </pre>
 * {@code filters} is {@code name,name,...} ({@code -} when {@code getFilters()}
 * is null) or {@code ERR:<Exc>}; {@code dec} renders {@code <len>/<sha8>} or
 * {@code ERR:<ExcSimpleName>} when decode throws; {@code raw} is the verbatim
 * encoded body. sha8 = first 8 hex chars of SHA-256.
 */
public final class CosStreamFilterFuzzProbe {

    static final COSName FILTER = COSName.FILTER;

    // FlateDecode of "Hello, PDFBox!" (14 decoded bytes).
    static final byte[] FLATE_HELLO = hex("789cf348cdc9c9d75108707173caaf50040022410465");
    // ASCIIHexDecode of "Hi" -> "4869>" (5 raw bytes, 2 decoded).
    static final byte[] AHX_HI = "4869>".getBytes();

    static COSStream build(String id) throws Exception {
        COSStream s = new COSStream();
        switch (id) {
            case "single_valid_flate":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, COSName.FLATE_DECODE);
                break;
            case "non_name_string":
                // Non-name scalar /Filter -> lenient "no filters", dec == raw.
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, new COSString("FlateDecode"));
                break;
            case "non_name_int":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, COSInteger.get(7));
                break;
            case "non_name_bool":
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, COSBoolean.TRUE);
                break;
            case "array_non_name_element":
                // A non-name element inside the array -> IOException.
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, mixedArr(COSName.FLATE_DECODE, COSInteger.get(3)));
                break;
            case "dup_flate":
                // [FlateDecode, FlateDecode] over a single-flate body:
                // dedups to one, decodes once -> "Hello, PDFBox!".
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, arr(COSName.FLATE_DECODE, COSName.FLATE_DECODE));
                break;
            case "dup_flate_abbrev":
                // [Fl, Fl] -> same FlateFilter instance -> dedup to one.
                writeRaw(s, FLATE_HELLO);
                s.setItem(FILTER, arr(COSName.getPDFName("Fl"), COSName.getPDFName("Fl")));
                break;
            case "distinct_ahx_flate":
                // [ASCIIHexDecode, FlateDecode] distinct -> both apply.
                writeRaw(s, asciiHexEncode(FLATE_HELLO));
                s.setItem(FILTER, arr(COSName.ASCII_HEX_DECODE, COSName.FLATE_DECODE));
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

    static byte[] asciiHexEncode(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            sb.append(String.format("%02x", b & 0xff));
        }
        sb.append('>');
        return sb.toString().getBytes();
    }

    static COSArray arr(COSName... items) {
        COSArray a = new COSArray();
        for (COSName b : items) {
            a.add(b);
        }
        return a;
    }

    static COSArray mixedArr(COSBase... items) {
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

    static String filtersProj(COSStream s) {
        try {
            COSBase f = s.getFilters();
            if (f == null) {
                return "-";
            }
            if (f instanceof COSName) {
                return ((COSName) f).getName();
            }
            if (f instanceof COSArray) {
                COSArray a = (COSArray) f;
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < a.size(); i++) {
                    if (i > 0) {
                        sb.append(',');
                    }
                    COSBase e = a.get(i);
                    sb.append(e instanceof COSName ? ((COSName) e).getName()
                            : e.getClass().getSimpleName());
                }
                return sb.toString();
            }
            return f.getClass().getSimpleName();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String decProj(COSStream s) {
        try (InputStream is = s.createInputStream()) {
            byte[] b = IOUtils.toByteArray(is);
            return b.length + "/" + sha8(b);
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String rawProj(COSStream s) {
        try (InputStream is = s.createRawInputStream()) {
            byte[] b = IOUtils.toByteArray(is);
            return b.length + "/" + sha8(b);
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    public static void main(String[] args) {
        StringBuilder out = new StringBuilder();
        for (String id : args) {
            String filters;
            String dec;
            String raw;
            try {
                COSStream s = build(id);
                filters = filtersProj(s);
                dec = decProj(s);
                raw = rawProj(s);
            } catch (Exception e) {
                filters = "BUILD:" + e.getClass().getSimpleName();
                dec = "-";
                raw = "-";
            }
            out.append("CASE ").append(id)
                    .append(" filters=").append(filters)
                    .append(" dec=").append(dec)
                    .append(" raw=").append(raw)
                    .append('\n');
        }
        System.out.print(out);
    }
}
