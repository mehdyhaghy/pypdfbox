import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;

/**
 * Live oracle probe: exercises the caching + type-leniency edges of
 * PDFontDescriptor that FontDescFlagsProbe (wave 1468) does not cover:
 *   - getCapHeight()/getXHeight() cache the abs() of the dict value on first
 *     read into an instance field; setCapHeight/setXHeight overwrite that
 *     cache with the *raw* (possibly negative) value.
 *   - getFlags() caches the dict int on first read; setFlags overwrites it.
 *   - type leniency: /Flags as a COSString, /CapHeight as a COSInteger,
 *     /FontFamily as a COSName (getString tolerates? -> no), /FontStretch as
 *     a COSString (getNameAsString tolerates? -> yes), /CharSet as COSName.
 *   - getFontBoundingBox() with a malformed 3-entry array.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FontDescCacheLenientProbe <case>
 * Output: one or more "KEY\tvalue" lines (UTF-8, stdout).
 */
public final class FontDescCacheLenientProbe {
    static PrintStream out;

    public static void main(String[] args) {
        out = new PrintStream(System.out, true, java.nio.charset.StandardCharsets.UTF_8);
        String c = args[0];
        switch (c) {
            case "capheight_setraw_after_read": capHeightSetRawAfterRead(); break;
            case "xheight_setraw_after_read": xHeightSetRawAfterRead(); break;
            case "capheight_negative_first_read": capHeightNegativeFirstRead(); break;
            case "flags_cache_after_directmutate": flagsCacheAfterDirectMutate(); break;
            case "flags_as_string": flagsAsString(); break;
            case "capheight_as_integer": capHeightAsInteger(); break;
            case "fontfamily_as_name": fontFamilyAsName(); break;
            case "fontfamily_as_string": fontFamilyAsString(); break;
            case "fontstretch_as_string": fontStretchAsString(); break;
            case "charset_as_name": charsetAsName(); break;
            case "charset_as_string": charsetAsString(); break;
            case "bbox_three_entries": bboxThreeEntries(); break;
            case "bbox_missing": bboxMissing(); break;
            case "fontname_as_string": fontNameAsString(); break;
            case "setbbox_null_removes": setBboxNullRemoves(); break;
            default: out.println("ERR\tunknown case " + c);
        }
    }

    private static String fmt(float v) {
        if (v == 0.0f) v = 0.0f;
        return String.format(Locale.ROOT, "%.4f", v);
    }

