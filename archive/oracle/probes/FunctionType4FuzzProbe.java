import java.io.OutputStream;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Differential fuzz probe for the Type 4 PostScript calculator function —
 * the token stream lexer/parser ({@code type4.Parser} /
 * {@code InstructionSequenceBuilder}) and the stack-machine evaluator
 * ({@code PDFunctionType4.eval} driving {@code ArithmeticOperators},
 * {@code RelationalOperators}, {@code StackOperators},
 * {@code ConditionalOperators}, {@code BitwiseOperators}), Apache PDFBox
 * 3.0.7 (wave 1522, agent A).
 *
 * This is a DEEPER angle than FunctionEvalFuzzProbe / FunctionCreateFuzzProbe
 * which fuzz the COS-spec construction contract across all function types.
 * Here every case is a Type 4 PostScript program; the corpus stresses the
 * calculator language itself: malformed/unbalanced braces, empty programs,
 * nested if/ifelse with wrong stack arity, unknown operator tokens, numeric
 * literal forms (leading +/-, exponents, radix), division by zero, sqrt/ln/log
 * of negatives, type errors (boolean where number expected), stack
 * underflow/overflow, index/roll/copy out-of-range/negative args,
 * truncate/round/cvi/cvr edge cases, two-arg atan, bitshift extremes, 32-bit
 * integer wrap, and value clamping against Domain/Range.
 *
 * Deterministic and seed-free: the corpus is a fixed inline list. The pypdfbox
 * sibling (tests/pdmodel/common/function/oracle/
 * test_function_type4_fuzz_wave1522.py) rebuilds the identical specs and
 * asserts each line matches.
 *
 * Line grammar (one per case):
 *   CASE &lt;name&gt; create=&lt;ok|ERR&gt; eval=&lt;ERR | f0 f1 ...&gt;
 * "create=ERR" means create() threw. "eval=ERR" means create() succeeded but
 * eval() threw. A float list means both succeeded; floats are %.6f (or the
 * IEEE tokens NaN / Infinity / -Infinity).
 */
public final class FunctionType4FuzzProbe {

    static PrintStream out;

    static String fmt(float v) {
        if (Float.isNaN(v)) {
            return "NaN";
        }
        if (Float.isInfinite(v)) {
            return v > 0 ? "Infinity" : "-Infinity";
        }
        return String.format(Locale.ROOT, "%.6f", v);
    }

    static COSArray floats(double... vals) {
        COSArray a = new COSArray();
        for (double v : vals) {
            a.add(new COSFloat((float) v));
        }
        return a;
    }

