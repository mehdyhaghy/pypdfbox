import java.awt.geom.Point2D;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.contentstream.PDFGraphicsStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.graphics.DrawObject;
import org.apache.pdfbox.contentstream.operator.state.Concatenate;
import org.apache.pdfbox.contentstream.operator.state.SetGraphicsStateParameters;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;
import org.apache.pdfbox.pdmodel.graphics.form.PDTransparencyGroup;
import org.apache.pdfbox.pdmodel.graphics.image.PDImage;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for the operand / lookup gatekeeping of the GRAPHICS
 * content-stream operator processors: {@code Do} (DrawObject — draw XObject),
 * {@code cm} (Concatenate — concatenate CTM), {@code gs}
 * (SetGraphicsStateParameters — apply named ExtGState).
 *
 * <p>Each processor's {@code process(Operator, List)} is called DIRECTLY with a
 * hand-built operand list (routing through {@code processOperator} would swallow
 * the exception into {@code operatorException}, hiding the arity/type contract).
 * For each case the probe emits one tab-separated line:
 *
 * <pre>
 *   &lt;id&gt;\tERR:&lt;SimpleExceptionName&gt;       # process() threw
 *   &lt;id&gt;\tINVOKED|&lt;detail&gt;                  # process() did real work
 *   &lt;id&gt;\tSKIP                               # process() returned a no-op
 * </pre>
 *
 * <p>For {@code cm} the engine records the post-call CTM so a silent-skip (bad
 * operand) is distinguishable from an applied concatenation. For {@code Do} the
 * engine records which hook fired (drawImage / showForm / showTransparencyGroup)
 * by appending a marker to a per-case trace. For {@code gs} a clean return is
 * reported as SKIP/INVOKED — gs has no observable abstract hook, so the signal
 * is purely the thrown-exception contract plus clean-return.
 *
 * <p>A shared {@link PDResources} holds a form XObject under {@code /Frm}, an
 * image XObject under {@code /Img}, a NON-stream /XObject entry under
 * {@code /Bad}, a valid ExtGState dict under {@code /GS}, and a NON-dict
 * /ExtGState entry under {@code /GSbad}.
 */
public final class GraphicsOperatorFuzzProbe {

    static final class RecordingEngine extends PDFGraphicsStreamEngine {
        final PDResources res;
        String trace = "";
        org.apache.pdfbox.pdmodel.graphics.state.PDGraphicsState gs =
                new org.apache.pdfbox.pdmodel.graphics.state.PDGraphicsState(
                        new org.apache.pdfbox.pdmodel.common.PDRectangle(
                                0, 0, 100, 100));

        RecordingEngine(PDPage page, PDResources r) {
            super(page);
            this.res = r;
        }

        void reset() {
            trace = "";
        }

        @Override
        public org.apache.pdfbox.pdmodel.graphics.state.PDGraphicsState
                getGraphicsState() {
            return gs;
        }

        @Override
        public PDResources getResources() {
            return res;
        }

        @Override
        public void drawImage(PDImage pdImage) {
            trace = "image";
        }

        @Override
        public void showForm(PDFormXObject form) {
            trace = "form";
            // Do NOT recurse into content (base would re-run processStream);
            // we only need to know the dispatch landed here.
        }

        @Override
        public void showTransparencyGroup(PDTransparencyGroup group) {
            trace = "group";
        }

        // ---- unused abstract path hooks ----
        @Override
        public void appendRectangle(Point2D p0, Point2D p1, Point2D p2,
                Point2D p3) {
        }

        @Override
        public void clip(int windingRule) {
        }

        @Override
        public void moveTo(float x, float y) {
        }

        @Override
        public void lineTo(float x, float y) {
        }

        @Override
        public void curveTo(float x1, float y1, float x2, float y2, float x3,
                float y3) {
        }

        @Override
        public Point2D getCurrentPoint() {
            return new Point2D.Float(0, 0);
        }

        @Override
        public void closePath() {
        }

        @Override
        public void endPath() {
        }

        @Override
        public void strokePath() {
        }

        @Override
        public void fillPath(int windingRule) {
        }

        @Override
        public void fillAndStrokePath(int windingRule) {
        }

