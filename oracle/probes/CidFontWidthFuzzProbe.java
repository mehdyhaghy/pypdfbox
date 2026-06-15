import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdmodel.font.PDCIDFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;
import org.apache.pdfbox.util.Vector;

/**
 * Differential fuzz probe for {@code PDCIDFont} per-CID width-table parsing,
 * Apache PDFBox 3.0.7 (wave 1528, agent D).
 *
 * <h2>What this covers that the existing CID probes do not</h2>
 * {@code CidWidthProbe} loads real, WELL-FORMED Type0 fixtures and verifies the
 * value-parity of {@code getWidth} / {@code hasExplicitWidth} / {@code /DW}.
 * {@code CidToGidStreamProbe} covers {@code /CIDToGIDMap}. Neither fuzzes the
 * {@code /W} / {@code /W2} / {@code /DW} / {@code /DW2} dictionary entries
 * themselves. This probe builds deliberately MALFORMED descendant-CIDFont
 * dictionaries in memory (wrapped in a minimal Identity-H {@code PDType0Font}
 * so {@code codeToCID(code) == code}) and projects the leniency / failure mode
 * of each width accessor:
 *
 * <ul>
 *   <li>{@code /W} missing (all default) / empty array;</li>
 *   <li>{@code /W} {@code c [w1 w2 ...]} list form, {@code c1 c2 w} range form,
 *       mixed forms in one array;</li>
 *   <li>malformed {@code /W} runs: non-numeric {@code c}, non-numeric {@code w},
 *       a number where an array is expected, an array where a range width is
 *       expected, odd trailing token, premature end, {@code c2 < c1},
 *       negative CIDs, huge CIDs, {@code null} entries;</li>
 *   <li>{@code /DW} missing (default 1000) / non-numeric / float;</li>
 *   <li>{@code /W2} missing / list form / range form / malformed (non-number
 *       first element, ragged inner array, non-number range token) — note
 *       {@code readVerticalDisplacements} uses UNCHECKED casts upstream, so a
 *       malformed {@code /W2} throws {@code ClassCastException} from the CIDFont
 *       constructor;</li>
 *   <li>{@code /DW2} missing (default {880,-1000}) / malformed.</li>
 * </ul>
 *
 * <h2>Input</h2>
 * Deterministic, seed-free, no file I/O: a fixed inline corpus built identically
 * on both sides. The pypdfbox sibling
 * (tests/pdmodel/font/oracle/test_cid_font_width_fuzz_wave1528.py) rebuilds the
 * identical dicts and asserts each {@code CASE} line matches; intentional
 * pypdfbox robustness divergences are pinned both-sides with a CHANGES.md
 * citation.
 *
 * <h2>Output grammar (one line per case)</h2>
 * <pre>
 *   CASE &lt;name&gt; create=&lt;ok|ERR:X|nodesc&gt; dw=&lt;f&gt;
 *        w&lt;cid&gt;=&lt;f|ERR&gt; hx&lt;cid&gt;=&lt;bool|ERR&gt; ...
 *        vy&lt;cid&gt;=&lt;f|ERR&gt; pv&lt;cid&gt;=&lt;x,y|ERR&gt; ...
 * </pre>
 * Floats are rendered with {@link #f(float)} (trailing zeros trimmed) so 600 and
 * 600.0 render identically across both languages. {@code dw} is read directly
 * from the dict (the private {@code getDefaultWidth} mirror) like CidWidthProbe.
 */
public final class CidFontWidthFuzzProbe {

    static PrintStream out;

    // CIDs probed for every case: spans list/range coverage, gaps (default
    // fallback), negative + huge + zero. Kept in lockstep with the Python side.
    static final int[] PROBE_CIDS = {
        0, 1, 5, 10, 11, 12, 13, 20, 21, 22, 23, 100, 200, 1000, 65535, -1
    };

    static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    static COSInteger i(int v) {
        return COSInteger.get(v);
    }

    static COSFloat fl(double v) {
        return new COSFloat((float) v);
    }

