import java.io.IOException;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.contentstream.PDFGraphicsStreamEngine;
import org.apache.pdfbox.contentstream.operator.MissingOperandException;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.graphics.ShadingFill;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDStream;

/**
 * Live oracle probe for the {@code sh} (shading fill) content-stream operator's
 * operand validation and shading-resource lookup, as implemented by
 * {@link org.apache.pdfbox.contentstream.operator.graphics.ShadingFill}.
 *
 * Two complementary signals per case:
 *
 *   1. ENGINE path — a minimal {@link PDFGraphicsStreamEngine} processes a tiny
 *      synthetic content stream and records every {@code shadingFill(COSName)}
 *      invocation that survives the engine's {@code operatorException} triage
 *      (a {@link MissingOperandException} is logged + swallowed upstream, so an
 *      invalid {@code sh} produces NO invocation and does not abort the stream).
 *      Reported as {@code engine=fill:<name>} per surviving call, or
 *      {@code engine=none} when none fired.
 *
 *   2. PROCESS path — {@code ShadingFill.process(op, operands)} is called
 *      directly with hand-built operand lists so the raw operand-count /
 *      operand-type gate is observed without the engine's swallow:
 *      {@code process=ok} (returned normally, i.e. forwarded to shadingFill),
 *      {@code process=missing-operand} ({@link MissingOperandException}),
 *      or {@code process=err:<SimpleClassName>} for any other throwable.
 *
 * argv[0] = case name (see CASES in the Python test).
 */
public final class ShadingFillFuzzProbe {

    /** Engine that records shadingFill invocations; all paint ops are no-ops. */
    static final class RecordingEngine extends PDFGraphicsStreamEngine {
        final List<String> fills = new ArrayList<>();

        RecordingEngine(PDPage page) {
            super(page);
        }

        @Override
        public void shadingFill(COSName shadingName) {
            fills.add(shadingName == null ? "null" : shadingName.getName());
        }

        @Override
        public void appendRectangle(java.awt.geom.Point2D p0,
                java.awt.geom.Point2D p1, java.awt.geom.Point2D p2,
                java.awt.geom.Point2D p3) { }

        @Override
        public void drawImage(org.apache.pdfbox.pdmodel.graphics.image.PDImage i) { }

        @Override
        public void clip(int windingRule) { }

        @Override
        public void moveTo(float x, float y) { }

        @Override
        public void lineTo(float x, float y) { }

        @Override
        public void curveTo(float x1, float y1, float x2, float y2,
                float x3, float y3) { }

        @Override
        public java.awt.geom.Point2D getCurrentPoint() {
            return new java.awt.geom.Point2D.Float(0, 0);
        }

        @Override
        public void closePath() { }

        @Override
        public void endPath() { }

        @Override
        public void strokePath() { }

        @Override
        public void fillPath(int windingRule) { }

        @Override
        public void fillAndStrokePath(int windingRule) { }
    }

    /** A minimal axial (type-2) shading dictionary. */
    static COSDictionary axialShading() {
        COSDictionary sh = new COSDictionary();
        sh.setInt(COSName.SHADING_TYPE, 2);
        sh.setItem(COSName.COLORSPACE, COSName.DEVICERGB);
        COSArray coords = new COSArray();
        coords.add(new COSFloat(0));
        coords.add(new COSFloat(0));
        coords.add(new COSFloat(100));
        coords.add(new COSFloat(0));
        sh.setItem(COSName.COORDS, coords);
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
        COSArray c1 = new COSArray();
        c1.add(new COSFloat(1));
        c1.add(new COSFloat(1));
        c1.add(new COSFloat(1));
        fn.setItem(COSName.getPDFName("C0"), c0);
        fn.setItem(COSName.getPDFName("C1"), c1);
        fn.setItem(COSName.N, new COSFloat(1));
        sh.setItem(COSName.FUNCTION, fn);
        return sh;
    }

