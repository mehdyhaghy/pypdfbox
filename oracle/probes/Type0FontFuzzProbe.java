import java.io.OutputStream;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.font.PDCIDFont;
import org.apache.pdfbox.pdmodel.font.PDCIDSystemInfo;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontFactory;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Differential fuzz probe for {@code PDType0Font} (composite font) + its
 * descendant {@code PDCIDFontType0} / {@code PDCIDFontType2} construction
 * leniency over malformed font dictionaries, Apache PDFBox 3.0.7 (wave 1513,
 * agent E).
 *
 * <h2>How this complements FontFactoryFuzzProbe</h2>
 * {@code FontFactoryFuzzProbe} (wave 1510) fuzzed the {@code PDFontFactory}
 * subtype-dispatch + simple-font construction surface (Type1 / Type1C /
 * MMType1 / TrueType / Type3 widths + FontFile corners) and touched Type 0
 * only lightly (missing / empty / dict-shaped {@code /DescendantFonts}). This
 * probe goes DEEP into the composite-font path that the earlier probe did not
 * exercise:
 * <ul>
 *   <li>descendant {@code /Subtype} CIDFontType0 vs CIDFontType2 vs unknown
 *       vs missing;</li>
 *   <li>{@code /Encoding} predefined-name vs Identity-H/V vs missing vs
 *       unknown name (its effect on {@code codeToCID});</li>
 *   <li>the descendant {@code /W} width array in all its malformed shapes —
 *       {@code c [w...]} (form 1), {@code c1 c2 w} (form 2), out-of-order
 *       ranges, non-numeric / null entries, truncated tails;</li>
 *   <li>{@code /DW} default width missing / float / string / negative;</li>
 *   <li>{@code /CIDToGIDMap} Identity vs stream vs absent vs odd-name vs
 *       wrong-type (reported as the raw COS-entry KIND, NOT resolved through
 *       a substitute font — keeps the contract font-mapper-free);</li>
 *   <li>{@code /CIDSystemInfo} missing / partial (any of /Registry,
 *       /Ordering, /Supplement dropped or mistyped).</li>
 * </ul>
 *
 * <h2>Why the projection avoids glyph substitution</h2>
 * None of the fuzz dicts embed a real font program. Upstream's
 * {@code PDCIDFontType2.codeToGID} (and {@code getWidthFromFont}) fall back to
 * a system-substitute font when the program is absent; pypdfbox's mapper is
 * deliberately trimmed (wave 1377), so those paths diverge by design and were
 * already pinned in wave 1510. To keep THIS probe a clean dict-parse contract,
 * the projection reports only values that are pure dictionary interpretation:
 * the descendant class, the {@code /CIDSystemInfo} triple, the parsed default
 * width, two {@code codeToCID} samples, two {@code /W}-table width lookups
 * ({@code getWidth}, which reads {@code /W} with {@code /DW} fallback — no
 * embedded-program consult for an unmapped CID), and the {@code /CIDToGIDMap}
 * entry KIND read straight off the COS dictionary.
 *
 * <h2>Input</h2>
 * Deterministic and seed-free: the corpus is a fixed inline list of font
 * COSDictionaries built identically on both sides (no file I/O — font dicts,
 * unlike whole PDFs, round-trip exactly through the in-memory COS builders, so
 * "same bytes" is guaranteed by building the same COS graph). The pypdfbox
 * sibling
 * (tests/pdmodel/font/oracle/test_type0_font_fuzz_wave1513.py) rebuilds the
 * identical dicts and asserts each line matches; intentional pypdfbox
 * robustness divergences are pinned both-sides there with a CHANGES.md
 * citation.
 *
 * <h2>Output grammar (one line per case)</h2>
 * <pre>
 *   CASE &lt;name&gt; &lt;create=ERR:&lt;ExcSimpleName&gt; | ok desc=&lt;C&gt; csi=&lt;reg-ord-supp|null&gt;
 *        dw=&lt;n|ERR&gt; cidA=&lt;n|ERR&gt; cidHi=&lt;n|ERR&gt; wA=&lt;w|ERR&gt; wHi=&lt;w|ERR&gt;
 *        c2g=&lt;Identity|stream|absent|name:&lt;x&gt;|&lt;type&gt;|-&gt;&gt;
 * </pre>
 * where:
 * <ul>
 *   <li>{@code create=ERR:X} — {@code PDFontFactory.createFont} (or the
 *       PDType0Font constructor it invokes) threw exception class X;</li>
 *   <li>{@code desc} — descendant CIDFont simple class name, or {@code null}
 *       when no descendant resolved;</li>
 *   <li>{@code csi} — descendant {@code /CIDSystemInfo} as
 *       {@code Registry-Ordering-Supplement} (PDCIDSystemInfo.toString), or
 *       {@code null};</li>
 *   <li>{@code dw} — descendant {@code getDefaultWidth} (int, the parsed
 *       {@code /DW}; spec default 1000), or {@code -} when no descendant;</li>
 *   <li>{@code cidA} / {@code cidHi} — {@code codeToCID(0x0041)} /
 *       {@code codeToCID(0x4E00)};</li>
 *   <li>{@code wA} / {@code wHi} — {@code getWidth(0x0041)} /
 *       {@code getWidth(0x4E00)} (%.3f), the {@code /W}+{@code /DW} advance;</li>
 *   <li>{@code c2g} — the {@code /CIDToGIDMap} entry KIND read off the
 *       descendant COS dict ({@code Identity} name, {@code stream},
 *       {@code absent}, {@code name:&lt;x&gt;} for any other name,
 *       {@code &lt;type&gt;} for a wrong-typed entry), or {@code -} when no
 *       descendant / a CIDFontType0 descendant (which has no /CIDToGIDMap).</li>
 * </ul>
 */
