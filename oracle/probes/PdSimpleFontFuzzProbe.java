import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontFactory;
import org.apache.pdfbox.pdmodel.font.PDSimpleFont;
import org.apache.pdfbox.pdmodel.font.encoding.Encoding;
import org.apache.pdfbox.pdmodel.font.encoding.GlyphList;

/**
 * Live oracle probe: pin Apache PDFBox 3.0.7's {@code PDSimpleFont} code ->
 * glyph-name -> Unicode resolution surface (the {@code toUnicode(int)} chain),
 * the {@code getGlyphList()} flavour pick (AGL vs ZapfDingbats), and the
 * {@code getEncoding()} class for each malformed input — wave 1533, agent D.
 *
 * <h2>How this complements FontEncodingFuzzProbe (wave 1516)</h2>
 * {@code FontEncodingFuzzProbe} pinned only the resolved <i>encoding</i> class +
 * {@code Encoding.getName(code)} (the encoding-resolution leniency surface). It
 * never drove {@code PDSimpleFont.toUnicode(int)} — the encoding -> glyph-name
 * -> glyph-list -> Unicode chain, the {@code /ToUnicode} CMap override/fallback
 * interaction, or the {@code getGlyphList()} flavour pick. This probe targets
 * exactly that downstream path on the same simple-font dictionaries.
 *
 * <h2>Surface exercised</h2>
 * <ul>
 *   <li>{@code toUnicode} for a code whose glyph name is a <b>uniXXXX</b> name
 *       (synthesised via the Adobe Glyph List name-to-unicode algorithm) —
 *       e.g. {@code /Differences} mapping code -> {@code uni20AC};</li>
 *   <li>{@code toUnicode} for a standard glyph name ({@code A}, {@code Euro}),
 *       for {@code .notdef}, and for a glyph name absent from the AGL;</li>
 *   <li>the {@code /ToUnicode} CMap override (a present mapping always wins) and
 *       fallback (a CMap miss falls through to encoding + glyph list);</li>
 *   <li>{@code /ToUnicode} of the WRONG COS type (a name, an int) — upstream
 *       treats a non-stream {@code /ToUnicode} as absent;</li>
 *   <li>the {@code getGlyphList()} flavour: Standard-14 {@code Symbol} and
 *       {@code ZapfDingbats} (the Zapf list), vs everything else (AGL);</li>
 *   <li>a code with no glyph at all (encoding resolves it to {@code .notdef}
 *       -> {@code toUnicode} is {@code null}).</li>
 * </ul>
 *
 * <h2>Output grammar (one line per (case, code))</h2>
 * <pre>
 *   CASE &lt;name&gt; create=ERR:&lt;Exc&gt;
 *   CASE &lt;name&gt; enc=&lt;EncodingClass|null&gt; gl=&lt;GlyphListFlavour&gt; \
 *        c&lt;code&gt;:&lt;glyph&gt;-&gt;&lt;U+XXXX...|null&gt; ...
 * </pre>
 * {@code gl} is {@code ZAPF} when {@code getGlyphList()} resolves a Zapf-only
 * glyph ({@code a1} -> non-null) AND the AGL does not — a cheap flavour probe
 * that needs no reflection; otherwise {@code AGL}. {@code glyph} is the
 * encoding's {@code getName(code)} (or {@code -} when the encoding is null).
 * Unicode is rendered as space-joined {@code U+XXXX} code points, {@code null}
 * when {@code toUnicode} returns null. The pypdfbox sibling rebuilds the
 * identical dictionaries and asserts each line matches.
 */
public final class PdSimpleFontFuzzProbe {

    static PrintStream out;