    /** Resources flavour to build for a given case. */
    static PDResources buildResources(PDDocument doc, String which) {
        PDResources res = new PDResources();
        switch (which) {
            case "no_shading_dict":
                // Resources present, but no /Shading sub-dict at all.
                return res;
            case "wrong_type_entry": {
                // /Shading present, but /Sh1 is a name, not a dict/stream.
                COSDictionary shDict = new COSDictionary();
                shDict.setItem(COSName.getPDFName("Sh1"),
                        COSName.getPDFName("Bogus"));
                res.getCOSObject().setItem(COSName.SHADING, shDict);
                return res;
            }
            case "missing_name": {
                // /Shading present with /Other, but the stream asks for /Sh1.
                COSDictionary shDict = new COSDictionary();
                shDict.setItem(COSName.getPDFName("Other"), axialShading());
                res.getCOSObject().setItem(COSName.SHADING, shDict);
                return res;
            }
            default: {
                // Normal: /Shading /Sh1 -> axial shading dict.
                COSDictionary shDict = new COSDictionary();
                shDict.setItem(COSName.getPDFName("Sh1"), axialShading());
                res.getCOSObject().setItem(COSName.SHADING, shDict);
                return res;
            }
        }
    }

    static String contentFor(String which) {
        switch (which) {
            case "no_operand":
                return "sh\n";
            case "extra_operands":
                return "1 2 /Sh1 sh\n";
            case "non_name_operand":
                return "42 sh\n";
            case "missing_name":
                return "/Sh1 sh\n";
            case "no_shading_dict":
                return "/Sh1 sh\n";
            case "wrong_type_entry":
                return "/Sh1 sh\n";
            case "null_resources":
                return "/Sh1 sh\n";
            default:
                return "/Sh1 sh\n";
        }
    }

    static void runEngine(String which, StringBuilder out) throws IOException {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            if (!"null_resources".equals(which)) {
                page.setResources(buildResources(doc, which));
            }
            PDStream cs = new PDStream(doc);
            try (OutputStream os = cs.createOutputStream()) {
                os.write(contentFor(which).getBytes("US-ASCII"));
            }
            page.setContents(cs);

            RecordingEngine engine = new RecordingEngine(page);
            engine.processPage(page);
            if (engine.fills.isEmpty()) {
                out.append("engine=none\n");
            } else {
                for (String f : engine.fills) {
                    out.append("engine=fill:").append(f).append('\n');
                }
            }
        }
    }

    /** Build the operand list the direct-process path should see. */
    static List<COSBase> operandsFor(String which) {
        List<COSBase> ops = new ArrayList<>();
        switch (which) {
            case "no_operand":
                break;
            case "extra_operands":
                ops.add(COSInteger.get(1));
                ops.add(COSInteger.get(2));
                ops.add(COSName.getPDFName("Sh1"));
                break;
            case "non_name_operand":
                ops.add(COSInteger.get(42));
                break;
            default:
                ops.add(COSName.getPDFName("Sh1"));
                break;
        }
        return ops;
    }

    static void runProcess(String which, StringBuilder out) throws IOException {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            if (!"null_resources".equals(which)) {
                page.setResources(buildResources(doc, which));
            }
            RecordingEngine engine = new RecordingEngine(page);
            ShadingFill op = new ShadingFill(engine);
            Operator operator = Operator.getOperator("sh");
            try {
                op.process(operator, operandsFor(which));
                out.append("process=ok\n");
            } catch (MissingOperandException e) {
                out.append("process=missing-operand\n");
            } catch (Throwable t) {
                out.append("process=err:")
                        .append(t.getClass().getSimpleName())
                        .append('\n');
            }
        }
    }

    public static void main(String[] argv) throws Exception {
        final String which = argv.length > 0 ? argv[0] : "normal";
        StringBuilder out = new StringBuilder();
        runEngine(which, out);
        runProcess(which, out);
        System.out.print(out);
    }
}
