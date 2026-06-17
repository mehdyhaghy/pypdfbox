import java.io.PrintStream;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.OperatorProcessor;
import org.apache.pdfbox.contentstream.operator.state.SetMatrix;
import org.apache.pdfbox.contentstream.operator.text.MoveText;
import org.apache.pdfbox.contentstream.operator.text.MoveTextSetLeading;
import org.apache.pdfbox.contentstream.operator.text.NextLine;
import org.apache.pdfbox.contentstream.operator.text.SetCharSpacing;
import org.apache.pdfbox.contentstream.operator.text.SetFontAndSize;
import org.apache.pdfbox.contentstream.operator.text.SetTextHorizontalScaling;
import org.apache.pdfbox.contentstream.operator.text.SetTextLeading;
import org.apache.pdfbox.contentstream.operator.text.SetTextRenderingMode;
import org.apache.pdfbox.contentstream.operator.text.SetTextRise;
import org.apache.pdfbox.contentstream.operator.text.SetWordSpacing;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import java.util.Deque;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.state.PDGraphicsState;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe: drive each text-state / text-positioning operator
 * processor's {@code process(Operator, List)} DIRECTLY with hand-built,
 * malformed operand lists and report whether it throws (and what) or
 * silently returns.
 *
 * <p>The engine's {@code processOperator} swallows {@code MissingOperandException}
 * (and friends) and routes them to {@code operatorException}, so the
 * operand-checking contract is invisible at the engine layer. Calling
 * {@code process()} directly isolates exactly that contract — the assigned
 * fuzz surface (operand arity / type handling of the text operators).
 *
 * <p>For each case the probe emits one tab-separated line:
 * <pre>
 *   &lt;id&gt; \t OK
 *   &lt;id&gt; \t ERR:&lt;SimpleExceptionName&gt;
 * </pre>
 * {@code OK} means {@code process()} returned without throwing (whether or
 * not it mutated the text state — the no-op-on-bad-type path also reports
 * {@code OK}). The cases mirror the Python side byte-for-byte.
 *
 * <p>A real PDPage/PDResources is wired so {@code Tf} can resolve a font name
 * against the resources (missing-font path logs + still calls setFont(null)).
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; TextStateOperatorFuzzProbe
 */
public final class TextStateOperatorFuzzProbe {

    // Sentinel text-matrix translate so a silent-ignore (no mutation) is
    // distinguishable from an applied update in the fingerprint.
    private static final Matrix SENTINEL =
            new Matrix(1f, 0f, 0f, 1f, 999f, 888f);

    private static PDFStreamEngine engine;
    private static Deque<PDGraphicsState> stack;

    private static List<COSBase> ops(COSBase... items) {
        return new ArrayList<>(Arrays.asList(items));
    }

    /**
     * Reset the mutable text state to a known baseline so the post-call
     * fingerprint reflects only this case's mutation: a fresh default
     * graphics-state frame (text state at PDF defaults) plus sentinel text
     * + text-line matrices.
     */
    private static void resetState() {
        stack.clear();
        stack.push(new PDGraphicsState(new PDRectangle()));
        engine.setTextMatrix(SENTINEL.clone());
        engine.setTextLineMatrix(SENTINEL.clone());
    }

