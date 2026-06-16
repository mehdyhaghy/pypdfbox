package org.apache.fontbox.ttf;

import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for the FontBox TrueType METRIC / NAME tables at the
 * table-{@code read()} level (wave 1553 differential fuzz).
 *
 * Where the existing {@code PostTableProbe} / {@code NameTableProbe} /
 * {@code Os2MetricsProbe} / {@code HmtxLsbProbe} / {@code HeadMaxpProbe} parse a
 * REAL, well-formed SFNT and read the accessors, THIS probe drives the
 * package-private {@code read(TrueTypeFont, TTFDataStream)} of each table
 * DIRECTLY over a buffer of hand-crafted (often MALFORMED) table bytes the
 * Python companion hands in as hex. That is exactly the surface pypdfbox ports
 * in {@code post_script_table.py} / {@code naming_table.py} /
 * {@code os2_windows_metrics_table.py} / {@code horizontal_metrics_table.py} /
 * {@code horizontal_header_table.py} / {@code header_table.py}.
 *
 * The probe lives in package {@code org.apache.fontbox.ttf} so it can call the
 * package-private {@code TTFTable.read(...)} and the table setters
 * ({@code setOffset} / {@code setLength}). A bare {@code TrueTypeFont} is built
 * over the table blob; for the {@code post} format-2.5 / hmtx cases the
 * dependent {@code maxp} (numGlyphs) and {@code hhea} (numberOfHMetrics) tables
 * are pre-read from synthetic blobs and added to the font so
 * {@code getNumberOfGlyphs()} / {@code getHorizontalHeader()} resolve without
 * touching the (absent) font directory.
 *
 * Usage:
 *   java ... TtfMetricTableFuzzProbe POST  numGlyphs hex -- gid...
 *   java ... TtfMetricTableFuzzProbe NAME  hex -- nameId,plat,enc,lang...
 *   java ... TtfMetricTableFuzzProbe OS2   hex
 *   java ... TtfMetricTableFuzzProbe HMTX  numGlyphs numHMetrics hex -- gid...
 *   java ... TtfMetricTableFuzzProbe HEAD  hex
 *
 * Output: UTF-8, tab-separated, deterministic line order. Every mode prints a
 * leading status token (ok|err). On {@code err} the exception simple-name is the
 * sole payload (the cross-language exception-class mapping is documented in the
 * Python companion; the parity criterion is the "does it decode" outcome bucket
 * plus the projected accessor values when it does).
 */
