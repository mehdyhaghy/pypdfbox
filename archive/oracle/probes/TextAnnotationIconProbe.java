import java.io.File;
import java.io.PrintStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationText;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;

/**
 * Live oracle probe for TEXT (sticky-note) annotation appearance generation —
 * the OPERAND-LEVEL /AP /N content (not just operator keywords).
 *
 * Drives PDTextAppearanceHandler.generateNormalAppearance() (invoked via
 * PDAnnotationText.constructAppearances(doc)) for each of the 16 standard icon
 * names — Note/Comment/Key/Help/NewParagraph/Paragraph/Insert/Circle/Cross/
 * Star/Check/RightArrow/RightPointer/UpArrow/UpLeftArrow/CrossHairs — and emits
 * the FULL token stream, every operand number/name canonicalised to 3 decimals.
 *
 * Also emits, for each annotation, the /AP /N resources /ExtGState entries
 * (CA/ca/BM) so the translucent-white halo emission is pinned operand-level.
 *
 * Two modes:
 *
 *   java ... TextAnnotationIconProbe write out.pdf
 *   java ... TextAnnotationIconProbe read out.pdf
 */
public final class TextAnnotationIconProbe {
    private static final String[] NAMES = {
        PDAnnotationText.NAME_NOTE,
        PDAnnotationText.NAME_COMMENT,
        PDAnnotationText.NAME_KEY,
        PDAnnotationText.NAME_HELP,
        PDAnnotationText.NAME_NEW_PARAGRAPH,
        PDAnnotationText.NAME_PARAGRAPH,
        PDAnnotationText.NAME_INSERT,
        PDAnnotationText.NAME_CIRCLE,
        PDAnnotationText.NAME_CROSS,
        PDAnnotationText.NAME_STAR,
        PDAnnotationText.NAME_CHECK,
        PDAnnotationText.NAME_RIGHT_ARROW,
        PDAnnotationText.NAME_RIGHT_POINTER,
        PDAnnotationText.NAME_UP_ARROW,
        PDAnnotationText.NAME_UP_LEFT_ARROW,
        PDAnnotationText.NAME_CROSS_HAIRS,
    };

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        File file = new File(args[1]);
        if ("write".equals(mode)) {
            write(file);
        } else {
            read(file);
        }
    }

    private static void write(File file) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.A4);
            doc.addPage(page);
            float y = 750;
            // 1) every standard icon name, no colour.
            for (String name : NAMES) {
                PDAnnotationText ann = new PDAnnotationText();
                ann.setRectangle(new PDRectangle(50, y, 30, 30));
                ann.setName(name);
                ann.constructAppearances(doc);
                page.getAnnotations().add(ann);
                y -= 45;
            }
            // 2) colour set on two icons (Note + Insert) — exercises the
            //    setNonStrokingColor(PDColor) ``/DeviceRGB cs r g b sc`` path.
            float[] red = {1f, 0f, 0f};
            float[] green = {0f, 1f, 0f};
            for (Object[] spec : new Object[][] {
                {PDAnnotationText.NAME_NOTE, red},
                {PDAnnotationText.NAME_INSERT, green},
            }) {
                PDAnnotationText ann = new PDAnnotationText();
                ann.setRectangle(new PDRectangle(50, y, 30, 30));
                ann.setName((String) spec[0]);
                ann.setColor(new PDColor((float[]) spec[1], PDDeviceRGB.INSTANCE));
                ann.constructAppearances(doc);
                page.getAnnotations().add(ann);
                y -= 45;
            }
            // 3) /Name absent — getName() defaults to "Note".
            PDAnnotationText missing = new PDAnnotationText();
            missing.setRectangle(new PDRectangle(50, y, 30, 30));
            missing.constructAppearances(doc);
            page.getAnnotations().add(missing);
            y -= 45;
            // 4) unknown /Name — falls through the dispatch switch.
            PDAnnotationText unknown = new PDAnnotationText();
            unknown.setRectangle(new PDRectangle(50, y, 30, 30));
            unknown.setName("DefinitelyNotAStandardIcon");
            unknown.constructAppearances(doc);
            page.getAnnotations().add(unknown);
            doc.save(file);
        }
    }

    private static void read(File file) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(file)) {
            for (PDPage page : doc.getPages()) {
                for (PDAnnotation annot : page.getAnnotations()) {
                    emit(sb, annot);
                }
            }
        }
        out.print(sb);
    }

    private static void emit(StringBuilder sb, PDAnnotation annot) throws Exception {
        sb.append("ANNOT ").append(((PDAnnotationText) annot).getName()).append('\n');
        // Raw /Name (or __absent__) so the test can separate the missing-name
        // case (defaults to Note) from an explicit unknown name.
        COSBase rawName = annot.getCOSObject().getDictionaryObject(COSName.NAME);
        sb.append("RAWNAME ")
          .append(rawName instanceof COSName ? ((COSName) rawName).getName() : "__absent__")
          .append('\n');
        sb.append("RECT ").append(rectStr(annot.getRectangle())).append('\n');

        PDAppearanceStream stream = normalStream(annot);
        if (stream == null) {
            sb.append("NOAP\nEND\n");
            return;
        }
        sb.append("BBOX ").append(rectStr(stream.getBBox())).append('\n');

        // ExtGState halo pin: emit CA / ca / BM of each /ExtGState in resources.
        PDResources res = stream.getResources();
        if (res != null) {
            for (COSName n : res.getExtGStateNames()) {
                PDExtendedGraphicsState gs = res.getExtGState(n);
                sb.append("GS ")
                  .append(numOrNull(gs.getStrokingAlphaConstant())).append(' ')
                  .append(numOrNull(gs.getNonStrokingAlphaConstant())).append(' ')
                  .append(gs.getBlendMode() == null ? "null" : gs.getBlendMode().getClass().getSimpleName())
                  .append('\n');
            }
        }

        PDFStreamParser parser = new PDFStreamParser(stream);
        List<Object> tokens = parser.parse();
        for (Object tok : tokens) {
            sb.append("TOK ").append(canonToken(tok)).append('\n');
        }
        sb.append("END\n");
    }

    private static String numOrNull(Float f) {
        return f == null ? "null" : canon(f);
    }

    private static String canonToken(Object tok) {
        if (tok instanceof Operator) {
            return ((Operator) tok).getName();
        }
        if (tok instanceof COSNumber) {
            return canon(((COSNumber) tok).floatValue());
        }
        if (tok instanceof COSName) {
            return "/" + ((COSName) tok).getName();
        }
        if (tok instanceof COSBase) {
            return tok.getClass().getSimpleName();
        }
        return String.valueOf(tok);
    }

    private static String rectStr(PDRectangle r) {
        if (r == null) {
            return "none";
        }
        return canon(r.getLowerLeftX()) + ","
                + canon(r.getLowerLeftY()) + ","
                + canon(r.getUpperRightX()) + ","
                + canon(r.getUpperRightY());
    }

    private static String canon(double value) {
        BigDecimal bd = new BigDecimal(Double.toString(value))
                .setScale(3, RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if (s.equals("-0") || s.isEmpty()) {
            s = "0";
        }
        return s;
    }

    private static PDAppearanceStream normalStream(PDAnnotation annot) {
        PDAppearanceDictionary ap = annot.getAppearance();
        if (ap == null) {
            return null;
        }
        PDAppearanceEntry normal = ap.getNormalAppearance();
        if (normal == null || normal.isSubDictionary()) {
            return null;
        }
        return normal.getAppearanceStream();
    }
}
