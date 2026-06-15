import java.io.PrintStream;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Deque;
import java.util.List;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.OperatorProcessor;
import org.apache.pdfbox.contentstream.operator.state.SetFlatness;
import org.apache.pdfbox.contentstream.operator.state.SetLineCapStyle;
import org.apache.pdfbox.contentstream.operator.state.SetLineDashPattern;
import org.apache.pdfbox.contentstream.operator.state.SetLineJoinStyle;
import org.apache.pdfbox.contentstream.operator.state.SetLineMiterLimit;
import org.apache.pdfbox.contentstream.operator.state.SetLineWidth;
import org.apache.pdfbox.contentstream.operator.state.SetRenderingIntent;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern;
import org.apache.pdfbox.pdmodel.graphics.state.PDGraphicsState;

/**
 * Live oracle probe: drive each LINE-STATE content-stream operator
 * processor's {@code process(Operator, List)} DIRECTLY with hand-built,
 * malformed operand lists and report whether it throws (and what) plus a
 * fingerprint of the resulting graphics-state line fields.
 *
 * <p>Covered operators: {@code w} (line width), {@code J} (line cap),
 * {@code j} (line join), {@code M} (miter limit), {@code d} (dash array +
 * phase), {@code ri} (rendering intent), {@code i} (flatness).
 *
 * <p>The engine's {@code processOperator} swallows
 * {@code MissingOperandException} into {@code operatorException}, so the
 * operand-checking contract is invisible at the engine layer. Calling
 * {@code process()} directly isolates exactly that contract — the assigned
 * fuzz surface (operand arity / type handling of the line-state operators).
 *
 * <p>For each case the probe emits one tab-separated line:
 * <pre>
 *   &lt;id&gt; \t OK|&lt;fingerprint&gt;
 *   &lt;id&gt; \t ERR:&lt;SimpleExceptionName&gt;
 * </pre>
 * {@code OK} means {@code process()} returned without throwing (whether or
 * not it mutated the graphics state — the no-op-on-bad-type path also
 * reports {@code OK}, distinguishable via the fingerprint). The cases
 * mirror the Python side byte-for-byte.
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; LineStateOperatorFuzzProbe
 */
public final class LineStateOperatorFuzzProbe {

    // Sentinel line-state values so a silent-ignore (no mutation) is
    // distinguishable from an applied update in the fingerprint.
    private static final float SENT_W = 777.0f;
    private static final int SENT_CAP = 5;
    private static final int SENT_JOIN = 6;
    private static final float SENT_MITER = 444.0f;
    private static final float SENT_FLAT = 333.0f;

    private static PDFStreamEngine engine;
    private static Deque<PDGraphicsState> stack;

    private static List<COSBase> ops(COSBase... items) {
        return new ArrayList<>(Arrays.asList(items));
    }

    private static void resetState() {
        stack.clear();
        PDGraphicsState gs = new PDGraphicsState(new PDRectangle());
        gs.setLineWidth(SENT_W);
        gs.setLineCap(SENT_CAP);
        gs.setLineJoin(SENT_JOIN);
        gs.setMiterLimit(SENT_MITER);
        gs.setFlatness(SENT_FLAT);
        gs.setLineDashPattern(null);
        gs.setRenderingIntent(null);
        stack.push(gs);
    }

    private static String fingerprint() {
        PDGraphicsState gs = engine.getGraphicsState();
        PDLineDashPattern dash = gs.getLineDashPattern();
        String dashStr;
        if (dash == null) {
            dashStr = "null";
        } else {
            float[] arr = dash.getDashArray();
            dashStr = "len=" + (arr == null ? -1 : arr.length)
                    + ",ph=" + dash.getPhase();
        }
        return String.format(java.util.Locale.ROOT,
                "w=%.2f|cap=%d|join=%d|miter=%.2f|flat=%.2f|dash=%s|ri=%s",
                gs.getLineWidth(), gs.getLineCap(), gs.getLineJoin(),
                gs.getMiterLimit(), gs.getFlatness(), dashStr,
                gs.getRenderingIntent() == null
                        ? "null" : gs.getRenderingIntent().toString());
    }

