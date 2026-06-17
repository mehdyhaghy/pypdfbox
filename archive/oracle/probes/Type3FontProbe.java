import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType3Font;
import org.apache.pdfbox.pdmodel.font.encoding.Encoding;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.util.Vector;

/**
 * Live oracle probe for Type 3 fonts.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Type3FontProbe input.pdf
 *
 * For every PDType3Font found in page resources, emit canonical TAB-delimited
 * lines:
 *   FONT  <pageIndex> <resName> <fontName>
 *   MATRIX <a> <b> <c> <d> <e> <f>            (6 floats from getFontMatrix)
 *   ENC   <code> <glyphName>                  (code 0..255, glyphName or .notdef)
 *   WIDTH <code> <width>                      (code FirstChar..LastChar, getWidth(code))
 *   PROC  <glyphName>                          (each /CharProcs key, sorted)
 *   BBOX  <llx> <lly> <urx> <ury>             (font.getFontBBox(), or NONE)
 *   DISP  <code> <tx> <ty>                    (font.getDisplacement(code), in-range)
 * Then once for the whole page:
 *   TEXT  <extracted text for the page, one trailing block>
 *
 * Numbers formatted with a fixed Locale.US 6-decimal layout so the Python side
 * can reproduce them byte-for-byte.
 */
public final class Type3FontProbe {
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
            // Page text extraction (whole document, single block).
            PDFTextStripper stripper = new PDFTextStripper();
            out.print("TEXT\t");
            out.print(stripper.getText(doc));
        }
    }

    private static void emitFont(
            PrintStream out, int pageIndex, COSName name, PDType3Font font)
            throws Exception {
        String fontName = font.getName();
        out.println("FONT\t" + pageIndex + "\t" + name.getName() + "\t" + fontName);

        org.apache.pdfbox.util.Matrix mx = font.getFontMatrix();
        // PDF /FontMatrix [a b c d e f] -> 3x3 layout:
        // a=(0,0) b=(0,1) c=(1,0) d=(1,1) e=(2,0) f=(2,1).
        float[] m = {
            mx.getValue(0, 0), mx.getValue(0, 1),
            mx.getValue(1, 0), mx.getValue(1, 1),
            mx.getValue(2, 0), mx.getValue(2, 1),
        };
        StringBuilder mb = new StringBuilder("MATRIX");
        for (int i = 0; i < 6; i++) {
            mb.append('\t').append(fmt(m[i]));
        }
        out.println(mb.toString());

        Encoding enc = font.getEncoding();
        for (int code = 0; code <= 255; code++) {
            String glyph = (enc == null) ? ".notdef" : enc.getName(code);
            if (glyph == null) {
                glyph = ".notdef";
            }
            out.println("ENC\t" + code + "\t" + glyph);
        }

        int first = font.getCOSObject().getInt(COSName.FIRST_CHAR, -1);
        int last = font.getCOSObject().getInt(COSName.LAST_CHAR, -1);
        for (int code = first; code <= last && first >= 0; code++) {
            out.println("WIDTH\t" + code + "\t" + fmt(font.getWidth(code)));
        }

        if (font.getCharProcs() != null) {
            java.util.List<String> names = new java.util.ArrayList<>();
            for (COSName key : font.getCharProcs().keySet()) {
                names.add(key.getName());
            }
            java.util.Collections.sort(names);
            for (String n : names) {
                out.println("PROC\t" + n);
            }
        }

        PDRectangle bbox = font.getFontBBox();
        if (bbox == null) {
            out.println("BBOX\tNONE");
        } else {
            out.println(
                "BBOX\t"
                + fmt(bbox.getLowerLeftX()) + "\t"
                + fmt(bbox.getLowerLeftY()) + "\t"
                + fmt(bbox.getUpperRightX()) + "\t"
                + fmt(bbox.getUpperRightY())
            );
        }

        for (int code = first; code <= last && first >= 0; code++) {
            Vector disp = font.getDisplacement(code);
            out.println(
                "DISP\t" + code + "\t" + fmt(disp.getX()) + "\t" + fmt(disp.getY())
            );
        }
    }

    private static String fmt(float v) {
        return String.format(Locale.US, "%.6f", v);
    }
}
