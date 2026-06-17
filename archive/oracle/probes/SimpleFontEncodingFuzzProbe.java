import java.io.PrintStream;
import java.util.Locale;
import java.util.Map;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontFactory;
import org.apache.pdfbox.pdmodel.font.PDSimpleFont;
import org.apache.pdfbox.pdmodel.font.encoding.DictionaryEncoding;
import org.apache.pdfbox.pdmodel.font.encoding.Encoding;

/**
 * Differential fuzz probe for the simple-font ({@code PDType1Font} /
 * {@code PDTrueTypeFont}) {@code /Encoding} <b>reverse-mapping</b> and
 * {@code /Differences} cursor surface, Apache PDFBox 3.0.7 — wave 1548, agent B.
 *
 * <h2>How this complements the existing encoding probes</h2>
 * <ul>
 *   <li>{@code FontEncodingFuzzProbe} (wave 1516) pinned only the resolved
 *       Encoding <i>class</i>, its base, and {@code getName(65)} /
 *       {@code getName(0x80)} — the forward code -&gt; name direction at two
 *       fixed codes.</li>
 *   <li>{@code PdSimpleFontFuzzProbe} (wave 1533) pinned {@code toUnicode(int)}
 *       and the glyph-list flavour.</li>
 *   <li>{@code SimpleFontWidthsProbe} pinned {@code getWidth} / the
 *       {@code /Widths} array.</li>
 * </ul>
 * NONE of them drove the <b>reverse direction</b> ({@code getNameToCodeMap()}),
 * the {@code /Differences} cursor semantics for codes <b>outside 0..255</b>
 * (negative, &gt;255) or a <b>leading name with no preceding integer</b>, or the
 * resulting {@code getCodeToNameMap().size()}. PDFBox's {@code applyDifferences}
 * starts the cursor at -1 and applies every name at whatever the cursor is —
 * there is no {@code code >= 0} guard — so a leading name lands at code -1 and a
 * name after a negative/high integer marker lands at that exact out-of-range
 * code, and both stay in the forward and reverse maps. This probe pins exactly
 * that.
 *
 * <h2>Input</h2>
 * Deterministic and seed-free: a fixed inline corpus of simple-font
 * {@code COSDictionary}s built identically on both sides (no fixture, no file
 * I/O). None embed a real font program, so the resolved encoding is pure
 * dictionary / base interpretation. The pypdfbox sibling
 * (tests/pdmodel/font/oracle/test_simple_font_encoding_fuzz_wave1548.py)
 * rebuilds the identical dicts and asserts each line matches.
 *
 * <h2>Output grammar</h2>
 * <pre>
 *   CASE &lt;name&gt; create=ERR:&lt;Exc&gt;
 *   CASE &lt;name&gt; enc=&lt;EncodingClass|null&gt; ename=&lt;name|null&gt; \
 *        base=&lt;baseName|-|null&gt; size=&lt;codeToName count&gt;
 *   FWD &lt;name&gt; c&lt;code&gt;=&lt;glyph&gt;          (getName(code))
 *   REV &lt;name&gt; g&lt;glyph&gt;=&lt;code|null&gt;       (getNameToCodeMap().get(glyph))
 *   CONT &lt;name&gt; code&lt;code&gt;=&lt;true|false&gt;   (contains(int))
 *   CONTN &lt;name&gt; name&lt;glyph&gt;=&lt;true|false&gt; (contains(String))
 * </pre>
 * A {@code null} encoding emits only the CASE line (enc=null). Spaces in the
 * encoding name are collapsed to {@code _} so each token stays single-word.
 */
public final class SimpleFontEncodingFuzzProbe {

    static PrintStream out;

    static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    static COSInteger i(int v) {
        return COSInteger.get(v);
    }