    /**
     * A compact, deterministic snapshot of every text-state field the
     * operators can touch. Rounded to keep float formatting stable.
     */
    private static String fingerprint() {
        var ts = engine.getGraphicsState().getTextState();
        Matrix tm = engine.getTextMatrix();
        return String.format(java.util.Locale.ROOT,
                "tc=%.2f|tw=%.2f|tl=%.2f|tz=%.2f|ts=%.2f|tr=%d|fs=%.2f"
                        + "|font=%s|tmx=%.2f|tmy=%.2f|tma=%.2f",
                ts.getCharacterSpacing(), ts.getWordSpacing(),
                ts.getLeading(), ts.getHorizontalScaling(), ts.getRise(),
                ts.getRenderingMode().intValue(), ts.getFontSize(),
                ts.getFont() == null ? "null" : "set",
                tm.getTranslateX(), tm.getTranslateY(), tm.getScaleX());
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

        // A fresh engine; empty resources are enough for the operand-handling
        // contract (Tf's resource lookup just misses -> setFont(null)).
        engine = new PDFStreamEngine() {};
        // Make resources available so Tf's font lookup runs (missing-font path).
        // The setter is private upstream; reflect the field directly.
        Field resField = PDFStreamEngine.class.getDeclaredField("resources");
        resField.setAccessible(true);
        resField.set(engine, new PDResources());
        // Grab the graphics-state stack (seeded normally by the private
        // initPage) so resetState() can install a default frame per case.
        Field stackField =
                PDFStreamEngine.class.getDeclaredField("graphicsStack");
        stackField.setAccessible(true);
        @SuppressWarnings("unchecked")
        Deque<PDGraphicsState> s =
                (Deque<PDGraphicsState>) stackField.get(engine);
        stack = s;

        // Register the text operators so the TD / T* DECOMPOSITION path fires
        // (TD -> processOperator("TL"+"Td"); T* -> processOperator("Td")) —
        // this is the realistic engine config. Without registration the
        // delegated operators would silently no-op.
        engine.addOperator(new SetCharSpacing(engine));
        engine.addOperator(new SetWordSpacing(engine));
        engine.addOperator(new SetTextLeading(engine));
        engine.addOperator(new SetTextHorizontalScaling(engine));
        engine.addOperator(new SetTextRise(engine));
        engine.addOperator(new SetTextRenderingMode(engine));
        engine.addOperator(new SetFontAndSize(engine));
        engine.addOperator(new MoveText(engine));
        engine.addOperator(new MoveTextSetLeading(engine));
        engine.addOperator(new SetMatrix(engine));
        engine.addOperator(new NextLine(engine));

        // Reusable COS operands.
        final COSBase num = new COSFloat(3.5f);
        final COSBase num2 = new COSFloat(-7.0f);
        final COSBase intv = COSInteger.get(2);
        final COSBase name = COSName.getPDFName("F1");
        final COSBase str = new COSString("x");
        final COSBase arr = new COSArray();
        final COSBase nul = COSNull.NULL;

        // ---- (id, processor, operands) tuples mirrored on the Python side ---
        // Tc -- SetCharSpacing: empty->throw, last-arg, instanceof
        emit(sb, "tc_empty", new SetCharSpacing(engine), ops());
        emit(sb, "tc_num", new SetCharSpacing(engine), ops(num));
        emit(sb, "tc_name", new SetCharSpacing(engine), ops(name));
        emit(sb, "tc_str", new SetCharSpacing(engine), ops(str));
        emit(sb, "tc_null", new SetCharSpacing(engine), ops(nul));
        emit(sb, "tc_extra_last_num", new SetCharSpacing(engine), ops(name, num));
        emit(sb, "tc_extra_last_name", new SetCharSpacing(engine), ops(num, name));

        // Tw -- SetWordSpacing: empty->SILENT, get(0), instanceof
        emit(sb, "tw_empty", new SetWordSpacing(engine), ops());
        emit(sb, "tw_num", new SetWordSpacing(engine), ops(num));
        emit(sb, "tw_name", new SetWordSpacing(engine), ops(name));
        emit(sb, "tw_str", new SetWordSpacing(engine), ops(str));
        emit(sb, "tw_extra", new SetWordSpacing(engine), ops(num, num2));

        // TL -- SetTextLeading: empty->throw, get(0), instanceof
        emit(sb, "tl_empty", new SetTextLeading(engine), ops());
        emit(sb, "tl_num", new SetTextLeading(engine), ops(num));
        emit(sb, "tl_name", new SetTextLeading(engine), ops(name));
        emit(sb, "tl_arr", new SetTextLeading(engine), ops(arr));

        // Tz -- SetTextHorizontalScaling: empty->throw, get(0), instanceof
        emit(sb, "tz_empty", new SetTextHorizontalScaling(engine), ops());
        emit(sb, "tz_num", new SetTextHorizontalScaling(engine), ops(num));
        emit(sb, "tz_zero", new SetTextHorizontalScaling(engine),
                ops(new COSFloat(0f)));
        emit(sb, "tz_neg", new SetTextHorizontalScaling(engine),
                ops(new COSFloat(-50f)));
        emit(sb, "tz_name", new SetTextHorizontalScaling(engine), ops(name));
        emit(sb, "tz_null", new SetTextHorizontalScaling(engine), ops(nul));

        // Ts -- SetTextRise: empty->SILENT, get(0), instanceof
        emit(sb, "ts_empty", new SetTextRise(engine), ops());
        emit(sb, "ts_num", new SetTextRise(engine), ops(num));
        emit(sb, "ts_name", new SetTextRise(engine), ops(name));
        emit(sb, "ts_str", new SetTextRise(engine), ops(str));

        // Tr -- SetTextRenderingMode: empty->throw, get(0), instanceof, range
        emit(sb, "tr_empty", new SetTextRenderingMode(engine), ops());
        emit(sb, "tr_zero", new SetTextRenderingMode(engine),
                ops(COSInteger.get(0)));
        emit(sb, "tr_seven", new SetTextRenderingMode(engine),
                ops(COSInteger.get(7)));
        emit(sb, "tr_eight", new SetTextRenderingMode(engine),
                ops(COSInteger.get(8)));
        emit(sb, "tr_neg", new SetTextRenderingMode(engine),
                ops(COSInteger.get(-1)));
        emit(sb, "tr_float_in_range", new SetTextRenderingMode(engine),
                ops(new COSFloat(2.9f)));
        emit(sb, "tr_name", new SetTextRenderingMode(engine), ops(name));
        emit(sb, "tr_str", new SetTextRenderingMode(engine), ops(str));

        // Tf -- SetFontAndSize: <2->throw, name+number
        emit(sb, "tf_empty", new SetFontAndSize(engine), ops());
        emit(sb, "tf_one", new SetFontAndSize(engine), ops(name));
        emit(sb, "tf_unknown_font", new SetFontAndSize(engine), ops(name, num));
        emit(sb, "tf_num_for_name", new SetFontAndSize(engine), ops(num, num));
        emit(sb, "tf_str_for_name", new SetFontAndSize(engine), ops(str, num));
        emit(sb, "tf_name_for_size", new SetFontAndSize(engine),
                ops(name, name));
        emit(sb, "tf_null_size", new SetFontAndSize(engine), ops(name, nul));
        emit(sb, "tf_extra", new SetFontAndSize(engine), ops(name, num, num2));

        // Td -- MoveText: <2->throw, get(0)/get(1) instanceof
        emit(sb, "td_empty", new MoveText(engine), ops());
        emit(sb, "td_one", new MoveText(engine), ops(num));
        emit(sb, "td_two", new MoveText(engine), ops(num, num2));
        emit(sb, "td_name_first", new MoveText(engine), ops(name, num2));
        emit(sb, "td_name_second", new MoveText(engine), ops(num, name));
        emit(sb, "td_both_name", new MoveText(engine), ops(name, name));
        emit(sb, "td_extra", new MoveText(engine), ops(num, num2, num));

        // TD -- MoveTextSetLeading: <2->throw, get(1) instanceof
        emit(sb, "td2_empty", new MoveTextSetLeading(engine), ops());
        emit(sb, "td2_one", new MoveTextSetLeading(engine), ops(num));
        emit(sb, "td2_two", new MoveTextSetLeading(engine), ops(num, num2));
        emit(sb, "td2_name_second", new MoveTextSetLeading(engine),
                ops(num, name));
        emit(sb, "td2_name_first", new MoveTextSetLeading(engine),
                ops(name, num2));

        // Tm -- SetMatrix (state pkg): <6->throw, checkArrayTypesClass(ALL)
        emit(sb, "tm_empty", new SetMatrix(engine), ops());
        emit(sb, "tm_five", new SetMatrix(engine),
                ops(num, num, num, num, num));
        emit(sb, "tm_six", new SetMatrix(engine),
                ops(num, num, num, num, num, num));
        emit(sb, "tm_six_with_int", new SetMatrix(engine),
                ops(intv, num, num, num, num, num));
        emit(sb, "tm_six_one_name", new SetMatrix(engine),
                ops(num, num, num, num, num, name));
        emit(sb, "tm_six_first_name", new SetMatrix(engine),
                ops(name, num, num, num, num, num));
        // seven operands, all numbers -> OK (uses first 6)
        emit(sb, "tm_seven_all_num", new SetMatrix(engine),
                ops(num, num, num, num, num, num, num));
        // seven operands, trailing non-number -> upstream checkArrayTypesClass
        // over the WHOLE list fails -> silent no-op (the wave-1525 bug case)
        emit(sb, "tm_seven_trailing_name", new SetMatrix(engine),
                ops(num, num, num, num, num, num, name));
        emit(sb, "tm_seven_trailing_null", new SetMatrix(engine),
                ops(num, num, num, num, num, num, nul));

        // T* -- NextLine: no operand check at all
        emit(sb, "tstar_empty", new NextLine(engine), ops());
        emit(sb, "tstar_extra", new NextLine(engine), ops(num, num2));

        out.print(sb);
    }

    private static void emit(StringBuilder sb, String id,
            OperatorProcessor proc, List<COSBase> operands) {
        Operator op = Operator.getOperator(proc.getName());
        sb.append(id).append('\t').append(outcome(proc, op, operands))
                .append('\n');
    }
}
