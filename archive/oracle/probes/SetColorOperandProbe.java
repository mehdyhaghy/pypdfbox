import java.io.ByteArrayOutputStream;
import java.io.OutputStream;
import java.util.List;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.color.SetNonStrokingColor;
import org.apache.pdfbox.contentstream.operator.color.SetNonStrokingColorN;
import org.apache.pdfbox.contentstream.operator.color.SetNonStrokingColorSpace;
import org.apache.pdfbox.contentstream.operator.color.SetStrokingColor;
import org.apache.pdfbox.contentstream.operator.color.SetStrokingColorN;
import org.apache.pdfbox.contentstream.operator.color.SetStrokingColorSpace;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;

/**
 * Live oracle probe for the {@code sc}/{@code scn}/{@code SC}/{@code SCN}
 * colour-set operators' operand handling across DeviceGray (1 comp),
 * DeviceRGB (3), DeviceCMYK (4), a Separation (1) colorant, and a Pattern
 * colour space (trailing /Name operand). Each named content stream is driven
 * through a minimal {@link PDFStreamEngine} that registers exactly the colour
 * and colour-space operators, then the resulting current stroking /
 * non-stroking {@link PDColor} is emitted as a canonical line so the Python
 * side can assert byte-identical operand-count / pattern-name / clamp
 * behaviour.
 *
 * Canonical signal per emit:
 *   {@code <which>=comps[<c0>,<c1>,...] pattern=<name|null> cs=<csname>}
 * where {@code <which>} is {@code stroke} or {@code nonstroke}. Components are
 * the float[] from {@link PDColor#getComponents()} formatted with {@code fmt}.
 *
 * argv[0] = case name (see CASES below).
 */
public final class SetColorOperandProbe {

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

    /** A separation colorspace: [ /Separation /Spot /DeviceCMYK <type2 fn> ]. */
    static COSArray separationCS() {
        COSDictionary fn = new COSDictionary();
        fn.setInt(COSName.FUNCTION_TYPE, 2);
        COSArray domain = new COSArray();
        domain.add(new COSFloat(0));
        domain.add(new COSFloat(1));
        fn.setItem(COSName.DOMAIN, domain);
        COSArray c0 = new COSArray();
        c0.add(new COSFloat(0));
        c0.add(new COSFloat(0));
        c0.add(new COSFloat(0));
        c0.add(new COSFloat(0));
        COSArray c1 = new COSArray();
        c1.add(new COSFloat(0));
        c1.add(new COSFloat(1));
        c1.add(new COSFloat(0));
        c1.add(new COSFloat(0));
        fn.setItem(COSName.getPDFName("C0"), c0);
        fn.setItem(COSName.getPDFName("C1"), c1);
        fn.setItem(COSName.N, new COSFloat(1));
        COSArray sep = new COSArray();
        sep.add(COSName.SEPARATION);
        sep.add(COSName.getPDFName("Spot"));
        sep.add(COSName.DEVICECMYK);
        sep.add(fn);
        return sep;
    }

    static String contentFor(String which) {
        switch (which) {
            case "rgb":
                return "/CSRGB cs /CSRGB CS 0.1 0.2 0.3 scn 0.4 0.5 0.6 SCN\n";
            case "cmyk":
                return "/CSCMYK cs 0.1 0.2 0.3 0.4 scn\n";
            case "sep":
                return "/Sep cs /Sep CS 0.7 scn 0.3 SCN\n";
            case "pattern_name_only":
                return "/Pattern cs /P1 scn\n";
            case "pattern_with_comps":
                return "/PatternU cs 0.5 /P1 scn\n";
            // sc/scn with too few operands for the current cs (RGB needs 3).
            case "too_few":
                return "/CSRGB cs 0.1 0.2 scn\n";
            // non-numeric (name) operand in a non-pattern cs -> invalid color.
            case "nonnumeric":
                return "/CSRGB cs /Foo /Bar /Baz scn\n";
            // same, but via the non-N operators sc / SC.
            case "nonnumeric_sc":
                return "/CSRGB cs /CSRGB CS /Foo /Bar /Baz sc "
                        + "/Foo /Bar /Baz SC\n";
            // extra operands beyond component count (RGB given 4 numbers).
            case "extra":
                return "/CSRGB cs 0.1 0.2 0.3 0.9 scn\n";
            // device operators rg / g / k with a non-numeric operand.
            case "device_nonnumeric":
                return "/Foo /Bar /Baz rg\n";
            default:
                return "";
        }
    }

