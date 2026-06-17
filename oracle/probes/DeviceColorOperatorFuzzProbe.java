import java.io.OutputStream;
import java.util.List;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.color.SetNonStrokingDeviceCMYKColor;
import org.apache.pdfbox.contentstream.operator.color.SetNonStrokingDeviceGrayColor;
import org.apache.pdfbox.contentstream.operator.color.SetNonStrokingDeviceRGBColor;
import org.apache.pdfbox.contentstream.operator.color.SetStrokingDeviceCMYKColor;
import org.apache.pdfbox.contentstream.operator.color.SetStrokingDeviceGrayColor;
import org.apache.pdfbox.contentstream.operator.color.SetStrokingDeviceRGBColor;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;

/**
 * Live oracle probe for the device-colour content-stream operators
 * {@code G}/{@code g}/{@code RG}/{@code rg}/{@code K}/{@code k}. These all
 * extend the abstract {@code SetColor} via the per-device subclasses
 * ({@code SetStrokingDeviceRGBColor} &c.), whose {@code process} installs the
 * device colour space onto the graphics state *before* delegating to
 * {@code SetColor.process} — which raises {@code MissingOperandException} for a
 * too-short operand list and sets an invalid {@code PDColor(new float[0], null)}
 * for a non-numeric operand (PDFBOX-5851).
 *
 * Unlike {@code SetColorOperandProbe} (which emits only the resulting
 * {@link PDColor}), this probe also emits the current graphics-state stroking /
 * non-stroking *colour space* name after the last operator, so the Python side
 * can pin the gap-(1) behaviour: a too-short {@code rg} still leaves the
 * current colour space at DeviceRGB even though the colour value is unchanged.
 *
 * Canonical signal per emit:
 *   {@code <which>=comps[<c0>,...] pattern=<name|null> cs=<csname|null>}
 *   {@code <which>_space=<csname|null>}
 * where {@code <which>} is {@code stroke} or {@code nonstroke}.
 *
 * argv[0] = case name (see CASES below); covers the 21 fuzz cases the
 * device-colour parity gap was found against.
 */
public final class DeviceColorOperatorFuzzProbe {

    static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Integer.toString((int) v);
        }
        return Float.toString(v);
    }

    static String describe(PDColor c) {
        if (c == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder();
        sb.append("comps[");
        float[] comps = c.getComponents();
        for (int i = 0; i < comps.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(fmt(comps[i]));
        }
        sb.append("] pattern=");
        COSName pn = c.getPatternName();
        sb.append(pn == null ? "null" : pn.getName());
        sb.append(" cs=");
        sb.append(c.getColorSpace() == null ? "null" : c.getColorSpace().getName());
        return sb.toString();
    }

    static String spaceName(PDColorSpace cs) {
        return cs == null ? "null" : cs.getName();
    }

    static String contentFor(String which) {
        switch (which) {
            // ---- well-formed, full arity ----
            case "rg":
                return "0.1 0.2 0.3 rg\n";
            case "RG":
                return "0.4 0.5 0.6 RG\n";
            case "g":
                return "0.5 g\n";
            case "G":
                return "0.75 G\n";
            case "k":
                return "0.1 0.2 0.3 0.4 k\n";
            case "K":
                return "0.9 0.8 0.7 0.6 K\n";
            case "rg_out_of_range":
                return "-0.5 2.0 0.3 rg\n";
            // ---- non-numeric operand -> invalid PDColor([], null) ----
            case "rg_nonnumeric_first":
                return "/Foo /Bar /Baz rg\n";
            case "rg_nonnumeric_middle":
                return "0.1 /Bad 0.3 rg\n";
            case "g_nonnumeric":
                return "/Foo g\n";
            case "k_nonnumeric":
                return "0.1 0.2 /Bad 0.4 k\n";
            case "RG_nonnumeric":
                return "/A /B /C RG\n";
            case "rg_nonnumeric_string":
                return "(a) (b) (c) rg\n";
            // ---- too few operands -> MissingOperandException, cs switched ----
            case "rg_too_few":
                return "0.1 0.2 rg\n";
            case "RG_too_few":
                return "0.1 0.2 RG\n";
            case "k_too_few":
                return "0.1 0.2 0.3 k\n";
            case "g_empty":
                return "g\n";
            // ---- extra trailing operands -> first n consumed ----
            case "rg_extra":
                return "0.1 0.2 0.3 0.9 rg\n";
            case "k_extra":
                return "0.1 0.2 0.3 0.4 0.5 k\n";
            // ---- device op after a named cs: device op switches the space ----
            case "cs_then_rg":
                return "/DeviceCMYK cs 0.1 0.2 0.3 rg\n";
            case "cs_then_rg_too_few":
                return "/DeviceCMYK cs 0.1 0.2 rg\n";
            default:
                return "";
        }
    }

    public static void main(String[] argv) throws Exception {
        final String which = argv.length > 0 ? argv[0] : "rg";
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDResources res = new PDResources();

            byte[] content = contentFor(which).getBytes("US-ASCII");
            PDStream cs = new PDStream(doc);
            try (OutputStream os = cs.createOutputStream()) {
                os.write(content);
            }
            page.setContents(cs);
            page.setResources(res);

            final PDColor[] captured = new PDColor[2];
            final PDColorSpace[] capturedSpace = new PDColorSpace[2];
            PDFStreamEngine engine = new PDFStreamEngine() {
                @Override
                public void processOperator(Operator operator,
                        List<org.apache.pdfbox.cos.COSBase> operands)
                        throws java.io.IOException {
                    super.processOperator(operator, operands);
                    captured[0] = getGraphicsState().getStrokingColor();
                    captured[1] = getGraphicsState().getNonStrokingColor();
                    capturedSpace[0] = getGraphicsState().getStrokingColorSpace();
                    capturedSpace[1] = getGraphicsState().getNonStrokingColorSpace();
                }
            };
            engine.addOperator(new SetStrokingDeviceGrayColor(engine));
            engine.addOperator(new SetNonStrokingDeviceGrayColor(engine));
            engine.addOperator(new SetStrokingDeviceRGBColor(engine));
            engine.addOperator(new SetNonStrokingDeviceRGBColor(engine));
            engine.addOperator(new SetStrokingDeviceCMYKColor(engine));
            engine.addOperator(new SetNonStrokingDeviceCMYKColor(engine));
            engine.addOperator(
                    new org.apache.pdfbox.contentstream.operator.color
                            .SetStrokingColorSpace(engine));
            engine.addOperator(
                    new org.apache.pdfbox.contentstream.operator.color
                            .SetNonStrokingColorSpace(engine));

            engine.processPage(page);

            System.out.println("stroke=" + describe(captured[0]));
            System.out.println("nonstroke=" + describe(captured[1]));
            System.out.println("stroke_space=" + spaceName(capturedSpace[0]));
            System.out.println("nonstroke_space=" + spaceName(capturedSpace[1]));
        }
    }
}