        @Override
        public void shadingFill(COSName shadingName) {
        }
    }

    static COSStream formStream() {
        COSStream s = new COSStream();
        s.setItem(COSName.TYPE, COSName.getPDFName("XObject"));
        s.setItem(COSName.SUBTYPE, COSName.getPDFName("Form"));
        s.setItem(COSName.BBOX, rect());
        return s;
    }

    static COSStream imageStream() {
        COSStream s = new COSStream();
        s.setItem(COSName.TYPE, COSName.getPDFName("XObject"));
        s.setItem(COSName.SUBTYPE, COSName.getPDFName("Image"));
        s.setItem(COSName.WIDTH, COSInteger.get(1));
        s.setItem(COSName.HEIGHT, COSInteger.get(1));
        s.setItem(COSName.BITS_PER_COMPONENT, COSInteger.get(8));
        s.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        return s;
    }

    static COSArray rect() {
        COSArray a = new COSArray();
        a.add(COSInteger.get(0));
        a.add(COSInteger.get(0));
        a.add(COSInteger.get(1));
        a.add(COSInteger.get(1));
        return a;
    }

    static PDResources buildResources() {
        COSDictionary root = new COSDictionary();

        COSDictionary xobjects = new COSDictionary();
        xobjects.setItem(COSName.getPDFName("Frm"), formStream());
        xobjects.setItem(COSName.getPDFName("Img"), imageStream());
        xobjects.setItem(COSName.getPDFName("Bad"), new COSDictionary());
        root.setItem(COSName.XOBJECT, xobjects);

        COSDictionary extgs = new COSDictionary();
        COSDictionary goodGs = new COSDictionary();
        goodGs.setItem(COSName.TYPE, COSName.getPDFName("ExtGState"));
        goodGs.setItem(COSName.getPDFName("LW"), new COSFloat(3.0f));
        extgs.setItem(COSName.getPDFName("GS"), goodGs);
        extgs.setItem(COSName.getPDFName("GSbad"), COSName.getPDFName("nope"));
        root.setItem(COSName.getPDFName("ExtGState"), extgs);

        return new PDResources(root);
    }

    static final COSBase NUM = new COSFloat(1.5f);
    static final COSBase HUGE = new COSFloat(1.0e30f);
    static final COSBase INT = COSInteger.get(2);
    static final COSBase NAME_FRM = COSName.getPDFName("Frm");
    static final COSBase NAME_IMG = COSName.getPDFName("Img");
    static final COSBase NAME_BAD = COSName.getPDFName("Bad");
    static final COSBase NAME_MISS = COSName.getPDFName("Nope");
    static final COSBase NAME_GS = COSName.getPDFName("GS");
    static final COSBase NAME_GSBAD = COSName.getPDFName("GSbad");
    static final COSBase NAME_GSMISS = COSName.getPDFName("Zzz");
    static final COSBase STR = new COSString("x");
    static final COSBase ARR = new COSArray();
    static final COSBase NUL = COSNull.NULL;