    static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase b : items) {
            a.add(b);
        }
        return a;
    }

    static COSInteger i(int v) {
        return COSInteger.get(v);
    }

    // ---------- dictionary builders ----------

    static COSDictionary descriptor(boolean symbolic) {
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, n("FontDescriptor"));
        fd.setItem(COSName.FONT_NAME, n("MyCustomFont"));
        fd.setInt(COSName.FLAGS, symbolic ? 4 : 32);
        return fd;
    }

    static COSDictionary type1(String baseFont, Boolean symbolic) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        d.setItem(COSName.SUBTYPE, n("Type1"));
        if (baseFont != null) {
            d.setItem(COSName.BASE_FONT, n(baseFont));
        }
        if (symbolic != null) {
            d.setItem(COSName.FONT_DESC, descriptor(symbolic));
        }
        return d;
    }

    static COSDictionary dictEncoding(String baseEnc, COSArray differences) {
        COSDictionary enc = new COSDictionary();
        enc.setItem(COSName.TYPE, n("Encoding"));
        if (baseEnc != null) {
            enc.setItem(n("BaseEncoding"), n(baseEnc));
        }
        if (differences != null) {
            enc.setItem(n("Differences"), differences);
        }
        return enc;
    }

    /** A /ToUnicode stream mapping the given (code -> 4-hex-unicode) bfchar pairs. */
    static COSStream toUnicodeStream(int[] codes, String[] hexUnicodes)
            throws Exception {
        StringBuilder sb = new StringBuilder();
        sb.append("/CIDInit /ProcSet findresource begin\n");
        sb.append("12 dict begin\nbegincmap\n");
        sb.append("/CMapType 2 def\n");
        sb.append("1 begincodespacerange\n<00> <FF>\nendcodespacerange\n");
        sb.append(codes.length).append(" beginbfchar\n");
        for (int k = 0; k < codes.length; k++) {
            sb.append(String.format("<%02X> <%s>%n", codes[k], hexUnicodes[k]));
        }
        sb.append("endbfchar\nendcmap\n");
        sb.append("CMapName currentdict /CMap defineresource pop\nend\nend\n");
        COSStream s = new COSStream();
        try (java.io.OutputStream os = s.createOutputStream()) {
            os.write(sb.toString().getBytes("US-ASCII"));
        }
        return s;
    }

    // ---------- projection ----------

    static String hexUni(String u) {
        if (u == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder();
        u.codePoints().forEach(cp -> {
            if (sb.length() > 0) {
                sb.append(' ');
            }
            sb.append(String.format("U+%04X", cp));
        });
        return sb.length() == 0 ? "EMPTY" : sb.toString();
    }

    /** AGL vs ZAPF: probe with a Zapf-only glyph name ("a1"). */
    static String glyphFlavour(PDSimpleFont sf) {
        try {
            GlyphList gl = sf.getGlyphList();
            String zapfProbe = gl.toUnicode("a1");
            // The AGL has no "a1"; ZapfDingbatsGlyphList maps it to U+2701.
            return zapfProbe != null ? "ZAPF" : "AGL";
        } catch (Throwable t) {
            return "GL_ERR";
        }
    }

    static String encName(PDSimpleFont sf) {
        Encoding enc;
        try {
            enc = sf.getEncoding();
        } catch (Throwable t) {
            return "ENC_ERR";
        }
        return enc == null ? "null" : enc.getClass().getSimpleName();
    }

    static String glyphName(PDSimpleFont sf, int code) {
        Encoding enc;
        try {
            enc = sf.getEncoding();
        } catch (Throwable t) {
            return "ERR";
        }
        if (enc == null) {
            return "-";
        }
        try {
            String g = enc.getName(code);
            return g == null ? "null" : g;
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static void emit(String name, COSDictionary dict, int[] codes) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDFont font;
        try {
            font = PDFontFactory.createFont(dict);
        } catch (Throwable t) {
            out.println(sb.append("create=ERR:")
                    .append(t.getClass().getSimpleName()).toString());
            return;
        }
        if (!(font instanceof PDSimpleFont)) {
            out.println(sb.append("create=ERR:NotSimple").toString());
            return;
        }
        PDSimpleFont sf = (PDSimpleFont) font;
        sb.append("enc=").append(encName(sf))
          .append(" gl=").append(glyphFlavour(sf));
        for (int code : codes) {
            String u;
            try {
                u = hexUni(sf.toUnicode(code));
            } catch (Throwable t) {
                u = "TU_ERR";
            }
            sb.append(' ').append('c').append(code).append(':')
              .append(glyphName(sf, code)).append("->").append(u);
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // Codes probed across most cases: 65 'A', 0x80 (the /Differences slot),
        // 0x20 space, 0x01 (typically .notdef in WinAnsi).
        int[] codes = {65, 0x80, 0x20, 0x01};

        // ===== plain named encodings: toUnicode via encoding + AGL =====
        COSDictionary winansi = type1("Helvetica", false);
        winansi.setItem(COSName.ENCODING, n("WinAnsiEncoding"));
        emit("name_winansi_tounicode", winansi, codes);

        COSDictionary standard = type1("Helvetica", false);
        standard.setItem(COSName.ENCODING, n("StandardEncoding"));
        emit("name_standard_tounicode", standard, codes);

        // ===== /Differences glyph-name flavours feeding toUnicode =====
        // uniXXXX synthetic name: code 0x80 -> /uni20AC -> U+20AC via AGL algo.
        COSDictionary diffUni = type1("Helvetica", false);
        diffUni.setItem(COSName.ENCODING,
                dictEncoding("WinAnsiEncoding", arr(i(0x80), n("uni20AC"))));
        emit("diff_uniXXXX", diffUni, codes);

        // standard glyph name overlay: code 0x80 -> /Euro -> U+20AC.
        COSDictionary diffEuro = type1("Helvetica", false);
        diffEuro.setItem(COSName.ENCODING,
                dictEncoding("WinAnsiEncoding", arr(i(0x80), n("Euro"))));
        emit("diff_euro", diffEuro, codes);

        // a glyph name absent from the AGL: toUnicode must be null at that slot.
        COSDictionary diffUnknownGlyph = type1("Helvetica", false);
        diffUnknownGlyph.setItem(COSName.ENCODING,
                dictEncoding("WinAnsiEncoding", arr(i(0x80), n("Frobnicate"))));
        emit("diff_unknown_glyph", diffUnknownGlyph, codes);

        // .notdef overlay: explicitly map 0x80 -> /.notdef -> toUnicode null.
        COSDictionary diffNotdef = type1("Helvetica", false);
        diffNotdef.setItem(COSName.ENCODING,
                dictEncoding("WinAnsiEncoding", arr(i(0x80), n(".notdef"))));
        emit("diff_notdef", diffNotdef, codes);

        // a uniXXXX name describing a multi-unit BMP point + a surrogate-form
        // "u1F600" (5-6 hex) name — AGL handles "uXXXXXX" too.
        COSDictionary diffUlong = type1("Helvetica", false);
        diffUlong.setItem(COSName.ENCODING,
                dictEncoding("WinAnsiEncoding", arr(i(0x80), n("u1F600"))));
        emit("diff_u_long", diffUlong, codes);

        // ===== /ToUnicode CMap override + fallback =====
        // CMap maps 65 -> U+005A (overrides 'A'), leaves 0x80/0x20/0x01 alone.
        COSDictionary tuOverride = type1("Helvetica", false);
        tuOverride.setItem(COSName.ENCODING, n("WinAnsiEncoding"));
        tuOverride.setItem(n("ToUnicode"),
                toUnicodeStream(new int[] {65}, new String[] {"005A"}));
        emit("tounicode_override", tuOverride, codes);

        // /ToUnicode of WRONG type (a name) -> treated as absent.
        COSDictionary tuName = type1("Helvetica", false);
        tuName.setItem(COSName.ENCODING, n("WinAnsiEncoding"));
        tuName.setItem(n("ToUnicode"), n("Identity-H"));
        emit("tounicode_wrong_type_name", tuName, codes);

        // /ToUnicode of WRONG type (an int) -> treated as absent.
        COSDictionary tuInt = type1("Helvetica", false);
        tuInt.setItem(COSName.ENCODING, n("WinAnsiEncoding"));
        tuInt.setItem(n("ToUnicode"), i(42));
        emit("tounicode_wrong_type_int", tuInt, codes);

        // /ToUnicode maps the .notdef slot 0x01 -> U+0041 (CMap supplies a code
        // the encoding leaves at .notdef).
        COSDictionary tuNotdef = type1("Helvetica", false);
        tuNotdef.setItem(COSName.ENCODING, n("WinAnsiEncoding"));
        tuNotdef.setItem(n("ToUnicode"),
                toUnicodeStream(new int[] {0x01}, new String[] {"0041"}));
        emit("tounicode_fills_notdef", tuNotdef, codes);

        // ===== glyph-list flavour: Symbol / ZapfDingbats Standard 14 =====
        COSDictionary symbol = type1("Symbol", null);
        emit("std14_symbol", symbol, new int[] {65, 0x61, 0x20});

        COSDictionary zapf = type1("ZapfDingbats", null);
        emit("std14_zapfdingbats", zapf, new int[] {65, 0x61, 0x20});

        // ZapfDingbats with an explicit (ignored, when not embedded) name
        // encoding — flavour must still be ZAPF.
        COSDictionary zapfNamed = type1("ZapfDingbats", null);
        zapfNamed.setItem(COSName.ENCODING, n("WinAnsiEncoding"));
        emit("std14_zapf_named_enc", zapfNamed, new int[] {65, 0x61, 0x20});

        // ===== no /Encoding at all on a non-embedded Standard 14 =====
        emit("no_encoding_helvetica", type1("Helvetica", false),
                new int[] {65, 0x80, 0x20});

        // ===== /Differences with a uniXXXX name that has trailing junk =====
        // "uni20ACxx" is NOT a valid uniXXXX (odd length) -> AGL returns null.
        COSDictionary diffBadUni = type1("Helvetica", false);
        diffBadUni.setItem(COSName.ENCODING,
                dictEncoding("WinAnsiEncoding", arr(i(0x80), n("uni20ACzz"))));
        emit("diff_bad_uni", diffBadUni, codes);

        // ===== /Differences "g123" style + dotted suffix names =====
        // "A.sc" small-cap suffix -> AGL strips the suffix -> U+0041.
        COSDictionary diffSuffix = type1("Helvetica", false);
        diffSuffix.setItem(COSName.ENCODING,
                dictEncoding("WinAnsiEncoding", arr(i(0x80), n("A.sc"))));
        emit("diff_dotted_suffix", diffSuffix, codes);
    }
}
