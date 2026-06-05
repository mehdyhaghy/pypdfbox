import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;
import java.util.TreeSet;
import org.apache.fontbox.pfb.PfbParser;
import org.apache.fontbox.type1.Type1Font;
import org.apache.fontbox.util.BoundingBox;

/**
 * Live oracle probe for the *direct* FontBox Type 1 parse surface — i.e.
 * {@link Type1Font#createWithPFB(byte[])} on a raw .pfb file, with no PDF
 * involved. Dumps the parsed font's name, font matrix, font bounding box,
 * encoding class identity, /Subrs count, and charstring names. Also splits
 * the .pfb with {@link PfbParser} and re-parses via
 * {@link Type1Font#createWithSegments(byte[], byte[])} to assert the two
 * construction paths produce an equivalent parsed surface.
 *
 * Usage: java -cp pdfbox-app.jar:build Type1PfbDirectProbe font.pfb
 *
 * Canonical line format (UTF-8, deterministic ordering):
 *   NAME &lt;name&gt;
 *   FONTNAME &lt;fontName&gt;
 *   MATRIX a b c d e f
 *   BBOX llx lly urx ury
 *   ENCCLASS &lt;simpleClassName-of-getEncoding&gt;
 *   SUBRS &lt;count&gt;
 *   NGLYPHS &lt;count&gt;
 *   GLYPH &lt;name&gt;                  (one per charstring name, sorted)
 *   SEGEQ &lt;true|false&gt;            createWithPFB vs createWithSegments parity
 */
public final class Type1PfbDirectProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] pfb = Files.readAllBytes(Paths.get(args[0]));

        Type1Font t1 = Type1Font.createWithPFB(pfb);

        out.println("NAME " + t1.getName());
        out.println("FONTNAME " + t1.getFontName());

        StringBuilder mb = new StringBuilder("MATRIX");
        for (Number n : t1.getFontMatrix()) {
            mb.append(' ').append(canonNumber(n.doubleValue()));
        }
        out.println(mb.toString());

        BoundingBox bbox = t1.getFontBBox();
        out.println("BBOX "
                + canonNumber(bbox.getLowerLeftX()) + " "
                + canonNumber(bbox.getLowerLeftY()) + " "
                + canonNumber(bbox.getUpperRightX()) + " "
                + canonNumber(bbox.getUpperRightY()));

        org.apache.fontbox.encoding.Encoding enc = t1.getEncoding();
        out.println("ENCCLASS " + (enc == null ? "null" : enc.getClass().getSimpleName()));

        out.println("SUBRS " + t1.getSubrsArray().size());

        TreeSet<String> names = new TreeSet<String>(t1.getCharStringsDict().keySet());
        out.println("NGLYPHS " + names.size());
        for (String gn : names) {
            out.println("GLYPH " + gn);
        }

        // createWithPFB vs createWithSegments parity
        PfbParser parser = new PfbParser(pfb);
        Type1Font t2 = Type1Font.createWithSegments(parser.getSegment1(), parser.getSegment2());
        boolean eq = t1.getName().equals(t2.getName())
                && t1.getFontMatrix().equals(t2.getFontMatrix())
                && t1.getSubrsArray().size() == t2.getSubrsArray().size()
                && t1.getCharStringsDict().keySet().equals(t2.getCharStringsDict().keySet());
        out.println("SEGEQ " + eq);
    }

    private static String canonNumber(double v) {
        if (v == Math.rint(v) && !Double.isInfinite(v)) {
            return Long.toString((long) v);
        }
        return Double.toString(v);
    }
}
