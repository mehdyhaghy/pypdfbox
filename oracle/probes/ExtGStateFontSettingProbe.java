import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.graphics.PDFontSetting;
import org.apache.pdfbox.pdmodel.graphics.blend.BlendMode;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;

/**
 * Live oracle probe for the typed /Font accessor of PDExtendedGraphicsState
 * (getFontSetting -> PDFontSetting) plus the BlendMode-as-array fallback that
 * the scalar ExtGStateProbe does not exercise.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ExtGStateFontSettingProbe <mode>
 *
 *   font    -> /Font [<<Type1 Helvetica>> 12.0]; reports getFontSetting()
 *              non-null, getFontSize(), and the resolved PDFont's getName()
 *              + getSubType().
 *   nofont  -> only /Type present; getFontSetting() must be null.
 *   bmarray -> /BM [/Bogus /Multiply]; getBlendMode() must skip the
 *              unrecognised first entry and resolve to the first recognised
 *              name (Multiply), exercising BlendMode.getInstance(COSArray).
 *   bmarraynone -> /BM [/Bogus /AlsoBogus]; no recognised entry -> Normal.
 *
 * Output (UTF-8): one "key=value" line per facet, fixed order.
 */
public final class ExtGStateFontSettingProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        COSDictionary dict = build(mode);
        PDExtendedGraphicsState gs = new PDExtendedGraphicsState(dict);

        PDFontSetting fs = gs.getFontSetting();
        out.println("fontSettingNull=" + (fs == null));
        if (fs == null) {
            out.println("fontSize=null");
            out.println("fontNull=true");
            out.println("fontName=null");
            out.println("fontSubType=null");
        } else {
            out.println("fontSize=" + fmt(fs.getFontSize()));
            PDFont f = fs.getFont();
            out.println("fontNull=" + (f == null));
            out.println("fontName=" + (f == null ? "null" : f.getName()));
            out.println("fontSubType=" + (f == null ? "null" : f.getSubType()));
        }
        out.println("blendMode=" + gs.getBlendMode().getCOSName().getName());
    }

    private static COSDictionary build(String mode) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.getPDFName("ExtGState"));
        if ("font".equals(mode)) {
            COSDictionary fd = new COSDictionary();
            fd.setItem(COSName.TYPE, COSName.getPDFName("Font"));
            fd.setItem(COSName.getPDFName("Subtype"), COSName.getPDFName("Type1"));
            fd.setItem(COSName.getPDFName("BaseFont"), COSName.getPDFName("Helvetica"));
            COSArray font = new COSArray();
            font.add(fd);
            font.add(new COSFloat(12.0f));
            d.setItem(COSName.getPDFName("Font"), font);
        } else if ("bmarray".equals(mode)) {
            COSArray bm = new COSArray();
            bm.add(COSName.getPDFName("Bogus"));
            bm.add(COSName.getPDFName("Multiply"));
            d.setItem(COSName.getPDFName("BM"), bm);
        } else if ("bmarraynone".equals(mode)) {
            COSArray bm = new COSArray();
            bm.add(COSName.getPDFName("Bogus"));
            bm.add(COSName.getPDFName("AlsoBogus"));
            d.setItem(COSName.getPDFName("BM"), bm);
        }
        // "nofont" leaves the dictionary at /Type only.
        return d;
    }

    private static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Long.toString((long) v);
        }
        String s = String.format(Locale.ROOT, "%.6f", v);
        int end = s.length();
        while (end > 0 && s.charAt(end - 1) == '0') {
            end--;
        }
        if (end > 0 && s.charAt(end - 1) == '.') {
            end--;
        }
        return s.substring(0, end);
    }
}
