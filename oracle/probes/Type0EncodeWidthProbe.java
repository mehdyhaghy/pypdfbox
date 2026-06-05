import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;
import org.apache.pdfbox.cos.COSName;

/**
 * Live oracle probe: emit Apache PDFBox's PDType0Font WRITE-side encode +
 * getStringWidth(String) pipeline for every Type0 (composite) font on every
 * page of a PDF.
 *
 * This is the complement of Type0ReadWidthProbe (which drives the decode/width
 * read surface). Here we drive the encode roundtrip: for a sample string we
 * call font.encode(String) -> bytes (hex), and font.getStringWidth(String) ->
 * advance. The sample string is derived from the font's own /ToUnicode CMap so
 * the characters are ones the font actually covers (otherwise every font would
 * just throw on encode). For a symbolic subset CIDFontType2 with only a (3,0)
 * Microsoft-symbol cmap this exercises the symbol-cmap fallback in
 * PDCIDFontType2.encode that the read path never touches.
 *
 * Output (UTF-8, tab-delimited, deterministic order: page, font name):
 *   FONT \t page \t fontKey \t baseFont
 *   ENC  \t page \t fontKey \t sampleHexUtf16 \t encodedHex \t stringWidth
 *   CHENC\t page \t fontKey \t codepoint \t encodedHex \t glyphWidth
 * Calls that throw upstream are emitted with "ERR" so pypdfbox pins the same
 * failure boundary. Widths use Locale.ROOT %.4f with -0.0 collapsed to 0.0.
 */
public final class Type0EncodeWidthProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res != null) {
                    emitPage(out, res, pageIndex);
                }
                pageIndex++;
            }
        }
    }

    private static void emitPage(PrintStream out, PDResources res, int pageIndex)
            throws Exception {
        for (COSName name : res.getFontNames()) {
            PDFont font;
            try {
                font = res.getFont(name);
            } catch (Exception e) {
                continue;
            }
            if (!(font instanceof PDType0Font)) {
                continue;
            }
            PDType0Font t0 = (PDType0Font) font;
            out.printf("FONT\t%d\t%s\t%s%n",
                pageIndex, name.getName(), String.valueOf(t0.getName()));

            // Build a sample string from the font's own toUnicode map by
            // probing codepoints that the font can decode. We harvest unicode
            // characters by round-tripping a range of CIDs through toUnicode.
            List<Integer> cps = sampleCodepoints(t0);
            StringBuilder sb = new StringBuilder();
            for (int cp : cps) {
                sb.appendCodePoint(cp);
                // Per-codepoint encode + width for fine-grained pins.
                String chStr = new String(Character.toChars(cp));
                String encHex;
                String w;
                try {
                    encHex = hex(t0.encode(chStr));
                } catch (Exception e) {
                    encHex = "ERR";
                }
                try {
                    int code = firstCode(t0, chStr);
                    w = code < 0 ? "ERR" : fmt(t0.getWidth(code));
                } catch (Exception e) {
                    w = "ERR";
                }
                out.printf("CHENC\t%d\t%s\t%d\t%s\t%s%n",
                    pageIndex, name.getName(), cp, encHex, w);
            }
            String sample = sb.toString();
            String encodedHex;
            try {
                encodedHex = hex(t0.encode(sample));
            } catch (Exception e) {
                encodedHex = "ERR";
            }
            String sw;
            try {
                sw = fmt(t0.getStringWidth(sample));
            } catch (Exception e) {
                sw = "ERR";
            }
            out.printf("ENC\t%d\t%s\t%s\t%s\t%s%n",
                pageIndex, name.getName(), hexUtf16(sample), encodedHex, sw);
        }
    }

    /**
     * Encode a single codepoint to its code via encode(), then return that
     * code (Identity-H 2-byte big-endian). Returns -1 on failure.
     */
    private static int firstCode(PDType0Font t0, String chStr) {
        try {
            byte[] enc = t0.encode(chStr);
            int code = 0;
            for (byte b : enc) {
                code = (code << 8) | (b & 0xFF);
            }
            return code;
        } catch (Exception e) {
            return -1;
        }
    }

    /**
     * Harvest up to 8 distinct unicode codepoints the font can decode, by
     * walking low CIDs through toUnicode (Identity-H: code == CID). Skips
     * .notdef and whitespace-only mappings.
     */
    private static List<Integer> sampleCodepoints(PDType0Font t0) {
        List<Integer> out = new ArrayList<>();
        for (int code = 1; code < 65535 && out.size() < 8; code++) {
            String u;
            try {
                u = t0.toUnicode(code);
            } catch (Exception e) {
                continue;
            }
            if (u == null || u.isEmpty()) {
                continue;
            }
            int cp = u.codePointAt(0);
            if (Character.isWhitespace(cp)) {
                continue;
            }
            if (!out.contains(cp)) {
                out.add(cp);
            }
        }
        return out;
    }

    private static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) {
            sb.append(String.format("%02X", x & 0xFF));
        }
        return sb.toString();
    }

    private static String hexUtf16(String s) {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            bos.write((c >> 8) & 0xFF);
            bos.write(c & 0xFF);
        }
        return hex(bos.toByteArray());
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
