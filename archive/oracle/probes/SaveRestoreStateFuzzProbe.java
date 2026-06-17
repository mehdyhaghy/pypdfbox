import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.state.Restore;
import org.apache.pdfbox.contentstream.operator.state.Save;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;

/**
 * Live oracle probe: project Apache PDFBox's behaviour of the ``q`` (Save) and
 * ``Q`` (Restore) graphics-state operator processors plus the engine's
 * graphics-state stack nesting.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SaveRestoreStateFuzzProbe
 *
 * The probe subclasses {@link PDFStreamEngine} and OVERRIDES the three stack
 * hooks the operators call (``saveGraphicsState`` / ``restoreGraphicsState`` /
 * ``getGraphicsStackSize``) with a plain depth counter seeded at 1. This models
 * the exact arithmetic the real base engine performs — ``saveGraphicsState``
 * pushes a clone of the top frame (depth+1), ``restoreGraphicsState`` pops
 * (depth-1), ``getGraphicsStackSize`` is the depth — while side-stepping the
 * need for a real PDPage / PDGraphicsState (the base ``saveGraphicsState``
 * NPEs on an empty deque, and ``initPage`` is private). The depth-1 seed mirrors
 * the post-``initPage`` starting state of a real page run. The surface under
 * test is the ``Save`` / ``Restore`` OPERATOR logic (operand handling + the
 * ``size > 1`` Restore guard), which this exercises faithfully — exactly the
 * contract pypdfbox mirrors through its own engine hooks.
 *
 * Save#process: unconditionally calls ``getContext().saveGraphicsState()`` and
 * IGNORES its operand list entirely (no arity / type guard).
 *
 * Restore#process: ``if getGraphicsStackSize() > 1 -> restoreGraphicsState();
 * else throw new EmptyGraphicsStackException();`` — it THROWS on an empty /
 * single-frame stack (PDFBOX-161; the lenient log-and-skip happens one level up
 * in ``operatorException``, not in the operator).
 *
 * For each fuzz case the probe emits one tab-separated line::
 *
 *   <id>\t<size-after>          # sequence ran clean; size = final stack depth
 *   <id>\tERR:<SimpleName>@<n>  # process() threw; n = stack depth at throw
 *
 * A "case" is a sequence of single-character steps: 'q' = drive Save#process,
 * 'Q' = drive Restore#process. Optional per-step operands are encoded by the
 * variant id, not the step string. Operand lists are passed verbatim so the
 * "operands are ignored" contract is observable.
 */
public final class SaveRestoreStateFuzzProbe {

    /** Engine that shadows the base graphics-stack hooks with a plain depth
     * counter seeded at 1 (post-initPage starting state). The base hooks need a
     * real PDGraphicsState deque (and NPE on an empty one); overriding them lets
     * us drive the real ``Save`` / ``Restore`` operators against deterministic
     * depth arithmetic. */
    static final class ProbeEngine extends PDFStreamEngine {
        private int depth = 1;

        @Override
        public void saveGraphicsState() {
            depth++;
        }

        @Override
        public void restoreGraphicsState() {
            depth--;
        }

        @Override
        public int getGraphicsStackSize() {
            return depth;
        }
    }

    static List<COSBase> noOperands() {
        return new ArrayList<>();
    }

    static List<COSBase> someOperands() {
        List<COSBase> ops = new ArrayList<>();
        ops.add(new COSFloat(1.5f));
        ops.add(COSInteger.get(2));
        ops.add(COSName.getPDFName("X"));
        return ops;
    }

    /** Run a q/Q step sequence, returning the projected outcome line body. */
    static String runSequence(String steps, List<COSBase> qOperands,
            List<COSBase> bigQOperands) {
        ProbeEngine engine = new ProbeEngine();
        Save save = new Save(engine);
        Restore restore = new Restore(engine);
        Operator qOp = Operator.getOperator("q");
        Operator bigQOp = Operator.getOperator("Q");
        try {
            for (int i = 0; i < steps.length(); i++) {
                char c = steps.charAt(i);
                if (c == 'q') {
                    save.process(qOp, qOperands);
                } else {
                    restore.process(bigQOp, bigQOperands);
                }
            }
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName() + "@"
                    + engine.getGraphicsStackSize();
        }
        return Integer.toString(engine.getGraphicsStackSize());
    }

    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();

        List<COSBase> none = noOperands();
        List<COSBase> some = someOperands();

        // (id, steps, q-operands, Q-operands)
        emit(sb, "q_only", "q", none, none);
        emit(sb, "qq", "qq", none, none);
        emit(sb, "qqq", "qqq", none, none);
        emit(sb, "q_then_Q", "qQ", none, none);
        emit(sb, "qq_QQ", "qqQQ", none, none);
        emit(sb, "qqq_QQQ", "qqqQQQ", none, none);
        emit(sb, "nested_balanced", "qqQqQQ", none, none);
        // Q on the seed (size-1) stack -> throws (more restores than saves).
        emit(sb, "Q_only", "Q", none, none);
        emit(sb, "QQ_only", "QQ", none, none);
        emit(sb, "q_QQ_unbalanced", "qQQ", none, none);
        emit(sb, "qq_QQQ_unbalanced", "qqQQQ", none, none);
        // Q exactly draining to the seed frame is fine; one more throws.
        emit(sb, "qqQQ_then_Q", "qqQQQ", none, none);
        // operands on q are ignored (size unaffected).
        emit(sb, "q_with_operands", "q", some, none);
        emit(sb, "qq_with_operands", "qq", some, none);
        // operands on Q are ignored (still pops normally).
        emit(sb, "qQ_with_Q_operands", "qQ", none, some);
        emit(sb, "q_operands_both", "qQ", some, some);
        // round-trip: q then Q returns to seed depth (1).
        emit(sb, "round_trip", "qQ", none, none);
        emit(sb, "deep_round_trip", "qqqqQQQQ", none, none);

        out.print(sb);
    }

    static void emit(StringBuilder sb, String id, String steps,
            List<COSBase> qOps, List<COSBase> bigQOps) {
        sb.append(id).append('\t')
                .append(runSequence(steps, qOps, bigQOps)).append('\n');
    }
}
