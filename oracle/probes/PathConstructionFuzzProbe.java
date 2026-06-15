import java.awt.geom.Point2D;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.contentstream.PDFGraphicsStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.OperatorProcessor;
import org.apache.pdfbox.contentstream.operator.graphics.AppendRectangleToPath;
import org.apache.pdfbox.contentstream.operator.graphics.CloseAndStrokePath;
import org.apache.pdfbox.contentstream.operator.graphics.CloseFillEvenOddAndStrokePath;
import org.apache.pdfbox.contentstream.operator.graphics.CloseFillNonZeroAndStrokePath;
import org.apache.pdfbox.contentstream.operator.graphics.ClosePath;
import org.apache.pdfbox.contentstream.operator.graphics.CurveTo;
import org.apache.pdfbox.contentstream.operator.graphics.CurveToReplicateFinalPoint;
import org.apache.pdfbox.contentstream.operator.graphics.CurveToReplicateInitialPoint;
import org.apache.pdfbox.contentstream.operator.graphics.EndPath;
import org.apache.pdfbox.contentstream.operator.graphics.FillEvenOddAndStrokePath;
import org.apache.pdfbox.contentstream.operator.graphics.FillEvenOddRule;
import org.apache.pdfbox.contentstream.operator.graphics.FillNonZeroAndStrokePath;
import org.apache.pdfbox.contentstream.operator.graphics.FillNonZeroRule;
import org.apache.pdfbox.contentstream.operator.graphics.LegacyFillNonZeroRule;
import org.apache.pdfbox.contentstream.operator.graphics.LineTo;
import org.apache.pdfbox.contentstream.operator.graphics.MoveTo;
import org.apache.pdfbox.contentstream.operator.graphics.StrokePath;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDPage;

/**
 * Live oracle probe: differential operand / current-point fuzz of the
 * PATH-CONSTRUCTION and PATH-PAINTING content-stream operator processors
 * (PDF 32000-1 §8.5.2 path construction / §8.5.3 path painting).
 *
 * <p>Construction operators (m / l / c / v / y / re / h) each read a fixed
 * number of {@code COSNumber} operands; their gatekeeping (arity, per-operand
 * vs whole-list type guard, current-point fallbacks) is the surface. Painting
 * operators (S / s / f / F / f* / B / B* / b / b* / n) take no operands; their
 * surface is the current-path / current-point state interaction and tolerance
 * of trailing operands.
 *
 * <p>The probe subclasses {@link PDFGraphicsStreamEngine} with a recording
 * graphics context that models a tiny current-path: a nullable current point
 * plus a trace of which path hooks fired. Each operator processor is
 * instantiated with this engine and its {@code process(Operator, List)} is
 * called DIRECTLY — routing through {@code processStream} would swallow
 * exceptions into the engine's operatorException handling and hide the
 * arity/type contract.
 *
 * <p>Usage: {@code java -cp <pdfbox-app.jar>:<build> PathConstructionFuzzProbe}
 * Output (UTF-8, to stdout), one line per case:
 * <pre>
 *   &lt;id&gt;\tERR:&lt;SimpleExceptionName&gt;   # process() threw
 *   &lt;id&gt;\t&lt;trace&gt;|cp=&lt;point-or-none&gt;    # process() ran; trace = fired hooks
 * </pre>
 * where {@code trace} is a {@code >}-joined list of {@code move/line/curve/
 * rect/close/stroke/fill/fillstroke/endpath} hook names (empty = SKIP) and
 * {@code cp} is the post-call current point ({@code none} or
 * {@code x,y} rendered with {@code %.3f}).
 */
public final class PathConstructionFuzzProbe {

    /** Recording graphics engine: a nullable current point + a hook trace. */
    private static final class Recorder extends PDFGraphicsStreamEngine {
        private Point2D current;
        private final StringBuilder trace = new StringBuilder();

        Recorder() {
            super(new PDPage());
        }

