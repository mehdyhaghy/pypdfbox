import java.io.File;
import java.io.InputStream;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType3CharProc;
import org.apache.pdfbox.pdmodel.font.PDType3Font;

/**
 * Live oracle probe for PDType3Font structural accessors NOT covered by
 * Type3FontProbe (which already pins getFontMatrix / getEncoding name map /
 * getWidth / getCharProcs key set / getFontBBox / getDisplacement).
 *
 * This probe pins the per-code getCharProc(int) resolution and the shared
 * getResources() surface:
 *
 *   CHARPROC <code> <present|null> [<wx> <bboxOrNONE> <decodedLen>]
 *       - getCharProc(code): resolves code through /Encoding /Differences to a
 *         glyph name, then to the /CharProcs stream. Emits "null" when the
 *         code maps to .notdef / an unlisted code / a missing glyph stream.
 *         For a present proc emits the d0/d1 advance (getWidth), the glyph
 *         bbox from a leading d1 (getGlyphBBox, or NONE for d0), and the
 *         decoded content-stream byte length (proves stream identity).
 *   FONTRES  <count> <name0> <name1> ...
 *       - font.getResources().getFontNames(), sorted (shared by all procs).
 *   PROCRES  <glyphName> <count> <name0> ...
 *       - charProc.getResources().getFontNames() per present glyph, sorted —
 *         proves the char proc falls back to the font's shared /Resources.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Type3CharProcAccessorProbe in.pdf
 *
 * Numbers use a fixed Locale.US 6-decimal layout so the Python side reproduces
 * them byte-for-byte.
 */
public final class Type3CharProcAccessorProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res != null) {
                    for (COSName name : res.getFontNames()) {
                        PDFont font = res.getFont(name);
                        if (font instanceof PDType3Font) {
                            emitFont(out, pageIndex, name, (PDType3Font) font);
                        }
                    }
                }
                pageIndex++;
            }
        }
    }

    private static void emitFont(
            PrintStream out, int pageIndex, COSName name, PDType3Font font)
            throws Exception {
        out.println("FONT\t" + pageIndex + "\t" + name.getName() + "\t" + font.getName());

        int first = font.getCOSObject().getInt(COSName.FIRST_CHAR, -1);
        int last = font.getCOSObject().getInt(COSName.LAST_CHAR, -1);

        for (int code = 0; code <= 255; code++) {
            PDType3CharProc proc = font.getCharProc(code);
            if (proc == null) {
                // Only emit the in-window codes plus a couple of probes outside
                // it to keep output bounded; null lines for the whole 0..255
                // range would dominate the diff. Emit nulls only inside window.
                if (first >= 0 && code >= first && code <= last) {
                    out.println("CHARPROC\t" + code + "\tnull");
                }
                continue;
            }
            float wx = proc.getWidth();
            PDRectangle gb = proc.getGlyphBBox();
            String bbox = (gb == null)
                ? "NONE"
                : fmt(gb.getLowerLeftX()) + " " + fmt(gb.getLowerLeftY())
                  + " " + fmt(gb.getUpperRightX()) + " " + fmt(gb.getUpperRightY());
            int len = decodedLength(proc);
            out.println(
                "CHARPROC\t" + code + "\tpresent\t" + fmt(wx) + "\t" + bbox + "\t" + len);

            // Per-proc resources (shared with the font in the well-formed case).
            out.println("PROCRES\t" + code + "\t" + fontNames(proc.getResources()));
        }

        out.println("FONTRES\t" + fontNames(font.getResources()));
    }

    private static String fontNames(PDResources res) {
        if (res == null) {
            return "null";
        }
        List<String> names = new ArrayList<>();
        for (COSName n : res.getFontNames()) {
            names.add(n.getName());
        }
        Collections.sort(names);
        StringBuilder sb = new StringBuilder();
        sb.append(names.size());
        for (String n : names) {
            sb.append('\t').append(n);
        }
        return sb.toString();
    }

    private static int decodedLength(PDType3CharProc proc) throws Exception {
        int total = 0;
        try (InputStream in = proc.getContents()) {
            byte[] buf = new byte[4096];
            int r;
            while ((r = in.read(buf)) != -1) {
                total += r;
            }
        }
        return total;
    }

    private static String fmt(float v) {
        return String.format(Locale.US, "%.6f", v);
    }
}