    private static PDFontDescriptor fresh() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        return new PDFontDescriptor(d);
    }

    static void capHeightSetRawAfterRead() {
        COSDictionary d = new COSDictionary();
        d.setFloat(COSName.CAP_HEIGHT, 662.0f);
        PDFontDescriptor fd = new PDFontDescriptor(d);
        out.println("read1\t" + fmt(fd.getCapHeight()));   // caches abs -> 662
        fd.setCapHeight(-100.0f);                            // stores raw -100 in cache
        out.println("read2\t" + fmt(fd.getCapHeight()));    // cached raw -100?
        out.println("dict\t" + fmt(d.getFloat(COSName.CAP_HEIGHT, 0)));
    }

    static void xHeightSetRawAfterRead() {
        COSDictionary d = new COSDictionary();
        d.setFloat(COSName.XHEIGHT, 450.0f);
        PDFontDescriptor fd = new PDFontDescriptor(d);
        out.println("read1\t" + fmt(fd.getXHeight()));
        fd.setXHeight(-50.0f);
        out.println("read2\t" + fmt(fd.getXHeight()));
        out.println("dict\t" + fmt(d.getFloat(COSName.XHEIGHT, 0)));
    }

    static void capHeightNegativeFirstRead() {
        COSDictionary d = new COSDictionary();
        d.setFloat(COSName.CAP_HEIGHT, -662.0f);
        PDFontDescriptor fd = new PDFontDescriptor(d);
        out.println("read\t" + fmt(fd.getCapHeight()));     // abs -> 662
    }

    static void flagsCacheAfterDirectMutate() {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FLAGS, 4);
        PDFontDescriptor fd = new PDFontDescriptor(d);
        out.println("read1\t" + fd.getFlags());             // caches 4
        d.setInt(COSName.FLAGS, 64);                        // mutate dict directly
        out.println("read2\t" + fd.getFlags());             // stale cache -> 4?
        out.println("symbolic\t" + (fd.isSymbolic() ? 1 : 0));
        out.println("italic\t" + (fd.isItalic() ? 1 : 0));
    }

    static void flagsAsString() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.FLAGS, new COSString("64"));
        PDFontDescriptor fd = new PDFontDescriptor(d);
        out.println("flags\t" + fd.getFlags());
        out.println("italic\t" + (fd.isItalic() ? 1 : 0));
    }

    static void capHeightAsInteger() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.CAP_HEIGHT, COSInteger.get(662));
        PDFontDescriptor fd = new PDFontDescriptor(d);
        out.println("capHeight\t" + fmt(fd.getCapHeight()));
    }

    static void fontFamilyAsName() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.FONT_FAMILY, COSName.getPDFName("Times"));
        PDFontDescriptor fd = new PDFontDescriptor(d);
        String v = fd.getFontFamily();
        out.println("fontFamily\t" + (v == null ? "<null>" : v));
    }

    static void fontFamilyAsString() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.FONT_FAMILY, new COSString("Times"));
        PDFontDescriptor fd = new PDFontDescriptor(d);
        String v = fd.getFontFamily();
        out.println("fontFamily\t" + (v == null ? "<null>" : v));
    }

    static void fontStretchAsString() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.FONT_STRETCH, new COSString("Condensed"));
        PDFontDescriptor fd = new PDFontDescriptor(d);
        String v = fd.getFontStretch();
        out.println("fontStretch\t" + (v == null ? "<null>" : v));
    }

    static void charsetAsName() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.CHAR_SET, COSName.getPDFName("StandardEncoding"));
        PDFontDescriptor fd = new PDFontDescriptor(d);
        String v = fd.getCharSet();
        out.println("charSet\t" + (v == null ? "<null>" : v));
    }

    static void charsetAsString() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.CHAR_SET, new COSString("/a/b/c"));
        PDFontDescriptor fd = new PDFontDescriptor(d);
        String v = fd.getCharSet();
        out.println("charSet\t" + (v == null ? "<null>" : v));
    }

    static void fontNameAsString() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.FONT_NAME, new COSString("ABCDEF+Helvetica"));
        PDFontDescriptor fd = new PDFontDescriptor(d);
        String v = fd.getFontName();
        out.println("fontName\t" + (v == null ? "<null>" : v));
    }

    static void bboxThreeEntries() {
        COSDictionary d = new COSDictionary();
        COSArray arr = new COSArray();
        arr.add(COSInteger.get(0));
        arr.add(COSInteger.get(-200));
        arr.add(COSInteger.get(1000));
        d.setItem(COSName.FONT_BBOX, arr);
        PDFontDescriptor fd = new PDFontDescriptor(d);
        try {
            PDRectangle r = fd.getFontBoundingBox();
            if (r == null) {
                out.println("bbox\t<null>");
            } else {
                out.println("bbox\t" + fmt(r.getLowerLeftX()) + "," + fmt(r.getLowerLeftY())
                        + "," + fmt(r.getUpperRightX()) + "," + fmt(r.getUpperRightY()));
            }
        } catch (Exception e) {
            out.println("bbox\tEXC:" + e.getClass().getSimpleName());
        }
    }

    static void bboxMissing() {
        PDFontDescriptor fd = fresh();
        PDRectangle r = fd.getFontBoundingBox();
        out.println("bbox\t" + (r == null ? "<null>" : "notnull"));
    }

    static void setBboxNullRemoves() {
        PDFontDescriptor fd = fresh();
        PDRectangle r = new PDRectangle(0, -200, 1000, 900);
        fd.setFontBoundingBox(r);
        out.println("present1\t" + (fd.getCOSObject().containsKey(COSName.FONT_BBOX) ? 1 : 0));
        fd.setFontBoundingBox(null);
        out.println("present2\t" + (fd.getCOSObject().containsKey(COSName.FONT_BBOX) ? 1 : 0));
    }
}
