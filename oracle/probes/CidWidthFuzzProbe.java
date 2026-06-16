import java.io.OutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Differential fuzz probe for the {@code PDType0Font} code -> CID -> GID -> width
 * PIPELINE, Apache PDFBox 3.0.7 (wave 1543, agent C).
 *
 * <h2>What this covers that the existing CID probes do not</h2>
 * The wave-1528 {@code CidFontWidthFuzzProbe} fuzzes the descendant CIDFont's
 * {@code /W} / {@code /W2} / {@code /DW} / {@code /DW2} ARRAY parsing while
 * holding {@code codeToCID} fixed at identity (it never sets {@code /Encoding}
 * to anything other than the implicit Identity-H wrapper and reads from the
 * BARE descendant). {@code CidGidProbe} / {@code CidToGidStreamProbe} load real
 * on-disk PDF fixtures. NEITHER fuzzes the {@code code -> CID} resolution itself
 * (the encoding CMap) or the {@code CID -> GID} resolution ({@code /CIDToGIDMap}
 * as a stream) together with the WIDTH lookup, all driven through the public
 * {@code PDType0Font} accessors.
 *
 * <p>This probe builds in-memory {@code PDType0Font} dictionaries with:
 * <ul>
 *   <li>{@code /Encoding} as a custom embedded CMap STREAM (1- and 2-byte
 *       codespace ranges; {@code cidchar} + {@code cidrange}; out-of-codespace
 *       codes; a code the CMap maps to CID 0);</li>
 *   <li>{@code /Encoding} as a predefined name ({@code Identity-H});</li>
 *   <li>{@code /CIDToGIDMap} = {@code /Identity}, absent, or a packed-uint16
 *       STREAM (in-bounds GIDs, an out-of-bounds CID resolving to GID 0, an
 *       odd-length trailing byte, an empty stream);</li>
 *   <li>{@code /W} runs (list + range form) so the width sweep crosses covered
 *       and uncovered CIDs (the latter falling back to {@code /DW});</li>
 *   <li>{@code /DW} present / absent so the default-width fallback is exercised
 *       through the FULL pipeline (code -> CID -> width), not just CID -> width.</li>
 * </ul>
 *
 * <p>For every case we sweep a fixed set of CHARACTER CODES and project the
 * public pipeline accessors:
 * {@code codeToCID(code)}, {@code codeToGID(code)}, {@code getWidth(code)},
 * {@code getWidthFromFont(code)}. No embedded font program is present, so
 * {@code getWidthFromFont} returns 0 on both sides (the descendant CIDFontType2
 * has no {@code /FontFile2}); it is projected anyway to pin that contract.
 *
 * <h2>Input</h2>
 * Deterministic, seed-free, no file I/O. The pypdfbox sibling
 * (tests/pdmodel/font/oracle/test_cid_width_fuzz_wave1543.py) rebuilds identical
 * dicts and asserts each CASE line matches token-for-token.
 *
 * <h2>Output grammar (one line per case)</h2>
 * <pre>
 *   CASE &lt;name&gt; create=&lt;ok|ERR:X|nodesc&gt;
 *        c&lt;code&gt;=&lt;cid|ERR&gt; g&lt;code&gt;=&lt;gid|ERR&gt;
 *        w&lt;code&gt;=&lt;f|ERR&gt; wf&lt;code&gt;=&lt;f|ERR&gt; ...
 * </pre>
 * Floats render via {@link #f(float)} (trailing zeros trimmed) so 555 and 555.0
 * render identically across both languages.
 */
public final class CidWidthFuzzProbe {

    static PrintStream out;

    // Character codes swept for every case: spans below / inside / above the
    // codespace, codes the CMap maps to CID 0 (notdef), a covered /W CID, an
    // uncovered CID (/DW fallback), and a huge code. Kept in lockstep with the
    // Python side.
    static final int[] PROBE_CODES = {
        0, 1, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 100, 200, 1000, 65535
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

    /** Build an in-memory COSStream carrying {@code body} verbatim (no filter). */
    static COSStream stream(byte[] body) throws Exception {
        COSStream s = new COSStream();
        try (OutputStream os = s.createOutputStream()) {
            os.write(body);
        }
        return s;
    }

    /**
     * A small custom CMap source: 1-byte codespace {@code <00>..<FF>},
     * {@code <41> -> CID 100} (cidchar), {@code <42>..<44> -> CID 200..202}
     * (cidrange). Code 0x40 / 0x45 are in-codespace but unmapped -> CID 0.
     */
    static final byte[] CUSTOM_CMAP_1B = (
        "/CIDInit /ProcSet findresource begin\n"
        + "12 dict begin\n"
        + "begincmap\n"
        + "/CMapName /CustomFuzz1B def\n"
        + "/CMapType 1 def\n"
        + "1 begincodespacerange\n"
        + "<00> <ff>\n"
        + "endcodespacerange\n"
        + "1 begincidchar\n"
        + "<41> 100\n"
        + "endcidchar\n"
        + "1 begincidrange\n"
        + "<42> <44> 200\n"
        + "endcidrange\n"
        + "endcmap\n"
        + "end end\n"
    ).getBytes(java.nio.charset.StandardCharsets.US_ASCII);

    /**
     * A 2-byte codespace CMap {@code <0000>..<FFFF>} with the same logical
     * mappings as {@link #CUSTOM_CMAP_1B} but addressed by 2-byte codes:
     * {@code <0041> -> 100}, {@code <0042>..<0044> -> 200..202}.
     */
    static final byte[] CUSTOM_CMAP_2B = (
        "/CIDInit /ProcSet findresource begin\n"
        + "12 dict begin\n"
        + "begincmap\n"
        + "/CMapName /CustomFuzz2B def\n"
        + "/CMapType 1 def\n"
        + "1 begincodespacerange\n"
        + "<0000> <ffff>\n"
        + "endcodespacerange\n"
        + "1 begincidchar\n"
        + "<0041> 100\n"
        + "endcidchar\n"
        + "1 begincidrange\n"
        + "<0042> <0044> 200\n"
        + "endcidrange\n"
        + "endcmap\n"
        + "end end\n"
    ).getBytes(java.nio.charset.StandardCharsets.US_ASCII);

    /** Minimal descendant CIDFontType2 skeleton; callers add the fuzzed entries. */
    static COSDictionary cidFont() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        d.setItem(COSName.SUBTYPE, n("CIDFontType2"));
        d.setItem(n("BaseFont"), n("Test"));
        return d;
    }

    /** A /W table covering CIDs 100, 200..202 with distinct widths. */
    static COSArray sampleW() {
        // 100 [555]   (list form, one CID)
        // 200 202 777 (range form)
        return arr(i(100), arr(i(555)), i(200), i(202), i(777));
    }

    /** Wrap a descendant CIDFont dict in a Type0 font with the given /Encoding. */
    static COSDictionary wrap(COSDictionary cid, COSBase encoding) {
        COSDictionary t0 = new COSDictionary();
        t0.setItem(COSName.TYPE, COSName.FONT);
        t0.setItem(COSName.SUBTYPE, n("Type0"));
        t0.setItem(n("BaseFont"), n("Test"));
        t0.setItem(COSName.ENCODING, encoding);
        t0.setItem(n("DescendantFonts"), arr(cid));
        return t0;
    }

    static void emit(String name, COSDictionary cid, COSBase encoding) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDType0Font t0;
        try {
            t0 = new PDType0Font(wrap(cid, encoding));
        } catch (Throwable t) {
            out.println(sb.append("create=ERR:")
                    .append(t.getClass().getSimpleName()).toString());
            return;
        }
        if (t0.getDescendantFont() == null) {
            out.println(sb.append("create=nodesc").toString());
            return;
        }
        sb.append("create=ok");
        for (int code : PROBE_CODES) {
            sb.append(" c").append(code).append('=');
            try {
                sb.append(t0.codeToCID(code));
            } catch (Throwable t) {
                sb.append("ERR");
            }
            sb.append(" g").append(code).append('=');
            try {
                sb.append(t0.codeToGID(code));
            } catch (Throwable t) {
                sb.append("ERR");
            }
            sb.append(" w").append(code).append('=');
            try {
                sb.append(f(t0.getWidth(code)));
            } catch (Throwable t) {
                sb.append("ERR");
            }
            sb.append(" wf").append(code).append('=');
            try {
                sb.append(f(t0.getWidthFromFont(code)));
            } catch (Throwable t) {
                sb.append("ERR");
            }
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ===== predefined Identity-H, /W present, /DW present =====
        COSDictionary idDw = cidFont();
        idDw.setItem(n("DW"), i(333));
        idDw.setItem(n("W"), sampleW());
        emit("identity_dw_w", idDw, n("Identity-H"));

        // ===== predefined Identity-H, /W present, /DW absent (default 1000) =====
        COSDictionary idNoDw = cidFont();
        idNoDw.setItem(n("W"), sampleW());
        emit("identity_no_dw", idNoDw, n("Identity-H"));

        // ===== predefined Identity-H, no /W at all (all /DW) =====
        COSDictionary idBare = cidFont();
        idBare.setItem(n("DW"), i(444));
        emit("identity_bare_dw", idBare, n("Identity-H"));

        // ===== custom 1-byte CMap stream, /W keyed by CID (not code) =====
        COSDictionary c1 = cidFont();
        c1.setItem(n("DW"), i(333));
        c1.setItem(n("W"), sampleW());
        emit("custom1b_dw_w", c1, stream(CUSTOM_CMAP_1B));

        // ===== custom 1-byte CMap stream, /W absent (all /DW after CID map) =====
        COSDictionary c1NoW = cidFont();
        c1NoW.setItem(n("DW"), i(333));
        emit("custom1b_no_w", c1NoW, stream(CUSTOM_CMAP_1B));

        // ===== custom 2-byte CMap stream, /W keyed by CID =====
        COSDictionary c2 = cidFont();
        c2.setItem(n("DW"), i(333));
        c2.setItem(n("W"), sampleW());
        emit("custom2b_dw_w", c2, stream(CUSTOM_CMAP_2B));

        // ===== Identity-H + /CIDToGIDMap = /Identity (explicit name) =====
        COSDictionary gidId = cidFont();
        gidId.setItem(n("W"), sampleW());
        gidId.setItem(n("CIDToGIDMap"), n("Identity"));
        emit("gid_identity_name", gidId, n("Identity-H"));

        // ===== Identity-H + /CIDToGIDMap stream (in-bounds remap) =====
        // CID i -> GID via packed uint16; index 0..4 -> [0, 50, 51, 0, 99].
        byte[] gmap = new byte[] {
            0, 0,  0, 50,  0, 51,  0, 0,  0, 99
        };
        COSDictionary gidStream = cidFont();
        gidStream.setItem(n("W"), sampleW());
        gidStream.setItem(n("CIDToGIDMap"), stream(gmap));
        emit("gid_stream", gidStream, n("Identity-H"));

        // ===== /CIDToGIDMap stream, odd trailing byte (ignored) =====
        byte[] gmapOdd = new byte[] {
            0, 0,  0, 50,  0, 51,  9
        };
        COSDictionary gidOdd = cidFont();
        gidOdd.setItem(n("W"), sampleW());
        gidOdd.setItem(n("CIDToGIDMap"), stream(gmapOdd));
        emit("gid_stream_odd", gidOdd, n("Identity-H"));

        // ===== /CIDToGIDMap empty stream (every CID -> GID 0) =====
        COSDictionary gidEmpty = cidFont();
        gidEmpty.setItem(n("W"), sampleW());
        gidEmpty.setItem(n("CIDToGIDMap"), stream(new byte[0]));
        emit("gid_stream_empty", gidEmpty, n("Identity-H"));

        // ===== custom 1-byte CMap + /CIDToGIDMap stream together =====
        // Exercises the full pipeline: code -> (CMap) CID -> (stream) GID. The
        // stream only has 5 entries, so CID 100/200+ (mapped by the CMap) land
        // out-of-bounds -> GID 0.
        COSDictionary combo = cidFont();
        combo.setItem(n("DW"), i(333));
        combo.setItem(n("W"), sampleW());
        combo.setItem(n("CIDToGIDMap"), stream(gmap));
        emit("custom1b_gid_stream", combo, stream(CUSTOM_CMAP_1B));

        // ===== Identity-H, /W with a range crossing the probe codes =====
        COSDictionary rangeW = cidFont();
        rangeW.setItem(n("DW"), i(333));
        rangeW.setItem(n("W"), arr(i(0x40), i(0x44), i(888)));
        emit("identity_range_w", rangeW, n("Identity-H"));

        // ===== /Encoding absent entirely (no CMap) =====
        COSDictionary noEnc = cidFont();
        noEnc.setItem(n("DW"), i(333));
        noEnc.setItem(n("W"), sampleW());
        // wrap() always sets /Encoding; build the dict by hand to omit it.
        COSDictionary t0NoEnc = new COSDictionary();
        t0NoEnc.setItem(COSName.TYPE, COSName.FONT);
        t0NoEnc.setItem(COSName.SUBTYPE, n("Type0"));
        t0NoEnc.setItem(n("BaseFont"), n("Test"));
        t0NoEnc.setItem(n("DescendantFonts"), arr(noEnc));
        {
            StringBuilder sb = new StringBuilder("CASE no_encoding ");
            PDType0Font t0;
            try {
                t0 = new PDType0Font(t0NoEnc);
            } catch (Throwable t) {
                out.println(sb.append("create=ERR:")
                        .append(t.getClass().getSimpleName()).toString());
                return;
            }
            if (t0.getDescendantFont() == null) {
                out.println(sb.append("create=nodesc").toString());
            } else {
                sb.append("create=ok");
                for (int code : PROBE_CODES) {
                    sb.append(" c").append(code).append('=');
                    try {
                        sb.append(t0.codeToCID(code));
                    } catch (Throwable t) {
                        sb.append("ERR");
                    }
                    sb.append(" g").append(code).append('=');
                    try {
                        sb.append(t0.codeToGID(code));
                    } catch (Throwable t) {
                        sb.append("ERR");
                    }
                    sb.append(" w").append(code).append('=');
                    try {
                        sb.append(f(t0.getWidth(code)));
                    } catch (Throwable t) {
                        sb.append("ERR");
                    }
                    sb.append(" wf").append(code).append('=');
                    try {
                        sb.append(f(t0.getWidthFromFont(code)));
                    } catch (Throwable t) {
                        sb.append("ERR");
                    }
                }
                out.println(sb.toString());
            }
        }
    }
}