public final class Type0FontFuzzProbe {

    static PrintStream out;

    static final COSName CID_TO_GID_MAP = COSName.getPDFName("CIDToGIDMap");

    static String fmt(float v) {
        return String.format(Locale.ROOT, "%.3f", v);
    }

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

    static COSStream newStream() {
        return new COSStream();
    }

    static COSStream cidToGidStream() throws Exception {
        // CID 3 -> GID 77, CID 4 -> GID 88; CIDs 0..2 -> GID 0. Packed as
        // big-endian uint16 words (the /CIDToGIDMap stream format).
        COSStream s = new COSStream();
        OutputStream os = s.createOutputStream();
        os.write(new byte[] {0, 0, 0, 0, 0, 0, 0, 77, 0, 88});
        os.close();
        return s;
    }

    // ---------- dictionary builders ----------

    static COSDictionary csi(String registry, String ordering, Integer supplement) {
        COSDictionary d = new COSDictionary();
        if (registry != null) {
            d.setString(n("Registry"), registry);
        }
        if (ordering != null) {
            d.setString(n("Ordering"), ordering);
        }
        if (supplement != null) {
            d.setInt(n("Supplement"), supplement);
        }
        return d;
    }

    static COSDictionary cidFont(String subtype) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        if (subtype != null) {
            d.setItem(COSName.SUBTYPE, n(subtype));
        }
        d.setItem(COSName.BASE_FONT, n("Arial"));
        d.setItem(n("CIDSystemInfo"), csi("Adobe", "Identity", 0));
        return d;
    }

    static COSArray descArray(COSDictionary cid) {
        COSArray a = new COSArray();
        a.add(cid);
        return a;
    }

    static COSDictionary type0(COSBase descendants, String encoding) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        d.setItem(COSName.SUBTYPE, n("Type0"));
        d.setItem(COSName.BASE_FONT, n("Arial-Identity-H"));
        if (encoding != null) {
            d.setItem(COSName.ENCODING, n(encoding));
        }
        if (descendants != null) {
            d.setItem(n("DescendantFonts"), descendants);
        }
        return d;
    }

    // ---------- projection ----------

    static String cidSystemInfo(PDCIDFont cid) {
        try {
            PDCIDSystemInfo info = cid.getCIDSystemInfo();
            return info == null ? "null" : info.toString();
        } catch (Throwable t) {
            return "null";
        }
    }

    static String cidToGidKind(PDCIDFont cid) {
        // CIDFontType0 has no /CIDToGIDMap at all.
        if (!"CIDFontType2".equals(safeSubtype(cid))) {
            return "-";
        }
        try {
            COSBase entry = cid.getCOSObject().getDictionaryObject(CID_TO_GID_MAP);
            if (entry == null) {
                return "absent";
            }
            if (entry instanceof COSStream) {
                return "stream";
            }
            if (entry instanceof COSName) {
                String nm = ((COSName) entry).getName();
                return "Identity".equals(nm) ? "Identity" : "name:" + nm;
            }
            return entry.getClass().getSimpleName();
        } catch (Throwable t) {
            return "-";
        }
    }

    static String safeSubtype(PDCIDFont cid) {
        try {
            return cid.getCOSObject().getNameAsString(COSName.SUBTYPE);
        } catch (Throwable t) {
            return null;
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
        if (!(font instanceof PDType0Font)) {
            out.println(sb.append("create=ERR:NotType0").toString());
            return;
        }
        PDType0Font t0 = (PDType0Font) font;
        PDCIDFont desc;
        try {
            desc = t0.getDescendantFont();
        } catch (Throwable t) {
            desc = null;
        }
        String descName = desc == null ? "null" : desc.getClass().getSimpleName();
        String csiStr = desc == null ? "null" : cidSystemInfo(desc);
        String dw;
        try {
            // getDefaultWidth() is private upstream; read /DW straight off the
            // descendant COS dict (the same parse contract, spec default 1000).
            dw = desc == null
                    ? "-"
                    : Integer.toString(
                            desc.getCOSObject().getInt(n("DW"), 1000));
        } catch (Throwable t) {
            dw = "ERR";
        }
        String cidA = sampleCid(t0, 0x0041);
        String cidHi = sampleCid(t0, 0x4E00);
        String wA = sampleWidth(t0, 0x0041);
        String wHi = sampleWidth(t0, 0x4E00);
        String c2g = desc == null ? "-" : cidToGidKind(desc);
        sb.append("create=ok desc=").append(descName)
          .append(" csi=").append(csiStr)
          .append(" dw=").append(dw)
          .append(" cidA=").append(cidA)
          .append(" cidHi=").append(cidHi)
          .append(" wA=").append(wA)
          .append(" wHi=").append(wHi)
          .append(" c2g=").append(c2g);
        out.println(sb.toString());
    }

    static String sampleCid(PDType0Font t0, int code) {
        try {
            return Integer.toString(t0.codeToCID(code));
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String sampleWidth(PDType0Font t0, int code) {
        try {
            return fmt(t0.getWidth(code));
        } catch (Throwable t) {
            return "ERR";
        }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ===== descendant /Subtype variants =====
        emit("desc_cidtype2", type0(descArray(cidFont("CIDFontType2")), "Identity-H"));
        emit("desc_cidtype0", type0(descArray(cidFont("CIDFontType0")), "Identity-H"));
        emit("desc_unknown_subtype",
             type0(descArray(cidFont("CIDFontTypeX")), "Identity-H"));
        emit("desc_missing_subtype",
             type0(descArray(cidFont(null)), "Identity-H"));

        // ===== /DescendantFonts shape variants =====
        emit("descendants_missing", type0(null, "Identity-H"));
        emit("descendants_empty", type0(new COSArray(), "Identity-H"));
        // /DescendantFonts as a dictionary (not an array).
        emit("descendants_as_dict",
             type0(cidFont("CIDFontType2"), "Identity-H"));
        // /DescendantFonts as a name.
        emit("descendants_as_name", type0(n("Bogus"), "Identity-H"));
        // /DescendantFonts array whose first element is not a dictionary.
        emit("descendants_first_nonarray_elem",
             type0(arr(i(42)), "Identity-H"));
        // Two descendants (oversized array — upstream uses [0]).
        COSArray two = descArray(cidFont("CIDFontType2"));
        two.add(cidFont("CIDFontType0"));
        emit("descendants_two", type0(two, "Identity-H"));

        // ===== /Encoding variants =====
        emit("encoding_identity_v",
             type0(descArray(cidFont("CIDFontType2")), "Identity-V"));
        emit("encoding_missing",
             type0(descArray(cidFont("CIDFontType2")), null));
        emit("encoding_unknown_name",
             type0(descArray(cidFont("CIDFontType2")), "NoSuchCMap-Frob"));
        // /Encoding as a predefined CJK CMap name.
        emit("encoding_predefined_cjk",
             type0(descArray(cidFont("CIDFontType2")), "GBK-EUC-H"));
        // /Encoding as an embedded (empty / garbage) CMap stream.
        COSDictionary encStream = type0(descArray(cidFont("CIDFontType2")), null);
        encStream.setItem(COSName.ENCODING, newStream());
        emit("encoding_empty_stream", encStream);

        // ===== /W width-array shapes =====
        // form 1: c [w1 w2 w3] starting at CID 0x41 (so code 'A' maps).
        COSDictionary wForm1 = cidFont("CIDFontType2");
        wForm1.setItem(n("W"),
                arr(i(0x41), arr(i(600), i(601), i(602))));
        emit("w_form1_covers_A", type0(descArray(wForm1), "Identity-H"));

        // form 2: c1 c2 w covering 0x41..0x50.
        COSDictionary wForm2 = cidFont("CIDFontType2");
        wForm2.setItem(n("W"), arr(i(0x41), i(0x50), i(777)));
        emit("w_form2_range_covers_A", type0(descArray(wForm2), "Identity-H"));

        // form 2 out of order: c1 > c2 -> empty range (no CIDs assigned).
        COSDictionary wOoo = cidFont("CIDFontType2");
        wOoo.setItem(n("W"), arr(i(0x50), i(0x41), i(777)));
        emit("w_form2_out_of_order", type0(descArray(wOoo), "Identity-H"));

        // form 1 with non-numeric leading CID -> entry skipped.
        COSDictionary wBadFirst = cidFont("CIDFontType2");
        wBadFirst.setItem(n("W"), arr(n("X"), arr(i(600))));
        emit("w_nonnumeric_first_cid", type0(descArray(wBadFirst), "Identity-H"));

        // form 1 with a null + name hole inside the inner array (CID 0x41).
        COSDictionary wInnerHole = cidFont("CIDFontType2");
        wInnerHole.setItem(n("W"),
                arr(i(0x41), arr(i(600), COSNull.NULL, n("Bad"), i(603))));
        emit("w_inner_array_holes", type0(descArray(wInnerHole), "Identity-H"));

        // truncated form 1 tail: c with no following operand.
        COSDictionary wTrunc = cidFont("CIDFontType2");
        wTrunc.setItem(n("W"), arr(i(0x41)));
        emit("w_truncated_tail", type0(descArray(wTrunc), "Identity-H"));

        // truncated form 2 tail: c1 c2 with no width.
        COSDictionary wTrunc2 = cidFont("CIDFontType2");
        wTrunc2.setItem(n("W"), arr(i(0x41), i(0x50)));
        emit("w_truncated_range_tail", type0(descArray(wTrunc2), "Identity-H"));

        // /W as a dictionary (wrong type) instead of an array.
        COSDictionary wDict = cidFont("CIDFontType2");
        wDict.setItem(n("W"), new COSDictionary());
        emit("w_as_dict", type0(descArray(wDict), "Identity-H"));

        // form 1 with float widths.
        COSDictionary wFloat = cidFont("CIDFontType2");
        wFloat.setItem(n("W"),
                arr(i(0x41), arr(new COSFloat(600.5f), new COSFloat(601.25f))));
        emit("w_float_widths", type0(descArray(wFloat), "Identity-H"));

        // ===== /DW default-width shapes =====
        COSDictionary dwMissing = cidFont("CIDFontType2");
        // (no /DW set — spec default 1000)
        emit("dw_missing", type0(descArray(dwMissing), "Identity-H"));

        COSDictionary dwExplicit = cidFont("CIDFontType2");
        dwExplicit.setInt(n("DW"), 500);
        emit("dw_explicit_500", type0(descArray(dwExplicit), "Identity-H"));

        COSDictionary dwFloat = cidFont("CIDFontType2");
        dwFloat.setItem(n("DW"), new COSFloat(444.5f));
        emit("dw_float", type0(descArray(dwFloat), "Identity-H"));

        COSDictionary dwString = cidFont("CIDFontType2");
        dwString.setItem(n("DW"), new COSString("600"));
        emit("dw_as_string", type0(descArray(dwString), "Identity-H"));

        COSDictionary dwNeg = cidFont("CIDFontType2");
        dwNeg.setInt(n("DW"), -250);
        emit("dw_negative", type0(descArray(dwNeg), "Identity-H"));

        // ===== /CIDToGIDMap shapes (CIDFontType2 only) =====
        COSDictionary c2gIdentity = cidFont("CIDFontType2");
        c2gIdentity.setItem(CID_TO_GID_MAP, n("Identity"));
        emit("cid2gid_identity", type0(descArray(c2gIdentity), "Identity-H"));

        COSDictionary c2gStream = cidFont("CIDFontType2");
        c2gStream.setItem(CID_TO_GID_MAP, cidToGidStream());
        emit("cid2gid_stream", type0(descArray(c2gStream), "Identity-H"));

        // absent /CIDToGIDMap (treated as Identity per §9.7.4.2).
        emit("cid2gid_absent",
             type0(descArray(cidFont("CIDFontType2")), "Identity-H"));

        COSDictionary c2gBadName = cidFont("CIDFontType2");
        c2gBadName.setItem(CID_TO_GID_MAP, n("Frobnicate"));
        emit("cid2gid_bad_name", type0(descArray(c2gBadName), "Identity-H"));

        // /CIDToGIDMap as an array (wrong type).
        COSDictionary c2gArr = cidFont("CIDFontType2");
        c2gArr.setItem(CID_TO_GID_MAP, arr(i(1), i(2)));
        emit("cid2gid_as_array", type0(descArray(c2gArr), "Identity-H"));

        // /CIDToGIDMap on a CIDFontType0 (illegal — has no such key).
        COSDictionary c2gOnType0 = cidFont("CIDFontType0");
        c2gOnType0.setItem(CID_TO_GID_MAP, n("Identity"));
        emit("cid2gid_on_cidtype0", type0(descArray(c2gOnType0), "Identity-H"));

        // ===== /CIDSystemInfo shapes =====
        COSDictionary csiMissing = cidFont("CIDFontType2");
        csiMissing.removeItem(n("CIDSystemInfo"));
        emit("csi_missing", type0(descArray(csiMissing), "Identity-H"));

        COSDictionary csiNoOrdering = cidFont("CIDFontType2");
        csiNoOrdering.setItem(n("CIDSystemInfo"), csi("Adobe", null, 0));
        emit("csi_no_ordering", type0(descArray(csiNoOrdering), "Identity-H"));

        COSDictionary csiNoRegistry = cidFont("CIDFontType2");
        csiNoRegistry.setItem(n("CIDSystemInfo"), csi(null, "Japan1", 2));
        emit("csi_no_registry", type0(descArray(csiNoRegistry), "Identity-H"));

        COSDictionary csiNoSupp = cidFont("CIDFontType2");
        csiNoSupp.setItem(n("CIDSystemInfo"), csi("Adobe", "GB1", null));
        emit("csi_no_supplement", type0(descArray(csiNoSupp), "Identity-H"));

        COSDictionary csiEmpty = cidFont("CIDFontType2");
        csiEmpty.setItem(n("CIDSystemInfo"), new COSDictionary());
        emit("csi_empty_dict", type0(descArray(csiEmpty), "Identity-H"));

        // /CIDSystemInfo with /Registry as a name (getNameAsString tolerates).
        COSDictionary csiNameReg = cidFont("CIDFontType2");
        COSDictionary csiNR = new COSDictionary();
        csiNR.setItem(n("Registry"), n("Adobe"));
        csiNR.setItem(n("Ordering"), n("Korea1"));
        csiNR.setInt(n("Supplement"), 1);
        csiNameReg.setItem(n("CIDSystemInfo"), csiNR);
        emit("csi_name_typed_fields", type0(descArray(csiNameReg), "Identity-H"));

        // /CIDSystemInfo as an array (wrong type).
        COSDictionary csiArr = cidFont("CIDFontType2");
        csiArr.setItem(n("CIDSystemInfo"), arr(i(1)));
        emit("csi_as_array", type0(descArray(csiArr), "Identity-H"));
    }
}