    private static String outcome(OperatorProcessor proc, Operator op,
            List<COSBase> operands) {
        resetState();
        try {
            proc.process(op, operands);
        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName();
        }
        return "OK|" + fingerprint();
    }

    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        final StringBuilder sb = new StringBuilder();

        engine = new PDFStreamEngine() {};
        Field stackField =
                PDFStreamEngine.class.getDeclaredField("graphicsStack");
        stackField.setAccessible(true);
        @SuppressWarnings("unchecked")
        Deque<PDGraphicsState> s =
                (Deque<PDGraphicsState>) stackField.get(engine);
        stack = s;

        // Reusable COS operands.
        final COSBase num = new COSFloat(3.5f);
        final COSBase num2 = new COSFloat(-7.0f);
        final COSBase intv = COSInteger.get(2);
        final COSBase negint = COSInteger.get(-1);
        final COSBase bigint = COSInteger.get(99);
        final COSBase name = COSName.getPDFName("Perceptual");
        final COSBase badname = COSName.getPDFName("Bogus");
        final COSBase str = new COSString("x");
        final COSBase nul = COSNull.NULL;

        // ---- w : SetLineWidth (empty->throw, whole-list COSNumber) --------
        emit(sb, "w_empty", new SetLineWidth(engine), ops());
        emit(sb, "w_num", new SetLineWidth(engine), ops(num));
        emit(sb, "w_int", new SetLineWidth(engine), ops(intv));
        emit(sb, "w_neg", new SetLineWidth(engine), ops(num2));
        emit(sb, "w_name", new SetLineWidth(engine), ops(name));
        emit(sb, "w_str", new SetLineWidth(engine), ops(str));
        emit(sb, "w_null", new SetLineWidth(engine), ops(nul));
        emit(sb, "w_num_extra_num", new SetLineWidth(engine), ops(num, num2));
        emit(sb, "w_num_extra_name", new SetLineWidth(engine), ops(num, name));

        // ---- J : SetLineCapStyle (empty->throw, whole-list, no clamp) -----
        emit(sb, "j_cap_empty", new SetLineCapStyle(engine), ops());
        emit(sb, "j_cap_zero", new SetLineCapStyle(engine),
                ops(COSInteger.get(0)));
        emit(sb, "j_cap_two", new SetLineCapStyle(engine), ops(intv));
        emit(sb, "j_cap_neg", new SetLineCapStyle(engine), ops(negint));
        emit(sb, "j_cap_big", new SetLineCapStyle(engine), ops(bigint));
        emit(sb, "j_cap_float", new SetLineCapStyle(engine), ops(num));
        emit(sb, "j_cap_name", new SetLineCapStyle(engine), ops(name));
        emit(sb, "j_cap_str", new SetLineCapStyle(engine), ops(str));
        emit(sb, "j_cap_extra_name", new SetLineCapStyle(engine),
                ops(intv, name));

        // ---- j : SetLineJoinStyle -----------------------------------------
        emit(sb, "j_join_empty", new SetLineJoinStyle(engine), ops());
        emit(sb, "j_join_zero", new SetLineJoinStyle(engine),
                ops(COSInteger.get(0)));
        emit(sb, "j_join_two", new SetLineJoinStyle(engine), ops(intv));
        emit(sb, "j_join_neg", new SetLineJoinStyle(engine), ops(negint));
        emit(sb, "j_join_big", new SetLineJoinStyle(engine), ops(bigint));
        emit(sb, "j_join_name", new SetLineJoinStyle(engine), ops(name));
        emit(sb, "j_join_extra_name", new SetLineJoinStyle(engine),
                ops(intv, name));