        void reset() {
            current = null;
            trace.setLength(0);
        }

        void seedMove() {
            // Pre-open a subpath so "with current point" variants exercise the
            // non-null branch. Uses the same hook the engine would.
            current = new Point2D.Float(10f, 20f);
        }

        private void mark(String hook) {
            if (trace.length() > 0) {
                trace.append('>');
            }
            trace.append(hook);
        }

        @Override
        public void moveTo(float x, float y) {
            mark("move");
            current = new Point2D.Float(x, y);
        }

        @Override
        public void lineTo(float x, float y) {
            mark("line");
            current = new Point2D.Float(x, y);
        }

        @Override
        public void curveTo(float x1, float y1, float x2, float y2,
                            float x3, float y3) {
            mark("curve");
            current = new Point2D.Float(x3, y3);
        }

        @Override
        public void appendRectangle(Point2D p0, Point2D p1, Point2D p2,
                                    Point2D p3) {
            mark("rect");
            current = new Point2D.Double(p0.getX(), p0.getY());
        }

        @Override
        public Point2D.Float transformedPoint(float x, float y) {
            // The probe drives the processors directly (no active stream),
            // so the real graphics-state stack / CTM is null and the
            // inherited transformedPoint would NPE before the path hook is
            // reached. The operand-validation + current-point-fallback
            // surface under test is independent of the CTM, so model an
            // identity transform here to make the hooks observable.
            return new Point2D.Float(x, y);
        }

        @Override
        public Point2D getCurrentPoint() {
            return current;
        }

        @Override
        public void closePath() {
            mark("close");
        }

        @Override
        public void endPath() {
            mark("endpath");
            current = null;
        }

        @Override
        public void strokePath() {
            mark("stroke");
            current = null;
        }

        @Override
        public void fillPath(int windingRule) {
            mark("fill");
            current = null;
        }

        @Override
        public void fillAndStrokePath(int windingRule) {
            mark("fillstroke");
            current = null;
        }

        @Override
        public void clip(int windingRule) {
            mark("clip");
        }

        @Override
        public void shadingFill(COSName name) {
            mark("shading");
        }

        @Override
        public void drawImage(org.apache.pdfbox.pdmodel.graphics.image.PDImage img) {
            mark("image");
        }

        String fingerprint() {
            StringBuilder sb = new StringBuilder(trace);
            sb.append("|cp=");
            if (current == null) {
                sb.append("none");
            } else {
                sb.append(String.format(java.util.Locale.ROOT, "%.3f,%.3f",
                        current.getX(), current.getY()));
            }
            return sb.toString();
        }
    }

    // --- reusable operands ---------------------------------------------------
    private static final COSBase NUM = new COSFloat(1.5f);
    private static final COSBase NUM2 = new COSFloat(3.25f);
    private static final COSBase NEG = new COSFloat(-4.0f);
    // A large magnitude that is exactly representable as both a 32-bit
    // (Java float) and 64-bit (Python float) IEEE value, so the post-call
    // current-point fingerprint can't drift on float-width alone. 2^17.
    private static final COSBase HUGE = new COSFloat(131072.0f);
    private static final COSBase INT = COSInteger.get(2);
    private static final COSBase NAME = COSName.getPDFName("X");
    private static final COSBase STR = new COSString("z");
    private static final COSBase NULL = COSNull.NULL;
    private static final COSBase ARR = new COSArray();

    private static List<COSBase> ops(COSBase... items) {
        List<COSBase> list = new ArrayList<>();
        for (COSBase b : items) {
            list.add(b);
        }
        return list;
    }