    static List<COSBase> ops(COSBase... items) {
        List<COSBase> l = new ArrayList<>();
        for (COSBase b : items) {
            l.add(b);
        }
        return l;
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        PDResources res = buildResources();
        PDPage page = new PDPage();
        RecordingEngine engine = new RecordingEngine(page, res);

        StringBuilder sb = new StringBuilder();

        Concatenate cm = new Concatenate(engine);
        runCm(engine, cm, sb, "cm_empty", ops());
        runCm(engine, cm, sb, "cm_five", ops(NUM, NUM, NUM, NUM, NUM));
        runCm(engine, cm, sb, "cm_six", ops(NUM, NUM, NUM, NUM, NUM, NUM));
        runCm(engine, cm, sb, "cm_six_int", ops(INT, NUM, NUM, NUM, NUM, NUM));
        runCm(engine, cm, sb, "cm_six_first_name",
                ops(NAME_FRM, NUM, NUM, NUM, NUM, NUM));
        runCm(engine, cm, sb, "cm_six_one_str",
                ops(NUM, NUM, STR, NUM, NUM, NUM));
        runCm(engine, cm, sb, "cm_six_one_null",
                ops(NUM, NUM, NUM, NUM, NUL, NUM));
        runCm(engine, cm, sb, "cm_huge",
                ops(HUGE, NUM, NUM, HUGE, NUM, NUM));
        runCm(engine, cm, sb, "cm_seven_all_num",
                ops(NUM, NUM, NUM, NUM, NUM, NUM, NUM));
        runCm(engine, cm, sb, "cm_seven_trailing_name",
                ops(NUM, NUM, NUM, NUM, NUM, NUM, NAME_FRM));
        runCm(engine, cm, sb, "cm_seven_trailing_null",
                ops(NUM, NUM, NUM, NUM, NUM, NUM, NUL));

        DrawObject doOp = new DrawObject(engine);
        runDo(engine, doOp, sb, "do_empty", ops());
        runDo(engine, doOp, sb, "do_num", ops(NUM));
        runDo(engine, doOp, sb, "do_str", ops(STR));
        runDo(engine, doOp, sb, "do_null", ops(NUL));
        runDo(engine, doOp, sb, "do_form", ops(NAME_FRM));
        runDo(engine, doOp, sb, "do_image", ops(NAME_IMG));
        runDo(engine, doOp, sb, "do_missing", ops(NAME_MISS));
        runDo(engine, doOp, sb, "do_nonstream", ops(NAME_BAD));
        runDo(engine, doOp, sb, "do_extra_trailing", ops(NAME_FRM, NUM));

        SetGraphicsStateParameters gs = new SetGraphicsStateParameters(engine);
        runGs(engine, gs, sb, "gs_empty", ops());
        runGs(engine, gs, sb, "gs_num", ops(NUM));
        runGs(engine, gs, sb, "gs_str", ops(STR));
        runGs(engine, gs, sb, "gs_null", ops(NUL));
        runGs(engine, gs, sb, "gs_arr", ops(ARR));
        runGs(engine, gs, sb, "gs_good", ops(NAME_GS));
        runGs(engine, gs, sb, "gs_missing", ops(NAME_GSMISS));
        runGs(engine, gs, sb, "gs_nondict", ops(NAME_GSBAD));
        runGs(engine, gs, sb, "gs_extra_trailing", ops(NAME_GS, NUM));

        out.print(sb);
    }

    static void runCm(RecordingEngine engine, Concatenate op, StringBuilder sb,
            String id, List<COSBase> operands) {
        engine.reset();
        engine.getGraphicsState().setCurrentTransformationMatrix(new Matrix());
        emit(sb, id, () -> {
            op.process(Operator.getOperator("cm"), operands);
            Matrix m = engine.getGraphicsState()
                    .getCurrentTransformationMatrix();
            if (m.getScaleX() == 1.0f && m.getScaleY() == 1.0f
                    && m.getShearX() == 0.0f && m.getShearY() == 0.0f
                    && m.getTranslateX() == 0.0f
                    && m.getTranslateY() == 0.0f) {
                return "SKIP";
            }
            return String.format(Locale.ROOT, "INVOKED|a=%.4g|d=%.4g|e=%.4g",
                    m.getScaleX(), m.getScaleY(), m.getTranslateX());
        });
    }

    static void runDo(RecordingEngine engine, DrawObject op, StringBuilder sb,
            String id, List<COSBase> operands) {
        engine.reset();
        emit(sb, id, () -> {
            op.process(Operator.getOperator("Do"), operands);
            return engine.trace.isEmpty() ? "SKIP" : "INVOKED|" + engine.trace;
        });
    }

    static void runGs(RecordingEngine engine, SetGraphicsStateParameters op,
            StringBuilder sb, String id, List<COSBase> operands) {
        engine.reset();
        emit(sb, id, () -> {
            op.process(Operator.getOperator("gs"), operands);
            return "OK";
        });
    }

    interface Body {
        String run() throws Exception;
    }

    static void emit(StringBuilder sb, String id, Body body) {
        try {
            String r = body.run();
            sb.append(id).append('\t').append(r).append('\n');
        } catch (Throwable t) {
            sb.append(id).append('\t').append("ERR:")
                    .append(t.getClass().getSimpleName()).append('\n');
        }
    }

    private GraphicsOperatorFuzzProbe() {
    }
}
