import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.OperatorName;
import org.apache.pdfbox.contentstream.operator.OperatorProcessor;
import org.apache.pdfbox.contentstream.operator.text.BeginText;
import org.apache.pdfbox.contentstream.operator.text.EndText;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for the {@code BT} / {@code ET} (begin/end text object)
 * content-stream operator processors and the text-matrix reset they perform.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TextObjectFuzzProbe
 *
 * Upstream {@code BeginText.process} resets the text matrix and the text-line
 * matrix to identity ({@code context.setTextMatrix(new Matrix());
 * context.setTextLineMatrix(new Matrix()); context.beginText();}) and takes no
 * operands. {@code EndText.process} clears both matrices to {@code null}
 * ({@code context.setTextLineMatrix(null); context.setTextMatrix(null);
 * context.endText();}) and likewise takes no operands. Neither validates its
 * operand window, so extra operands are simply ignored.
 *
 * The probe calls {@code process(Operator, List)} DIRECTLY on a fresh
 * BeginText / EndText bound to a recording engine, for a sequence of fuzz
 * cases (extra operands, ET-without-BT underflow, BT/ET nesting/balance,
 * BT then a Tm-style text positioning then ET). After every operator call it
 * snapshots the engine's text matrix + text-line matrix (via getTextMatrix /
 * getTextLineMatrix) so the differential pins the exact reset/clear semantics.
 * Calling process directly (not through processOperator) keeps any thrown
 * exception visible — processOperator would swallow it into operatorException.
 *
 * For every step it emits one tab-separated line:
 *   <id>\tERR:<SimpleExceptionName>          # process() threw
 *   <id>\tOK|<text-matrix fingerprint>       # process() returned
 *
 * The fingerprint encodes both matrices (or the literal {@code null}) so an
 * identity-reset, a clear, and a left-over positioning state all read
 * distinctly. Floats use %.2f with Locale.ROOT for cross-platform stability.
 */
public final class TextObjectFuzzProbe {

    /** Engine that actually stores the text matrices the operators write. */
    static final class RecordingEngine extends PDFStreamEngine {
        private Matrix tm;
        private Matrix tlm;
        private int beginCount;
        private int endCount;

        void resetState() {
            // Sentinel so a no-op (operator that fails to touch state) reads
            // differently from an applied identity reset / null clear.
            tm = new Matrix(1, 0, 0, 1, 999, 888);
            tlm = new Matrix(1, 0, 0, 1, 777, 666);
            beginCount = 0;
            endCount = 0;
        }

        @Override
        public Matrix getTextMatrix() {
            return tm;
        }

        @Override
        public void setTextMatrix(Matrix value) {
            this.tm = value;
        }

        @Override
        public Matrix getTextLineMatrix() {
            return tlm;
        }

        @Override
        public void setTextLineMatrix(Matrix value) {
            this.tlm = value;
        }

        @Override
        public void beginText() {
            beginCount++;
        }

        @Override
        public void endText() {
            endCount++;
        }
    }

    private static String mat(Matrix m) {
        if (m == null) {
            return "null";
        }
        return String.format(
                Locale.ROOT,
                "[%.2f %.2f %.2f %.2f %.2f %.2f]",
                m.getScaleX(), m.getShearY(),
                m.getShearX(), m.getScaleY(),
                m.getTranslateX(), m.getTranslateY());
    }

    private static String fingerprint(RecordingEngine e) {
        return "tm=" + mat(e.tm) + "|tlm=" + mat(e.tlm)
                + "|bc=" + e.beginCount + "|ec=" + e.endCount;
    }

    private static Operator op(String name) {
        return Operator.getOperator(name);
    }

    private static List<COSBase> ops(COSBase... items) {
        return new ArrayList<>(Arrays.asList(items));
    }

