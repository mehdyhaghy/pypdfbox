import java.io.PrintStream;
import org.apache.fontbox.cmap.CMap;
import org.apache.fontbox.cmap.CMapParser;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.io.RandomAccessReadBuffer;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;
import org.apache.pdfbox.pdmodel.font.PDType1Font;

/**
 * Live oracle probe for the font code -> Unicode resolution edge cases that the
 * existing ToUnicode probes do NOT cover. Two sub-surfaces are exercised, both
 * emitting the same canonical line format the other probes use:
 *
 *     UNI <tag> <code> -> U+XXXX[ U+YYYY...]   (or "(none)")
 *
 * where code points are taken via String.codePoints() so a surrogate pair
 * collapses to one U+1XXXX entry exactly as Python iterates a str.
 *
 * (A) RAW CMAP DECODE — feeds a hand-built /ToUnicode CMap program straight to
 *     CMapParser and queries CMap.toUnicode, isolating the decode of:
 *       - an EMPTY bfchar destination  <01> <>      (maps to "")
 *       - a U+FFFD replacement char    <02> <FFFD>
 *       - U+0000 (NUL) destination     <03> <0000>
 *       - a PUA codepoint              <04> <E000>
 *       - a bfrange spanning a surrogate boundary
 *               <0005> <0007> <D7FF>  -> U+D7FF, U+E000, U+E001
 *         (the increment steps across the UTF-16 surrogate block; PDFBox treats
 *          the destination as a raw UTF-16BE code unit and increments the last
 *          unit, so the middle value is the literal surrogate-block boundary).
 *
 * (B) FONT-LEVEL RESOLVE — builds real PDFont objects and calls toUnicode(int):
 *       - Type0/Identity-H font: code present in ToUnicode (wins), code absent
 *         (-> null on a Type0 font; no encoding fallback);
 *       - simple Type1 (Helvetica/WinAnsi) with NO ToUnicode at all: pure
 *         encoding -> glyph name -> AGL fallback (0x41 -> "A"), and an unmapped
 *         code (0x80 in WinAnsi has a glyph "Euro" -> U+20AC; 0x7F has none
 *         -> null);
 *       - simple Type1 WITH a ToUnicode that maps 0x41 to a PUA codepoint:
 *         ToUnicode wins over the encoding's "A".
 *
 * Usage: java ToUnicodeResolveFuzzProbe
 * (self-contained; takes no arguments).
 */
public final class ToUnicodeResolveFuzzProbe {

    // (A) raw CMap program covering the edge destinations above.
    private static final String CMAP_TEXT =
            "/CIDInit /ProcSet findresource begin\n"
          + "12 dict begin\n"
          + "begincmap\n"
          + "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
          + "/CMapName /Adobe-Identity-UCS def\n"
          + "/CMapType 2 def\n"
          + "1 begincodespacerange\n"
          + "<0000> <FFFF>\n"
          + "endcodespacerange\n"
          + "4 beginbfchar\n"
          + "<0001> <>\n"        // empty destination
          + "<0002> <FFFD>\n"    // U+FFFD replacement char
          + "<0003> <0000>\n"    // U+0000 NUL
          + "<0004> <E000>\n"    // PUA start
          + "endbfchar\n"
          + "1 beginbfrange\n"
          + "<0005> <0007> <D7FF>\n"  // range stepping across surrogate boundary
          + "endbfrange\n"
          + "endcmap\n"
          + "CMapName currentdict /CMap defineresource pop\n"
          + "end\n"
          + "end\n";

    // Codes probed against the raw CMap (2-byte big-endian).
    private static final int[] RAW_CODES = {1, 2, 3, 4, 5, 6, 7, 8};

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // ---- (A) raw CMap decode ----
        CMap cmap = new CMapParser()
                .parse(new RandomAccessReadBuffer(CMAP_TEXT.getBytes("US-ASCII")));
        for (int code : RAW_CODES) {
            byte[] codeBytes = {(byte) ((code >> 8) & 0xFF), (byte) (code & 0xFF)};
            String uni;
            try {
                uni = cmap.toUnicode(codeBytes);
            } catch (Exception e) {
                emit(out, "RAW", code, null, true);
                continue;
            }
            emit(out, "RAW", code, uni, false);
        }

        // ---- (B) font-level resolve ----
        // Type0 / Identity-H with the same edge CMap as /ToUnicode.
        try (PDDocument doc = new PDDocument()) {
            PDFont type0 = buildType0(doc);
            // present in ToUnicode (PUA E000) and absent (0x09 -> null on Type0).
            emitFont(out, "T0", type0, 4);
            emitFont(out, "T0", type0, 9);
        } catch (Exception e) {
            out.println("UNI T0 ERR -> " + e.getClass().getSimpleName());
        }

