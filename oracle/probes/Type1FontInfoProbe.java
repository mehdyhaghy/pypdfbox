import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import org.apache.fontbox.type1.Type1Font;
import org.apache.fontbox.util.BoundingBox;

/**
 * Live oracle probe: load a Type 1 (.pfb) program directly via
 * {@link Type1Font#createWithPFB(byte[])} and emit every cleartext
 * /FontInfo and top-level metadata accessor as canonical KEY VALUE lines.
 *
 * This is the /FontInfo metadata facet — distinct from Type1FontProbe which
 * exercises name / matrix / encoding / per-glyph widths via a PDF.
 *
 * Usage: java -cp pdfbox-app.jar:build Type1FontInfoProbe font.pfb
 *
 * Canonical line format (UTF-8, deterministic ordering):
 *   FONTNAME &lt;str&gt;
 *   FULLNAME &lt;str&gt;
 *   FAMILYNAME &lt;str&gt;
 *   WEIGHT &lt;str&gt;
 *   VERSION &lt;str&gt;
 *   NOTICE &lt;str&gt;
 *   ITALICANGLE &lt;num&gt;
 *   ISFIXEDPITCH &lt;true|false&gt;
 *   UNDERLINEPOSITION &lt;num&gt;
 *   UNDERLINETHICKNESS &lt;num&gt;
 *   PAINTTYPE &lt;int&gt;
 *   FONTTYPE &lt;int&gt;
 *   UNIQUEID &lt;int&gt;
 *   STROKEWIDTH &lt;num&gt;
 *   FONTBBOX &lt;llx&gt; &lt;lly&gt; &lt;urx&gt; &lt;ury&gt;   (or "FONTBBOX null")
 */
public final class Type1FontInfoProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] pfb = Files.readAllBytes(new File(args[0]).toPath());
        Type1Font t1 = Type1Font.createWithPFB(pfb);

        out.println("FONTNAME " + t1.getFontName());
        out.println("FULLNAME " + t1.getFullName());
        out.println("FAMILYNAME " + t1.getFamilyName());
        out.println("WEIGHT " + t1.getWeight());
        out.println("VERSION " + t1.getVersion());
        out.println("NOTICE " + t1.getNotice());
        out.println("ITALICANGLE " + canonNumber(t1.getItalicAngle()));
        out.println("ISFIXEDPITCH " + t1.isFixedPitch());
        out.println("UNDERLINEPOSITION " + canonNumber(t1.getUnderlinePosition()));
        out.println("UNDERLINETHICKNESS " + canonNumber(t1.getUnderlineThickness()));
        out.println("PAINTTYPE " + t1.getPaintType());
        out.println("FONTTYPE " + t1.getFontType());
        out.println("UNIQUEID " + t1.getUniqueID());
        out.println("STROKEWIDTH " + canonNumber(t1.getStrokeWidth()));

        BoundingBox bbox = t1.getFontBBox();
        if (bbox == null) {
            out.println("FONTBBOX null");
        } else {
            out.println(
                "FONTBBOX "
                    + canonNumber(bbox.getLowerLeftX())
                    + " "
                    + canonNumber(bbox.getLowerLeftY())
                    + " "
                    + canonNumber(bbox.getUpperRightX())
                    + " "
                    + canonNumber(bbox.getUpperRightY()));
        }
    }

    // Canonicalise a numeric value so Java and Python render it identically:
    // integral values as plain integers, otherwise a trimmed decimal.
    private static String canonNumber(double v) {
        if (v == Math.rint(v) && !Double.isInfinite(v)) {
            return Long.toString((long) v);
        }
        return Double.toString(v);
    }
}
