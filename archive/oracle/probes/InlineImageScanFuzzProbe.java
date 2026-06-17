import java.io.PrintStream;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdfparser.PDFStreamParser;

/**
 * Live oracle probe (wave 1559): drive Apache PDFBox's {@code PDFStreamParser}
 * over raw content-stream byte buffers that embed inline images (BI/ID/EI) and
 * project, in stream order:
 * <ul>
 *   <li>the parsed inline-image facts assembled by the parser — the BI parameter
 *       dictionary keys (W/H/BPC/CS/F) PLUS the length + tail of the binary image
 *       data the ID..EI scanner delimited;</li>
 *   <li>the OPERATORS that follow EI — i.e. whether the EI-terminator heuristic
 *       resynchronised the operator stream correctly after the binary payload
 *       (a mis-detected terminator desyncs everything downstream).</li>
 * </ul>
 *
 * <p>This is the operator-stream BI/ID/EI SCAN + collate surface, distinct from
 * {@code InlineImageOperatorFuzzProbe} (graphics-engine draw dispatch),
 * {@code InlineCsResolveProbe} (colour-space resolution against page resources),
 * and {@code InlineEiScanProbe} (raw data length/sha only). The fuzz angles
 * concentrate on the EI-detection edge cases: binary data containing the bytes
 * {@code EI} mid-stream (the scanner must use length / whitespace heuristics, not
 * the first {@code EI}); abbreviated keys + abbreviated filters/colour spaces;
 * whitespace variations after {@code ID}; missing {@code EI}; and an inline image
 * immediately followed by a real operator.
 *
 * <p>Output (UTF-8) is one block per case key:
 * <pre>
 *   case=&lt;key&gt; ops=&lt;total-token-count&gt; err=&lt;none|throw&gt;
 *   img w=&lt;W&gt; h=&lt;H&gt; bpc=&lt;BPC&gt; cs=&lt;name|-&gt; f=&lt;filters|-&gt; len=&lt;data-len&gt; tail=&lt;hex&gt;
 *   post=&lt;space-joined operator names AFTER this BI, to end of stream&gt;
 * </pre>
 * one {@code img}+{@code post} pair per {@code BI} operator carrying image data.
 *
 * <p>Usage: {@code java -cp <pdfbox-app.jar>:<build> InlineImageScanFuzzProbe <case>}
 */
public final class InlineImageScanFuzzProbe {

    /** Named fuzz cases — identical content-stream bytes to the pytest side. */
    static final Map<String, String> CASES = new LinkedHashMap<>();