    static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase b : items) {
            a.add(b);
        }
        return a;
    }

    static String f(float v) {
        if (v == 0.0f) {
            v = 0.0f; // collapse -0.0
        }
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Long.toString((long) v);
        }
        return Float.toString(v);
    }

    /** Minimal descendant CIDFontType2 skeleton; callers add the fuzzed entries. */
    static COSDictionary cidFont() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        d.setItem(COSName.SUBTYPE, n("CIDFontType2"));
        d.setItem(n("BaseFont"), n("Test"));
        return d;
    }

    /** Wrap a descendant CIDFont dict in a minimal Identity-H Type0 font dict. */
    static COSDictionary wrap(COSDictionary cid) {
        COSDictionary t0 = new COSDictionary();
        t0.setItem(COSName.TYPE, COSName.FONT);
        t0.setItem(COSName.SUBTYPE, n("Type0"));
        t0.setItem(n("BaseFont"), n("Test"));
        t0.setItem(COSName.ENCODING, n("Identity-H"));
        t0.setItem(n("DescendantFonts"), arr(cid));
        return t0;
    }

    /** The /DW default width as PDFBox's private getDefaultWidth() computes it. */
    static float readDw(PDCIDFont d) {
        COSBase dw = d.getCOSObject().getDictionaryObject(COSName.DW);
        if (dw instanceof COSNumber) {
            return ((COSNumber) dw).floatValue();
        }
        return 1000.0f;
    }

    static void emit(String name, COSDictionary cid) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDType0Font t0;
        try {
            t0 = new PDType0Font(wrap(cid));
        } catch (Throwable t) {
            out.println(sb.append("create=ERR:")
                    .append(t.getClass().getSimpleName()).toString());
            return;
        }
        PDCIDFont d = t0.getDescendantFont();
        if (d == null) {
            out.println(sb.append("create=nodesc").toString());
            return;
        }
        sb.append("create=ok dw=").append(f(readDw(d)));
        for (int pcid : PROBE_CIDS) {
            sb.append(" w").append(pcid).append('=');
            try {
                sb.append(f(d.getWidth(pcid)));
            } catch (Throwable t) {
                sb.append("ERR");
            }
            sb.append(" hx").append(pcid).append('=');
            try {
                sb.append(d.hasExplicitWidth(pcid) ? "true" : "false");
            } catch (Throwable t) {
                sb.append("ERR");
            }
        }
        for (int vcid : PROBE_CIDS) {
            sb.append(" vy").append(vcid).append('=');
            try {
                sb.append(f(d.getVerticalDisplacementVectorY(vcid)));
            } catch (Throwable t) {
                sb.append("ERR");
            }
            sb.append(" pv").append(vcid).append('=');
            try {
                Vector v = d.getPositionVector(vcid);
                sb.append(v == null ? "null" : (f(v.getX()) + "," + f(v.getY())));
            } catch (Throwable t) {
                sb.append("ERR");
            }
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ===== /W missing / empty =====
        emit("w_missing", cidFont());

        COSDictionary wEmpty = cidFont();
        wEmpty.setItem(n("W"), new COSArray());
        emit("w_empty", wEmpty);

        // ===== /W list form: c [w1 w2 w3] =====
        COSDictionary wList = cidFont();
        wList.setItem(n("W"), arr(i(10), arr(i(100), i(200), i(300))));
        emit("w_list", wList);

        // ===== /W range form: c1 c2 w =====
        COSDictionary wRange = cidFont();
        wRange.setItem(n("W"), arr(i(20), i(22), i(500)));
        emit("w_range", wRange);

        // ===== /W mixed forms =====
        COSDictionary wMixed = cidFont();
        wMixed.setItem(n("W"),
                arr(i(10), arr(i(100), i(200), i(300)), i(20), i(22), i(500)));
        emit("w_mixed", wMixed);

        // ===== /W float widths =====
        COSDictionary wFloat = cidFont();
        wFloat.setItem(n("W"), arr(i(10), arr(fl(100.5), fl(200.25))));
        emit("w_float", wFloat);

        // ===== /W non-numeric leading c (form 1 position) =====
        COSDictionary wBadC = cidFont();
        wBadC.setItem(n("W"), arr(n("X"), arr(i(100), i(200))));
        emit("w_nonnumeric_c", wBadC);

        // ===== /W list form with a non-number inside the inner array =====
        COSDictionary wBadInner = cidFont();
        wBadInner.setItem(n("W"), arr(i(10), arr(i(100), n("Y"), i(300))));
        emit("w_inner_nonnumeric", wBadInner);

        // ===== /W range form, third token non-number =====
        COSDictionary wBadW = cidFont();
        wBadW.setItem(n("W"), arr(i(20), i(22), n("Z")));
        emit("w_range_nonnumeric_w", wBadW);

        // ===== /W odd trailing token (single number at end) =====
        COSDictionary wOdd = cidFont();
        wOdd.setItem(n("W"), arr(i(10), arr(i(100)), i(99)));
        emit("w_odd_trailing", wOdd);

        // ===== /W premature end: c then a number, but nothing for w =====
        COSDictionary wPrem = cidFont();
        wPrem.setItem(n("W"), arr(i(10), i(20)));
        emit("w_premature_end", wPrem);

        // ===== /W range c2 < c1 (empty range) =====
        COSDictionary wRev = cidFont();
        wRev.setItem(n("W"), arr(i(22), i(20), i(500)));
        emit("w_range_reversed", wRev);

        // ===== /W negative CIDs in list form =====
        COSDictionary wNeg = cidFont();
        wNeg.setItem(n("W"), arr(i(-1), arr(i(100), i(200))));
        emit("w_negative_cid", wNeg);

        // ===== /W huge starting CID =====
        COSDictionary wHuge = cidFont();
        wHuge.setItem(n("W"), arr(i(65535), arr(i(700))));
        emit("w_huge_cid", wHuge);

        // ===== /W null entry where c expected =====
        COSDictionary wNullC = cidFont();
        wNullC.setItem(n("W"), arr(COSNull.NULL, arr(i(100))));
        emit("w_null_c", wNullC);

        // ===== /W overlapping runs (later wins?) =====
        COSDictionary wOverlap = cidFont();
        wOverlap.setItem(n("W"),
                arr(i(10), i(12), i(111), i(11), arr(i(999))));
        emit("w_overlap", wOverlap);

        // ===== /W is not an array (a name) -> getCOSArray returns null =====
        COSDictionary wNotArr = cidFont();
        wNotArr.setItem(n("W"), n("Nope"));
        emit("w_not_array", wNotArr);

        // ===== /DW non-default integer =====
        COSDictionary dwInt = cidFont();
        dwInt.setItem(n("DW"), i(222));
        emit("dw_int", dwInt);

        // ===== /DW float =====
        COSDictionary dwFloat = cidFont();
        dwFloat.setItem(n("DW"), fl(333.5));
        emit("dw_float", dwFloat);

        // ===== /DW non-numeric (name) -> default 1000 =====
        COSDictionary dwName = cidFont();
        dwName.setItem(n("DW"), n("Big"));
        emit("dw_nonnumeric", dwName);

        // ===== /DW with /W: list + range + gaps all using custom DW =====
        COSDictionary dwAndW = cidFont();
        dwAndW.setItem(n("DW"), i(222));
        dwAndW.setItem(n("W"),
                arr(i(10), arr(i(100), i(200), i(300)), i(20), i(22), i(500)));
        emit("dw_and_w", dwAndW);

        // ===== /W2 list form: c [w1y vx vy w1y vx vy] =====
        COSDictionary w2List = cidFont();
        w2List.setItem(n("W2"),
                arr(i(10), arr(i(-1000), i(500), i(880),
                               i(-1100), i(510), i(890))));
        emit("w2_list", w2List);

        // ===== /W2 range form: c1 c2 w1y vx vy =====
        COSDictionary w2Range = cidFont();
        w2Range.setItem(n("W2"), arr(i(20), i(22), i(-1000), i(500), i(880)));
        emit("w2_range", w2Range);

        // ===== /W2 missing -> defaults from /DW2 (880,-1000) =====
        emit("w2_missing", cidFont());

        // ===== /DW2 explicit non-default =====
        COSDictionary dw2 = cidFont();
        dw2.setItem(n("DW2"), arr(i(900), i(-1100)));
        emit("dw2_explicit", dw2);

        // ===== /DW2 malformed (one entry) -> upstream keeps default both =====
        COSDictionary dw2Short = cidFont();
        dw2Short.setItem(n("DW2"), arr(i(900)));
        emit("dw2_short", dw2Short);

        // ===== /DW2 non-numeric -> default 880,-1000 =====
        COSDictionary dw2Name = cidFont();
        dw2Name.setItem(n("DW2"), arr(n("A"), n("B")));
        emit("dw2_nonnumeric", dw2Name);

        // ===== /W2 first element not a number (upstream: unchecked cast) =====
        COSDictionary w2BadC = cidFont();
        w2BadC.setItem(n("W2"), arr(n("X"), arr(i(-1000), i(500), i(880))));
        emit("w2_nonnumeric_c", w2BadC);

        // ===== /W2 ragged inner array (size not divisible by 3) =====
        COSDictionary w2Ragged = cidFont();
        w2Ragged.setItem(n("W2"), arr(i(10), arr(i(-1000), i(500))));
        emit("w2_ragged_inner", w2Ragged);

        // ===== /W2 range with a non-number metric token =====
        COSDictionary w2BadMetric = cidFont();
        w2BadMetric.setItem(n("W2"), arr(i(20), i(22), i(-1000), n("Y"), i(880)));
        emit("w2_range_nonnumeric", w2BadMetric);

        // ===== /W2 range c2 < c1 (empty) =====
        COSDictionary w2Rev = cidFont();
        w2Rev.setItem(n("W2"), arr(i(22), i(20), i(-1000), i(500), i(880)));
        emit("w2_range_reversed", w2Rev);
    }
}
