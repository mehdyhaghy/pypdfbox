package org.apache.fontbox.ttf;

import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for the FontBox {@code glyf} GLYPH-RECORD PARSERS at the
 * BYTE level (wave 1545 differential glyf-table fuzz).
 *
 * Where {@code GlyfDecodeFuzzProbe} (wave 1525) splices a hostile glyph into a
 * real SFNT and decodes it through the full {@code GlyphData} / {@code loca}
 * pipeline, THIS probe drives FontBox's hand-rolled record parsers DIRECTLY —
 * {@code GlyfSimpleDescript(short, TTFDataStream, short)},
 * {@code GlyfCompositeDescript(TTFDataStream, GlyphTable, int)}, and
 * {@code GlyfCompositeComp(TTFDataStream)} — over a buffer of raw glyf bytes the
 * Python companion hands in as hex. That is exactly the surface pypdfbox ports
 * in {@code glyf_simple_descript.py} / {@code glyf_composite_descript.py} /
 * {@code glyf_composite_comp.py}, so this probe pins the byte-decode loops
 * (endPts read, the 0xFFFF empty-contour sentinel, flag REPEAT runs overrunning
 * the data, instructionLength, coordinate deltas exhausting the stream,
 * composite MORE_COMPONENTS chains, ARG words-vs-bytes, scale / 2x2 transform
 * reads, component glyph indices) without going through fontTools or {@code loca}.
 *
 * The probe lives in package {@code org.apache.fontbox.ttf} so it can call the
 * package-private constructors. The {@code GlyphTable} argument to the composite
 * constructor is passed as {@code null} (no parent table → no sub-glyph
 * descriptions resolved), which keeps the test self-contained: the point of this
 * arm is the component-chain DECODE, not the cross-glyph flatten.
 *
 * Usage: java ... org.apache.fontbox.ttf.GlyfTableFuzzProbe MODE NC HEX
 *   MODE = SIMPLE | COMPOSITE | COMP        (which parser to drive)
 *   NC   = numberOfContours short value (SIMPLE only; ignored otherwise)
 *   HEX  = raw glyf-record bytes AFTER the numberOfContours+bbox header
 *          (SIMPLE: endPts.. onward) or the full component chain (COMPOSITE/COMP)
 *
 * Output is one stable tab-separated line:
 *   SIMPLE:    SIMPLE \t ok   \t pointCount \t contourCount \t endPts(csv) \t flags(csv)
 *              SIMPLE \t err  \t <exception-simple-name>
 *   COMPOSITE: COMP_DESC \t ok \t componentCount \t glyphIndices(csv) \t flags(csv)
 *              COMP_DESC \t err \t <exception-simple-name>
 *   COMP:      COMP \t ok \t glyphIndex \t flags \t arg1 \t arg2 \t xTranslate
 *              COMP \t err \t <exception-simple-name>
 */
public final class GlyfTableFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        short nc = (short) Integer.parseInt(args[1]);
        byte[] bytes = hex(args[2]);
        switch (mode) {
            case "SIMPLE":
                emitSimple(out, nc, bytes);
                break;
            case "COMPOSITE":
                emitComposite(out, bytes);
                break;
            case "COMP":
                emitComp(out, bytes);
                break;
            default:
                out.printf("ERR\tbad_mode\t%s%n", mode);
        }
    }

    private static TTFDataStream stream(byte[] bytes) throws Exception {
        return new RandomAccessReadDataStream(new RandomAccessReadBuffer(bytes));
    }

    private static void emitSimple(PrintStream out, short nc, byte[] bytes) {
        try {
            GlyfSimpleDescript d = new GlyfSimpleDescript(nc, stream(bytes), (short) 0);
            int points = d.getPointCount();
            int contours = d.getContourCount();
            StringBuilder endPts = new StringBuilder();
            for (int i = 0; i < contours; i++) {
                if (i > 0) {
                    endPts.append(',');
                }
                endPts.append(d.getEndPtOfContours(i));
            }
            StringBuilder flags = new StringBuilder();
            for (int i = 0; i < points; i++) {
                if (i > 0) {
                    flags.append(',');
                }
                flags.append(d.getFlags(i) & 0xFF);
            }
            out.printf("SIMPLE\tok\t%d\t%d\t%s\t%s%n", points, contours, endPts, flags);
        } catch (Throwable t) {
            out.printf("SIMPLE\terr\t%s%n", t.getClass().getSimpleName());
        }
    }

    private static void emitComposite(PrintStream out, byte[] bytes) {
        try {
            GlyfCompositeDescript d = new GlyfCompositeDescript(stream(bytes), null, 0);
            List<GlyfCompositeComp> comps = d.getComponents();
            int count = comps.size();
            StringBuilder gids = new StringBuilder();
            StringBuilder flags = new StringBuilder();
            for (int i = 0; i < count; i++) {
                if (i > 0) {
                    gids.append(',');
                    flags.append(',');
                }
                gids.append(comps.get(i).getGlyphIndex());
                flags.append(comps.get(i).getFlags() & 0xFFFF);
            }
            out.printf("COMP_DESC\tok\t%d\t%s\t%s%n", count, gids, flags);
        } catch (Throwable t) {
            out.printf("COMP_DESC\terr\t%s%n", t.getClass().getSimpleName());
        }
    }

    private static void emitComp(PrintStream out, byte[] bytes) {
        try {
            GlyfCompositeComp c = new GlyfCompositeComp(stream(bytes));
            out.printf("COMP\tok\t%d\t%d\t%d\t%d\t%d%n",
                    c.getGlyphIndex(), c.getFlags() & 0xFFFF,
                    c.getArgument1(), c.getArgument2(), c.getXTranslate());
        } catch (Throwable t) {
            out.printf("COMP\terr\t%s%n", t.getClass().getSimpleName());
        }
    }

    private static byte[] hex(String s) {
        if (s == null || s.isEmpty() || "-".equals(s)) {
            return new byte[0];
        }
        int n = s.length() / 2;
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) {
            b[i] = (byte) Integer.parseInt(s.substring(2 * i, 2 * i + 2), 16);
        }
        return b;
    }
}
