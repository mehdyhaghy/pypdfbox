import java.io.OutputStream;
import java.util.Locale;

import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDType3CharProc;
import org.apache.pdfbox.pdmodel.font.PDType3Font;

/**
 * Live oracle probe for the {@code PDType3CharProc} glyph-metric parsing edge
 * cases (synthetic char-proc streams; no PDF on disk needed).
 *
 * For each labelled char-proc body it emits, tab-separated:
 *
 *   <label> WIDTH=<%.6f | EXC:<class>> BBOX=<NULL | llx,lly,urx,ury | EXC:<class>>
 *
 * {@code getWidth()} reads the {@code wx} operand of the leading {@code d0} /
 * {@code d1} operator (throwing {@code IOException} on a missing / non-d0/d1
 * first operator or a non-numeric first operand); {@code getGlyphBBox()}
 * returns the {@code d1} bounding box, but only when the leading operator is
 * {@code d1} with EXACTLY six operands (upstream {@code arguments.size() == 6}).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Type3CharProcEdgeProbe
 */
public final class Type3CharProcEdgeProbe {

    private static PDType3Font font;

    private static COSStream mk(String body) throws Exception {
        COSStream s = new COSStream();
        try (OutputStream os = s.createOutputStream()) {
            os.write(body.getBytes("ISO-8859-1"));
        }
        return s;
    }

    private static void probe(String label, String body) throws Exception {
        PDType3CharProc p = new PDType3CharProc(font, mk(body));
        String w;
        try {
            w = String.format(Locale.US, "%.6f", p.getWidth());
        } catch (Exception e) {
            w = "EXC:" + e.getClass().getSimpleName();
        }
        String bb;
        try {
            PDRectangle r = p.getGlyphBBox();
            if (r == null) {
                bb = "NULL";
            } else {
                bb = String.format(Locale.US, "%.4f,%.4f,%.4f,%.4f",
                        r.getLowerLeftX(), r.getLowerLeftY(),
                        r.getUpperRightX(), r.getUpperRightY());
            }
        } catch (Exception e) {
            bb = "EXC:" + e.getClass().getSimpleName();
        }
        System.out.println(label + "\tWIDTH=" + w + "\tBBOX=" + bb);
    }

    public static void main(String[] args) throws Exception {
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, COSName.getPDFName("Font"));
        fd.setItem(COSName.SUBTYPE, COSName.getPDFName("Type3"));
        font = new PDType3Font(fd);

        probe("d1_normal", "750 0 0 0 500 700 d1\n0 0 500 700 re f");
        probe("d0_normal", "640 0 d0\n0 0 500 700 re f");
        probe("d1_leading_comment", "% comment line\n750 0 0 0 500 700 d1\nf");
        probe("d1_leading_ws", "   \n\t 750 0 0 0 500 700 d1\nf");
        probe("d1_5args", "750 0 0 0 500 d1\nf");
        probe("d1_7args", "750 0 0 0 500 700 900 d1\nf");
        probe("d1_4args", "0 0 500 700 d1\nf");
        probe("d0_only_wx", "640 d0\nf");
        probe("d1_realnums", "750.5 0 10.25 20.5 510.75 720.0 d1\nf");
        probe("d1_negative", "750 0 -10 -20 500 700 d1\nf");
        probe("d1_then_garbage", "750 0 0 0 500 700 d1 extra 99 d0\nf");
    }
}