    private static void run(PrintStream out, Recorder eng, boolean seed,
                            String id, OperatorProcessor proc, String opName,
                            List<COSBase> operands) {
        eng.reset();
        if (seed) {
            eng.seedMove();
        }
        Operator op = Operator.getOperator(opName);
        String result;
        try {
            proc.process(op, operands);
            result = eng.fingerprint();
        } catch (Exception ex) {
            result = "ERR:" + ex.getClass().getSimpleName();
        }
        out.println(id + "\t" + result);
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        Recorder eng = new Recorder();

        MoveTo m = new MoveTo(eng);
        LineTo l = new LineTo(eng);
        CurveTo c = new CurveTo(eng);
        CurveToReplicateInitialPoint v = new CurveToReplicateInitialPoint(eng);
        CurveToReplicateFinalPoint y = new CurveToReplicateFinalPoint(eng);
        AppendRectangleToPath re = new AppendRectangleToPath(eng);
        ClosePath h = new ClosePath(eng);
        StrokePath sUp = new StrokePath(eng);
        CloseAndStrokePath s = new CloseAndStrokePath(eng);
        FillNonZeroRule f = new FillNonZeroRule(eng);
        LegacyFillNonZeroRule fLegacy = new LegacyFillNonZeroRule(eng);
        FillEvenOddRule fStar = new FillEvenOddRule(eng);
        FillNonZeroAndStrokePath bUpper = new FillNonZeroAndStrokePath(eng);
        FillEvenOddAndStrokePath bStarUpper = new FillEvenOddAndStrokePath(eng);
        CloseFillNonZeroAndStrokePath b = new CloseFillNonZeroAndStrokePath(eng);
        CloseFillEvenOddAndStrokePath bStar =
                new CloseFillEvenOddAndStrokePath(eng);
        EndPath n = new EndPath(eng);

        // --- m (MoveTo): arity, per-operand type, value ----------------------
        run(out, eng, false, "m_empty", m, "m", ops());
        run(out, eng, false, "m_one", m, "m", ops(NUM));
        run(out, eng, false, "m_two", m, "m", ops(NUM, NUM2));
        run(out, eng, false, "m_two_int", m, "m", ops(INT, INT));
        run(out, eng, false, "m_first_name", m, "m", ops(NAME, NUM));
        run(out, eng, false, "m_second_str", m, "m", ops(NUM, STR));
        run(out, eng, false, "m_two_neg", m, "m", ops(NEG, NEG));
        run(out, eng, false, "m_two_huge", m, "m", ops(HUGE, HUGE));
        run(out, eng, false, "m_three_trailing_name", m, "m",
                ops(NUM, NUM2, NAME));
        run(out, eng, false, "m_three_trailing_num", m, "m",
                ops(NUM, NUM2, INT));

        // --- l (LineTo): with and without a current point --------------------
        run(out, eng, false, "l_empty", l, "l", ops());
        run(out, eng, false, "l_one", l, "l", ops(NUM));
        run(out, eng, false, "l_two_nocp", l, "l", ops(NUM, NUM2));
        run(out, eng, true, "l_two_cp", l, "l", ops(NUM, NUM2));
        run(out, eng, false, "l_first_name_nocp", l, "l", ops(NAME, NUM));
        run(out, eng, true, "l_first_name_cp", l, "l", ops(NAME, NUM));
        run(out, eng, false, "l_three_trailing_name_nocp", l, "l",
                ops(NUM, NUM2, NAME));

        // --- c (CurveTo): 6 operands, current-point fallback -----------------
        run(out, eng, false, "c_empty", c, "c", ops());
        run(out, eng, false, "c_five", c, "c",
                ops(NUM, NUM, NUM, NUM, NUM));
        run(out, eng, false, "c_six_nocp", c, "c",
                ops(NUM, NUM2, NUM, NUM2, NUM, NUM2));
        run(out, eng, true, "c_six_cp", c, "c",
                ops(NUM, NUM2, NUM, NUM2, NUM, NUM2));
        run(out, eng, true, "c_six_one_str", c, "c",
                ops(NUM, NUM2, STR, NUM2, NUM, NUM2));
        run(out, eng, true, "c_six_one_null", c, "c",
                ops(NUM, NUM2, NUM, NULL, NUM, NUM2));
        run(out, eng, true, "c_seven_trailing_name", c, "c",
                ops(NUM, NUM2, NUM, NUM2, NUM, NUM2, NAME));

        // --- v (CurveToReplicateInitialPoint): 4 operands, fallback ----------
        run(out, eng, false, "v_empty", v, "v", ops());
        run(out, eng, false, "v_three", v, "v", ops(NUM, NUM, NUM));
        run(out, eng, false, "v_four_nocp", v, "v",
                ops(NUM, NUM2, NUM, NUM2));
        run(out, eng, true, "v_four_cp", v, "v",
                ops(NUM, NUM2, NUM, NUM2));
        run(out, eng, true, "v_four_one_name", v, "v",
                ops(NUM, NAME, NUM, NUM2));
        run(out, eng, true, "v_five_trailing_null", v, "v",
                ops(NUM, NUM2, NUM, NUM2, NULL));

        // --- y (CurveToReplicateFinalPoint): 4 operands, fallback ------------
        run(out, eng, false, "y_empty", y, "y", ops());
        run(out, eng, false, "y_three", y, "y", ops(NUM, NUM, NUM));
        run(out, eng, false, "y_four_nocp", y, "y",
                ops(NUM, NUM2, NUM, NUM2));
        run(out, eng, true, "y_four_cp", y, "y",
                ops(NUM, NUM2, NUM, NUM2));
        run(out, eng, true, "y_four_one_str", y, "y",
                ops(NUM, NUM2, STR, NUM2));
        run(out, eng, true, "y_five_trailing_name", y, "y",
                ops(NUM, NUM2, NUM, NUM2, NAME));

        // --- re (AppendRectangleToPath): 4 operands --------------------------
        run(out, eng, false, "re_empty", re, "re", ops());
        run(out, eng, false, "re_three", re, "re", ops(NUM, NUM, NUM));
        run(out, eng, false, "re_four", re, "re",
                ops(INT, INT, INT, INT));
        run(out, eng, false, "re_four_neg", re, "re",
                ops(NEG, NEG, NUM, NUM));
        run(out, eng, false, "re_four_one_name", re, "re",
                ops(NUM, NAME, NUM, NUM));
        run(out, eng, false, "re_four_one_arr", re, "re",
                ops(NUM, NUM, ARR, NUM));
        run(out, eng, false, "re_five_trailing_name", re, "re",
                ops(NUM, NUM, NUM, NUM, NAME));

        // --- h (ClosePath): current-point guard ------------------------------
        run(out, eng, false, "h_nocp", h, "h", ops());
        run(out, eng, true, "h_cp", h, "h", ops());
        run(out, eng, true, "h_cp_extra", h, "h", ops(NUM));

        // --- painting ops: no operands, current-point interaction ------------
        run(out, eng, false, "S_nocp", sUp, "S", ops());
        run(out, eng, true, "S_cp", sUp, "S", ops());
        run(out, eng, true, "S_cp_extra", sUp, "S", ops(NUM));
        run(out, eng, false, "s_nocp", s, "s", ops());
        run(out, eng, true, "s_cp", s, "s", ops());
        run(out, eng, false, "f_nocp", f, "f", ops());
        run(out, eng, true, "f_cp", f, "f", ops());
        run(out, eng, true, "F_cp", fLegacy, "F", ops());
        run(out, eng, true, "fstar_cp", fStar, "f*", ops());
        run(out, eng, true, "B_cp", bUpper, "B", ops());
        run(out, eng, true, "Bstar_cp", bStarUpper, "B*", ops());
        run(out, eng, false, "b_nocp", b, "b", ops());
        run(out, eng, true, "b_cp", b, "b", ops());
        run(out, eng, true, "bstar_cp", bStar, "b*", ops());
        run(out, eng, false, "n_nocp", n, "n", ops());
        run(out, eng, true, "n_cp", n, "n", ops());
        run(out, eng, true, "n_cp_extra", n, "n", ops(NUM));
    }
}