    static {
        // 1) Plain uncompressed 2x2 RGB raster (12 bytes) then a real operator.
        CASES.put("basic_then_q", "BI /W 2 /H 2 /BPC 8 /CS /RGB ID abcdefghijkl EI Q");
        // 2) Binary payload that CONTAINS the bytes "EI" mid-stream: the scanner
        //    must skip the embedded EI and stop at the whitespace-delimited one.
        CASES.put("embedded_ei",
                "BI /W 4 /H 1 /BPC 8 /CS /G ID aEIbcdEIfg EI Q");
        // 3) Embedded "EI" right at a word boundary followed by more data.
        CASES.put("embedded_ei_ws",
                "BI /W 6 /H 1 /BPC 8 /CS /G ID xx EI yy EI Q");
        // 4) Abbreviated colour space /G + abbreviated filter /AHx (ASCIIHex).
        //    Payload is ASCIIHex of "abc" => 616263, '>' terminator.
        CASES.put("ahx_filter",
                "BI /W 1 /H 1 /BPC 8 /CS /G /F /AHx ID 616263> EI Q");
        // 5) Filter chain /AHx then /Fl (ASCIIHex outer, Flate inner) as array.
        CASES.put("filter_chain",
                "BI /W 1 /H 1 /BPC 8 /CS /G /F [/AHx /Fl] ID 78da4b4c4a0600026d0121> EI Q");
        // 6) Abbreviated /RGB device colour.
        CASES.put("rgb_abbrev", "BI /W 1 /H 1 /BPC 8 /CS /RGB ID abc EI Q");
        // 7) Abbreviated /CMYK device colour.
        CASES.put("cmyk_abbrev", "BI /W 1 /H 1 /BPC 8 /CS /CMYK ID abcd EI Q");
        // 8) Indexed via /I abbreviation, base /RGB abbrev.
        CASES.put("indexed_i",
                "BI /W 2 /H 1 /BPC 8 /CS [/I /RGB 1 <000000ffffff>] ID   EI Q");
        // 9) Long-form keys throughout.
        CASES.put("long_keys",
                "BI /Width 2 /Height 2 /BitsPerComponent 8 /ColorSpace /DeviceRGB ID abcdefghijkl EI Q");
        // 10) Stencil image mask via /IM true, missing /CS, 1 bpc implied.
        CASES.put("stencil", "BI /W 8 /H 1 /IM true ID ÿ EI Q");
        // 11) Whitespace variation: a single LF separates ID from data.
        CASES.put("id_lf", "BI /W 1 /H 1 /BPC 8 /CS /G ID\nabc EI Q");
        // 12) Whitespace variation: CR LF after ID.
        CASES.put("id_crlf", "BI /W 1 /H 1 /BPC 8 /CS /G ID\r\nabc EI Q");
        // 13) Whitespace variation: a space then the data (canonical).
        CASES.put("id_space", "BI /W 1 /H 1 /BPC 8 /CS /G ID abc EI Q");
        // 14) Inline image followed by ANOTHER inline image (resync between).
        CASES.put("two_inline",
                "BI /W 1 /H 1 /BPC 8 /CS /G ID a EI BI /W 1 /H 1 /BPC 8 /CS /RGB ID abc EI Q");
        // 15) Inline image followed by a text-show sequence.
        CASES.put("then_text",
                "BI /W 1 /H 1 /BPC 8 /CS /G ID a EI BT (hi) Tj ET");
        // 16) Missing EI entirely — scanner runs to end of buffer.
        CASES.put("missing_ei", "BI /W 1 /H 1 /BPC 8 /CS /G ID abcdef");
        // 17) Zero-byte data: ID immediately followed by EI (one space each).
        CASES.put("zero_data", "BI /W 1 /H 1 /BPC 8 /CS /G ID  EI Q");
        // 18) Payload ending with the letter 'E' just before the EI delimiter.
        CASES.put("trailing_e", "BI /W 1 /H 1 /BPC 8 /CS /G ID abcE EI Q");
        // 19) Payload that ends in "EI" bytes with NO trailing whitespace before
        //     the real " EI": stresses the look-ahead/binary follow-on probe.
        CASES.put("ei_glued", "BI /W 1 /H 1 /BPC 8 /CS /G ID abEI EI Q");
        // 20) Two operators after EI (Q then a path move).
        CASES.put("post_two_ops",
                "BI /W 1 /H 1 /BPC 8 /CS /G ID a EI Q 0 0 m");
        // 21) Inline image with /D decode array.
        CASES.put("decode_arr",
                "BI /W 1 /H 1 /BPC 8 /CS /G /D [1 0] ID a EI Q");
        // 22) Interpolate /I true (the /I abbreviation here is Interpolate, not
        //     Indexed — Indexed only appears as the head of a /CS array).
        CASES.put("interpolate", "BI /W 1 /H 1 /BPC 8 /CS /G /I true ID a EI Q");
        // 23) Extra whitespace runs inside the dict.
        CASES.put("loose_ws",
                "BI   /W   2   /H 2   /BPC 8   /CS /RGB   ID abcdefghijkl EI Q");
        // 24) Tab + form-feed whitespace around ID and EI.
        CASES.put("tab_ff",
                "BI /W 1 /H 1 /BPC 8 /CS /G ID\tabc\fEI Q");
        // 25) Payload contains a newline + "EI" but no whitespace AFTER (so it
        //     is binary, not a terminator) before the real terminator.
        CASES.put("ei_then_data",
                "BI /W 5 /H 1 /BPC 8 /CS /G ID ab\nEIcd EI Q");
        // 26) Bigger payload (RunLengthDecode abbrev /RL) — literal run of 3.
        CASES.put("rl_filter",
                "BI /W 1 /H 1 /BPC 8 /CS /G /F /RL ID abc EI Q");
        // 27) /CS before /W (key order does not matter to the dict).
        CASES.put("key_order",
                "BI /CS /G /BPC 8 /H 2 /W 2 ID abcd EI Q");
        // 28) ASCII85 abbreviation /A85.
        CASES.put("a85_filter",
                "BI /W 1 /H 1 /BPC 8 /CS /G /F /A85 ID @:E_WAS~> EI Q");
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String key = args[0];
        String content = CASES.get(key);
        if (content == null) {
            out.print("err=nocase\n");
            return;
        }
        byte[] bytes = content.getBytes("ISO-8859-1");

        StringBuilder sb = new StringBuilder();
        boolean threw = false;
        List<Object> tokens = new ArrayList<>();
        try {
            PDFStreamParser parser = new PDFStreamParser(bytes);
            for (Object tok : parser.parse()) {
                tokens.add(tok);
            }
        } catch (Throwable t) {
            threw = true;
        }
        sb.append("case=").append(key)
          .append(" ops=").append(tokens.size())
          .append(" err=").append(threw ? "throw" : "none").append('\n');

        for (int i = 0; i < tokens.size(); i++) {
            Object tok = tokens.get(i);
            if (!(tok instanceof Operator)) {
                continue;
            }
            Operator op = (Operator) tok;
            if (!"BI".equals(op.getName()) || op.getImageData() == null) {
                continue;
            }
            byte[] data = op.getImageData();
            COSDictionary params = op.getImageParameters();
            sb.append("img ")
              .append("w=").append(intKey(params, "W", "Width"))
              .append(" h=").append(intKey(params, "H", "Height"))
              .append(" bpc=").append(intKey(params, "BPC", "BitsPerComponent"))
              .append(" cs=").append(csKey(params))
              .append(" f=").append(filterKey(params))
              .append(" len=").append(data.length)
              .append(" tail=").append(tail(data, 8))
              .append('\n');
            sb.append("post=").append(postOps(tokens, i + 1)).append('\n');
        }
        out.print(sb);
    }