public final class TtfMetricTableFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        switch (mode) {
            case "POST":
                emitPost(out, args);
                break;
            case "NAME":
                emitName(out, args);
                break;
            case "OS2":
                emitOs2(out, args);
                break;
            case "HMTX":
                emitHmtx(out, args);
                break;
            case "HEAD":
                emitHead(out, args);
                break;
            default:
                out.println("err\tunknown-mode");
        }
    }

    // ----- POST -----------------------------------------------------------
    private static void emitPost(PrintStream out, String[] args) throws Exception {
        int numGlyphs = Integer.parseInt(args[1]);
        byte[] blob = hex(args[2]);
        int sep = sepIndex(args);
        TrueTypeFont font = font(blob);
        addMaxp(font, numGlyphs);
        PostScriptTable post = new PostScriptTable();
        post.setOffset(0);
        post.setLength(blob.length);
        try {
            post.read(font, stream(blob));
            out.printf("ok\t%s%n", fmt(post.getFormatType()));
            for (int i = sep + 1; i < args.length; i++) {
                int gid = Integer.parseInt(args[i]);
                String name = post.getName(gid);
                out.printf("NAME\t%d\t%s%n", gid, name == null ? "NULL" : name);
            }
        } catch (Throwable t) {
            out.printf("err\t%s%n", t.getClass().getSimpleName());
        }
    }

    // ----- NAME -----------------------------------------------------------
    private static void emitName(PrintStream out, String[] args) throws Exception {
        byte[] blob = hex(args[1]);
        int sep = sepIndex(args);
        TrueTypeFont font = font(blob);
        NamingTable name = new NamingTable();
        name.setOffset(0);
        name.setLength(blob.length);
        try {
            name.read(font, stream(blob));
            out.printf("ok\t%d%n", name.getNameRecords().size());
            out.printf("FAMILY\t%s%n", nz(name.getFontFamily()));
            out.printf("SUBFAMILY\t%s%n", nz(name.getFontSubFamily()));
            out.printf("PSNAME\t%s%n", nz(name.getPostScriptName()));
            for (int i = sep + 1; i < args.length; i++) {
                String[] p = args[i].split(",");
                int nid = Integer.parseInt(p[0]);
                int plat = Integer.parseInt(p[1]);
                int enc = Integer.parseInt(p[2]);
                int lang = Integer.parseInt(p[3]);
                String v = name.getName(nid, plat, enc, lang);
                out.printf("LOOKUP\t%s\t%s%n", args[i], nz(v));
            }
        } catch (Throwable t) {
            out.printf("err\t%s%n", t.getClass().getSimpleName());
        }
    }

    // ----- OS/2 -----------------------------------------------------------
    private static void emitOs2(PrintStream out, String[] args) throws Exception {
        byte[] blob = hex(args[1]);
        TrueTypeFont font = font(blob);
        OS2WindowsMetricsTable os2 = new OS2WindowsMetricsTable();
        os2.setOffset(0);
        os2.setLength(blob.length);
        try {
            os2.read(font, stream(blob));
            out.printf("ok\t%d%n", os2.getVersion());
            out.printf("WEIGHT\t%d%n", os2.getWeightClass());
            out.printf("FSTYPE\t%d%n", os2.getFsType());
            out.printf("TYPOASC\t%d%n", os2.getTypoAscender());
            out.printf("WINASC\t%d%n", os2.getWinAscent());
            out.printf("CODEPAGE1\t%d%n", os2.getCodePageRange1());
            out.printf("CAPHEIGHT\t%d%n", os2.getCapHeight());
        } catch (Throwable t) {
            out.printf("err\t%s%n", t.getClass().getSimpleName());
        }
    }

    // ----- HMTX -----------------------------------------------------------
    private static void emitHmtx(PrintStream out, String[] args) throws Exception {
        int numGlyphs = Integer.parseInt(args[1]);
        int numHMetrics = Integer.parseInt(args[2]);
        byte[] blob = hex(args[3]);
        int sep = sepIndex(args);
        TrueTypeFont font = font(blob);
        addMaxp(font, numGlyphs);
        addHhea(font, numHMetrics);
        HorizontalMetricsTable hmtx = new HorizontalMetricsTable();
        hmtx.setOffset(0);
        hmtx.setLength(blob.length);
        try {
            hmtx.read(font, stream(blob));
            out.printf("ok\t%d\t%d%n", numGlyphs, numHMetrics);
            for (int i = sep + 1; i < args.length; i++) {
                int gid = Integer.parseInt(args[i]);
                String adv;
                String lsb;
                try {
                    adv = Integer.toString(hmtx.getAdvanceWidth(gid));
                } catch (Throwable t) {
                    adv = "ERR(" + t.getClass().getSimpleName() + ")";
                }
                try {
                    lsb = Integer.toString(hmtx.getLeftSideBearing(gid));
                } catch (Throwable t) {
                    lsb = "ERR(" + t.getClass().getSimpleName() + ")";
                }
                out.printf("HM\t%d\t%s\t%s%n", gid, adv, lsb);
            }
        } catch (Throwable t) {
            out.printf("err\t%s%n", t.getClass().getSimpleName());
        }
    }

    // ----- HEAD -----------------------------------------------------------
    private static void emitHead(PrintStream out, String[] args) throws Exception {
        byte[] blob = hex(args[1]);
        TrueTypeFont font = font(blob);
        HeaderTable head = new HeaderTable();
        head.setOffset(0);
        head.setLength(blob.length);
        try {
            head.read(font, stream(blob));
            out.printf("ok\t%d%n", head.getUnitsPerEm());
            out.printf("INDEXTOLOC\t%d%n", head.getIndexToLocFormat());
            out.printf("MACSTYLE\t%d%n", head.getMacStyle());
            out.printf("MAGIC\t%d%n", head.getMagicNumber());
            out.printf("FLAGS\t%d%n", head.getFlags());
        } catch (Throwable t) {
            out.printf("err\t%s%n", t.getClass().getSimpleName());
        }
    }

    // ----- helpers --------------------------------------------------------
    private static TrueTypeFont font(byte[] blob) throws Exception {
        return new TrueTypeFont(stream(blob));
    }

    private static RandomAccessReadDataStream stream(byte[] blob) throws Exception {
        return new RandomAccessReadDataStream(new RandomAccessReadBuffer(blob));
    }

    private static void addMaxp(TrueTypeFont font, int numGlyphs) throws Exception {
        // version 0.5 maxp = 4-byte fixed (0x00005000) + uint16 numGlyphs.
        byte[] m = new byte[6];
        m[0] = 0x00;
        m[1] = 0x00;
        m[2] = 0x50;
        m[3] = 0x00;
        m[4] = (byte) ((numGlyphs >> 8) & 0xFF);
        m[5] = (byte) (numGlyphs & 0xFF);
        MaximumProfileTable maxp = new MaximumProfileTable();
        maxp.setTag("maxp");
        maxp.setOffset(0);
        maxp.setLength(m.length);
        maxp.read(font, stream(m));
        font.addTable(maxp);
    }

    private static void addHhea(TrueTypeFont font, int numHMetrics) throws Exception {
        // 36-byte hhea: trailing uint16 numberOfHMetrics, rest zero.
        byte[] h = new byte[36];
        h[34] = (byte) ((numHMetrics >> 8) & 0xFF);
        h[35] = (byte) (numHMetrics & 0xFF);
        HorizontalHeaderTable hhea = new HorizontalHeaderTable();
        hhea.setTag("hhea");
        hhea.setOffset(0);
        hhea.setLength(h.length);
        hhea.read(font, stream(h));
        font.addTable(hhea);
    }

    private static int sepIndex(String[] args) {
        for (int i = 0; i < args.length; i++) {
            if ("--".equals(args[i])) {
                return i;
            }
        }
        return args.length - 1;
    }

    private static String nz(String s) {
        return s == null ? "NULL" : s;
    }

    private static String fmt(float f) {
        return Float.toString(f);
    }

    private static byte[] hex(String s) {
        if (s == null || s.isEmpty()) {
            return new byte[0];
        }
        List<Byte> bs = new ArrayList<>();
        for (int i = 0; i + 1 < s.length(); i += 2) {
            bs.add((byte) Integer.parseInt(s.substring(i, i + 2), 16));
        }
        byte[] out = new byte[bs.size()];
        for (int i = 0; i < out.length; i++) {
            out[i] = bs.get(i);
        }
        return out;
    }
}
