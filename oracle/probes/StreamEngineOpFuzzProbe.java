import java.awt.geom.Point2D;
import java.io.PrintStream;
import org.apache.pdfbox.contentstream.PDFGraphicsStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;
import org.apache.pdfbox.pdmodel.graphics.image.PDImage;

/**
 * Live oracle probe for the OPERATOR ENGINE dispatch surface of
 * {@link PDFGraphicsStreamEngine} / {@link org.apache.pdfbox.contentstream.PDFStreamEngine}
 * — operand accumulation, unknown-operator handling, the q/Q graphics-state
 * stack balance, nested form-XObject {@code Do} dispatch, resource resolution
 * during processing, and the {@code operatorException} lenient-recovery triage.
 *
 * <p>Distinct from {@code GraphicsOperatorFuzzProbe} (which calls one processor's
 * {@code process()} directly with a hand-built operand list) and
 * {@code ContentFuzzProbe} (which projects {@code PDFTextStripper.getText}): this
 * probe runs WHOLE malformed content streams end-to-end through
 * {@code processPage} and projects the dispatch internals, so it exercises the
 * engine's token loop + exception swallowing rather than a single operator.
 *
 * <p>A minimal {@link PDFGraphicsStreamEngine} subclass overrides the abstract
 * draw hooks to count {@code Do}-form / image dispatches, overrides
 * {@code unsupportedOperator} to count unknown operators, and tracks the BT/ET
 * and BDC/EMC nesting via the notification hooks. The real registered processors
 * (Save/Restore/Concatenate/DrawObject/SetGraphicsStateParameters/colour/text/
 * marked-content) do the real operand validation against a real
 * {@link org.apache.pdfbox.pdmodel.graphics.state.PDGraphicsState}.
 *
 * <p>Usage:  java -cp ... StreamEngineOpFuzzProbe &lt;caseName&gt;
 *
 * <p>Output (stdout, UTF-8, deterministic):
 * <pre>
 *   err=&lt;none|SimpleName&gt;
 *   gdepth=&lt;final graphics-state stack depth&gt;
 *   btdepth=&lt;final BT/ET balance, never below 0&gt;
 *   mcdepth=&lt;final BMC/BDC vs EMC balance, never below 0&gt;
 *   forms=&lt;Do-form dispatches&gt;
 *   images=&lt;image / inline-image dispatches&gt;
 *   unknown=&lt;unsupportedOperator dispatches&gt;
 * </pre>
 */
public final class StreamEngineOpFuzzProbe {

    static final class RecordingEngine extends PDFGraphicsStreamEngine {
        int forms = 0;
        int images = 0;
        int unknown = 0;
        int bt = 0;
        int mc = 0;

        RecordingEngine(PDPage page) {
            super(page);
        }

        @Override
        public void unsupportedOperator(Operator operator, java.util.List<org.apache.pdfbox.cos.COSBase> operands) {
            unknown++;
        }

        @Override
        public void beginText() throws java.io.IOException {
            super.beginText();
            bt++;
        }

        @Override
        public void endText() throws java.io.IOException {
            super.endText();
            if (bt > 0) {
                bt--;
            }
        }

        @Override
        public void beginMarkedContentSequence(COSName tag, org.apache.pdfbox.cos.COSDictionary props) {
            mc++;
        }

        @Override
        public void endMarkedContentSequence() {
            if (mc > 0) {
                mc--;
            }
        }

        @Override
        public void drawImage(PDImage pdImage) {
            images++;
        }

        @Override
        public void showForm(PDFormXObject form) throws java.io.IOException {
            forms++;
            // Recurse like the base would so nested-form dispatch is exercised.
            super.showForm(form);
        }

        // ---- unused abstract path hooks ----
        @Override
        public void appendRectangle(Point2D p0, Point2D p1, Point2D p2, Point2D p3) {
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
        public void curveTo(float x1, float y1, float x2, float y2, float x3, float y3) {
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

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String name = args.length > 0 ? args[0] : "clean";
        byte[] content = caseBytes(name);

        StringBuilder sb = new StringBuilder();
        String err = "<none>";
        int gdepth = -1;
        int bt = -1;
        int mc = -1;
        int forms = -1;
        int images = -1;
        int unknown = -1;

        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            page.setResources(buildResources(doc));

            PDStream stream = new PDStream(doc);
            try (java.io.OutputStream os = stream.createOutputStream()) {
                os.write(content);
            }
            page.setContents(stream);

            RecordingEngine engine = new RecordingEngine(page);
            try {
                engine.processPage(page);
            } catch (Throwable t) {
                err = t.getClass().getSimpleName();
            }
            gdepth = engine.getGraphicsStackSize();
            bt = engine.bt;
            mc = engine.mc;
            forms = engine.forms;
            images = engine.images;
            unknown = engine.unknown;
        }

        sb.append("err=").append(err).append('\n');
        sb.append("gdepth=").append(gdepth).append('\n');
        sb.append("btdepth=").append(bt).append('\n');
        sb.append("mcdepth=").append(mc).append('\n');
        sb.append("forms=").append(forms).append('\n');
        sb.append("images=").append(images).append('\n');
        sb.append("unknown=").append(unknown).append('\n');
        out.print(sb);
    }