        // ---- M : SetLineMiterLimit (empty->throw, whole-list, no clamp) ---
        emit(sb, "m_empty", new SetLineMiterLimit(engine), ops());
        emit(sb, "m_num", new SetLineMiterLimit(engine), ops(num));
        emit(sb, "m_neg", new SetLineMiterLimit(engine), ops(num2));
        emit(sb, "m_zero", new SetLineMiterLimit(engine),
                ops(new COSFloat(0f)));
        emit(sb, "m_name", new SetLineMiterLimit(engine), ops(name));
        emit(sb, "m_str", new SetLineMiterLimit(engine), ops(str));
        emit(sb, "m_num_extra_name", new SetLineMiterLimit(engine),
                ops(num, name));

        // ---- i : SetFlatness ----------------------------------------------
        emit(sb, "i_empty", new SetFlatness(engine), ops());
        emit(sb, "i_num", new SetFlatness(engine), ops(num));
        emit(sb, "i_neg", new SetFlatness(engine), ops(num2));
        emit(sb, "i_name", new SetFlatness(engine), ops(name));
        emit(sb, "i_null", new SetFlatness(engine), ops(nul));
        emit(sb, "i_num_extra_name", new SetFlatness(engine), ops(num, name));

        // ---- ri : SetRenderingIntent (empty->throw, get(0) instanceof) ----
        emit(sb, "ri_empty", new SetRenderingIntent(engine), ops());
        emit(sb, "ri_known", new SetRenderingIntent(engine), ops(name));
        emit(sb, "ri_unknown", new SetRenderingIntent(engine), ops(badname));
        emit(sb, "ri_num", new SetRenderingIntent(engine), ops(num));
        emit(sb, "ri_str", new SetRenderingIntent(engine), ops(str));
        emit(sb, "ri_null", new SetRenderingIntent(engine), ops(nul));
        emit(sb, "ri_name_extra", new SetRenderingIntent(engine),
                ops(name, num));

        // ---- d : SetLineDashPattern (<2->throw, array+number, sanitize) ---
        emit(sb, "d_empty", new SetLineDashPattern(engine), ops());
        emit(sb, "d_one", new SetLineDashPattern(engine),
                ops(dashArray(3f, 2f)));
        emit(sb, "d_solid", new SetLineDashPattern(engine),
                ops(new COSArray(), COSInteger.get(0)));
        emit(sb, "d_arr_phase", new SetLineDashPattern(engine),
                ops(dashArray(3f, 2f), COSInteger.get(1)));
        emit(sb, "d_all_zero", new SetLineDashPattern(engine),
                ops(dashArray(0f, 0f), COSInteger.get(0)));
        emit(sb, "d_nonnum_entry", new SetLineDashPattern(engine),
                ops(dashArrayWith(name), COSInteger.get(0)));
        emit(sb, "d_first_not_array", new SetLineDashPattern(engine),
                ops(num, COSInteger.get(0)));
        emit(sb, "d_phase_not_num", new SetLineDashPattern(engine),
                ops(dashArray(3f, 2f), name));
        emit(sb, "d_phase_float", new SetLineDashPattern(engine),
                ops(dashArray(3f, 2f), new COSFloat(2.9f)));
        emit(sb, "d_extra", new SetLineDashPattern(engine),
                ops(dashArray(3f, 2f), COSInteger.get(1), num));

        out.print(sb);
    }

    private static COSArray dashArray(float... vals) {
        COSArray arr = new COSArray();
        for (float v : vals) {
            arr.add(new COSFloat(v));
        }
        return arr;
    }

    private static COSArray dashArrayWith(COSBase extra) {
        COSArray arr = new COSArray();
        arr.add(new COSFloat(3f));
        arr.add(extra);
        return arr;
    }

    private static void emit(StringBuilder sb, String id,
            OperatorProcessor proc, List<COSBase> operands) {
        Operator op = Operator.getOperator(proc.getName());
        sb.append(id).append('\t').append(outcome(proc, op, operands))
                .append('\n');
    }
}
