import java.io.PrintStream;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.pdmodel.graphics.image.PDInlineImage;

/**
 * Live oracle probe: exercise {@code PDInlineImage}'s abbreviated-key
 * resolution precedence directly against Apache PDFBox.
 *
 * <p>Each {@code PDInlineImage} getter (getWidth / getHeight /
 * getBitsPerComponent / isStencil / getInterpolate) reads an inline-image
 * dictionary entry via the two-key overload {@code getInt(short, long,
 * default)} / {@code getBoolean(short, long, default)}. Those overloads
 * delegate to {@code getDictionaryObject(firstKey, secondKey)}, which (a)
 * resolves {@code COSNull} to {@code null} and (b) only falls back to the
 * second key when the first resolves to {@code null}. The precedence and the
 * COSNull-fallback behaviour are the subtle facets this probe pins.
 *
 * <p>No input file: all cases are constructed in-process so the expected
 * literals are deterministic.
 *
 * <p>Output (UTF-8): one {@code key=value} line per case.
 */
public final class InlineImageKeyResolveProbe {

    static PDInlineImage img(COSDictionary d) throws Exception {
        // empty data, null resources -- we only read scalar getters.
        return new PDInlineImage(d, new byte[0], null);
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();

        // Case 1: both /W and /Width present -> short form wins.
        COSDictionary d1 = new COSDictionary();
        d1.setItem(COSName.getPDFName("W"), COSInteger.get(7));
        d1.setItem(COSName.getPDFName("Width"), COSInteger.get(99));
        sb.append("both_W_Width=").append(img(d1).getWidth()).append('\n');

        // Case 2: only /Width present -> long form fallback.
        COSDictionary d2 = new COSDictionary();
        d2.setItem(COSName.getPDFName("Width"), COSInteger.get(42));
        sb.append("only_Width=").append(img(d2).getWidth()).append('\n');

        // Case 3: /W = COSNull, /Width = 13 -> short resolves null, fall back to long.
        COSDictionary d3 = new COSDictionary();
        d3.setItem(COSName.getPDFName("W"), COSNull.NULL);
        d3.setItem(COSName.getPDFName("Width"), COSInteger.get(13));
        sb.append("Wnull_Width13=").append(img(d3).getWidth()).append('\n');

        // Case 4: /W = COSNull only -> resolves null, no long, default -1.
        COSDictionary d4 = new COSDictionary();
        d4.setItem(COSName.getPDFName("W"), COSNull.NULL);
        sb.append("Wnull_only=").append(img(d4).getWidth()).append('\n');

        // Case 5: /H = COSName (non-number), /Height = 21 -> short resolves
        // non-null but not a COSNumber -> getInt returns default (NOT long fallback).
        COSDictionary d5 = new COSDictionary();
        d5.setItem(COSName.getPDFName("H"), COSName.getPDFName("Foo"));
        d5.setItem(COSName.getPDFName("Height"), COSInteger.get(21));
        sb.append("Hname_Height21=").append(img(d5).getHeight()).append('\n');

        // Case 6: /BPC null, /BitsPerComponent 4 -> fall back to long.
        COSDictionary d6 = new COSDictionary();
        d6.setItem(COSName.getPDFName("BPC"), COSNull.NULL);
        d6.setItem(COSName.getPDFName("BitsPerComponent"), COSInteger.get(4));
        sb.append("BPCnull_BPCfull4=").append(img(d6).getBitsPerComponent()).append('\n');

        // Case 7: boolean two-key -- /IM null, /ImageMask true -> fall back to long.
        COSDictionary d7 = new COSDictionary();
        d7.setItem(COSName.getPDFName("IM"), COSNull.NULL);
        d7.setItem(COSName.getPDFName("ImageMask"), COSBoolean.TRUE);
        sb.append("IMnull_ImageMaskTrue=").append(img(d7).isStencil()).append('\n');

        // Case 8: /IM false explicitly, /ImageMask true -> short wins (false).
        COSDictionary d8 = new COSDictionary();
        d8.setItem(COSName.getPDFName("IM"), COSBoolean.FALSE);
        d8.setItem(COSName.getPDFName("ImageMask"), COSBoolean.TRUE);
        sb.append("IMfalse_ImageMaskTrue=").append(img(d8).isStencil()).append('\n');

        // Case 9: /I (interpolate) null, /Interpolate true -> fall back to long.
        COSDictionary d9 = new COSDictionary();
        d9.setItem(COSName.getPDFName("I"), COSNull.NULL);
        d9.setItem(COSName.getPDFName("Interpolate"), COSBoolean.TRUE);
        sb.append("Inull_InterpolateTrue=").append(img(d9).getInterpolate()).append('\n');

        out.print(sb);
    }
}