    private static final COSBase NUM = new COSFloat(3.5f);
    private static final COSBase NAME = COSName.getPDFName("F1");
    private static final COSBase STR = new COSString("x");
    private static final COSBase NULL = COSNull.NULL;
    private static final COSBase ARR = new COSArray();

    /** One fuzz step: an operator processor, its operand window, and an id. */
    private static void step(StringBuilder sb, String id, OperatorProcessor proc,
            RecordingEngine engine, Operator operator, List<COSBase> operands) {
        try {
            proc.process(operator, operands);
            sb.append(id).append('\t').append("OK|")
                    .append(fingerprint(engine)).append('\n');
        } catch (Exception ex) {
            sb.append(id).append('\t').append("ERR:")
                    .append(ex.getClass().getSimpleName()).append('\n');
        }
    }

    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        final StringBuilder sb = new StringBuilder();

        final RecordingEngine engine = new RecordingEngine();
        final BeginText bt = new BeginText(engine);
        final EndText et = new EndText(engine);

        // --- BT: no operands -> identity reset of both matrices ---
        engine.resetState();
        step(sb, "bt_empty", bt, engine, op(OperatorName.BEGIN_TEXT), ops());

        // --- BT: extra operands ignored (one / many) ---
        engine.resetState();
        step(sb, "bt_extra_num", bt, engine, op(OperatorName.BEGIN_TEXT), ops(NUM));
        engine.resetState();
        step(sb, "bt_extra_many", bt, engine, op(OperatorName.BEGIN_TEXT),
                ops(NUM, NAME, STR, NULL, ARR));

        // --- ET: no operands -> clears both matrices to null ---
        engine.resetState();
        step(sb, "et_empty", et, engine, op(OperatorName.END_TEXT), ops());

        // --- ET: extra operands ignored ---
        engine.resetState();
        step(sb, "et_extra_num", et, engine, op(OperatorName.END_TEXT), ops(NUM));
        engine.resetState();
        step(sb, "et_extra_many", et, engine, op(OperatorName.END_TEXT),
                ops(NUM, NAME, STR));

        // --- ET without a preceding BT (underflow): still clears, no throw ---
        engine.resetState();
        step(sb, "et_underflow", et, engine, op(OperatorName.END_TEXT), ops());

        // --- BT then ET (balanced): identity, then null ---
        engine.resetState();
        step(sb, "balanced_bt", bt, engine, op(OperatorName.BEGIN_TEXT), ops());
        step(sb, "balanced_et", et, engine, op(OperatorName.END_TEXT), ops());

        // --- BT then BT (nested / re-open): second BT re-resets to identity ---
        engine.resetState();
        step(sb, "nested_bt1", bt, engine, op(OperatorName.BEGIN_TEXT), ops());
        // mutate the matrices the way a positioning op would, between the BTs
        engine.setTextMatrix(new Matrix(2, 0, 0, 2, 50, 60));
        engine.setTextLineMatrix(new Matrix(2, 0, 0, 2, 50, 60));
        step(sb, "nested_bt2", bt, engine, op(OperatorName.BEGIN_TEXT), ops());

        // --- ET then ET (double end): second ET clears the already-null state ---
        engine.resetState();
        step(sb, "double_et1", et, engine, op(OperatorName.END_TEXT), ops());
        step(sb, "double_et2", et, engine, op(OperatorName.END_TEXT), ops());

        // --- BT, text positioning (Tm-style), ET ---
        engine.resetState();
        step(sb, "seq_bt", bt, engine, op(OperatorName.BEGIN_TEXT), ops());
        // simulate Tm: a positioning op replaces both matrices
        engine.setTextMatrix(new Matrix(1, 0, 0, 1, 100, 200));
        engine.setTextLineMatrix(new Matrix(1, 0, 0, 1, 100, 200));
        sb.append("seq_after_tm").append('\t').append("OK|")
                .append(fingerprint(engine)).append('\n');
        step(sb, "seq_et", et, engine, op(OperatorName.END_TEXT), ops());

        out.print(sb);
    }
}
