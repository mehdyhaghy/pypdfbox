import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.util.Base64;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts.FontName;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for differential FUZZING of the high-level
 * {@code PDPageContentStream} WRITER API against PDFBox 3.0.7.
 *
 * Sibling to {@code ContentStreamGenProbe} (which pins one fixed drawing
 * script and the float formatter in isolation). This probe instead drives a
 * BATTERY of ~30 short edge-case op sequences and, for each, projects EITHER
 * the exact emitted content-stream bytes (base64) OR the exception class +
 * message if the call sequence throws. One result per line:
 *
 *     &lt;case-name&gt;\tOK\t&lt;base64-of-stream-bytes&gt;
 *     &lt;case-name&gt;\tEXC\t&lt;exception-class&gt;\t&lt;message&gt;
 *
 * Edge angles (NOT already covered by ContentStreamGenProbe.drawScript):
 *   - showText escaping: parens / backslash / tab / CR / LF / non-Latin1
 *   - setFont size 0 / negative / fractional
 *   - colour setters with out-of-range components (raise)
 *   - line width negative / huge; dash pattern empty / zero / phase
 *   - NaN / +Inf / -Inf coordinates (raise)
 *   - very small / very large floats (number-format precision)
 *   - transform with extreme matrix
 *   - newLineAtOffset, multiple BT/ET
 *   - drawImage placement matrix
 *   - state guards (path op inside BT, nested BT, ET without BT)
 *
 * The paired pytest reproduces the identical sequences with pypdfbox and
 * asserts the projection matches line-for-line (after collapsing the
 * auto-allocated font-resource key /F0 vs /F1, a resource-slot surface).
 *
 * Usage: java ContentStreamGenFuzzProbe
 */
public final class ContentStreamGenFuzzProbe {

    private static final PrintStream OUT;
    static {
        OUT = new PrintStream(System.out, true, java.nio.charset.StandardCharsets.UTF_8);
    }

    /** A drawing script that mutates a PDPageContentStream. */
    private interface Script {
        void run(PDDocument doc, PDPage page, PDPageContentStream cs) throws Exception;
    }

