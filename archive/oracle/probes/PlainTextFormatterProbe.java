import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDAppearanceContentStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.pdmodel.interactive.annotation.layout.AppearanceStyle;
import org.apache.pdfbox.pdmodel.interactive.annotation.layout.PlainText;
import org.apache.pdfbox.pdmodel.interactive.annotation.layout.PlainTextFormatter;

/**
 * Live oracle probe for the ported PlainTextFormatter word-wrap path.
 *
 * Drives org.apache.pdfbox.pdmodel.interactive.annotation.layout.PlainTextFormatter
 * directly (the same class the FreeText appearance handler routes /Contents
 * through) and fingerprints the emitted content-stream operator tokens, so the
 * Python port can be compared op-for-op including operands.
 *
 * Usage:
 *   java ... PlainTextFormatterProbe <width> <fontSize> <align> <wrap> <text>
 *
 *   width     formatter width (clip width)
 *   fontSize  font size
 *   align     one of: left center right justify
 *   wrap      one of: wrap nowrap  (wrapLines true/false)
 *   text      the content string ('\n' in the argument is treated as a hard
 *             line break, matching how the Python harness passes it)
 *
 * Output: one "TOK <op> <operand>..." line per operator token in the order
 * emitted, with canonical 3-dp floats — identical rendering to the other
 * FreeText probes.
 */
public final class PlainTextFormatterProbe {
    public static void main(String[] args) throws Exception {
        float width = Float.parseFloat(args[0]);
        float fontSize = Float.parseFloat(args[1]);
        String align = args[2];
        boolean wrap = !"nowrap".equals(args[3]);
        String text = args[4].replace("\\n", "\n");

        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();

        try (PDDocument doc = new PDDocument()) {
            PDFont font = new PDType1Font(Standard14Fonts.FontName.HELVETICA);
            PDAppearanceStream appearanceStream = new PDAppearanceStream(doc);
            appearanceStream.setResources(
                    new org.apache.pdfbox.pdmodel.PDResources());

            try (PDAppearanceContentStream cs =
                    new PDAppearanceContentStream(appearanceStream)) {
                cs.beginText();
                cs.setFont(font, fontSize);

                AppearanceStyle appearanceStyle = new AppearanceStyle();
                appearanceStyle.setFont(font);
                appearanceStyle.setFontSize(fontSize);

                PlainTextFormatter.Builder builder =
                        new PlainTextFormatter.Builder(cs)
                                .style(appearanceStyle)
                                .text(new PlainText(text))
                                .width(width)
                                .wrapLines(wrap)
                                .initialOffset(0, 0)
                                .textAlign(alignCode(align));
                builder.build().format();
                cs.endText();
            }

            PDFStreamParser parser = new PDFStreamParser(appearanceStream);
            List<Object> tokens = parser.parse();
            java.util.ArrayList<String> operands = new java.util.ArrayList<>();
            for (Object tok : tokens) {
                if (tok instanceof Operator) {
                    sb.append("TOK ").append(((Operator) tok).getName());
                    for (String op : operands) {
                        sb.append(' ').append(op);
                    }
                    sb.append('\n');
                    operands.clear();
                } else if (tok instanceof COSBase) {
                    operands.add(operand((COSBase) tok));
                }
            }
        }
        out.print(sb);
    }

    private static int alignCode(String align) {
        switch (align) {
            case "center":
                return 1;
            case "right":
                return 2;
            case "justify":
                return 4;
            case "left":
            default:
                return 0;
        }
    }

    private static String operand(COSBase b) {
        if (b instanceof COSName) {
            return "/" + ((COSName) b).getName();
        }
        if (b instanceof COSInteger || b instanceof COSFloat || b instanceof COSNumber) {
            return canonFloat(((COSNumber) b).floatValue());
        }
        return b.toString();
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
}