    /**
     * A /Resources with a real form XObject (/Frm), an ExtGState (/GS), and a
     * /Properties entry (/P0) so the resource-resolution branches of Do / gs /
     * BDC resolve, plus deliberately-missing names per case.
     */
    static PDResources buildResources(PDDocument doc) throws Exception {
        PDResources res = new PDResources();

        PDFormXObject form = new PDFormXObject(doc);
        form.setBBox(new org.apache.pdfbox.pdmodel.common.PDRectangle(0, 0, 10, 10));
        try (java.io.OutputStream os = form.getStream().createOutputStream()) {
            os.write("q 1 0 0 RG 0 0 5 5 re S Q".getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));
        }
        res.put(COSName.getPDFName("Frm"), form);

        org.apache.pdfbox.cos.COSDictionary gs = new org.apache.pdfbox.cos.COSDictionary();
        gs.setItem(COSName.TYPE, COSName.getPDFName("ExtGState"));
        gs.setItem(COSName.getPDFName("LW"), new org.apache.pdfbox.cos.COSFloat(3.0f));
        res.getCOSObject().setItem(COSName.getPDFName("ExtGState"),
                wrap("GS", gs));

        org.apache.pdfbox.cos.COSDictionary p0 = new org.apache.pdfbox.cos.COSDictionary();
        p0.setInt(COSName.MCID, 1);
        res.getCOSObject().setItem(COSName.PROPERTIES, wrap("P0", p0));

        return res;
    }

    static org.apache.pdfbox.cos.COSDictionary wrap(String key, org.apache.pdfbox.cos.COSBase value) {
        org.apache.pdfbox.cos.COSDictionary d = new org.apache.pdfbox.cos.COSDictionary();
        d.setItem(COSName.getPDFName(key), value);
        return d;
    }

    /** Named fuzz cases — raw content-stream bytes. */
    private static byte[] caseBytes(String name) {
        String s;
        switch (name) {
            case "clean":
                s = "q 1 0 0 1 0 0 cm Q";
                break;
            case "tf_one_arg":
                s = "/F1 Tf";
                break;
            case "tf_no_arg":
                s = "Tf";
                break;
            case "cm_five":
                s = "1 0 0 1 0 cm";
                break;
            case "cm_six_name":
                s = "/X 0 0 1 0 0 cm";
                break;
            case "cm_seven":
                s = "1 0 0 1 0 0 9 cm";
                break;
            case "unknown_single":
                s = "garbage";
                break;
            case "unknown_interspersed":
                s = "q foo Q bar baz";
                break;
            case "unknown_in_bx_ex":
                s = "BX undefinedop EX";
                break;
            case "q_only":
                s = "q";
                break;
            case "qq_unclosed":
                s = "q q q";
                break;
            case "extra_Q":
                s = "Q";
                break;
            case "extra_Q_double":
                s = "Q Q";
                break;
            case "q_extra_Q":
                s = "q Q Q";
                break;
            case "balanced_qQ":
                s = "q q Q Q";
                break;
            case "nested_deep_q":
                s = "q q q q q Q Q Q Q Q";
                break;
            case "do_missing":
                s = "/Nope Do";
                break;
            case "do_form":
                s = "/Frm Do";
                break;
            case "do_num_operand":
                s = "1 Do";
                break;
            case "do_no_operand":
                s = "Do";
                break;
            case "do_twice":
                s = "/Frm Do /Frm Do";
                break;
            case "gs_missing":
                s = "/Zzz gs";
                break;
            case "gs_good":
                s = "/GS gs";
                break;
            case "gs_no_operand":
                s = "gs";
                break;
            case "cs_missing":
                s = "/NoSuchCS cs";
                break;
            case "scn_no_cs":
                s = "0.5 scn";
                break;
            case "scn_missing_pattern":
                s = "/MissingPat scn";
                break;
            case "bt_et_balanced":
                s = "BT ET";
                break;
            case "bt_no_et":
                s = "BT 1 0 0 1 0 0 Tm";
                break;
            case "et_no_bt":
                s = "ET";
                break;
            case "bt_nested":
                s = "BT BT ET ET";
                break;
            case "bdc_emc_balanced":
                s = "/Span /P0 BDC EMC";
                break;
            case "bmc_no_emc":
                s = "/Span BMC";
                break;
            case "emc_no_bmc":
                s = "EMC";
                break;
            case "bdc_nested":
                s = "/A BMC /B BMC EMC EMC";
                break;
            case "mixed_chaos":
                s = "q /Span BMC BT /F1 12 Tf garbage /Frm Do ET EMC Q Q";
                break;
            case "truncated_operand":
                s = "1 0 0 1 0";
                break;
            default:
                s = "q Q";
                break;
        }
        return s.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);
    }

    private StreamEngineOpFuzzProbe() {
    }
}
