import java.io.OutputStream;
import java.io.PrintStream;
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
 * Differential fuzz probe for simple-font ({@code PDType1Font} /
 * {@code PDTrueTypeFont}) {@code /Encoding} resolution leniency, Apache PDFBox
 * 3.0.7 (wave 1516, agent D).
 *
 * <h2>How this complements FontFactoryFuzzProbe / Type0FontFuzzProbe</h2>
 * {@code FontFactoryFuzzProbe} (wave 1510) fuzzed {@code PDFontFactory}
 * subtype-dispatch + simple-font DICT CONSTRUCTION (widths, FontFile corners)
 * and never inspected the resolved encoding. {@code Type0FontFuzzProbe} (wave
 * 1513) fuzzed COMPOSITE fonts (the CMap / CIDSystemInfo / W path). This probe
 * targets the third, distinct surface neither touched: how a simple font builds
 * its code -&gt; glyph-name mapping from {@code /Encoding}. It exercises:
 * <ul>
 *   <li>{@code /Encoding} as a name — {@code /StandardEncoding},
 *       {@code /WinAnsiEncoding}, {@code /MacRomanEncoding},
 *       {@code /PDFDocEncoding} (not a valid font /Encoding),
 *       {@code /MacExpertEncoding}, an unknown name, and a missing entry
 *       (falls to the font's built-in default);</li>
 *   <li>{@code /Encoding} as a dict with {@code /BaseEncoding} valid / unknown
 *       / missing (defaults to Standard for non-symbolic) plus
 *       {@code /Differences};</li>
 *   <li>{@code /Differences} malformed: not-an-array, leading name with no
 *       code, multiple codes then names, code out of 0..255, negative code,
 *       non-integer (float / string) code, non-name entry, empty array,
 *       duplicate codes;</li>
 *   <li>the symbolic vs non-symbolic {@code /Flags} bit interaction with the
 *       default base encoding for a {@code /Differences}-only dict.</li>
 * </ul>
 *
 * <h2>Input</h2>
 * Deterministic and seed-free: a fixed inline corpus of simple-font
 * {@code COSDictionary}s built identically on both sides (font dicts round-trip
 * exactly through the in-memory COS builders, so "same bytes" is guaranteed by
 * building the same COS graph — no file I/O needed). None of the dicts embed a
 * real font program, so the resolved encoding is pure dictionary / built-in
 * default interpretation. The pypdfbox sibling
 * (tests/pdmodel/font/oracle/test_font_encoding_fuzz_wave1516.py) rebuilds the
 * identical dicts and asserts each line matches; intentional pypdfbox
 * robustness divergences are pinned both-sides there with a CHANGES.md
 * citation.
 *
 * <h2>Projection</h2>
 * Uses only the public encoding-resolution surface:
 * {@code PDSimpleFont.getEncoding()} (the typed {@code Encoding} that
 * {@code readEncoding()} resolved in the constructor) plus
 * {@code Encoding.getName(int)} / {@code Encoding.getEncodingName()} and (for a
 * {@code DictionaryEncoding}) {@code getBaseEncoding().getEncodingName()}.
 *
 * <h2>Output grammar (one line per case)</h2>
 * <pre>
 *   CASE &lt;name&gt; &lt;create=ERR:&lt;ExcSimpleName&gt; | enc=&lt;EncodingClass|null|ERR&gt;
 *        ename=&lt;encodingName|null|ERR&gt; n65=&lt;glyph&gt; nDiff=&lt;glyph&gt;
 *        base=&lt;baseEncodingName|-|null&gt;&gt;
 * </pre>
 * where:
 * <ul>
 *   <li>{@code create=ERR:X} — {@code PDFontFactory.createFont} threw class X;
 *       </li>
 *   <li>{@code enc} — {@code getEncoding().getClass().getSimpleName()}, or
 *       {@code null} when no encoding resolved, or {@code ERR} if the accessor
 *       threw;</li>
 *   <li>{@code ename} — {@code getEncoding().getEncodingName()} (e.g.
 *       {@code WinAnsiEncoding}, {@code "StandardEncoding with differences"}
 *       with spaces collapsed to {@code _}), {@code null}, or {@code ERR};</li>
 *   <li>{@code n65} — {@code getEncoding().getName(65)} ('A' slot), or
 *       {@code .notdef} / {@code ?} when unresolved;</li>
 *   <li>{@code nDiff} — {@code getEncoding().getName(0x80)} (code 128, the slot
 *       most cases overlay via {@code /Differences}), or the fallback glyph;
 *       </li>
 *   <li>{@code base} — for a {@code DictionaryEncoding},
 *       {@code getBaseEncoding().getEncodingName()} (or {@code null} for a
 *       base-less Type-3-style dict); {@code -} for every non-dictionary
 *       encoding.</li>
 * </ul>
 */
public final class FontEncodingFuzzProbe {

    static PrintStream out;

    static final int DIFF_CODE = 0x80;

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

    /** Font descriptor carrying just the /Flags symbolic bit (or not). */
    static COSDictionary descriptor(boolean symbolic) {
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, n("FontDescriptor"));
        fd.setItem(COSName.FONT_NAME, n("MyCustomFont"));
        // bit 3 (value 4) = Symbolic; bit 6 (value 32) = Nonsymbolic.
        fd.setInt(COSName.FLAGS, symbolic ? 4 : 32);
        return fd;
    }

    /**
     * Simple Type1 font dict. {@code baseFont} may be a Standard-14 name (so
     * the built-in default encoding is available without an embedded program)
     * or a custom name. {@code symbolic}: null = no descriptor, else the
     * /Flags symbolic bit.
     */
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

    /** A /Differences array overlaying code 0x80 with glyph "Euro". */
    static COSArray simpleDifferences() {
        return arr(i(DIFF_CODE), n("Euro"));
    }

    // ---------- projection ----------

    static String safeName(Encoding enc, int code) {
        try {
            String nm = enc.getName(code);
            return nm == null ? "null" : nm;
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String encodingName(Encoding enc) {
        try {
            String nm = enc.getEncodingName();
            // Collapse whitespace so the token stays single-word for parsing.
            return nm == null ? "null" : nm.replace(' ', '_');
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String baseName(Encoding enc) {
        if (!(enc instanceof DictionaryEncoding)) {
            return "-";
        }
        try {
            Encoding base = ((DictionaryEncoding) enc).getBaseEncoding();
            if (base == null) {
                return "null";
            }
            String nm = base.getEncodingName();
            return nm == null ? "null" : nm.replace(' ', '_');
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static void emit(String name, COSDictionary dict) {
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
        Encoding enc;
        try {
            enc = sf.getEncoding();
        } catch (Throwable t) {
            out.println(sb.append("enc=ERR ename=ERR n65=ERR nDiff=ERR base=ERR")
                    .toString());
            return;
        }
        if (enc == null) {
            out.println(sb.append("enc=null ename=null n65=? nDiff=? base=-")
                    .toString());
            return;
        }
        sb.append("enc=").append(enc.getClass().getSimpleName())
          .append(" ename=").append(encodingName(enc))
          .append(" n65=").append(safeName(enc, 65))
          .append(" nDiff=").append(safeName(enc, DIFF_CODE))
          .append(" base=").append(baseName(enc));
        out.println(sb.toString());
    }

    /** Build a font dict with /Encoding as a name. */
    static COSDictionary withNameEncoding(COSDictionary d, String encName) {
        d.setItem(COSName.ENCODING, n(encName));
        return d;
    }

    /** Build a font dict with /Encoding as a dict (base + differences). */
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

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ===== /Encoding as a name =====
        emit("name_standard",
             withNameEncoding(type1("Helvetica", false), "StandardEncoding"));
        emit("name_winansi",
             withNameEncoding(type1("Helvetica", false), "WinAnsiEncoding"));
        emit("name_macroman",
             withNameEncoding(type1("Helvetica", false), "MacRomanEncoding"));
        emit("name_macexpert",
             withNameEncoding(type1("Helvetica", false), "MacExpertEncoding"));
        // /PDFDocEncoding is NOT a valid font /Encoding name -> unknown ->
        // built-in default.
        emit("name_pdfdoc",
             withNameEncoding(type1("Helvetica", false), "PDFDocEncoding"));
        emit("name_unknown",
             withNameEncoding(type1("Helvetica", false), "FrobnicateEncoding"));
        // Missing /Encoding -> font built-in default (Standard14 AFM built-in
        // for non-embedded Helvetica).
        emit("name_missing_nonsymbolic", type1("Helvetica", false));
        emit("name_missing_no_descriptor", type1("Helvetica", null));
        // Missing /Encoding, custom (non-Standard14, non-embedded) base font.
        emit("name_missing_custom", type1("MyCustomFont", false));

        // ===== /Encoding as a dict: /BaseEncoding variants =====
        emit("dict_base_winansi_diff",
             withDictEncoding(type1("Helvetica", false),
                     "WinAnsiEncoding", simpleDifferences()));
        emit("dict_base_macroman_diff",
             withDictEncoding(type1("Helvetica", false),
                     "MacRomanEncoding", simpleDifferences()));
        // Unknown /BaseEncoding -> falls to Standard (non-symbolic).
        emit("dict_base_unknown_diff",
             withDictEncoding(type1("Helvetica", false),
                     "BogusEncoding", simpleDifferences()));
        // Missing /BaseEncoding, non-symbolic -> Standard base.
        emit("dict_base_missing_nonsymbolic",
             withDictEncoding(type1("Helvetica", false),
                     null, simpleDifferences()));
        // Missing /BaseEncoding, no descriptor at all.
        emit("dict_base_missing_no_descriptor",
             withDictEncoding(type1("Helvetica", null),
                     null, simpleDifferences()));
        // Dict /Encoding with no /Differences at all.
        emit("dict_no_differences",
             withDictEncoding(type1("Helvetica", false),
                     "WinAnsiEncoding", null));
        // Dict /Encoding, fully empty (no base, no diffs).
        emit("dict_empty",
             withDictEncoding(type1("Helvetica", false), null, null));

        // ===== symbolic vs non-symbolic flag interaction =====
        // Symbolic + dict /Encoding, no base: upstream asks the font program
        // for a built-in; with no embedded program the built-in is null, so
        // upstream throws IllegalArgumentException out of the DictionaryEncoding
        // ctor -> createFont reports the failure.
        emit("dict_base_missing_symbolic",
             withDictEncoding(type1("MyCustomFont", true),
                     null, simpleDifferences()));
        // Symbolic + valid base -> base wins, no program consult.
        emit("dict_base_winansi_symbolic",
             withDictEncoding(type1("MyCustomFont", true),
                     "WinAnsiEncoding", simpleDifferences()));

        // ===== /Differences malformed shapes =====
        // not-an-array: /Differences is a dictionary.
        COSDictionary diffNotArray = type1("Helvetica", false);
        COSDictionary encNotArray = new COSDictionary();
        encNotArray.setItem(COSName.TYPE, n("Encoding"));
        encNotArray.setItem(n("BaseEncoding"), n("WinAnsiEncoding"));
        encNotArray.setItem(n("Differences"), new COSDictionary());
        diffNotArray.setItem(COSName.ENCODING, encNotArray);
        emit("diff_not_an_array", diffNotArray);

        // leading name with no preceding code -> name is dropped.
        emit("diff_leading_name_no_code",
             withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                     arr(n("Alpha"), i(DIFF_CODE), n("Euro"))));

        // multiple codes then names: code, code, name, name (the second code
        // resets the cursor; the first name applies to the second code).
        emit("diff_multi_codes_then_names",
             withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                     arr(i(0x41), i(DIFF_CODE), n("Euro"), n("Alpha"))));

        // code out of 0..255 range (high).
        emit("diff_code_too_high",
             withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                     arr(i(300), n("Euro"))));

        // negative code.
        emit("diff_code_negative",
             withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                     arr(i(-5), n("Euro"))));

        // non-integer (float) code.
        emit("diff_code_float",
             withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                     arr(new COSFloat(128.0f), n("Euro"))));

        // code as a string.
        emit("diff_code_as_string",
             withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                     arr(new COSString("128"), n("Euro"))));

        // non-name entry where a name is expected (a number after the code).
        emit("diff_nonname_entry",
             withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                     arr(i(DIFF_CODE), i(999), n("Euro"))));

        // null entry inside the array.
        emit("diff_null_entry",
             withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                     arr(i(DIFF_CODE), COSNull.NULL, n("Euro"))));

        // empty /Differences array.
        emit("diff_empty_array",
             withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                     new COSArray()));

        // duplicate codes -> last name wins for that code.
        emit("diff_duplicate_codes",
             withDictEncoding(type1("Helvetica", false), "WinAnsiEncoding",
                     arr(i(DIFF_CODE), n("Alpha"), i(DIFF_CODE), n("Euro"))));

        // ===== TrueType counterparts (different built-in default path) =====
        emit("tt_name_winansi",
             withNameEncoding(trueType("Arial", false), "WinAnsiEncoding"));
        emit("tt_name_missing_nonsymbolic", trueType("Arial", false));
        emit("tt_name_missing_symbolic", trueType("Arial", true));
        emit("tt_dict_base_winansi_diff",
             withDictEncoding(trueType("Arial", false),
                     "WinAnsiEncoding", simpleDifferences()));
    }
}