    static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase b : items) {
            a.add(b);
        }
        return a;
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

    static COSDictionary trueType(String baseFont, Boolean symbolic) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        d.setItem(COSName.SUBTYPE, n("TrueType"));
        if (baseFont != null) {
            d.setItem(COSName.BASE_FONT, n(baseFont));
        }
        if (symbolic != null) {
            d.setItem(COSName.FONT_DESC, descriptor(symbolic));
        }
        return d;
    }

    static COSDictionary withDictEncoding(
            COSDictionary d, String baseEnc, COSArray differences) {
        COSDictionary enc = new COSDictionary();
        enc.setItem(COSName.TYPE, n("Encoding"));
        if (baseEnc != null) {
            enc.setItem(n("BaseEncoding"), n(baseEnc));
        }
        if (differences != null) {
            enc.setItem(n("Differences"), differences);
        }
        d.setItem(COSName.ENCODING, enc);
        return d;
    }

    static COSDictionary withNameEncoding(COSDictionary d, String encName) {
        d.setItem(COSName.ENCODING, n(encName));
        return d;
    }

    // ---------- projection ----------

    static String collapse(String s) {
        return s == null ? "null" : s.replace(' ', '_');
    }

    static String forward(Encoding enc, int code) {
        try {
            String g = enc.getName(code);
            return g == null ? "null" : g;
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String reverse(Encoding enc, String glyph) {
        try {
            Map<String, Integer> m = enc.getNameToCodeMap();
            Integer c = m.get(glyph);
            return c == null ? "null" : Integer.toString(c);
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String containsCode(Encoding enc, int code) {
        try {
            return enc.contains(code) ? "true" : "false";
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String containsName(Encoding enc, String glyph) {
        try {
            return enc.contains(glyph) ? "true" : "false";
        } catch (Throwable t) {
            return "ERR";
        }
    }

    /**
     * Probed codes (forward) and glyph names (reverse + contains). The glyph
     * names are the ones the corpus overlays plus a couple of base-encoding
     * glyphs so the reverse map of the base survives intact.
     */
    static final int[] CODES = {-5, -1, 0, 65, 128, 129, 130, 200, 255, 256, 300};
    static final String[] GLYPHS = {
        "A", "Euro", "Alpha", "Beta", "Gamma", "Delta", "space", ".notdef", "bullet"
    };

    static void emit(String name, COSDictionary dict) {
        StringBuilder head = new StringBuilder("CASE ").append(name).append(' ');
        PDFont font;
        try {
            font = PDFontFactory.createFont(dict);
        } catch (Throwable t) {
            out.println(head.append("create=ERR:")
                    .append(t.getClass().getSimpleName()).toString());
            return;
        }
        if (!(font instanceof PDSimpleFont)) {
            out.println(head.append("create=ERR:NotSimple").toString());
            return;
        }
        PDSimpleFont sf = (PDSimpleFont) font;
        Encoding enc;
        try {
            enc = sf.getEncoding();
        } catch (Throwable t) {
            out.println(head.append("enc=ERR").toString());
            return;
        }
        if (enc == null) {
            out.println(head.append("enc=null ename=null base=- size=0").toString());
            return;
        }
        String ename = collapse(safeEncodingName(enc));
        String base;
        if (enc instanceof DictionaryEncoding) {
            Encoding b = ((DictionaryEncoding) enc).getBaseEncoding();
            base = b == null ? "null" : collapse(safeEncodingName(b));
        } else {
            base = "-";
        }
        int size;
        try {
            size = enc.getCodeToNameMap().size();
        } catch (Throwable t) {
            size = -1;
        }
        out.printf(Locale.ROOT, "CASE %s enc=%s ename=%s base=%s size=%d%n",
                name, enc.getClass().getSimpleName(), ename, base, size);
        for (int code : CODES) {
            out.printf(Locale.ROOT, "FWD %s c%d=%s%n", name, code, forward(enc, code));
        }
        for (String g : GLYPHS) {
            out.printf(Locale.ROOT, "REV %s g%s=%s%n", name, g, reverse(enc, g));
        }
        for (int code : CODES) {
            out.printf(Locale.ROOT, "CONT %s code%d=%s%n",
                    name, code, containsCode(enc, code));
        }
        for (String g : GLYPHS) {
            out.printf(Locale.ROOT, "CONTN %s name%s=%s%n",
                    name, g, containsName(enc, g));
        }
    }

    static String safeEncodingName(Encoding enc) {
        try {
            return enc.getEncodingName();
        } catch (Throwable t) {
            return "ERR";
        }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ===== base named encodings: forward + reverse maps of the base =====
        emit("name_standard",
                withNameEncoding(type1("Helvetica", false), "StandardEncoding"));
        emit("name_winansi",
                withNameEncoding(type1("Helvetica", false), "WinAnsiEncoding"));
        emit("name_macroman",
                withNameEncoding(type1("Helvetica", false), "MacRomanEncoding"));
        emit("name_macexpert",
                withNameEncoding(type1("Helvetica", false), "MacExpertEncoding"));

        // ===== /Differences cursor: out-of-range + leading-name corners =====
        // Repeated/consecutive names increment the cursor: 128->Alpha, 129->Euro.
        // Then a high marker 300->Beta and a negative marker -5->Gamma, both
        // kept in the forward + reverse maps (no 0..255 guard upstream).
        emit("diff_out_of_range",
                withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                        arr(i(128), n("Alpha"), n("Euro"),
                                i(300), n("Beta"), i(-5), n("Gamma"))));

        // Leading name with no preceding integer -> applied at the initial
        // cursor -1, then the next name at 0 before the marker resets.
        emit("diff_leading_name",
                withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                        arr(n("Alpha"), n("Beta"), i(128), n("Euro"))));

        // Negative marker only.
        emit("diff_negative_only",
                withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                        arr(i(-1), n("Zeta"))));

        // High marker only (256, 300).
        emit("diff_high_only",
                withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                        arr(i(256), n("Eta"), n("Theta"), i(300), n("Iota"))));

        // Duplicate code: last name wins; the displaced name's reverse mapping
        // is dropped if it was the one bound to that code.
        emit("diff_duplicate_code",
                withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                        arr(i(128), n("Alpha"), i(128), n("Euro"))));

        // A name that ALSO exists in the base encoding remapped to a new code:
        // overwrite() rebinds the reverse map to the new (higher) code.
        emit("diff_remap_base_glyph",
                withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                        arr(i(200), n("A"))));

        // Non-integer markers between names: float / string code markers are
        // ignored (not COSNumber-int for string; COSFloat IS a COSNumber so its
        // intValue is taken). Pins the COSNumber vs non-number split.
        emit("diff_float_marker",
                withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                        arr(new COSFloat(128.7f), n("Alpha"))));
        emit("diff_string_marker",
                withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                        arr(new COSString("128"), n("Alpha"))));

        // Null entry, then a valid pair: the null is skipped, cursor untouched.
        emit("diff_null_entry",
                withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                        arr(i(128), COSNull.NULL, n("Euro"))));

        // Empty /Differences -> base map only.
        emit("diff_empty",
                withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                        new COSArray()));

        // ===== base-encoding fallback variants =====
        // Missing /BaseEncoding, non-symbolic -> StandardEncoding base.
        emit("diff_base_missing_nonsymbolic",
                withDictEncoding(type1("Helvetica", false), null,
                        arr(i(128), n("Euro"))));
        // Unknown /BaseEncoding -> StandardEncoding (non-symbolic fallback).
        emit("diff_base_unknown",
                withDictEncoding(type1("Helvetica", false), "BogusEncoding",
                        arr(i(128), n("Euro"))));

        // ===== TrueType counterpart (same dictionary path) =====
        emit("tt_diff_out_of_range",
                withDictEncoding(trueType("Arial", false), "WinAnsiEncoding",
                        arr(i(128), n("Alpha"), n("Euro"),
                                i(300), n("Beta"), i(-5), n("Gamma"))));
        emit("tt_name_winansi",
                withNameEncoding(trueType("Arial", false), "WinAnsiEncoding"));
    }
}