    private static String intKey(COSDictionary params, String shortKey, String longKey) {
        if (params == null) {
            return "-";
        }
        COSBase v = params.getDictionaryObject(
                COSName.getPDFName(shortKey), COSName.getPDFName(longKey));
        if (v instanceof org.apache.pdfbox.cos.COSNumber) {
            return Integer.toString(((org.apache.pdfbox.cos.COSNumber) v).intValue());
        }
        return "-";
    }

    private static String csKey(COSDictionary params) {
        if (params == null) {
            return "-";
        }
        COSBase v = params.getDictionaryObject(
                COSName.getPDFName("CS"), COSName.getPDFName("ColorSpace"));
        return cosShape(v);
    }

    private static String filterKey(COSDictionary params) {
        if (params == null) {
            return "-";
        }
        COSBase v = params.getDictionaryObject(
                COSName.getPDFName("F"), COSName.getPDFName("Filter"));
        return cosShape(v);
    }

    private static String cosShape(COSBase v) {
        if (v instanceof COSName) {
            return ((COSName) v).getName();
        }
        if (v instanceof COSArray) {
            StringBuilder s = new StringBuilder("[");
            COSArray arr = (COSArray) v;
            for (int i = 0; i < arr.size(); i++) {
                if (i > 0) {
                    s.append(',');
                }
                COSBase e = arr.getObject(i);
                if (e instanceof COSName) {
                    s.append(((COSName) e).getName());
                } else if (e != null) {
                    s.append(e.getClass().getSimpleName());
                } else {
                    s.append("null");
                }
            }
            return s.append(']').toString();
        }
        return "-";
    }

    private static String postOps(List<Object> tokens, int from) {
        StringBuilder s = new StringBuilder();
        for (int i = from; i < tokens.size(); i++) {
            Object t = tokens.get(i);
            if (t instanceof Operator) {
                if (s.length() > 0) {
                    s.append(' ');
                }
                s.append(((Operator) t).getName());
            }
        }
        return s.length() == 0 ? "-" : s.toString();
    }

    private static String tail(byte[] data, int n) {
        int start = Math.max(0, data.length - n);
        StringBuilder s = new StringBuilder();
        for (int i = start; i < data.length; i++) {
            int v = data[i] & 0xFF;
            s.append(Character.forDigit((v >> 4) & 0xF, 16));
            s.append(Character.forDigit(v & 0xF, 16));
        }
        return s.length() == 0 ? "-" : s.toString();
    }
}
