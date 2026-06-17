import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquiggly;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationStrikeout;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;

/**
 * Live oracle probe for the STRIKEOUT and SQUIGGLY text-markup appearance
 * handlers, drilling DEEPER than TextMarkupProbe (which normalises away the
 * colour-set operator and all coordinates).
 *
 * Two modes:
 *
 *   java ... StrikeoutSquigglyProbe write out.pdf
 *       One StrikeOut and one Squiggly over a horizontal 200pt band, each given
 *       a /Rect, a single /QuadPoints quad and a /C RGB colour, then
 *       constructAppearances(doc) + save. PDFBox-AUTHORED reference.
 *
 *   java ... StrikeoutSquigglyProbe read out.pdf
 *       Re-open ANY StrikeOut/Squiggly PDF and emit, per annotation in /Annots
 *       order:
 *
 *           ANNOT <subtype>
 *           BBOX <x0>,<y0>,<x1>,<y1>          (or NOAP)
 *           COLOROP <CS|RG|SC|none>           the colour-set operator KEYWORD
 *           COLORCS <name|none>               colour-space name preceding a CS op
 *           STROKEY <canonFloat|none>         the constant y of the stroked line
 *                                             (StrikeOut: midline; none if the
 *                                             segment is not horizontal)
 *           OPS <space-separated keyword sequence>
 *           END
 *
 * The COLOROP / COLORCS pair is the load-bearing fact this probe adds over
 * TextMarkupProbe: upstream emits the typed-PDColor colour ("/DeviceRGB CS r g b
 * SC"), not the device-shorthand "RG". STROKEY proves the StrikeOut line is
 * drawn through the vertical MIDDLE of the quad.
 */
public final class StrikeoutSquigglyProbe {
    public static void main(String[] args) throws Exception {
        String mode = args[0];
        File file = new File(args[1]);
        if ("write".equals(mode)) {
            write(file);
        } else {
            read(file);
        }
    }

    private static PDColor rgb(float r, float g, float b) {
        return new PDColor(new float[] {r, g, b}, PDDeviceRGB.INSTANCE);
    }

    private static void write(File file) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(0, 0, 300, 400));
            doc.addPage(page);

            PDAnnotationStrikeout strikeout = new PDAnnotationStrikeout();
            strikeout.setRectangle(new PDRectangle(50, 195, 200, 25));
            strikeout.setQuadPoints(new float[] {50, 215, 250, 215, 50, 200, 250, 200});
            strikeout.setColor(rgb(0, 0, 1));
            strikeout.constructAppearances(doc);
            page.getAnnotations().add(strikeout);

            PDAnnotationSquiggly squiggly = new PDAnnotationSquiggly();
            squiggly.setRectangle(new PDRectangle(50, 145, 200, 25));
            squiggly.setQuadPoints(new float[] {50, 165, 250, 165, 50, 150, 250, 150});
            squiggly.setColor(rgb(0, 0.5f, 0));
            squiggly.constructAppearances(doc);
            page.getAnnotations().add(squiggly);

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
        String subtype = annot.getSubtype();
        sb.append("ANNOT ").append(subtype == null ? "?" : subtype).append('\n');

        PDAppearanceStream stream = normalStream(annot);
        if (stream == null) {
            sb.append("NOAP\nEND\n");
            return;
        }
        PDRectangle bbox = stream.getBBox();
        if (bbox == null) {
            sb.append("BBOX none\n");
        } else {
            sb.append("BBOX ")
              .append(canonFloat(bbox.getLowerLeftX())).append(',')
              .append(canonFloat(bbox.getLowerLeftY())).append(',')
              .append(canonFloat(bbox.getUpperRightX())).append(',')
              .append(canonFloat(bbox.getUpperRightY())).append('\n');
        }

        PDFStreamParser parser = new PDFStreamParser(stream);
        List<Object> tokens = parser.parse();

        // Walk operators, tracking the operand stack to recover colour-op,
        // colour-space name, and the constant y of the (first) stroked segment.
        java.util.List<Float> operands = new java.util.ArrayList<>();
        COSName lastName = null;
        String colorOp = "none";
        String colorCs = "none";
        String strokeY = "none";
        StringBuilder ops = new StringBuilder();
        Float moveY = null;
        Float lineY = null;

        for (Object tok : tokens) {
            if (tok instanceof COSNumber) {
                operands.add(((COSNumber) tok).floatValue());
            } else if (tok instanceof COSName) {
                lastName = (COSName) tok;
            } else if (tok instanceof Operator) {
                String name = ((Operator) tok).getName();
                if (ops.length() > 0) {
                    ops.append(' ');
                }
                ops.append(name);
                switch (name) {
                    case "CS":
                    case "RG":
                    case "G":
                    case "K":
                    case "SC":
                    case "SCN":
                        // Treat the first colour-set keyword as the colour op,
                        // but prefer CS (colour-space select) when present.
                        if ("CS".equals(name)) {
                            colorOp = "CS";
                            colorCs = lastName == null ? "none" : lastName.getName();
                        } else if ("RG".equals(name) || "G".equals(name)
                                || "K".equals(name)) {
                            if ("none".equals(colorOp)) {
                                colorOp = name;
                            }
                        }
                        break;
                    case "m":
                        if (operands.size() >= 2) {
                            moveY = operands.get(operands.size() - 1);
                        }
                        break;
                    case "l":
                        if (operands.size() >= 2) {
                            lineY = operands.get(operands.size() - 1);
                        }
                        // First horizontal segment fixes the strike y.
                        if ("none".equals(strokeY) && moveY != null && lineY != null
                                && Math.abs(moveY - lineY) < 1e-3) {
                            strokeY = canonFloat(moveY);
                        }
                        break;
                    default:
                        break;
                }
                operands.clear();
                lastName = null;
            }
        }

        sb.append("COLOROP ").append(colorOp).append('\n');
        sb.append("COLORCS ").append(colorCs).append('\n');
        sb.append("STROKEY ").append(strokeY).append('\n');
        sb.append("OPS ").append(ops).append('\n');
        sb.append("END\n");
    }

    static String canonFloat(float f) {
        java.math.BigDecimal bd = new java.math.BigDecimal(Float.toString(f))
                .setScale(3, java.math.RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if (s.equals("-0")) {
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
