import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.image.LosslessFactory;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for the {@code PDPageContentStream.drawImage} overloads:
 * the emitted content-stream tokens for each form
 * ({@code drawImage(image, x, y)}, {@code drawImage(image, x, y, w, h)},
 * {@code drawImage(image, Matrix)}) must be {@code q} / {@code cm <matrix>} /
 * {@code /Name Do} / {@code Q} with the correct CTM, plus a {@code /XObject}
 * registration in the page resources.
 *
 * <p>For each overload the probe builds a fresh one-page document, draws a
 * fixed 4x3 deterministic image with that overload, saves, re-parses the page
 * content with {@code PDFStreamParser} and emits a canonical token stream. It
 * then dumps the page's {@code /Resources /XObject} entry as
 * {@code RES:/<name>=Subtype:<sub> Width:<w> Height:<h>}.
 *
 * <p>The three blocks are separated by {@code ===<form>===} marker lines so the
 * Python differential test can split them and compare each overload's tokens +
 * resource registration independently.
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; DrawImageProbe out.pdf
 */
public final class DrawImageProbe {

    static PrintStream out;

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File tmp = new File(args[0]);

        // --- drawImage(image, x, y) ---
        out.println("===xy===");
        emitDraw(tmp, (cs, img) -> cs.drawImage(img, 10f, 20f));

        // --- drawImage(image, x, y, w, h) ---
        out.println("===xywh===");
        emitDraw(tmp, (cs, img) -> cs.drawImage(img, 30f, 40f, 100f, 50f));

        // --- drawImage(image, Matrix) ---
        out.println("===matrix===");
        emitDraw(tmp, (cs, img) -> {
            Matrix m = new Matrix(2f, 0.5f, 0.25f, 3f, 7f, 11f);
            cs.drawImage(img, m);
        });
    }

    interface DrawCall {
        void draw(PDPageContentStream cs, PDImageXObject img) throws Exception;
    }

    /** A deterministic 4x3 ARGB image with a fixed pixel pattern. */
    static BufferedImage fixedImage() {
        BufferedImage bi = new BufferedImage(4, 3, BufferedImage.TYPE_INT_ARGB);
        for (int y = 0; y < 3; y++) {
            for (int x = 0; x < 4; x++) {
                bi.setRGB(x, y, 0xFF000000 | (x * 40) << 16 | (y * 60) << 8 | 0x33);
            }
        }
        return bi;
    }

    static void emitDraw(File tmp, DrawCall call) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(0, 0, 300, 400));
            doc.addPage(page);
            PDImageXObject img = LosslessFactory.createFromImage(doc, fixedImage());
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                call.draw(cs, img);
            }
            doc.save(tmp);
        }
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(tmp)) {
            PDPage page = doc.getPage(0);
            PDFStreamParser parser = new PDFStreamParser(page);
            List<Object> tokens = parser.parse();
            for (Object tok : tokens) {
                emit(sb, tok);
            }
            // Resource /XObject registration.
            PDResources res = page.getResources();
            for (COSName name : res.getXObjectNames()) {
                COSBase raw = res.getCOSObject()
                        .getCOSDictionary(COSName.XOBJECT)
                        .getDictionaryObject(name);
                if (raw instanceof COSStream) {
                    COSStream s = (COSStream) raw;
                    sb.append("RES:/").append(name.getName())
                            .append("=Subtype:").append(s.getNameAsString(COSName.SUBTYPE))
                            .append(" Width:").append(s.getInt(COSName.WIDTH))
                            .append(" Height:").append(s.getInt(COSName.HEIGHT))
                            .append('\n');
                }
            }
        }
        out.print(sb);
    }

    private static void emit(StringBuilder sb, Object tok) {
        if (tok instanceof Operator) {
            sb.append("OP:").append(((Operator) tok).getName()).append('\n');
        } else if (tok instanceof COSBase) {
            emitBase(sb, (COSBase) tok);
        } else {
            sb.append("UNKNOWN:").append(tok.getClass().getName()).append('\n');
        }
    }

    private static void emitBase(StringBuilder sb, COSBase b) {
        if (b instanceof COSInteger) {
            sb.append("INT:").append(((COSInteger) b).longValue()).append('\n');
        } else if (b instanceof COSFloat) {
            sb.append("REAL:").append(canonFloat(((COSNumber) b).floatValue())).append('\n');
        } else if (b instanceof COSName) {
            sb.append("NAME:/").append(((COSName) b).getName()).append('\n');
        } else if (b instanceof COSArray) {
            COSArray arr = (COSArray) b;
            sb.append("ARRAY:").append(arr.size()).append('\n');
            for (int i = 0; i < arr.size(); i++) {
                emitBase(sb, arr.get(i));
            }
        } else if (b instanceof COSDictionary) {
            COSDictionary d = (COSDictionary) b;
            sb.append("DICT:").append(d.size()).append('\n');
            for (COSName key : d.keySet()) {
                sb.append("NAME:/").append(key.getName()).append('\n');
                emitBase(sb, d.getDictionaryObject(key));
            }
        } else {
            sb.append("COS:").append(b.getClass().getSimpleName()).append('\n');
        }
    }

    static String canonFloat(float f) {
        if (Float.isNaN(f)) {
            return "nan";
        }
        if (Float.isInfinite(f)) {
            return f > 0 ? "inf" : "-inf";
        }
        java.math.BigDecimal bd = new java.math.BigDecimal(Float.toString(f))
                .setScale(5, java.math.RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if (s.equals("-0")) {
            s = "0";
        }
        return s;
    }
}