        // Simple Type1 Helvetica/WinAnsi, NO ToUnicode: encoding -> AGL.
        try {
            PDFont helv = new PDType1Font(
                    org.apache.pdfbox.pdmodel.font.Standard14Fonts.FontName.HELVETICA);
            emitFont(out, "ENC", helv, 0x41);  // 'A' -> U+0041
            emitFont(out, "ENC", helv, 0x80);  // WinAnsi Euro -> U+20AC
            emitFont(out, "ENC", helv, 0x7F);  // no glyph -> null
        } catch (Exception e) {
            out.println("UNI ENC ERR -> " + e.getClass().getSimpleName());
        }

        // Simple Type1 with a ToUnicode mapping 0x41 -> PUA E001 (overrides 'A').
        try (PDDocument doc = new PDDocument()) {
            PDFont helvTu = buildSimpleWithToUnicode(doc);
            emitFont(out, "OVR", helvTu, 0x41);  // ToUnicode wins -> U+E001
            emitFont(out, "OVR", helvTu, 0x42);  // not in ToUnicode -> 'B' (AGL)
        } catch (Exception e) {
            out.println("UNI OVR ERR -> " + e.getClass().getSimpleName());
        }
    }

    private static PDFont buildType0(PDDocument doc) throws Exception {
        COSDictionary cid = new COSDictionary();
        cid.setName(COSName.TYPE, "Font");
        cid.setName(COSName.SUBTYPE, "CIDFontType2");
        cid.setName(COSName.BASE_FONT, "ABCDEF+TestFont");
        COSDictionary si = new COSDictionary();
        si.setString(COSName.REGISTRY, "Adobe");
        si.setString(COSName.ORDERING, "Identity");
        si.setInt(COSName.SUPPLEMENT, 0);
        cid.setItem(COSName.CIDSYSTEMINFO, si);
        cid.setInt(COSName.DW, 1000);

        COSStream tu = doc.getDocument().createCOSStream();
        try (var os = tu.createOutputStream()) {
            os.write(CMAP_TEXT.getBytes("US-ASCII"));
        }

        COSDictionary font = new COSDictionary();
        font.setName(COSName.TYPE, "Font");
        font.setName(COSName.SUBTYPE, "Type0");
        font.setName(COSName.BASE_FONT, "ABCDEF+TestFont");
        font.setName(COSName.ENCODING, "Identity-H");
        COSArray arr = new COSArray();
        arr.add(cid);
        font.setItem(COSName.DESCENDANT_FONTS, arr);
        font.setItem(COSName.TO_UNICODE, tu);
        return PDFontFactoryLike(font);
    }

    private static PDFont buildSimpleWithToUnicode(PDDocument doc) throws Exception {
        String simpleCmap =
                "/CIDInit /ProcSet findresource begin\n"
              + "12 dict begin\nbegincmap\n"
              + "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
              + "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
              + "1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
              + "1 beginbfchar\n<41> <E001>\nendbfchar\n"
              + "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n";
        COSStream tu = doc.getDocument().createCOSStream();
        try (var os = tu.createOutputStream()) {
            os.write(simpleCmap.getBytes("US-ASCII"));
        }
        COSDictionary font = new COSDictionary();
        font.setName(COSName.TYPE, "Font");
        font.setName(COSName.SUBTYPE, "Type1");
        font.setName(COSName.BASE_FONT, "Helvetica");
        font.setName(COSName.ENCODING, "WinAnsiEncoding");
        font.setItem(COSName.TO_UNICODE, tu);
        return PDFontFactoryLike(font);
    }

    private static PDFont PDFontFactoryLike(COSDictionary font) throws Exception {
        return org.apache.pdfbox.pdmodel.font.PDFontFactory.createFont(font);
    }

    private static void emitFont(PrintStream out, String tag, PDFont font, int code) {
        String uni;
        try {
            uni = font.toUnicode(code);
        } catch (Exception e) {
            emit(out, tag, code, null, true);
            return;
        }
        emit(out, tag, code, uni, false);
    }

    private static void emit(PrintStream out, String tag, int code, String uni, boolean threw) {
        StringBuilder sb = new StringBuilder();
        sb.append("UNI ").append(tag).append(" ").append(code).append(" ->");
        if (threw) {
            sb.append(" (exception)");
        } else if (uni == null) {
            sb.append(" (none)");
        } else if (uni.isEmpty()) {
            sb.append(" (empty)");
        } else {
            uni.codePoints().forEach(cp -> sb.append(" U+").append(String.format("%04X", cp)));
        }
        out.println(sb.toString());
    }
}