    /**
     * Build a Type 4 function stream over the given /Domain and /Range with the
     * given PostScript body. nIn/nOut control Domain/Range arity so we can drive
     * multi-input programs and test /Range clamping at chosen bounds.
     */
    static COSStream t4(String ps, COSArray domain, COSArray range) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 4);
        s.setItem(COSName.DOMAIN, domain);
        s.setItem(COSName.RANGE, range);
        OutputStream os = s.createOutputStream();
        os.write(ps.getBytes("US-ASCII"));
        os.close();
        return s;
    }

    static void emit(String name, COSBase spec, float[] in) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDFunction fn;
        try {
            fn = PDFunction.create(spec);
        } catch (Throwable t) {
            out.println(sb.append("create=ERR").toString());
            return;
        }
        sb.append("create=ok eval=");
        try {
            float[] o = fn.eval(in);
            StringBuilder vals = new StringBuilder();
            for (int i = 0; i < o.length; i++) {
                if (i > 0) {
                    vals.append(' ');
                }
                vals.append(fmt(o[i]));
            }
            sb.append(vals);
        } catch (Throwable t) {
            sb.append("ERR");
        }
        out.println(sb.toString());
    }

    // One-input [0,1] domain, one-output [-1000,1000] range (the common case).
    static void e1(String name, String ps, float input) throws Exception {
        emit(name, t4(ps, floats(0, 1), floats(-1000, 1000)),
             new float[] {input});
    }

    // One-input domain, two-output range — for programs leaving 2 values.
    static void e1r2(String name, String ps, float input) throws Exception {
        emit(name, t4(ps, floats(0, 1), floats(-1000, 1000, -1000, 1000)),
             new float[] {input});
    }

    // Two-input domain [0,1]x[0,1], one-output range.
    static void e2(String name, String ps, float a, float b) throws Exception {
        emit(name, t4(ps, floats(0, 1, 0, 1), floats(-1000, 1000)),
             new float[] {a, b});
    }

    // One-input [0,1] domain, custom range to test clamping.
    static void e1Range(String name, String ps, float input,
                        double rlo, double rhi) throws Exception {
        emit(name, t4(ps, floats(0, 1), floats(rlo, rhi)),
             new float[] {input});
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ============ brace / structural corners ============
        e1("empty_prog", "{ }", 0.5f);
        e1("empty_no_braces", "", 0.5f);
        e1("just_open", "{", 0.5f);
        e1("just_close", "}", 0.5f);
        e1("double_close", "{ pop 5 } }", 0.5f);
        e1("missing_close", "{ pop 1 2 add", 0.0f);
        e1("trailing_after_close", "{ 1 } 99", 0.0f);
        e1("no_outer_wrapper", "pop 7", 0.5f);
        e1("nested_unbalanced", "{ pop { 1 2 add }", 0.0f);
        e1("stray_open_mid", "{ pop 3 { 4 }", 0.0f);
        e1("whitespace_only", "   \n\t  ", 0.5f);
        e1("comment_only", "% just a comment", 0.5f);
        e1("comment_inline", "{ pop % drop input\n 42 }", 0.5f);

        // ============ numeric literal forms ============
        e1("lit_plus", "{ pop +5 }", 0.5f);
        e1("lit_minus", "{ pop -5 }", 0.5f);
        e1("lit_real", "{ pop 3.14 }", 0.5f);
        e1("lit_real_lead_dot", "{ pop .5 }", 0.5f);
        e1("lit_real_trail_dot", "{ pop 5. }", 0.5f);
        e1("lit_exp", "{ pop 1.5e2 }", 0.5f);
        e1("lit_exp_neg", "{ pop 1.5e-1 }", 0.5f);
        e1("lit_exp_cap", "{ pop 2.0E1 }", 0.5f);
        e1("lit_huge_int", "{ pop 9999999999 }", 0.5f);
        e1("lit_int_max", "{ pop 2147483647 }", 0.5f);
        e1("lit_int_overflow", "{ pop 2147483648 }", 0.5f);
        e1("lit_radix_hex", "{ pop 16#FF }", 0.5f);
        e1("lit_radix_oct", "{ pop 8#17 }", 0.5f);
        e1("lit_neg_zero", "{ pop -0 }", 0.5f);

        // ============ unknown / illegal operators ============
        e1("unknown_op", "{ pop frobnicate }", 0.5f);
        e1("unknown_def", "{ pop /x 5 def }", 0.5f);
        e1("unknown_for", "{ pop 0 1 3 { } for }", 0.5f);
        e1("unknown_forall", "{ pop forall }", 0.5f);

        // ============ division / modulo by zero ============
        e1("div0_pos", "{ pop 1 0 div }", 0.0f);
        e1("div0_neg", "{ pop -1 0 div }", 0.0f);
        e1("div0_zero", "{ pop 0 0 div }", 0.0f);
        e1("idiv0", "{ pop 1 0 idiv }", 0.0f);
        e1("mod0", "{ pop 1 0 mod }", 0.0f);
        e1("idiv_neg", "{ pop -7 2 idiv }", 0.0f);
        e1("idiv_neg_div", "{ pop 7 -2 idiv }", 0.0f);
        e1("mod_neg", "{ pop -7 3 mod }", 0.0f);
        e1("mod_neg_div", "{ pop 7 -3 mod }", 0.0f);
        e1("idiv_real_operand", "{ pop 7.5 2 idiv }", 0.0f);
        e1("div_int_result_idiv", "{ pop 6 2 div 1 idiv }", 0.0f);

        // ============ transcendental domain corners ============
        e1("sqrt_neg", "{ pop -1 sqrt }", 0.0f);
        e1("sqrt_zero", "{ pop 0 sqrt }", 0.0f);
        e1("ln_zero", "{ pop 0 ln }", 0.0f);
        e1("ln_neg", "{ pop -5 ln }", 0.0f);
        e1("log_zero", "{ pop 0 log }", 0.0f);
        e1("log_neg", "{ pop -5 log }", 0.0f);
        e1("exp_neg_base_frac", "{ pop -2 0.5 exp }", 0.0f);
        e1("exp_zero_zero", "{ pop 0 0 exp }", 0.0f);
        e1("exp_big", "{ pop 10 100 exp }", 0.0f);

        // ============ atan two-arg ============
        e1("atan_q1", "{ pop 1 1 atan }", 0.0f);
        e1("atan_q2", "{ pop 1 -1 atan }", 0.0f);
        e1("atan_neg", "{ pop -1 -1 atan }", 0.0f);
        e1("atan_zero_zero", "{ pop 0 0 atan }", 0.0f);
        e1("atan_axis", "{ pop 1 0 atan }", 0.0f);

        // ============ truncate / round / floor / ceiling / cvi / cvr ============
        e1("round_half", "{ pop 2.5 round }", 0.0f);
        e1("round_neg_half", "{ pop -2.5 round }", 0.0f);
        e1("trunc_neg", "{ pop -2.7 truncate }", 0.0f);
        e1("floor_neg", "{ pop -2.3 floor }", 0.0f);
        e1("ceil_neg", "{ pop -2.3 ceiling }", 0.0f);
        e1("cvi_real", "{ pop 7.9 cvi }", 0.0f);
        e1("cvi_neg_real", "{ pop -7.9 cvi }", 0.0f);
        e1("cvr_int", "{ pop 5 cvr }", 0.0f);
        e1("cvi_then_idiv", "{ pop 7.9 cvi 2 idiv }", 0.0f);

        // ============ type errors (boolean where number expected) ============
        e1("add_bool", "{ pop true 1 add }", 0.0f);
        e1("lt_bool", "{ pop true 1 lt }", 0.0f);
        e1("neg_bool", "{ pop true neg }", 0.0f);
        e1("and_int_bool", "{ pop 5 true and }", 0.0f);
        e1("and_float", "{ pop 1.0 2.0 and }", 0.0f);
        e1("not_real", "{ pop 1.5 not }", 0.0f);
        e1("bitshift_real", "{ pop 1.0 2 bitshift }", 0.0f);

        // ============ stack underflow ============
        e1("underflow_add", "{ pop add }", 0.0f);
        e1("underflow_pop", "{ pop pop }", 0.0f);
        e1("underflow_dup", "{ pop pop dup }", 0.0f);
        e1("underflow_exch", "{ pop exch }", 0.0f);

        // ============ index / roll / copy ============
        e2("copy2", "{ 2 copy add add }", 0.3f, 0.7f);
        e1("copy0", "{ 0 copy 5 }", 0.5f);
        e1("copy_neg", "{ pop 1 2 -1 copy add }", 0.5f);
        e1("copy_overrange", "{ pop 1 5 copy }", 0.5f);
        e1("index0", "{ pop 1 2 3 0 index }", 0.5f);
        e1("index2", "{ 10 20 30 2 index }", 0.5f);
        e1("index_neg", "{ 10 20 -1 index }", 0.5f);
        e1("index_overrange", "{ 10 20 9 index }", 0.5f);
        e1("index_real", "{ 10 20 30 1.9 index }", 0.5f);
        e1("roll_pos", "{ 1 2 3 3 1 roll add add }", 0.5f);
        e1("roll_neg", "{ 1 2 3 3 -1 roll }", 0.5f);
        e1("roll_zero", "{ 1 2 3 3 0 roll add add }", 0.5f);
        e1("roll_n_neg", "{ 1 2 3 -1 1 roll }", 0.5f);
        e1("roll_j_overflow", "{ 1 2 3 3 7 roll }", 0.5f);
        e1("roll_n_overflow", "{ 1 2 9 1 roll }", 0.5f);

        // ============ bitshift / bitwise ============
        e1("bitshift_left", "{ pop 1 4 bitshift }", 0.5f);
        e1("bitshift_right", "{ pop 256 -2 bitshift }", 0.5f);
        e1("bitshift_big_left", "{ pop 1 40 bitshift }", 0.5f);
        e1("bitshift_neg_val", "{ pop -8 -1 bitshift }", 0.5f);
        e1("and_ints", "{ pop 12 10 and }", 0.5f);
        e1("or_ints", "{ pop 12 10 or }", 0.5f);
        e1("xor_ints", "{ pop 12 10 xor }", 0.5f);
        e1("not_int", "{ pop 5 not }", 0.5f);
        e1("and_bools", "{ pop true false and }", 0.5f);
        e1("xor_bools", "{ pop true false xor }", 0.5f);

        // ============ 32-bit integer wrap (arithmetic tag overflow) ============
        e1("mul_overflow", "{ pop 100000 100000 mul }", 0.5f);
        e1("add_overflow", "{ pop 2147483647 1 add }", 0.5f);
        e1("sub_overflow", "{ pop -2147483648 1 sub }", 0.5f);
        e1("neg_intmin", "{ pop -2147483648 neg }", 0.5f);
        e1("abs_intmin", "{ pop -2147483648 abs }", 0.5f);

        // ============ relational / eq / ne ============
        e1("eq_true", "{ pop 5 5 eq { 1 } { 0 } ifelse }", 0.5f);
        e1("eq_int_float", "{ pop 5 5.0 eq { 1 } { 0 } ifelse }", 0.5f);
        e1("ne_bool", "{ pop true false ne { 1 } { 0 } ifelse }", 0.5f);
        e1("eq_bool_int", "{ pop true 1 eq { 1 } { 0 } ifelse }", 0.5f);

        // ============ if / ifelse arity / type ============
        e1("if_true", "{ pop true { 11 } if }", 0.5f);
        e1("if_false", "{ pop false { 11 } if 22 }", 0.5f);
        e1("if_non_bool", "{ pop 1 { 11 } if }", 0.5f);
        e1("if_no_proc", "{ pop true if }", 0.5f);
        e1("ifelse_true", "{ pop true { 1 } { 2 } ifelse }", 0.5f);
        e1("ifelse_non_bool", "{ pop 5 { 1 } { 2 } ifelse }", 0.5f);
        e1("nested_if", "{ pop 1 { 2 { 3 } if } if }", 0.0f);
        e1("deep_nest", "{ pop { { { 5 } if } if } pop 5 }", 0.0f);

        // ============ Range clamping ============
        e1Range("clamp_high", "{ pop 5000 }", 0.5f, -10, 10);
        e1Range("clamp_low", "{ pop -5000 }", 0.5f, -10, 10);
        e1Range("clamp_div0", "{ pop 1 0 div }", 0.5f, -10, 10);
        e1Range("clamp_nan", "{ pop 0 0 div }", 0.5f, -10, 10);
        e1Range("clamp_ln0", "{ pop 0 ln }", 0.5f, -10, 10);
        e1Range("clamp_neg_inf", "{ pop -1 0 div }", 0.5f, -10, 10);

        // ============ multi-output programs ============
        e1r2("two_out", "{ dup 100 mul exch 200 mul }", 0.5f);
        e1r2("two_out_surplus", "{ 1 2 3 }", 0.5f);

        // ============ Domain clamping of input ============
        e1("dom_clamp_over", "{ 1000 mul }", 5.0f);
        e1("dom_clamp_under", "{ 1000 mul }", -5.0f);
    }
}