    public static void main(String[] argv) throws Exception {
        final String which = argv.length > 0 ? argv[0] : "rgb";
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDResources res = new PDResources();

            // Register named colour spaces in /Resources /ColorSpace.
            COSDictionary csDict = new COSDictionary();
            // Use the simple device names directly as named colorspaces.
            csDict.setItem(COSName.getPDFName("CSRGB"), COSName.DEVICERGB);
            csDict.setItem(COSName.getPDFName("CSCMYK"), COSName.DEVICECMYK);
            csDict.setItem(COSName.getPDFName("Sep"), separationCS());
            // Uncolored tiling pattern colorspace: [ /Pattern <baseCS> ].
            COSArray patU = new COSArray();
            patU.add(COSName.PATTERN);
            patU.add(COSName.DEVICEGRAY);
            csDict.setItem(COSName.getPDFName("PatternU"), patU);
            res.getCOSObject().setItem(COSName.COLORSPACE, csDict);

            // Register a pattern /P1 so the pattern name resolves.
            COSDictionary patDict = new COSDictionary();
            COSStream tiling = doc.getDocument().createCOSStream();
            tiling.setItem(COSName.TYPE, COSName.PATTERN);
            tiling.setInt(COSName.PATTERN_TYPE, 1);
            tiling.setInt(COSName.PAINT_TYPE, 1);
            tiling.setInt(COSName.TILING_TYPE, 1);
            COSArray bbox = new COSArray();
            bbox.add(new COSFloat(0));
            bbox.add(new COSFloat(0));
            bbox.add(new COSFloat(1));
            bbox.add(new COSFloat(1));
            tiling.setItem(COSName.BBOX, bbox);
            tiling.setFloat(COSName.X_STEP, 1);
            tiling.setFloat(COSName.Y_STEP, 1);
            patDict.setItem(COSName.getPDFName("P1"),
                    org.apache.pdfbox.pdmodel.graphics.pattern.PDAbstractPattern
                            .create(tiling, null).getCOSObject());
            res.getCOSObject().setItem(COSName.PATTERN, patDict);

            byte[] content = contentFor(which).getBytes("US-ASCII");
            PDStream cs = new PDStream(doc);
            try (OutputStream os = cs.createOutputStream()) {
                os.write(content);
            }
            page.setContents(cs);
            page.setResources(res);

            final PDColor[] captured = new PDColor[2];
            PDFStreamEngine engine = new PDFStreamEngine() {
                @Override
                public void processOperator(Operator operator,
                        List<org.apache.pdfbox.cos.COSBase> operands)
                        throws java.io.IOException {
                    super.processOperator(operator, operands);
                    captured[0] = getGraphicsState().getStrokingColor();
                    captured[1] = getGraphicsState().getNonStrokingColor();
                }
            };
            engine.addOperator(new SetStrokingColor(engine));
            engine.addOperator(new SetNonStrokingColor(engine));
            engine.addOperator(new SetStrokingColorN(engine));
            engine.addOperator(new SetNonStrokingColorN(engine));
            engine.addOperator(new SetStrokingColorSpace(engine));
            engine.addOperator(new SetNonStrokingColorSpace(engine));
            engine.addOperator(
                    new org.apache.pdfbox.contentstream.operator.color
                            .SetNonStrokingDeviceRGBColor(engine));
            engine.addOperator(
                    new org.apache.pdfbox.contentstream.operator.color
                            .SetStrokingDeviceRGBColor(engine));

            engine.processPage(page);

            System.out.println("stroke=" + describe(captured[0]));
            System.out.println("nonstroke=" + describe(captured[1]));
        }
    }
}