    public static void main(String[] args) throws Exception {
        run("show_text_parens_backslash", (d, p, cs) -> {
            cs.beginText();
            cs.setFont(font(), 12);
            cs.showText("a(b)c\\d");
            cs.endText();
        });
        run("show_text_tab", (d, p, cs) -> {
            cs.beginText();
            cs.setFont(font(), 12);
            cs.showText("a\tb");
            cs.endText();
        });
        run("show_text_newline", (d, p, cs) -> {
            cs.beginText();
            cs.setFont(font(), 12);
            cs.showText("a\nb");
            cs.endText();
        });
        run("show_text_carriage_return", (d, p, cs) -> {
            cs.beginText();
            cs.setFont(font(), 12);
            cs.showText("a\rb");
            cs.endText();
        });
        run("show_text_bell_control", (d, p, cs) -> {
            cs.beginText();
            cs.setFont(font(), 12);
            cs.showText("ab");
            cs.endText();
        });
        run("show_text_empty", (d, p, cs) -> {
            cs.beginText();
            cs.setFont(font(), 12);
            cs.showText("");
            cs.endText();
        });
        run("set_font_size_zero", (d, p, cs) -> {
            cs.beginText();
            cs.setFont(font(), 0);
            cs.endText();
        });
        run("set_font_size_negative", (d, p, cs) -> {
            cs.beginText();
            cs.setFont(font(), -12);
            cs.endText();
        });
        run("set_font_size_fractional", (d, p, cs) -> {
            cs.beginText();
            cs.setFont(font(), 10.333f);
            cs.endText();
        });
        run("stroking_color_gray_out_of_range_high", (d, p, cs) -> {
            cs.setStrokingColor(1.5f);
        });
        run("stroking_color_gray_out_of_range_low", (d, p, cs) -> {
            cs.setStrokingColor(-0.1f);
        });
        run("non_stroking_rgb_out_of_range", (d, p, cs) -> {
            cs.setNonStrokingColor(0.0f, 1.2f, 0.0f);
        });
        run("stroking_cmyk_out_of_range", (d, p, cs) -> {
            cs.setStrokingColor(0.1f, 0.2f, 0.3f, 2.0f);
        });
        run("rgb_boundary_zero_one", (d, p, cs) -> {
            cs.setNonStrokingColor(0.0f, 1.0f, 0.5f);
        });
        run("line_width_negative", (d, p, cs) -> {
            cs.setLineWidth(-3.5f);
        });
        run("line_width_zero", (d, p, cs) -> {
            cs.setLineWidth(0);
        });
        run("line_width_huge", (d, p, cs) -> {
            cs.setLineWidth(1.0e9f);
        });
        run("dash_empty", (d, p, cs) -> {
            cs.setLineDashPattern(new float[] {}, 0);
        });
        run("dash_zero_elements", (d, p, cs) -> {
            cs.setLineDashPattern(new float[] {0, 0}, 0);
        });
        run("dash_with_phase", (d, p, cs) -> {
            cs.setLineDashPattern(new float[] {3, 2}, 1.5f);
        });
        run("dash_fractional", (d, p, cs) -> {
            cs.setLineDashPattern(new float[] {1.25f, 0.75f}, 0.5f);
        });
        run("move_to_nan", (d, p, cs) -> {
            cs.moveTo(Float.NaN, 100);
        });
        run("move_to_pos_inf", (d, p, cs) -> {
            cs.moveTo(Float.POSITIVE_INFINITY, 100);
        });
        run("move_to_neg_inf", (d, p, cs) -> {
            cs.lineTo(0, Float.NEGATIVE_INFINITY);
        });
        run("add_rect_tiny_float", (d, p, cs) -> {
            cs.addRect(0.000005f, 0.000004f, 0.000025f, 0.123455f);
        });
        run("line_to_large_float", (d, p, cs) -> {
            cs.moveTo(0, 0);
            cs.lineTo(12345.6789f, 999999.5f);
        });
        run("transform_extreme_matrix", (d, p, cs) -> {
            cs.transform(new Matrix(1.0e6f, 0, 0, 1.0e6f, -50000.25f, 0.000001f));
        });
        run("transform_negative_scale", (d, p, cs) -> {
            cs.transform(new Matrix(-1, 0, 0, -1, 100, 200));
        });
        run("new_line_at_offset_negative", (d, p, cs) -> {
            cs.beginText();
            cs.newLineAtOffset(-72.5f, -10);
            cs.endText();
        });
        run("multiple_bt_et_blocks", (d, p, cs) -> {
            cs.beginText();
            cs.setFont(font(), 12);
            cs.showText("one");
            cs.endText();
            cs.beginText();
            cs.showText("two");
            cs.endText();
        });
        run("path_op_inside_text_block", (d, p, cs) -> {
            cs.beginText();
            cs.moveTo(0, 0);  // not allowed within BT/ET
        });
        run("nested_begin_text", (d, p, cs) -> {
            cs.beginText();
            cs.beginText();
        });
        run("end_text_without_begin", (d, p, cs) -> {
            cs.endText();
        });
        run("new_line_without_begin", (d, p, cs) -> {
            cs.newLine();
        });
        run("save_restore_pairs", (d, p, cs) -> {
            cs.saveGraphicsState();
            cs.saveGraphicsState();
            cs.restoreGraphicsState();
            cs.restoreGraphicsState();
        });
        run("text_with_positioning", (d, p, cs) -> {
            cs.beginText();
            cs.setFont(font(), 12);
            cs.showTextWithPositioning(new Object[] {"A", -120.5f, "B", 50, "C"});
            cs.endText();
        });
        run("set_leading_and_newline", (d, p, cs) -> {
            cs.beginText();
            cs.setFont(font(), 12);
            cs.setLeading(14.5f);
            cs.newLine();
            cs.endText();
        });
        run("set_text_matrix_extreme", (d, p, cs) -> {
            cs.beginText();
            cs.setTextMatrix(new Matrix(2.5f, 0, 0, 2.5f, 0.000001f, 1.0e7f));
            cs.endText();
        });
        run("negative_zero_operand", (d, p, cs) -> {
            cs.moveTo(-0.000005f, 0);
        });

        OUT.flush();
    }

    private static PDType1Font font() {
        return new PDType1Font(FontName.HELVETICA);
    }

    /** Run one script; project bytes or exception, base64-encode the bytes. */
    private static void run(String name, Script script) {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            byte[] bytes;
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                script.run(doc, page, cs);
            }
            PDStream contents = page.getContentStreams().next();
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            try (var in = contents.createInputStream()) {
                in.transferTo(baos);
            }
            bytes = baos.toByteArray();
            OUT.println(name + "\tOK\t" + Base64.getEncoder().encodeToString(bytes));
        } catch (Throwable t) {
            String msg = t.getMessage();
            OUT.println(name + "\tEXC\t" + t.getClass().getSimpleName()
                    + "\t" + (msg == null ? "" : msg.replace('\n', ' ').replace('\t', ' ')));
        }
    }
}
